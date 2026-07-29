'''
Tests for HTTPConMonitor, which counts the connections to the application port
by shelling out to netstat.
'''
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, 'booting_vms'))

import HTTPConMonitor as module
from HTTPConMonitor import HTTPConMonitor


class FakeCommands:
    '''Stands in for the commands module, returning a recorded result.'''

    def __init__(self, status, output):
        self.result = (status, output)
        self.called = []

    def getstatusoutput(self, cmd):
        self.called.append(cmd)
        return self.result


class HTTPConMonitorTest(unittest.TestCase):

    def setUp(self):
        self.real_commands = module.commands

    def tearDown(self):
        module.commands = self.real_commands

    def count(self, status, output):
        module.commands = FakeCommands(status, output)
        return HTTPConMonitor().get_http_connections()['connections']

    def test_reports_the_count(self):
        self.assertEqual(self.count(0, '7\n'), 7)

    def test_padded_output_is_still_a_number(self):
        #wc -l pads the count on some platforms
        self.assertEqual(self.count(0, '      12\n'), 12)

    def test_count_is_a_number(self):
        self.assertIsInstance(self.count(0, '3\n'), int)

    def test_a_failed_command_leaves_the_count_alone(self):
        #no netstat on the VM means no reading, not a wrong one
        self.assertEqual(self.count(127, 'sh: netstat: not found'), 0)

    def test_unparseable_output_leaves_the_count_alone(self):
        self.assertEqual(self.count(0, 'lots'), 0)

    def test_queries_the_application_port(self):
        module.commands = FakeCommands(0, '0\n')
        HTTPConMonitor().get_http_connections()
        self.assertIn('8080', module.commands.called[0])


if __name__ == '__main__':
    unittest.main()
