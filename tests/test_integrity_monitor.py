'''
Tests for IntegrityMonitor, which reports when tripwire last ran.
'''
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, 'booting_vms'))

from IntegrityMonitor import IntegrityMonitor

REPORT = '''Parsing policy file: /etc/tripwire/tw.pol
Report created on: Thu Aug  6 03:00:12 2026
Total violations found: 0
'''


class IntegrityMonitorTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def read(self, contents):
        path = os.path.join(self.tmp, 'tripwire.log')
        f = open(path, 'w')
        f.write(contents)
        f.close()
        return IntegrityMonitor(log_path=path).get_integrity_info()

    def test_reports_the_date_the_report_was_created(self):
        info = self.read(REPORT)
        self.assertEqual(info['last_performed'], 'Thu Aug  6 03:00:12 2026')

    def test_the_latest_run_in_the_log_wins(self):
        #tripwire appends each run to the same log
        info = self.read(REPORT + REPORT.replace('Aug  6', 'Aug  7'))
        self.assertEqual(info['last_performed'], 'Thu Aug  7 03:00:12 2026')

    def test_log_without_a_report_reports_unknown(self):
        self.assertEqual(self.read('Parsing policy file: /etc/tripwire/tw.pol\n')['last_performed'], '-')

    def test_empty_log_reports_unknown(self):
        self.assertEqual(self.read('')['last_performed'], '-')

    def test_default_path_is_the_tripwire_log(self):
        self.assertEqual(IntegrityMonitor().log_path, '/var/log/tripwire.log')


if __name__ == '__main__':
    unittest.main()
