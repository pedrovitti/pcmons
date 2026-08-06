'''
The contract between the two ends of the system.

The agent inside a VM decides what to collect and what to call it. The
controller decides what it knows how to read. Nothing connects those two
decisions -- they live in different directories, run on different machines and
are written years apart -- so a metric can be collected, transmitted and then
dropped without anything failing. That is exactly what happened to the eight
security metrics: the probes ran on every VM for years and the interface read
three of them.

These tests fail when the two sides stop agreeing.
'''
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
for path in (ROOT, os.path.join(ROOT, 'booting_vms')):
    sys.path.insert(0, path)

from Monitor import Monitor
from interface.nagios import services


class AnyProbe:
    '''A probe whose every method reports an empty reading.'''

    def __getattr__(self, name):
        return lambda: {}


def collected_metrics():
    '''The keys the agent puts in a notification, whatever its probes are.'''
    monitor = Monitor()
    for attribute in dir(monitor):
        if attribute.endswith('Monitor'):
            setattr(monitor, attribute, AnyProbe())
    return set(monitor.get_monitoring_data().keys())


def expected_metrics():
    return set(metric for metric, service in services.PASSIVE_SERVICES)


class PayloadContractTest(unittest.TestCase):

    def test_every_collected_metric_has_somewhere_to_go(self):
        #a metric with no entry in services.py is collected on every vm, sent
        #over the network, and thrown away by the interface
        orphaned = collected_metrics() - expected_metrics()
        self.assertEqual(orphaned, set(),
                         'collected but never read: %s'%', '.join(sorted(orphaned)))

    def test_every_expected_metric_is_actually_collected(self):
        #and the other way round: a service nagios is told about but never
        #receives a check for sits stale on the dashboard forever
        missing = expected_metrics() - collected_metrics()
        self.assertEqual(missing, set(),
                         'expected but never collected: %s'%', '.join(sorted(missing)))

    def test_every_expected_metric_can_be_read(self):
        #services.py names them; readings.py needs a format_ for each, or the
        #reading is logged as unreadable and dropped -- by every interface at
        #once, now that they share the judgement
        from interface import readings
        for metric in expected_metrics():
            self.assertTrue(hasattr(readings, 'format_%s'%metric),
                            'no format_%s in readings'%metric)

    def test_each_metric_maps_to_one_service(self):
        names = services.service_names()
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(len(names), len(expected_metrics()))


if __name__ == '__main__':
    unittest.main()
