'''
Tests for MemoryMonitor, which derives the memory figures from /proc/meminfo.
'''
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, 'booting_vms'))

from MemoryMonitor import MemoryMonitor

MEMINFO = '''MemTotal:        1000 kB
MemFree:          400 kB
MemAvailable:     600 kB
Buffers:           30 kB
Cached:            70 kB
SwapCached:       500 kB
'''


class MemoryMonitorTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def monitor(self, contents=MEMINFO):
        path = os.path.join(self.tmp, 'meminfo')
        f = open(path, 'w')
        f.write(contents)
        f.close()
        return MemoryMonitor(meminfo_path=path)

    def test_reads_the_reported_totals(self):
        memory = self.monitor().get_meminfo()
        self.assertEqual(memory['total'], 1000)
        self.assertEqual(memory['free'], 400)

    def test_used_is_total_minus_free(self):
        self.assertEqual(self.monitor().get_meminfo()['used'], 600)

    def test_cache_sums_buffers_and_cached(self):
        #and leaves SwapCached out of it: the pattern is anchored, so a line
        #whose name merely ends in "Cached" is not part of the page cache
        self.assertEqual(self.monitor().get_meminfo()['cache'], 100)

    def test_repeated_readings_do_not_accumulate(self):
        #the counters used to be kept on the instance and added to, so every
        #call reported a larger cache than the last
        monitor = self.monitor()
        first = dict(monitor.get_meminfo())
        self.assertEqual(monitor.get_meminfo(), first)

    def test_reading_is_kept_on_the_instance(self):
        monitor = self.monitor()
        self.assertEqual(monitor.get_meminfo(), monitor.memory)

    def test_missing_fields_stay_at_zero(self):
        memory = self.monitor('MemTotal:        1000 kB\n').get_meminfo()
        self.assertEqual(memory['free'], 0)
        self.assertEqual(memory['cache'], 0)
        self.assertEqual(memory['used'], 1000)

    def test_default_path_is_proc_meminfo(self):
        self.assertEqual(MemoryMonitor().meminfo_path, '/proc/meminfo')


if __name__ == '__main__':
    unittest.main()
