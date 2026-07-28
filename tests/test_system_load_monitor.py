'''
Tests for SystemLoadMonitor, which reports the three load averages.
'''
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, 'booting_vms'))

import SystemLoadMonitor as module
from SystemLoadMonitor import SystemLoadMonitor


class SystemLoadMonitorTest(unittest.TestCase):

    def setUp(self):
        self.real_getloadavg = module.os.getloadavg

    def tearDown(self):
        module.os.getloadavg = self.real_getloadavg

    def loadavg(self, values):
        module.os.getloadavg = lambda: values
        return SystemLoadMonitor().get_loadavg()

    def test_reports_each_window_in_order(self):
        #the third key is named '10' but holds what getloadavg returns last,
        #which is the 15 minute average. The Nagios interface reads these keys,
        #so the names are a contract and stay as they are
        self.assertEqual(self.loadavg((1.5, 0.75, 0.25)),
                         {'1':1.5, '5':0.75, '10':0.25})

    def test_an_idle_machine_reports_zero(self):
        self.assertEqual(self.loadavg((0.0, 0.0, 0.0)), {'1':0.0, '5':0.0, '10':0.0})

    def test_values_are_floats(self):
        #NagiosPassiveServer formats them with %.2f and compares them to 3.0
        for value in self.loadavg((2.0, 1.0, 0.5)).values():
            self.assertIsInstance(value, float)

    def test_reading_is_kept_on_the_instance(self):
        module.os.getloadavg = lambda: (0.1, 0.2, 0.3)
        monitor = SystemLoadMonitor()
        self.assertEqual(monitor.get_loadavg(), monitor.loadavg)

    def test_a_live_reading_has_the_three_windows(self):
        self.assertEqual(sorted(SystemLoadMonitor().get_loadavg().keys()), ['1', '10', '5'])


if __name__ == '__main__':
    unittest.main()
