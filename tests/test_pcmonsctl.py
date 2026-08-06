'''
Tests for pcmonsctl.

It is read at a terminal while something is wrong, so the cases below are
mostly about what it says when there is nothing to say -- an unknown vm, a
metric never recorded, an inventory that is empty -- and about the exit
status, which is what a cron entry acts on.
'''
import datetime
import os
import sys
import unittest

from StringIO import StringIO

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
sys.path.insert(0, ROOT)

import running_vms.cluster.cluster_config as cluster_config
cluster_config.PATH_TO_LOG_FILE = '/tmp/pcmons-ctl-test.log'

import pcmonsctl as module

NOW = datetime.datetime(2026, 8, 6, 12, 0, 0)


def minutes_ago(count):
    return NOW - datetime.timedelta(minutes=count)


class FakeDb:

    def __init__(self, vms=None):
        self.vms = vms if vms is not None else [
            {'instance_id':'i-42', 'user':'oneadmin', 'state':'running',
             'node_hostname':'node01', 'public_dns_name':'150.162.63.90'},
            {'instance_id':'i-7', 'user':'someone', 'state':'running',
             'node_hostname':'node02', 'public_dns_name':'150.162.63.91'},
        ]

    def get_running_vms(self):
        return self.vms


class FakeHistory:

    def __init__(self):
        self.latest_readings = {
            'i-42': {'memory':{'used':'1024', 'total':'2048'},
                     'loadavg':{'1':'0.5'}},
        }
        self.seen = {'i-42': minutes_ago(2), 'i-7': minutes_ago(90)}
        self.series_readings = {
            ('i-42', 'memory', 'used'): [(minutes_ago(10), '512'),
                                         (minutes_ago(5), '1024'),
                                         (minutes_ago(0), '768')],
        }
        self.forgotten = []

    def latest(self, instance_id):
        return self.latest_readings.get(instance_id, {})

    def last_seen(self, instance_id):
        return self.seen.get(instance_id)

    def is_silent(self, instance_id, minutes=15, now=None):
        seen = self.seen.get(instance_id)
        if seen is None:
            return True
        return (NOW - seen) > datetime.timedelta(minutes=minutes)

    def series(self, instance_id, metric, field, limit=100, since=None):
        found = self.series_readings.get((instance_id, metric, field), [])
        return found[-limit:]

    def numbers(self, instance_id, metric, field, limit):
        return [float(value) for when, value in
                self.series(instance_id, metric, field, limit=limit)]

    def average(self, instance_id, metric, field, limit=100, since=None):
        numbers = self.numbers(instance_id, metric, field, limit)
        if not numbers:
            return None
        return sum(numbers)/len(numbers)

    def peak(self, instance_id, metric, field, limit=100, since=None):
        numbers = self.numbers(instance_id, metric, field, limit)
        if not numbers:
            return None
        return max(numbers)

    def forget(self, instance_id):
        self.forgotten.append(instance_id)
        return 12


class ConsoleTest(unittest.TestCase):

    def setUp(self):
        self.out = StringIO()
        self.db = FakeDb()
        self.history = FakeHistory()
        self.console = module.Console(db=self.db, history=self.history, out=self.out)

    def run_command(self, *argv):
        status = module.main(['pcmonsctl'] + list(argv), console=self.console)
        return status, self.out.getvalue()

    def lines(self):
        return [line for line in self.out.getvalue().splitlines() if line.strip()]


class VmsTest(ConsoleTest):

    def test_it_lists_every_vm(self):
        status, output = self.run_command('vms')
        self.assertEqual(status, 0)
        self.assertIn('i-42', output)
        self.assertIn('i-7', output)

    def test_the_listing_carries_what_identifies_a_vm(self):
        status, output = self.run_command('vms')
        self.assertIn('oneadmin', output)
        self.assertIn('node01', output)
        self.assertIn('150.162.63.90', output)

    def test_the_vms_come_out_in_a_settled_order(self):
        #it is read at a terminal, and a listing that reorders itself between
        #runs is one nobody can compare
        self.run_command('vms')
        rows = self.lines()[1:]
        self.assertTrue(rows[0].startswith('i-42'))
        self.assertTrue(rows[1].startswith('i-7'))

    def test_a_vm_that_never_reported_says_so(self):
        self.history.seen = {}
        status, output = self.run_command('vms')
        self.assertIn('never', output)

    def test_an_empty_inventory_is_not_an_error(self):
        self.db.vms = []
        status, output = self.run_command('vms')
        self.assertEqual(status, 0)
        self.assertIn('no vms recorded', output)

    def test_the_columns_fit_what_is_in_them(self):
        #a vm whose name is longer than the heading is the normal case
        self.db.vms = [{'instance_id':'i-a-very-long-instance-name',
                        'user':'u', 'state':'running', 'node_hostname':'n',
                        'public_dns_name':'10.0.0.1'}]
        self.run_command('vms')
        heading, row = self.lines()[0], self.lines()[1]
        self.assertTrue(row.startswith('i-a-very-long-instance-name'))
        self.assertIn('USER', heading)


class ShowTest(ConsoleTest):

    def test_it_shows_every_metric(self):
        status, output = self.run_command('show', 'i-42')
        self.assertEqual(status, 0)
        self.assertIn('memory', output)
        self.assertIn('loadavg', output)

    def test_it_shows_the_values(self):
        status, output = self.run_command('show', 'i-42')
        self.assertIn('1024', output)
        self.assertIn('2048', output)

    def test_it_says_when_the_reading_arrived(self):
        status, output = self.run_command('show', 'i-42')
        self.assertIn('last reading', output)

    def test_a_vm_that_never_reported_is_answered_not_guessed(self):
        status, output = self.run_command('show', 'i-nobody')
        self.assertEqual(status, 1)
        self.assertIn('nothing has been recorded', output)

    def test_a_silent_vm_is_flagged(self):
        #the values shown are the last ones that arrived, which is not the
        #same as the state of the vm now
        self.history.latest_readings['i-7'] = {'memory':{'used':'1'}}
        status, output = self.run_command('show', 'i-7')
        self.assertIn('WARNING', output)

    def test_a_reporting_vm_is_not_flagged(self):
        status, output = self.run_command('show', 'i-42')
        self.assertNotIn('WARNING', output)

    def test_it_needs_a_vm(self):
        status, output = self.run_command('show')
        self.assertEqual(status, 2)
        self.assertIn('needs the instance id', output)


class HistoryTest(ConsoleTest):

    def test_it_shows_the_readings(self):
        status, output = self.run_command('history', 'i-42', 'memory', 'used')
        self.assertEqual(status, 0)
        self.assertIn('512', output)
        self.assertIn('768', output)

    def test_the_readings_run_oldest_first(self):
        self.run_command('history', 'i-42', 'memory', 'used')
        rows = self.lines()[1:4]
        self.assertIn('512', rows[0])
        self.assertIn('768', rows[2])

    def test_it_reports_the_average_and_the_peak(self):
        #a spike between two calm readings is easy to miss in a column
        status, output = self.run_command('history', 'i-42', 'memory', 'used')
        self.assertIn('average', output)
        self.assertIn('peak 1024.00', output)

    def test_a_count_can_be_asked_for(self):
        status, output = self.run_command('history', 'i-42', 'memory', 'used', '2')
        self.assertNotIn('512', output)
        self.assertIn('768', output)

    def test_a_count_that_is_not_a_number_is_refused(self):
        status, output = self.run_command('history', 'i-42', 'memory', 'used', 'lots')
        self.assertEqual(status, 2)
        self.assertIn('not a number', output)

    def test_a_field_never_recorded_is_answered_not_guessed(self):
        status, output = self.run_command('history', 'i-42', 'memory', 'swap')
        self.assertEqual(status, 1)
        self.assertIn('no memory swap recorded', output)

    def test_it_needs_a_metric_and_a_field(self):
        status, output = self.run_command('history', 'i-42')
        self.assertEqual(status, 2)
        self.assertIn('needs an instance id, a metric and a field', output)


class SilentTest(ConsoleTest):

    def test_it_lists_the_vms_that_stopped_reporting(self):
        status, output = self.run_command('silent')
        self.assertIn('i-7', output)
        self.assertNotIn('i-42', output)

    def test_a_silent_vm_is_a_non_zero_exit(self):
        #so a cron entry can act on it
        status, output = self.run_command('silent')
        self.assertEqual(status, 1)

    def test_a_healthy_cluster_exits_zero(self):
        self.history.seen = {'i-42':minutes_ago(1), 'i-7':minutes_ago(1)}
        status, output = self.run_command('silent')
        self.assertEqual(status, 0)
        self.assertIn('every vm reported', output)

    def test_the_threshold_can_be_asked_for(self):
        status, output = self.run_command('silent', '120')
        self.assertEqual(status, 0)

    def test_a_threshold_that_is_not_a_number_is_refused(self):
        status, output = self.run_command('silent', 'ages')
        self.assertEqual(status, 2)
        self.assertIn('not a number', output)

    def test_a_vm_that_never_reported_counts_as_silent(self):
        self.history.seen = {}
        status, output = self.run_command('silent')
        self.assertIn('never', output)


class ForgetTest(ConsoleTest):

    def test_it_drops_the_readings(self):
        status, output = self.run_command('forget', 'i-42')
        self.assertEqual(status, 0)
        self.assertEqual(self.history.forgotten, ['i-42'])

    def test_it_says_how_much_it_dropped(self):
        #the only command that writes, so it says what it did
        status, output = self.run_command('forget', 'i-42')
        self.assertIn('12 readings discarded', output)

    def test_it_needs_a_vm(self):
        status, output = self.run_command('forget')
        self.assertEqual(status, 2)
        self.assertEqual(self.history.forgotten, [])


class DispatchTest(ConsoleTest):

    def test_no_command_prints_the_usage(self):
        status, output = self.run_command()
        self.assertEqual(status, 2)
        self.assertIn('pcmonsctl vms', output)

    def test_a_command_that_does_not_exist_is_named(self):
        status, output = self.run_command('graph')
        self.assertEqual(status, 2)
        self.assertIn("'graph' is not a command", output)

    def test_every_listed_command_can_be_run(self):
        #the usage is the documentation, and a command listed there that does
        #not dispatch is worse than one that is missing
        for name in module.COMMANDS:
            self.assertIn(name, module.__doc__)
            self.assertTrue(hasattr(self.console, module.COMMANDS[name]), name)


if __name__ == '__main__':
    unittest.main()
