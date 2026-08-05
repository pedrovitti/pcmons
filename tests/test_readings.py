'''
Tests for the shared reading formatting.

Every interface asks the same question of a reading -- is this worth alerting
on, and what does it say -- so the judgement lives in one place and these are
the cases that make it. An interface decides what to do with a status; it does
not decide what the status is.
'''
import logging
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
sys.path.insert(0, ROOT)

from interface import readings as module


class FormatMetricTest(unittest.TestCase):
    """
    Each reading becomes a status code and a line of text. The status is
    what makes nagios alert, so the cases below are the ones that should.
    """

    def setUp(self):
        logging.disable(logging.ERROR)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def format(self, metric, reading):
        return module.format_metric(metric, reading)

    def test_malware_found_is_critical(self):
        status, output = self.format('malware', {'detected':2, 'last_scan':'today'})
        self.assertEqual(status, module.CRITICAL)
        self.assertIn('2 infected', output)

    def test_a_clean_scan_is_ok(self):
        status, output = self.format('malware', {'detected':0, 'last_scan':'today'})
        self.assertEqual(status, module.OK)

    def test_a_failed_vulnerability_check_is_critical(self):
        status, output = self.format('vulnerability', {'warn':2, 'fail':1})
        self.assertEqual(status, module.CRITICAL)

    def test_a_warned_vulnerability_check_is_a_warning(self):
        status, output = self.format('vulnerability', {'warn':2, 'fail':0})
        self.assertEqual(status, module.WARNING)

    def test_no_findings_is_ok(self):
        status, output = self.format('vulnerability', {'warn':0, 'fail':0})
        self.assertEqual(status, module.OK)

    def test_an_unencrypted_disk_is_a_warning(self):
        status, output = self.format('encryption', {'is_encrypted':'no', 'cipher':'-'})
        self.assertEqual(status, module.WARNING)

    def test_an_encrypted_disk_reports_its_cipher(self):
        status, output = self.format('encryption', {'is_encrypted':'yes', 'cipher':'aes-xts-plain64'})
        self.assertEqual(status, module.OK)
        self.assertIn('aes-xts-plain64', output)

    def test_passwords_that_never_expire_are_a_warning(self):
        #max_age 0 is what login.defs reports when the setting is absent
        status, output = self.format('password', {'max_age':0})
        self.assertEqual(status, module.WARNING)

    def test_a_password_policy_is_ok(self):
        status, output = self.format('password', {'max_age':90})
        self.assertEqual(status, module.OK)
        self.assertIn('90', output)

    def test_a_backup_that_never_ran_is_a_warning(self):
        status, output = self.format('backup', {'last_performed':''})
        self.assertEqual(status, module.WARNING)

    def test_an_integrity_scan_that_never_ran_is_a_warning(self):
        #IntegrityMonitor reports "-" when the log holds no report
        status, output = self.format('integrity', {'last_performed':'-'})
        self.assertEqual(status, module.WARNING)

    def test_ssh_attempts_are_reported_as_counts(self):
        #what makes a failed login count alarming is the operator's policy
        status, output = self.format('sshattempts', {'valid':'2', 'invalid':'3'})
        self.assertEqual(status, module.OK)
        self.assertIn('2 accepted', output)
        self.assertIn('3 failed', output)

    def test_an_overloaded_machine_is_critical(self):
        #this used to be registered with status 0, so nagios showed the word
        #CRITICAL in the text and never alerted on it
        status, output = self.format('loadavg', {'1':3.0, '5':2.0, '10':1.0})
        self.assertEqual(status, module.CRITICAL)

    def test_a_quote_in_a_value_is_removed(self):
        #the output is wrapped in quotes and passed to a shell script
        status, output = self.format('availability', {'uptime':'1:12" ; rm -rf /'})
        self.assertNotIn('"', output)

    def test_a_pipe_in_a_value_is_replaced(self):
        #nagios reads everything after a pipe as performance data
        status, output = self.format('encryption', {'is_encrypted':'yes', 'cipher':'aes|luks'})
        self.assertNotIn('|', output)

    def test_a_reading_that_cannot_be_read_is_skipped(self):
        self.assertIsNone(self.format('malware', {'detected':'lots'}))
        self.assertIsNone(self.format('password', {}))


class StatusTest(unittest.TestCase):
    """The names put in front of a person, and what an unknown code reads as."""

    def test_the_codes_are_the_ones_nagios_uses(self):
        #they travel to nagios as they are, so they cannot be renumbered
        self.assertEqual((module.OK, module.WARNING, module.CRITICAL), (0, 1, 2))

    def test_each_status_has_a_name(self):
        self.assertEqual(module.state(module.OK), 'OK')
        self.assertEqual(module.state(module.WARNING), 'WARNING')
        self.assertEqual(module.state(module.CRITICAL), 'CRITICAL')

    def test_a_status_from_nowhere_is_unknown_rather_than_an_error(self):
        self.assertEqual(module.state(9), 'UNKNOWN')

    def test_the_load_line_names_its_own_state(self):
        #the text and the status came apart once before: nagios showed the word
        #CRITICAL and alerted on nothing
        status, output = module.format_loadavg({'1':3.0, '5':2.0, '10':1.0})
        self.assertTrue(output.startswith(module.state(status)))


class UnknownMetricTest(unittest.TestCase):
    """
    the agent ships probes the cluster was not told about, and a reading it
    cannot judge must cost that reading alone
    """

    def setUp(self):
        logging.disable(logging.ERROR)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_a_metric_with_no_formatter_is_skipped(self):
        self.assertIsNone(module.format_metric('entropy', {'available':180}))

    def test_it_does_not_reach_for_anything_else_in_the_module(self):
        #the formatter is looked up by name, so a metric called 'metric' or
        #'sanitise' must not find format_metric or sanitise itself
        self.assertIsNone(module.format_metric('sanitise', {}))


if __name__ == '__main__':
    unittest.main()
