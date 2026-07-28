'''
Tests for AvailabilityMonitor, which reports how long the VM has been up.

The class shells out to uptime, so the tests feed it recorded output from the
platforms this ran on rather than whatever the test machine reports.
'''
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, 'booting_vms'))

import AvailabilityMonitor as module
from AvailabilityMonitor import AvailabilityMonitor


class FakeCommands:
    '''Stands in for the commands module, returning a recorded uptime.'''

    def __init__(self, output):
        self.output = output
        self.called = []

    def getoutput(self, cmd):
        self.called.append(cmd)
        return self.output


class AvailabilityMonitorTest(unittest.TestCase):

    def setUp(self):
        self.real_commands = module.commands

    def tearDown(self):
        module.commands = self.real_commands

    def uptime(self, output):
        module.commands = FakeCommands(output)
        return AvailabilityMonitor().get_availability_info()['uptime']

    def test_reports_the_elapsed_time(self):
        self.assertEqual(self.uptime(' 07:58:30 up  1:12,  0 users,  load average: 0.75, 0.29, 0.23'),
                         '1:12')

    def test_keeps_the_hours_once_uptime_spans_days(self):
        #once it reaches a day the value contains a comma of its own, and
        #splitting on the first comma silently dropped the "19:43"
        self.assertEqual(self.uptime(' 8:58  up 70 days, 19:43, 13 users, load averages: 7.03 5.92 6.84'),
                         '70 days, 19:43')

    def test_handles_a_single_user(self):
        #"1 user", not "1 users"
        self.assertEqual(self.uptime(' 12:00:01 up 3 min,  1 user,  load average: 0.10, 0.05, 0.01'),
                         '3 min')

    def test_unrecognised_output_falls_back_to_the_first_field(self):
        self.assertEqual(self.uptime('up 5 days'), 'up 5 days')

    def test_runs_uptime(self):
        module.commands = FakeCommands('')
        AvailabilityMonitor().get_availability_info()
        self.assertEqual(module.commands.called, ['uptime'])


if __name__ == '__main__':
    unittest.main()
