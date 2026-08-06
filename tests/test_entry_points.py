'''
Tests for the loops the three long-running processes sit in.

Every other test covers a piece; these cover the assembly. They are the only
thing that would notice a method being renamed out from under its caller, or
the steps of a poll being reordered into something that does not work -- a
controller that marks VMs terminated before storing what the cloud reported,
say, would terminate every VM on every pass.

Each loop runs forever by design, so the tests let one pass happen and then
raise out of the sleep.
'''
import os
import sys
import types
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
for path in (ROOT,
             os.path.join(ROOT, 'booting_vms'),
             os.path.join(ROOT, 'running_vms', 'cluster')):
    sys.path.insert(0, path)

import running_vms.cluster.cluster_config as cluster_config
cluster_config.PATH_TO_LOG_FILE = '/tmp/pcmons-entry-points-test.log'

import Monitor as agent_module
import VM_Monitoring_Cluster_Plugin as cluster_module


class StopTheLoop(Exception):
    '''Raised from the fake sleep to end an otherwise endless loop.'''


class Sleeper:
    '''Records how long each pass slept, then stops the loop.'''

    def __init__(self, passes=1):
        self.slept = []
        self.passes = passes

    def sleep(self, seconds):
        self.slept.append(seconds)
        if len(self.slept) >= self.passes:
            raise StopTheLoop()


class AgentLoopTest(unittest.TestCase):
    '''booting_vms/Monitor.py -- collect, send, wait.'''

    def setUp(self):
        self.real_time = agent_module.time
        self.monitor = agent_module.Monitor()
        self.steps = []
        self.monitor.get_monitoring_data = lambda: self.steps.append('collect') or {'memory':{}}
        self.monitor.send_monitoring_data = lambda data: self.steps.append('send %r'%(data,))

    def tearDown(self):
        agent_module.time = self.real_time

    def run_passes(self, passes=1):
        sleeper = Sleeper(passes)
        agent_module.time = sleeper
        try:
            self.monitor.run()
        except StopTheLoop:
            pass
        return sleeper

    def test_collects_then_sends(self):
        self.run_passes()
        self.assertEqual(self.steps, ['collect', "send {'memory': {}}"])

    def test_sends_what_it_collected(self):
        #not a fresh reading, and not the previous pass's
        self.run_passes()
        self.assertIn('memory', self.steps[1])

    def test_waits_five_minutes_between_readings(self):
        #the agent runs inside every monitored vm; polling harder costs the
        #cloud, not us
        self.assertEqual(self.run_passes().slept, [300])

    def test_keeps_going(self):
        self.run_passes(passes=3)
        self.assertEqual(self.steps.count('collect'), 3)


class ControllerLoopTest(unittest.TestCase):
    '''running_vms/cluster -- poll the cloud, then reconcile.'''

    def setUp(self):
        self.real_time = cluster_module.time
        self.plugin = types.InstanceType(cluster_module.VM_Monitoring_Cluster_Plugin)
        self.steps = []
        self.plugin.get_running_vms = lambda: self.steps.append('poll') or ['vm']
        self.plugin.store_vms_info = lambda vms: self.steps.append('store %s'%vms)
        self.plugin.mark_terminated_vms = lambda vms: self.steps.append('terminate %s'%vms)
        self.plugin.update_vms_info = lambda: self.steps.append('fill in')

    def tearDown(self):
        cluster_module.time = self.real_time

    def run_passes(self, passes=1):
        sleeper = Sleeper(passes)
        cluster_module.time = sleeper
        try:
            self.plugin.run()
        except StopTheLoop:
            pass
        return sleeper

    def test_stores_what_the_cloud_reported_before_reconciling(self):
        #the other order marks every vm terminated on the first pass, since
        #the inventory has not caught up with the cloud yet
        self.run_passes()
        self.assertEqual(self.steps.index("store ['vm']"), self.steps.index("terminate ['vm']") - 1)

    def test_a_pass_is_poll_store_terminate_fill_in(self):
        self.run_passes()
        self.assertEqual(self.steps, ['poll', "store ['vm']", "terminate ['vm']", 'fill in'])

    def test_the_same_reading_is_used_throughout_a_pass(self):
        #storing one list and reconciling against another would terminate vms
        #that are running
        self.run_passes()
        self.assertEqual(self.steps.count('poll'), 1)

    def test_polls_every_minute(self):
        self.assertEqual(self.run_passes().slept, [60])

    def test_keeps_going(self):
        self.run_passes(passes=3)
        self.assertEqual(self.steps.count('poll'), 3)


if __name__ == '__main__':
    unittest.main()
