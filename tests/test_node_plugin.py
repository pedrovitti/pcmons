'''
Tests for VM_Monitoring_Node_Plugin, which answers the cluster controller with
the VMs libvirt reports as running on this node.
'''
import logging
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, 'running_vms', 'node'))

import VM_Monitoring_Node_Plugin as module
from VM_Monitoring_Node_Plugin import VM_Monitoring_Node_Plugin

VIRSH = ''' Id    Name                           State
----------------------------------------------------
 1     one-42                         running
 2     one-43                         running
'''

#libvirt 3.x onwards pads differently and adds a trailing blank line
VIRSH_MODERN = ''' Id   Name       State
-----------------------------
 1    one-42     running
 2    one-43     running

'''

EMPTY = ''' Id    Name                           State
----------------------------------------------------

'''


class FakeCommands:
    '''Stands in for the commands module, answering by command.'''

    def __init__(self, virsh):
        self.outputs = {'hostname':'node01', 'virsh list':virsh}

    def getoutput(self, cmd):
        return self.outputs[cmd]


class NodePluginTest(unittest.TestCase):

    def setUp(self):
        self.real_commands = module.commands
        self.plugin = VM_Monitoring_Node_Plugin()
        logging.disable(logging.DEBUG)

    def tearDown(self):
        module.commands = self.real_commands
        logging.disable(logging.NOTSET)

    def listing(self, virsh, rename=None):
        module.commands = FakeCommands(virsh)
        return self.plugin.list_running_vms(rename)

    def test_reports_every_running_domain(self):
        #the parser used to drop the first domain, so every node under
        #reported its VMs by one for as long as this code has existed
        vms = self.listing(VIRSH)
        self.assertEqual([vm['instance_id'] for vm in vms], ['one-42', 'one-43'])

    def test_reads_a_narrower_virsh_layout(self):
        #column positions vary between libvirt versions; the name is the
        #second field, wherever it happens to start
        vms = self.listing(VIRSH_MODERN)
        self.assertEqual([vm['instance_id'] for vm in vms], ['one-42', 'one-43'])

    def test_a_node_with_no_vms_reports_none(self):
        self.assertEqual(self.listing(EMPTY), [])

    def test_every_vm_carries_the_node_hostname(self):
        for vm in self.listing(VIRSH):
            self.assertEqual(vm['node_hostname'], 'node01')

    def test_opennebula_domains_are_renamed_to_instance_ids(self):
        #opennebula names its domains one-xxx while the cloud reports i-xxx
        module.commands = FakeCommands(VIRSH)
        vms = self.plugin.opennebula()
        self.assertEqual([vm['instance_id'] for vm in vms], ['i-42', 'i-43'])

    def test_eucalyptus_domains_are_reported_as_they_are(self):
        module.commands = FakeCommands(VIRSH)
        vms = self.plugin.eucalyptus()
        self.assertEqual([vm['instance_id'] for vm in vms], ['one-42', 'one-43'])

    def test_get_vms_defaults_to_eucalyptus(self):
        module.commands = FakeCommands(VIRSH)
        self.assertEqual(self.plugin.get_vms(), self.plugin.eucalyptus())

    def test_get_vms_dispatches_on_the_platform(self):
        module.commands = FakeCommands(VIRSH)
        self.assertEqual(self.plugin.get_vms('opennebula'), self.plugin.opennebula())

    def test_an_unknown_platform_is_answered_with_the_supported_ones(self):
        answer = self.plugin.get_vms('vsphere')
        for infra in self.plugin.SUPPORTED_INFRA:
            self.assertIn(infra, answer)

    def test_monitoring_data_is_accepted(self):
        self.assertTrue(self.plugin.get_monitoring_data({'memory':{'used':1}}))


if __name__ == '__main__':
    unittest.main()
