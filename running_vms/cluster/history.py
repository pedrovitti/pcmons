'''
Keeps the readings the vms report, and answers questions about them.

Every notification was handed to the interface and then dropped, so the
only record of a vm was whatever the interface chose to draw. This keeps
the readings themselves: what a vm reported, when, and what it reported
before that.

A notification is stored one row per field, so the used memory of a vm
over a week is a query rather than a pile of payloads to parse.
'''
import datetime, logging, sys
sys.path.append('/opt/pcmons/')
from running_vms.cluster.Mysql_Db_Connector import Db_Connector
import running_vms.cluster.cluster_config as cluster_config

#a value wider than the column is stored cut rather than dropped: a truncated
#reading still says the vm was alive and reporting
VALUE_WIDTH = 255


class History:

    def __init__(self, db=None):
        self.db = db or Db_Connector()

    def record(self, instance_id, data, when=None):
        '''
        keep a notification. Returns the number of readings stored, which is
        0 for a payload with nothing readable in it rather than an error:
        an agent whose probes all failed still reported in
        '''
        rows = []
        recorded_at = when or datetime.datetime.now()
        for metric, field, value in self.flatten(data):
            rows.append((instance_id, metric, field, value, recorded_at))
        if not rows:
            return 0
        self.db.insert_readings(rows)
        return len(rows)

    def flatten(self, data):
        '''
        a notification as (metric, field, value) triples. A metric reported as
        a plain value rather than a group of them is kept under the field
        name 'value', and anything deeper than one level is left out: no
        probe sends one, and guessing at a name for it would store rows that
        nothing knows how to read back
        '''
        triples = []
        if not hasattr(data, 'items'):
            logging.error('notification is not a set of metrics: %r'%(data,))
            return triples
        for metric in sorted(data.keys()):
            reading = data[metric]
            if hasattr(reading, 'items'):
                for field in sorted(reading.keys()):
                    value = reading[field]
                    if self.is_scalar(value):
                        triples.append((str(metric), str(field), self.as_text(value)))
                    else:
                        logging.error('%s.%s is not a single value: %r'%(metric, field, value))
            elif self.is_scalar(reading):
                triples.append((str(metric), 'value', self.as_text(reading)))
            else:
                logging.error('%s is not a reading: %r'%(metric, reading))
        return triples

    def is_scalar(self, value):
        return not (hasattr(value, 'items') or isinstance(value, (list, tuple, set)))

    def as_text(self, value):
        '''
        a value as it will be stored. Floats go through repr so that a load
        average comes back as it went in; str() would round it
        '''
        if value is None:
            return None
        if isinstance(value, float):
            text = repr(value)
        else:
            text = str(value)
        return text[:VALUE_WIDTH]

    def latest(self, instance_id):
        '''
        the last value of every field this vm reported, as
        {metric: {field: value}}. A metric the agent stopped sending keeps the
        value it last sent: use last_seen to tell fresh readings from stale
        '''
        readings = {}
        for row in self.db.get_latest_readings(instance_id):
            readings.setdefault(row['metric'], {})[row['field']] = row['value']
        return readings

    def series(self, instance_id, metric, field, limit=100, since=None):
        '''
        (time, value) pairs oldest first, which is the order a graph is drawn
        in. limit counts back from the newest reading
        '''
        rows = self.db.get_readings(instance_id, metric=metric, field=field,
                                    since=since, limit=limit)
        pairs = [(row['recorded_at'], row['value']) for row in rows]
        pairs.reverse()
        return pairs

    def numeric_series(self, instance_id, metric, field, limit=100, since=None):
        '''
        the same, with the values as numbers. A reading that is not one is
        left out rather than raising: one bad row must not cost the graph
        '''
        numbers = []
        for recorded_at, value in self.series(instance_id, metric, field, limit, since):
            try:
                numbers.append((recorded_at, float(value)))
            except (TypeError, ValueError):
                logging.error('%s %s.%s is not a number: %r'%(instance_id, metric, field, value))
        return numbers

    def average(self, instance_id, metric, field, limit=100, since=None):
        '''
        mean of the readings in the window, or None if there are none
        '''
        numbers = [value for when, value in
                   self.numeric_series(instance_id, metric, field, limit, since)]
        if not numbers:
            return None
        return sum(numbers)/len(numbers)

    def peak(self, instance_id, metric, field, limit=100, since=None):
        numbers = [value for when, value in
                   self.numeric_series(instance_id, metric, field, limit, since)]
        if not numbers:
            return None
        return max(numbers)

    def last_seen(self, instance_id):
        '''
        when this vm last reported anything, or None if it never has. This is
        how a silent agent is told from a healthy one, since a vm that stopped
        sending keeps its last reading on the dashboard either way
        '''
        rows = self.db.get_readings(instance_id, limit=1)
        if not rows:
            return None
        return rows[0]['recorded_at']

    def is_silent(self, instance_id, minutes=15, now=None):
        '''
        whether nothing has arrived from this vm for a while. The agent
        reports every five minutes, so a quarter of an hour is three missed
        rounds and not a slow one
        '''
        seen = self.last_seen(instance_id)
        if seen is None:
            return True
        now = now or datetime.datetime.now()
        return (now - seen) > datetime.timedelta(minutes=minutes)

    def instance_ids(self):
        return [row['instance_id'] for row in self.db.get_reading_instance_ids()]

    def purge(self, days=None, now=None):
        '''
        discard readings past the retention window. Nothing calls this on a
        timer: a busy cluster writes a few hundred thousand rows a month, and
        when that is worth deleting is the operator's decision
        '''
        if days is None:
            days = cluster_config.HISTORY_RETENTION_DAYS
        now = now or datetime.datetime.now()
        cutoff = now - datetime.timedelta(days=days)
        return self.db.delete_readings_before(cutoff)

    def forget(self, instance_id):
        '''
        drop everything kept for a vm, for when it is gone for good
        '''
        return self.db.delete_readings_for(instance_id)
