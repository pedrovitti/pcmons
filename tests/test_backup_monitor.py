'''
Tests for BackupMonitor, which reports the timestamp of the last rsync run
recorded in the backup log.
'''
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, 'booting_vms'))

from BackupMonitor import BackupMonitor

FIRST = '2026/08/05 02:01:07 [1180] building file list\n'
LAST = '2026/08/06 02:01:19 [1421] sent 1,204 bytes  received 35 bytes\n'


class BackupMonitorTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def read(self, contents):
        path = os.path.join(self.tmp, 'rsync.log')
        f = open(path, 'w')
        f.write(contents)
        f.close()
        return BackupMonitor(log_path=path).get_backup_info()

    def test_reports_the_timestamp_of_the_last_line(self):
        info = self.read(FIRST + LAST)
        self.assertEqual(info['last_performed'], '2026/08/06 02:01:19')

    def test_only_the_last_line_counts(self):
        #rsync appends, so an older run further up the file is not the answer
        info = self.read(LAST + FIRST)
        self.assertEqual(info['last_performed'], '2026/08/05 02:01:07')

    def test_empty_log_reports_nothing(self):
        #a log created by rsync but not yet written to used to raise IndexError
        #and take the whole reading down with it
        self.assertEqual(self.read('')['last_performed'], '')

    def test_default_path_is_the_rsync_log(self):
        self.assertEqual(BackupMonitor().log_path, '/var/log/rsync.log')


if __name__ == '__main__':
    unittest.main()
