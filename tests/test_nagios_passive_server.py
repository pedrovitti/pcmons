'''
Tests for NagiosPassiveServer, which turns an agent's notification into Nagios
passive check results.

This is where the payload the agent sends is finally read, so the tests are as
much about the shape of that payload as about the formatting: every value the
interface touches is one a probe produced, and a probe that changed type here
would break the controller rather than the VM.
'''
import logging
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
sys.path.insert(0, ROOT)

import running_vms.cluster.cluster_config as cluster_config
#the interface configures logging to this path on construction
cluster_config.PATH_TO_LOG_FILE = '/tmp/pcmons-nagios-test.log'

from interface.nagios import NagiosPassiveServer as module
from interface.nagios import services


class FakeDb:

    def __init__(self, vm=None, known=True):
        self.vm = vm or {'user':'oneadmin', 'instance_id':'i-42', 'node_hostname':'node01'}
        self.known = known

    def get_id_by_ip(self, ip):
        self.ip = ip
        if not self.known:
            return None
        return {'instance_id':self.vm['instance_id']}

    def get_vm_info(self, instance_id):
        if not self.known:
            return None
        return self.vm

    def get_vm_by_ip(self, ip):
        self.ip = ip
        if not self.known:
            return None
        return self.vm


class FakeCommands:

    def __init__(self):
        self.called = []

    def getstatusoutput(self, cmd):
        self.called.append(cmd)
        return (0, '')


class Recorder:
    '''Stands in for register_passive_check, keeping what was registered.'''

    def __init__(self):
        self.checks = []

    def __call__(self, hostname, service, status, value):
        self.checks.append((hostname, service, status, value))

    def value(self, service):
        for check, name, status, value in self.checks:
            if name == service:
                return value
        return None

    def services(self):
        return [name for hostname, name, status, value in self.checks]


#a full reading, with the types the probes produce today
PAYLOAD = {
    'memory': {'used':1048576, 'free':1048576, 'cache':262144, 'total':2097152},
    'loadavg': {'1':0.75, '5':0.5, '10':0.25},
    'http': {'connections':7},
    'sshattempts': {'valid':'2', 'invalid':'3'},
    'availability': {'uptime':'1:12'},
    'backup': {'last_performed':'2026/08/06 02:01:19'},
    'encryption': {'is_encrypted':'yes', 'cipher':'aes-xts-plain64,luks'},
    'integrity': {'last_performed':'Thu Aug  6 03:00:12 2026'},
    'malware': {'detected':0, 'last_scan':'Thu Aug  6 04:58:44 2026'},
    'password': {'max_age':90},
    'vulnerability': {'warn':0, 'fail':0},
}


class NagiosPassiveServerTest(unittest.TestCase):

    def setUp(self):
        self.db = FakeDb()
        self.server = module.NagiosPassiveServer(db=self.db)
        self.recorder = Recorder()
        self.server.register_passive_check = self.recorder
        logging.disable(logging.ERROR)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def process(self, data=None, ip='10.0.0.10'):
        self.server.process_notification(PAYLOAD if data is None else data, ip)
        return self.recorder

    def test_names_the_host_from_the_stored_vm(self):
        self.process()
        self.assertEqual(self.recorder.checks[0][0], 'oneadmin_i-42_node01')

    def test_looks_the_vm_up_by_the_address_it_reported_from(self):
        self.process(ip='10.0.0.77')
        self.assertEqual(self.db.ip, '10.0.0.77')

    def test_registers_a_check_per_metric_it_understands(self):
        #every metric the agent sends, not just the three it used to read
        self.assertEqual(sorted(self.process().services()),
                         sorted(services.service_names()))

    def test_reports_memory_as_a_percentage_and_megabytes(self):
        self.assertEqual(self.process().value('RAM'), '"50;1024/2048"')

    def test_reports_the_connection_count(self):
        #the count is an int; the value used to be built by concatenation,
        #which raised TypeError as soon as the probe stopped returning a string
        self.assertEqual(self.process().value('HTTP_Connections'), '"7"')

    def test_reports_load_below_the_thresholds_as_ok(self):
        self.assertEqual(self.process().value('Cpu_Load'),
                         '"OK - load average: 0.75, 0.50, 0.25"')

    def test_reports_a_busy_machine_as_a_warning(self):
        data = dict(PAYLOAD, loadavg={'1':1.5, '5':1.0, '10':0.5})
        self.assertEqual(self.process(data).value('Cpu_Load'),
                         '"WARNING - load average: 1.50, 1.00, 0.50"')

    def test_reports_an_overloaded_machine_as_critical(self):
        data = dict(PAYLOAD, loadavg={'1':3.0, '5':2.0, '10':1.0})
        self.assertEqual(self.process(data).value('Cpu_Load'),
                         '"CRITICAL - load average: 3.00, 2.00, 1.00"')

    def test_a_missing_metric_does_not_lose_the_others(self):
        #the agent omits any probe that failed, so a notification can arrive
        #without a metric in it. That must not cost the whole notification.
        data = dict(PAYLOAD)
        del data['memory']
        registered = self.process(data).services()
        self.assertNotIn('RAM', registered)
        self.assertEqual(len(registered), len(services.service_names()) - 1)

    def test_a_notification_with_nothing_in_it_registers_nothing(self):
        self.assertEqual(self.process({}).services(), [])

    def test_a_memory_reading_without_a_total_is_skipped(self):
        #dividing by it would raise, and taking the rest of the reading down
        #with it would be worse than missing one check
        data = dict(PAYLOAD, memory={'used':0, 'free':0, 'cache':0, 'total':0})
        registered = self.process(data).services()
        self.assertNotIn('RAM', registered)
        self.assertIn('Cpu_Load', registered)

    def test_a_malformed_reading_costs_only_its_own_check(self):
        #a probe reporting something unexpected must not stop the rest
        data = dict(PAYLOAD, malware={'detected':'lots'})
        registered = self.process(data).services()
        self.assertNotIn('Malware', registered)
        self.assertIn('RAM', registered)

    def test_the_notification_is_acknowledged(self):
        self.assertTrue(self.server.process_notification(PAYLOAD, '10.0.0.10'))

    def test_an_address_no_running_vm_has_is_dropped(self):
        #an agent reporting after its vm was marked terminated, or from an
        #address the inventory never recorded. This used to raise IndexError
        #inside get_id_by_ip and take the notification down with it
        server = module.NagiosPassiveServer(db=FakeDb(known=False))
        server.register_passive_check = Recorder()
        self.assertFalse(server.process_notification(PAYLOAD, '10.0.0.99'))
        self.assertEqual(server.register_passive_check.services(), [])


class RegisterPassiveCheckTest(unittest.TestCase):
    '''The one place the interface shells out.'''

    def setUp(self):
        self.real_commands = module.commands
        module.commands = FakeCommands()
        self.server = module.NagiosPassiveServer(db=FakeDb())

    def tearDown(self):
        module.commands = self.real_commands

    def test_calls_the_nagios_script_with_the_check(self):
        self.server.register_passive_check('oneadmin_i-42_node01', 'RAM', 0, '"50;1024/2048"')
        self.assertEqual(module.commands.called,
                         ['./send_passive_check_nagios.sh oneadmin_i-42_node01 RAM 0 "50;1024/2048"'])


if __name__ == '__main__':
    unittest.main()
