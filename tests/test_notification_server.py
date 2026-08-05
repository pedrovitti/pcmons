'''
Tests for NotificationServer, which receives the agents' readings over XML-RPC
and hands them to the configured interface.

The address a notification arrived from is the only thing identifying the VM
that sent it, so most of these are about that address surviving the trip from
the request to the interface.
'''
import logging
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
sys.path.insert(0, ROOT)

import running_vms.cluster.cluster_config as cluster_config
cluster_config.PATH_TO_LOG_FILE = '/tmp/pcmons-notification-test.log'

from running_vms import Notification_Server as module


class FakeInterface:

    def __init__(self):
        self.notifications = []

    def process_notification(self, data, address):
        self.notifications.append((data, address))
        return True


class FakeServer:
    '''Stands in for the SimpleXMLRPCServer the handler writes onto.'''


class FakeDb:

    def __init__(self, instance_id='i-1'):
        self.instance_id = instance_id

    def get_id_by_ip(self, address):
        if self.instance_id is None:
            return None
        return {'instance_id':self.instance_id}


class FakeHistory:

    def __init__(self):
        self.recorded = []

    def record(self, instance_id, data):
        self.recorded.append((instance_id, data))
        return len(data)


class BrokenHistory:

    def record(self, instance_id, data):
        raise ValueError('the database is gone')


PAYLOAD = {'memory':{'used':1, 'total':2}}


class NotificationServerTest(unittest.TestCase):

    def setUp(self):
        self.server = module.NotificationServer(db=object())
        self.interface = FakeInterface()
        self.server.build_interface = lambda: self.interface
        logging.disable(logging.ERROR)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_hands_the_reading_to_the_interface(self):
        self.server.handle_notification(PAYLOAD, '10.0.0.10')
        self.assertEqual(self.interface.notifications, [(PAYLOAD, '10.0.0.10')])

    def test_the_agent_is_told_the_reading_was_taken(self):
        self.assertTrue(self.server.handle_notification(PAYLOAD, '10.0.0.10'))

    def test_the_address_of_the_current_request_is_used(self):
        #the handler puts it on the server; get_vm_notification reads it back.
        #it used to travel through a module global, which made the value
        #whatever the last request had set, process-wide
        self.server.server = FakeServer()
        self.server.server.notification_address = '10.0.0.20'
        self.server.get_vm_notification(PAYLOAD)
        self.assertEqual(self.interface.notifications[0][1], '10.0.0.20')

    def test_two_servers_in_one_process_do_not_share_an_address(self):
        first, second = module.NotificationServer(db=object()), module.NotificationServer(db=object())
        first.server, second.server = FakeServer(), FakeServer()
        first.server.notification_address = '10.0.0.20'
        second.server.notification_address = '10.0.0.30'
        self.assertEqual(first.client_address(), '10.0.0.20')
        self.assertEqual(second.client_address(), '10.0.0.30')

    def test_a_notification_outside_a_request_is_dropped(self):
        #calling the method directly, before any request has been served, used
        #to raise NameError on the global rather than report anything
        self.assertFalse(self.server.get_vm_notification(PAYLOAD))
        self.assertEqual(self.interface.notifications, [])

    def test_a_notification_with_no_interface_is_dropped(self):
        self.server.build_interface = lambda: None
        self.assertFalse(self.server.handle_notification(PAYLOAD, '10.0.0.10'))

    def test_the_payload_is_passed_through_untouched(self):
        #whatever the agent collected is the interface's problem to read
        payload = {'memory':{'used':1}, 'something_new':{'value':2}}
        self.server.handle_notification(payload, '10.0.0.10')
        self.assertEqual(self.interface.notifications[0][0], payload)


class HistoryTest(unittest.TestCase):
    '''
    the readings are kept on the way past. What matters here is that keeping
    them never costs the notification: the vm is waiting to have a check
    result filed, and history is worth less than that
    '''

    def setUp(self):
        self.history = FakeHistory()
        self.server = module.NotificationServer(db=FakeDb(), history=self.history)
        self.interface = FakeInterface()
        self.server.build_interface = lambda: self.interface
        self.keeping = cluster_config.KEEP_HISTORY
        logging.disable(logging.ERROR)

    def tearDown(self):
        cluster_config.KEEP_HISTORY = self.keeping
        logging.disable(logging.NOTSET)

    def test_the_readings_are_kept(self):
        self.server.handle_notification(PAYLOAD, '10.0.0.10')
        self.assertEqual(self.history.recorded, [('i-1', PAYLOAD)])

    def test_they_are_filed_against_the_vm_at_that_address(self):
        self.server.db = FakeDb(instance_id='i-99')
        self.server.handle_notification(PAYLOAD, '10.0.0.10')
        self.assertEqual(self.history.recorded[0][0], 'i-99')

    def test_the_interface_still_gets_the_notification(self):
        self.server.handle_notification(PAYLOAD, '10.0.0.10')
        self.assertEqual(self.interface.notifications, [(PAYLOAD, '10.0.0.10')])

    def test_nothing_is_kept_for_an_address_with_no_running_vm(self):
        self.server.db = FakeDb(instance_id=None)
        self.assertEqual(self.server.record_history(PAYLOAD, '10.0.0.10'), 0)
        self.assertEqual(self.history.recorded, [])

    def test_a_database_that_will_not_take_them_does_not_fail_the_notification(self):
        self.server.history = BrokenHistory()
        self.assertTrue(self.server.handle_notification(PAYLOAD, '10.0.0.10'))
        self.assertEqual(self.interface.notifications, [(PAYLOAD, '10.0.0.10')])

    def test_the_readings_are_kept_even_when_no_interface_is_configured(self):
        #a cluster whose interface is misconfigured still has its history
        self.server.build_interface = lambda: None
        self.assertFalse(self.server.handle_notification(PAYLOAD, '10.0.0.10'))
        self.assertEqual(self.history.recorded, [('i-1', PAYLOAD)])

    def test_history_can_be_turned_off(self):
        cluster_config.KEEP_HISTORY = False
        self.server.handle_notification(PAYLOAD, '10.0.0.10')
        self.assertEqual(self.history.recorded, [])

    def test_turning_it_off_leaves_the_notification_alone(self):
        cluster_config.KEEP_HISTORY = False
        self.assertTrue(self.server.handle_notification(PAYLOAD, '10.0.0.10'))
        self.assertEqual(self.interface.notifications, [(PAYLOAD, '10.0.0.10')])

    def test_a_notification_with_no_address_keeps_nothing(self):
        self.assertFalse(self.server.handle_notification(PAYLOAD, None))
        self.assertEqual(self.history.recorded, [])


class BuildInterfaceTest(unittest.TestCase):

    def setUp(self):
        self.real_interface = cluster_config.INTERFACE
        logging.disable(logging.ERROR)

    def tearDown(self):
        cluster_config.INTERFACE = self.real_interface
        logging.disable(logging.NOTSET)

    def test_an_unconfigured_interface_builds_nothing(self):
        cluster_config.INTERFACE = 'zabbix'
        self.assertIsNone(module.NotificationServer(db=object()).build_interface())

    def test_the_interface_name_is_matched_regardless_of_case(self):
        cluster_config.INTERFACE = 'NAGIOS'
        server = module.NotificationServer(db=object())
        self.assertIsNotNone(server.build_interface())


if __name__ == '__main__':
    unittest.main()
