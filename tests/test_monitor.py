'''
Tests for Monitor, the agent that runs inside the VM: it polls the probes and
pushes the readings to the notification server.
'''
import logging
import os
import socket
import sys
import unittest
import xmlrpclib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, 'booting_vms'))

import Monitor as module
from Monitor import Monitor

PROBES = {
    'memory': 'memoryMonitor.get_meminfo',
    'loadavg': 'systemLoadMonitor.get_loadavg',
    'http': 'httpMonitor.get_http_connections',
    'sshattempts': 'sshAccessMonitor.get_ssh_access_attempts',
    'availability': 'availabilityMonitor.get_availability_info',
    'backup': 'backupMonitor.get_backup_info',
    'encryption': 'encryptionMonitor.get_encryption_info',
    'integrity': 'integrityMonitor.get_integrity_info',
    'malware': 'malwareMonitor.get_malware_info',
    'password': 'passwordMonitor.get_password_security',
    'vulnerability': 'vulnerabilityMonitor.get_vulnerability_info',
}


class FakeProbe:
    '''A probe class exposing one named method, which returns or raises.'''

    def __init__(self, method, result):
        self.calls = 0
        setattr(self, method, self.reading)
        self.result = result

    def reading(self):
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeProxy:

    def __init__(self, url):
        self.url = url
        FakeProxy.last = self

    def get_vm_notification(self, data):
        self.sent = data
        return True


class FailingProxy(FakeProxy):

    def get_vm_notification(self, data):
        raise socket.error('connection refused')


class FakeXMLRPC:
    '''The xmlrpclib names Monitor uses, with a proxy we control.'''

    Fault = xmlrpclib.Fault
    ProtocolError = xmlrpclib.ProtocolError
    ResponseError = xmlrpclib.ResponseError

    def __init__(self, proxy):
        self.ServerProxy = proxy


class MonitorTest(unittest.TestCase):

    def setUp(self):
        self.real_xmlrpclib = module.xmlrpclib
        self.monitor = Monitor()
        #the failure paths log by design; keep the test output readable
        logging.disable(logging.ERROR)

    def tearDown(self):
        module.xmlrpclib = self.real_xmlrpclib
        logging.disable(logging.NOTSET)

    def fake_probes(self, failing=()):
        '''Replace every probe with one that reports its own name.'''
        probes = {}
        for name, attribute in PROBES.items():
            probe_name, method = attribute.split('.')
            result = Exception('no such file') if name in failing else {'value':name}
            probes[name] = FakeProbe(method, result)
            setattr(self.monitor, probe_name, probes[name])
        return probes

    def test_reports_every_probe(self):
        self.fake_probes()
        data = self.monitor.get_monitoring_data()
        self.assertEqual(sorted(data.keys()), sorted(PROBES.keys()))

    def test_each_probe_is_read_once(self):
        probes = self.fake_probes()
        self.monitor.get_monitoring_data()
        for name, probe in probes.items():
            self.assertEqual(probe.calls, 1, name)

    def test_a_failing_probe_does_not_take_the_others_with_it(self):
        #the VM image may not have tripwire or clamav installed, and a missing
        #log file must cost that one metric rather than the whole reading
        self.fake_probes(failing=('malware', 'integrity'))
        data = self.monitor.get_monitoring_data()
        self.assertNotIn('malware', data)
        self.assertNotIn('integrity', data)
        self.assertEqual(len(data), len(PROBES) - 2)

    def test_every_probe_may_fail(self):
        self.fake_probes(failing=PROBES.keys())
        self.assertEqual(self.monitor.get_monitoring_data(), {})

    def test_the_availability_key_is_spelled_correctly(self):
        #it went out as 'availabity' for years; the Nagios interface reads it
        self.fake_probes()
        self.assertIn('availability', self.monitor.get_monitoring_data())

    def test_sends_the_data_to_the_configured_server(self):
        module.xmlrpclib = FakeXMLRPC(FakeProxy)
        self.monitor.send_monitoring_data({'memory':{'used':1}})
        self.assertEqual(FakeProxy.last.url,
                         '%s:%s'%(module.settings.SERVER, module.settings.SERVER_PORT))
        self.assertEqual(FakeProxy.last.sent, {'memory':{'used':1}})

    def test_an_unreachable_server_is_not_fatal(self):
        #the agent keeps collecting while the controller is down
        module.xmlrpclib = FakeXMLRPC(FailingProxy)
        self.monitor.send_monitoring_data({})

    def test_constructing_the_agent_does_not_start_collecting(self):
        #the loop used to run inside __init__, so nothing could hold a Monitor
        self.assertTrue(hasattr(self.monitor, 'run'))


if __name__ == '__main__':
    unittest.main()
