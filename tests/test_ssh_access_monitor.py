'''
Tests for SSHAccessMonitor, which counts login attempts in the sshd log.

The counting is the whole point of the class, and auth.log carries plenty of
lines that mention neither outcome, so each case below is a log written for it.
'''
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, 'booting_vms'))

from SSHAccessMonitor import SSHAccessMonitor

FAILED = 'Aug  6 03:11:02 vm sshd[2140]: Failed password for root from 10.0.0.9 port 55012 ssh2\n'
ACCEPTED = 'Aug  6 03:12:44 vm sshd[2150]: Accepted password for ubuntu from 10.0.0.4 port 55020 ssh2\n'
NOISE = 'Aug  6 03:13:01 vm CRON[2160]: pam_unix(cron:session): session opened for user root\n'


class SSHAccessMonitorTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def read(self, contents):
        path = os.path.join(self.tmp, 'auth.log')
        f = open(path, 'w')
        f.write(contents)
        f.close()
        return SSHAccessMonitor(log_path=path).get_ssh_access_attempts()

    def test_counts_each_outcome(self):
        attempts = self.read(FAILED + ACCEPTED + FAILED)
        self.assertEqual(attempts['invalid'], '2')
        self.assertEqual(attempts['valid'], '1')

    def test_unrelated_lines_are_not_counted(self):
        #the previous implementation counted every line that was not a failure
        #as a successful login, which made cron and sudo look like ssh logins
        attempts = self.read(NOISE * 5 + ACCEPTED)
        self.assertEqual(attempts['valid'], '1')
        self.assertEqual(attempts['invalid'], '0')

    def test_empty_log_reports_no_attempts(self):
        attempts = self.read('')
        self.assertEqual(attempts, {'valid':'0', 'invalid':'0'})

    def test_counts_are_strings(self):
        #the payload goes out over XML-RPC and the Nagios interface formats it
        #as text, so the type is part of the contract
        attempts = self.read(FAILED)
        self.assertIsInstance(attempts['valid'], str)
        self.assertIsInstance(attempts['invalid'], str)

    def test_default_path_is_the_ubuntu_auth_log(self):
        self.assertEqual(SSHAccessMonitor().log_path, '/var/log/auth.log')


if __name__ == '__main__':
    unittest.main()
