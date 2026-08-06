'''
Tests for PasswordMonitor, which reports the password expiry policy configured
in login.defs.
'''
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, 'booting_vms'))

from PasswordMonitor import PasswordMonitor

LOGIN_DEFS = '''#
# Password aging controls:
#
#	PASS_MAX_DAYS	Maximum number of days a password may be used.
#
PASS_MAX_DAYS\t90
PASS_MIN_DAYS\t0
PASS_WARN_AGE\t7
'''


class PasswordMonitorTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def read(self, contents):
        path = os.path.join(self.tmp, 'login.defs')
        f = open(path, 'w')
        f.write(contents)
        f.close()
        return PasswordMonitor(login_defs_path=path).get_password_security()

    def test_reports_the_configured_maximum_age(self):
        self.assertEqual(self.read(LOGIN_DEFS)['max_age'], 90)

    def test_the_commented_documentation_is_not_read_as_the_setting(self):
        #login.defs describes PASS_MAX_DAYS in a comment above it, so a parser
        #that ignores the '#' picks up the documentation instead
        self.assertEqual(self.read('#\tPASS_MAX_DAYS\tMaximum number of days\n')['max_age'], 0)

    def test_absent_setting_reports_zero(self):
        #a login.defs that never sets it used to raise NameError
        self.assertEqual(self.read('PASS_MIN_DAYS\t0\n')['max_age'], 0)

    def test_empty_file_reports_zero(self):
        self.assertEqual(self.read('')['max_age'], 0)

    def test_a_malformed_value_is_ignored(self):
        self.assertEqual(self.read('PASS_MAX_DAYS\tnever\n')['max_age'], 0)

    def test_max_age_is_a_number(self):
        self.assertIsInstance(self.read(LOGIN_DEFS)['max_age'], int)

    def test_default_path_is_login_defs(self):
        self.assertEqual(PasswordMonitor().login_defs_path, '/etc/login.defs')


if __name__ == '__main__':
    unittest.main()
