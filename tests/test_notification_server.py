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
