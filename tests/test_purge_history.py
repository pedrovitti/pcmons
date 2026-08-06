'''
Tests for Purge_History, the cron entry that discards readings past the
retention window.

Purging is not undoable, so most of these are about the window it decides on:
the configured one, the one asked for, and refusing anything it cannot read as
a number of days rather than guessing.
'''
import logging
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
sys.path.insert(0, ROOT)

import running_vms.cluster.cluster_config as cluster_config
cluster_config.PATH_TO_LOG_FILE = '/tmp/pcmons-purge-test.log'

from running_vms.cluster import Purge_History as module


class FakeHistory:

    def __init__(self, discarded=3):
        self.purged = []
        self.discarded = discarded

    def purge(self, days=None):
        self.purged.append(days)
        return self.discarded


class ParseDaysTest(unittest.TestCase):

    def test_no_argument_means_the_configured_window(self):
        self.assertIsNone(module.parse_days(['Purge_History.py']))

    def test_a_window_given_on_the_command_line(self):
        self.assertEqual(module.parse_days(['Purge_History.py', '7']), 7)

    def test_a_window_that_is_not_a_number_is_refused(self):
        #guessing here would discard the wrong month of readings
        self.assertRaises(ValueError, module.parse_days, ['Purge_History.py', 'lastweek'])

    def test_a_negative_window_is_refused(self):
        #it would put the cutoff in the future and discard everything
        self.assertRaises(ValueError, module.parse_days, ['Purge_History.py', '-7'])

    def test_no_days_at_all_is_allowed(self):
        #asking for nothing to be kept is a decision, not a mistake
        self.assertEqual(module.parse_days(['Purge_History.py', '0']), 0)

    def test_extra_arguments_are_ignored(self):
        self.assertEqual(module.parse_days(['Purge_History.py', '7', 'please']), 7)


class PurgeTest(unittest.TestCase):

    def setUp(self):
        self.history = FakeHistory()
        logging.disable(logging.ERROR)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_it_purges(self):
        module.purge(days=7, history=self.history)
        self.assertEqual(self.history.purged, [7])

    def test_it_reports_how_many_readings_went(self):
        self.assertEqual(module.purge(days=7, history=self.history), 3)

    def test_no_window_leaves_the_choice_to_the_history(self):
        #which reads it from the config, so there is one place it is set
        module.purge(history=self.history)
        self.assertEqual(self.history.purged, [None])


if __name__ == '__main__':
    unittest.main()
