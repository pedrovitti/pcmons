'''
Tests for History, which keeps the readings the agents report.

Every notification used to be handed to the interface and dropped, so these
are about the shape of what is kept: one row per field of one metric, and the
questions that shape is meant to make answerable -- the last value of
everything, one value over time, and when a vm last said anything at all.

The fake database below stores rows in memory and answers the same queries the
connector does, so these exercise History's own behaviour rather than SQL.
'''
import datetime
import logging
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
sys.path.insert(0, ROOT)

import running_vms.cluster.cluster_config as cluster_config
cluster_config.PATH_TO_LOG_FILE = '/tmp/pcmons-history-test.log'

from running_vms.cluster.history import History

NOW = datetime.datetime(2026, 8, 6, 12, 0, 0)


def minutes_ago(count):
    return NOW - datetime.timedelta(minutes=count)


class FakeDb:
    '''
    the reading half of Db_Connector, in memory. Rows come back newest first
    the way the real queries order them, and ties break on insertion order so
    that two readings taken in the same second stay in the order they arrived
    '''

    def __init__(self):
        self.rows = []

    def insert_readings(self, rows):
        for instance_id, metric, field, value, recorded_at in rows:
            self.rows.append({'instance_id':instance_id, 'metric':metric,
                              'field':field, 'value':value, 'recorded_at':recorded_at})
        return len(rows)

    def get_readings(self, instance_id, metric=None, field=None, since=None, limit=None):
        found = []
        for position, row in enumerate(self.rows):
            if row['instance_id'] != instance_id:
                continue
            if metric is not None and row['metric'] != metric:
                continue
            if field is not None and row['field'] != field:
                continue
            if since is not None and row['recorded_at'] < since:
                continue
            found.append((row['recorded_at'], position, row))
        found.sort(reverse=True)
        rows = [row for recorded_at, position, row in found]
        if limit is not None:
            rows = rows[:limit]
        return rows

    def get_latest_readings(self, instance_id):
        newest = {}
        for row in self.rows:
            if row['instance_id'] != instance_id:
                continue
            key = (row['metric'], row['field'])
            if key not in newest or row['recorded_at'] >= newest[key]['recorded_at']:
                newest[key] = row
        return list(newest.values())

    def get_reading_instance_ids(self):
        seen = []
        for row in self.rows:
            if row['instance_id'] not in seen:
                seen.append(row['instance_id'])
        return [{'instance_id':instance_id} for instance_id in seen]

    def delete_readings_before(self, cutoff):
        kept = [row for row in self.rows if row['recorded_at'] >= cutoff]
        discarded = len(self.rows) - len(kept)
        self.rows = kept
        return discarded

    def delete_readings_for(self, instance_id):
        kept = [row for row in self.rows if row['instance_id'] != instance_id]
        discarded = len(self.rows) - len(kept)
        self.rows = kept
        return discarded


class HistoryTest(unittest.TestCase):

    def setUp(self):
        self.db = FakeDb()
        self.history = History(db=self.db)
        logging.disable(logging.ERROR)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def stored(self):
        return [(row['metric'], row['field'], row['value']) for row in self.db.rows]


class RecordTest(HistoryTest):

    def test_a_notification_is_stored_one_row_per_field(self):
        self.history.record('i-1', {'memory':{'used':512, 'total':1024}}, when=NOW)
        self.assertEqual(sorted(self.stored()),
                         [('memory', 'total', '1024'), ('memory', 'used', '512')])

    def test_it_reports_how_many_readings_it_kept(self):
        kept = self.history.record('i-1', {'memory':{'used':512, 'total':1024},
                                           'http':{'connections':7}}, when=NOW)
        self.assertEqual(kept, 3)

    def test_every_field_of_one_notification_shares_a_time(self):
        self.history.record('i-1', {'memory':{'used':512, 'total':1024}}, when=NOW)
        self.assertEqual(set(row['recorded_at'] for row in self.db.rows), set([NOW]))

    def test_the_readings_are_filed_against_the_vm(self):
        self.history.record('i-7', {'http':{'connections':1}}, when=NOW)
        self.assertEqual(self.db.rows[0]['instance_id'], 'i-7')

    def test_an_empty_notification_stores_nothing(self):
        #an agent whose probes all failed still reported in; that is not an
        #error, there is just nothing to keep
        self.assertEqual(self.history.record('i-1', {}, when=NOW), 0)
        self.assertEqual(self.db.rows, [])

    def test_a_notification_that_is_not_a_payload_is_refused(self):
        self.assertEqual(self.history.record('i-1', 'nonsense', when=NOW), 0)
        self.assertEqual(self.db.rows, [])

    def test_it_stores_metrics_it_has_never_heard_of(self):
        #the agent ships probes the cluster was not told about, and a reading
        #that arrives is worth keeping whether or not anything graphs it yet
        self.history.record('i-1', {'entropy':{'available':180}}, when=NOW)
        self.assertEqual(self.stored(), [('entropy', 'available', '180')])


class FlattenTest(HistoryTest):

    def test_a_metric_reported_as_one_value_is_kept_under_value(self):
        self.assertEqual(self.history.flatten({'uptime':'3 days'}),
                         [('uptime', 'value', '3 days')])

    def test_fields_come_out_in_a_settled_order(self):
        #two identical notifications must store identical rows, or a diff of
        #the history shows changes that never happened
        payload = {'b':{'z':1, 'a':2}, 'a':{'m':3}}
        self.assertEqual(self.history.flatten(payload),
                         [('a', 'm', '3'), ('b', 'a', '2'), ('b', 'z', '1')])

    def test_a_reading_nested_deeper_is_left_out(self):
        #no probe sends one, and inventing a name for it would store rows
        #nothing knows how to read back
        payload = {'disk':{'root':{'used':1}, 'total':10}}
        self.assertEqual(self.history.flatten(payload), [('disk', 'total', '10')])

    def test_a_list_of_values_is_left_out(self):
        payload = {'ports':{'open':[22, 80], 'count':2}}
        self.assertEqual(self.history.flatten(payload), [('ports', 'count', '2')])

    def test_the_rest_of_a_notification_survives_one_unreadable_field(self):
        payload = {'memory':{'used':[1, 2], 'total':1024}}
        self.assertEqual(self.history.flatten(payload), [('memory', 'total', '1024')])


class ValueTest(HistoryTest):

    def test_a_load_average_comes_back_as_it_went_in(self):
        #str() rounds a float; the point of keeping a load average is the
        #difference between 1.5 and 1.53
        value = self.history.as_text(0.1 + 0.2)
        self.assertEqual(float(value), 0.1 + 0.2)

    def test_a_missing_value_stays_missing(self):
        self.assertIsNone(self.history.as_text(None))

    def test_a_value_too_wide_for_the_column_is_cut_rather_than_dropped(self):
        #a truncated reading still says the vm was alive and reporting
        stored = self.history.as_text('x'*300)
        self.assertEqual(len(stored), 255)

    def test_text_is_kept_as_it_is(self):
        self.assertEqual(self.history.as_text('2 days, 4:11'), '2 days, 4:11')


class LatestTest(HistoryTest):

    def test_it_answers_with_the_last_value_of_every_field(self):
        self.history.record('i-1', {'memory':{'used':1}}, when=minutes_ago(10))
        self.history.record('i-1', {'memory':{'used':2}}, when=NOW)
        self.assertEqual(self.history.latest('i-1'), {'memory':{'used':'2'}})

    def test_it_groups_the_fields_under_their_metric(self):
        self.history.record('i-1', {'memory':{'used':1, 'total':2},
                                    'http':{'connections':3}}, when=NOW)
        self.assertEqual(self.history.latest('i-1'),
                         {'memory':{'used':'1', 'total':'2'},
                          'http':{'connections':'3'}})

    def test_a_metric_the_agent_stopped_sending_keeps_its_last_value(self):
        #a probe that starts failing must not make the vm look like it never
        #had the metric; last_seen is what tells fresh from stale
        self.history.record('i-1', {'malware':{'detected':0}}, when=minutes_ago(60))
        self.history.record('i-1', {'memory':{'used':1}}, when=NOW)
        self.assertEqual(self.history.latest('i-1')['malware'], {'detected':'0'})

    def test_a_vm_that_never_reported_has_nothing(self):
        self.assertEqual(self.history.latest('i-nobody'), {})

    def test_one_vm_does_not_see_another(self):
        self.history.record('i-1', {'memory':{'used':1}}, when=NOW)
        self.history.record('i-2', {'memory':{'used':2}}, when=NOW)
        self.assertEqual(self.history.latest('i-2'), {'memory':{'used':'2'}})


class SeriesTest(HistoryTest):

    def setUp(self):
        HistoryTest.setUp(self)
        for age, used in ((30, 1), (20, 2), (10, 3)):
            self.history.record('i-1', {'memory':{'used':used}}, when=minutes_ago(age))

    def test_a_series_runs_oldest_first(self):
        #the order a graph is drawn in
        self.assertEqual([value for when, value in self.history.series('i-1', 'memory', 'used')],
                         ['1', '2', '3'])

    def test_a_series_carries_the_time_of_each_reading(self):
        self.assertEqual(self.history.series('i-1', 'memory', 'used')[0][0], minutes_ago(30))

    def test_a_limit_counts_back_from_the_newest_reading(self):
        self.assertEqual([value for when, value in
                          self.history.series('i-1', 'memory', 'used', limit=2)],
                         ['2', '3'])

    def test_a_window_leaves_out_what_came_before_it(self):
        self.assertEqual([value for when, value in
                          self.history.series('i-1', 'memory', 'used', since=minutes_ago(21))],
                         ['2', '3'])

    def test_a_field_that_was_never_reported_is_an_empty_series(self):
        self.assertEqual(self.history.series('i-1', 'memory', 'swap'), [])

    def test_numbers_come_back_as_numbers(self):
        self.assertEqual([value for when, value in
                          self.history.numeric_series('i-1', 'memory', 'used')],
                         [1.0, 2.0, 3.0])

    def test_a_reading_that_is_not_a_number_is_left_out_of_a_numeric_series(self):
        #one unparseable row must not cost the whole graph
        self.history.record('i-1', {'memory':{'used':'unknown'}}, when=NOW)
        self.assertEqual([value for when, value in
                          self.history.numeric_series('i-1', 'memory', 'used')],
                         [1.0, 2.0, 3.0])


class SummaryTest(HistoryTest):

    def setUp(self):
        HistoryTest.setUp(self)
        for age, load in ((30, 1.0), (20, 4.0), (10, 1.0)):
            self.history.record('i-1', {'loadavg':{'1':load}}, when=minutes_ago(age))

    def test_the_average_of_a_window(self):
        self.assertEqual(self.history.average('i-1', 'loadavg', '1'), 2.0)

    def test_the_peak_of_a_window(self):
        #a spike between two calm readings is the thing worth keeping history
        #for; the last value alone never shows it
        self.assertEqual(self.history.peak('i-1', 'loadavg', '1'), 4.0)

    def test_an_average_over_nothing_is_not_a_number(self):
        self.assertIsNone(self.history.average('i-1', 'loadavg', '15'))

    def test_a_peak_over_nothing_is_not_a_number(self):
        self.assertIsNone(self.history.peak('i-1', 'loadavg', '15'))

    def test_the_window_narrows_the_average(self):
        self.assertEqual(self.history.average('i-1', 'loadavg', '1', since=minutes_ago(21)), 2.5)


class SilenceTest(HistoryTest):

    def test_when_a_vm_last_reported(self):
        self.history.record('i-1', {'memory':{'used':1}}, when=minutes_ago(30))
        self.history.record('i-1', {'memory':{'used':2}}, when=minutes_ago(5))
        self.assertEqual(self.history.last_seen('i-1'), minutes_ago(5))

    def test_a_vm_that_never_reported_was_never_seen(self):
        self.assertIsNone(self.history.last_seen('i-nobody'))

    def test_a_vm_reporting_on_schedule_is_not_silent(self):
        self.history.record('i-1', {'memory':{'used':1}}, when=minutes_ago(4))
        self.assertFalse(self.history.is_silent('i-1', now=NOW))

    def test_three_missed_rounds_count_as_silence(self):
        #the agent reports every five minutes
        self.history.record('i-1', {'memory':{'used':1}}, when=minutes_ago(20))
        self.assertTrue(self.history.is_silent('i-1', now=NOW))

    def test_a_vm_that_never_reported_counts_as_silent(self):
        self.assertTrue(self.history.is_silent('i-nobody', now=NOW))

    def test_the_silence_threshold_can_be_asked_for(self):
        self.history.record('i-1', {'memory':{'used':1}}, when=minutes_ago(20))
        self.assertFalse(self.history.is_silent('i-1', minutes=60, now=NOW))


class RetentionTest(HistoryTest):

    def setUp(self):
        HistoryTest.setUp(self)
        self.history.record('i-1', {'memory':{'used':1}}, when=NOW - datetime.timedelta(days=40))
        self.history.record('i-1', {'memory':{'used':2}}, when=NOW - datetime.timedelta(days=10))

    def test_purging_discards_readings_past_the_window(self):
        self.history.purge(days=30, now=NOW)
        self.assertEqual(self.stored(), [('memory', 'used', '2')])

    def test_purging_reports_how_many_it_discarded(self):
        self.assertEqual(self.history.purge(days=30, now=NOW), 1)

    def test_the_configured_window_is_used_when_none_is_asked_for(self):
        real = cluster_config.HISTORY_RETENTION_DAYS
        cluster_config.HISTORY_RETENTION_DAYS = 5
        try:
            self.history.purge(now=NOW)
        finally:
            cluster_config.HISTORY_RETENTION_DAYS = real
        self.assertEqual(self.stored(), [])

    def test_a_window_of_no_days_discards_everything(self):
        self.assertEqual(self.history.purge(days=0, now=NOW), 2)

    def test_forgetting_a_vm_drops_its_readings(self):
        self.history.record('i-2', {'memory':{'used':9}}, when=NOW)
        self.history.forget('i-1')
        self.assertEqual(self.stored(), [('memory', 'used', '9')])

    def test_forgetting_one_vm_leaves_the_others_alone(self):
        self.history.record('i-2', {'memory':{'used':9}}, when=NOW)
        self.history.forget('i-1')
        self.assertEqual(self.history.latest('i-2'), {'memory':{'used':'9'}})


class InstancesTest(HistoryTest):

    def test_it_lists_the_vms_it_has_readings_for(self):
        self.history.record('i-1', {'memory':{'used':1}}, when=NOW)
        self.history.record('i-2', {'memory':{'used':2}}, when=NOW)
        self.assertEqual(sorted(self.history.instance_ids()), ['i-1', 'i-2'])

    def test_a_vm_is_listed_once_however_often_it_reported(self):
        self.history.record('i-1', {'memory':{'used':1}}, when=minutes_ago(10))
        self.history.record('i-1', {'memory':{'used':2}}, when=NOW)
        self.assertEqual(self.history.instance_ids(), ['i-1'])

    def test_nothing_recorded_is_no_vms(self):
        self.assertEqual(self.history.instance_ids(), [])


if __name__ == '__main__':
    unittest.main()
