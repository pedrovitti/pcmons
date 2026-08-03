'''
Tests for VM_Monitoring_Cluster_Plugin, the controller that polls the cloud and
keeps the stored VM inventory in step with it.

Its constructor opens a database connection and an EC2 endpoint, neither of
which exists here, so the tests build an instance without running __init__ and
give it a fake database and a fake connection. That is what the class needs to
do its work: everything below operates on self.db and self.connection.
'''
import logging
import os
import shutil
import socket
import sys
import tempfile
import types
import unittest
import xmlrpclib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, 'running_vms', 'cluster'))

import VM_Monitoring_Cluster_Plugin as module
from VM_Monitoring_Cluster_Plugin import VM_Monitoring_Cluster_Plugin


class FakeInstance:

    def __init__(self, id, state='running'):
        self.id = id
        self.state = state
        self.placement = 'cluster1'
        self.launch_time = '2026-08-06T00:00:00'
        self.dns_name = 'vm.example.org'
        self.private_dns_name = '10.0.0.10'
        self.public_dns_name = '150.162.63.90'
        self.instance_type = 'm1.small'
        self.kernel = 'eki-1'
        self.ramdisk = 'eri-1'


class FakeReservation:

    def __init__(self, id, instances, owner_id='oneadmin'):
        self.id = id
        self.instances = instances
        self.owner_id = owner_id


class FakeConnection:

    def __init__(self, reservations):
        self.reservations = reservations

    def get_all_instances(self):
        return self.reservations


class FakeDb:
    '''Records what the controller asked of the database.'''

    def __init__(self, stored=(), running=(), rows=()):
        self.stored = list(stored)
        self.running = list(running)
        self.rows = list(rows)
        self.inserted = []
        self.updated = []
        self.terminated = []
        self.placed = []

    def get_vm_info(self, instance_id):
        if instance_id in self.stored:
            return {'instance_id':instance_id}
        return None

    def insert_new_vm(self, vm):
        self.inserted.append(vm['instance_id'])

    def update_stored_vm_info(self, vm):
        self.updated.append(vm['instance_id'])

    def get_info_for_monitoring_running_Vms(self):
        return [{'instance_id':id} for id in self.running]

    def set_status_terminated(self, instance_id):
        self.terminated.append(instance_id)

    def update_vm_Ip_hostname(self, ip, hostname, instance_id):
        self.placed.append((ip, hostname, instance_id))

    def get_running_vms(self):
        return self.rows


class FakeVM:
    '''Stands in for vms.VM, recording what was saved rather than writing it.'''

    saved = []

    def __init__(self):
        self.attributes = dict.fromkeys(
            ['node_ip', 'node_hostname', 'instance_id', 'state', 'user'])

    def save(self):
        FakeVM.saved.append(dict(self.attributes))


class FakeNode:
    """Stands in for a node's XML-RPC plugin."""

    def __init__(self, url, vms):
        self.url = url
        self.vms = vms
        FakeNode.last = self

    def get_vms(self, infra):
        self.asked = infra
        return self.vms


class FailingNode(FakeNode):

    def get_vms(self, infra):
        raise socket.error('connection refused')


class FakeXMLRPC:
    """The xmlrpclib names the plugin uses, with a proxy we control."""

    Fault = xmlrpclib.Fault
    ProtocolError = xmlrpclib.ProtocolError
    ResponseError = xmlrpclib.ResponseError

    def __init__(self, proxy):
        self.ServerProxy = proxy


def controller(db=None, connection=None):
    #old-style class: build the instance without calling __init__, which would
    #want a database and an EC2 endpoint
    plugin = types.InstanceType(VM_Monitoring_Cluster_Plugin)
    plugin.db = db
    plugin.connection = connection
    return plugin


class GetRunningVmsTest(unittest.TestCase):

    def test_flattens_reservations_into_one_entry_per_instance(self):
        #a reservation can hold several instances; each is its own VM row
        connection = FakeConnection([FakeReservation('r-01', [FakeInstance('i-1'), FakeInstance('i-2')])])
        vms = controller(connection=connection).get_running_vms()
        self.assertEqual([vm['instance_id'] for vm in vms], ['i-1', 'i-2'])

    def test_carries_the_reservation_and_owner_onto_each_vm(self):
        connection = FakeConnection([FakeReservation('r-01', [FakeInstance('i-1')], owner_id='shirlei')])
        vm = controller(connection=connection).get_running_vms()[0]
        self.assertEqual(vm['reservation'], 'r-01')
        self.assertEqual(vm['user'], 'shirlei')

    def test_reports_the_fields_the_inventory_stores(self):
        connection = FakeConnection([FakeReservation('r-01', [FakeInstance('i-1')])])
        vm = controller(connection=connection).get_running_vms()[0]
        self.assertEqual(sorted(vm.keys()),
                         ['availability_zone', 'dns_name', 'instance_id', 'instance_type',
                          'kernel', 'launch_time', 'private_dns_name', 'public_dns_name',
                          'ramdisk', 'reservation', 'state', 'user'])

    def test_an_idle_cloud_reports_no_vms(self):
        self.assertEqual(controller(connection=FakeConnection([])).get_running_vms(), [])


class StoreVmsInfoTest(unittest.TestCase):

    def test_a_new_vm_is_inserted(self):
        db = FakeDb(stored=[])
        controller(db=db).store_vms_info([{'instance_id':'i-1'}])
        self.assertEqual(db.inserted, ['i-1'])
        self.assertEqual(db.updated, [])

    def test_a_known_vm_is_updated(self):
        db = FakeDb(stored=['i-1'])
        controller(db=db).store_vms_info([{'instance_id':'i-1'}])
        self.assertEqual(db.updated, ['i-1'])
        self.assertEqual(db.inserted, [])


class MarkTerminatedVmsTest(unittest.TestCase):

    def setUp(self):
        logging.disable(logging.DEBUG)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def mark(self, running_in_db, vms_from_cloud):
        db = FakeDb(running=running_in_db)
        controller(db=db).mark_terminated_vms(vms_from_cloud)
        return sorted(db.terminated)

    def test_a_vm_the_cloud_no_longer_reports_is_terminated(self):
        self.assertEqual(self.mark(['i-1', 'i-2'], [{'instance_id':'i-1', 'state':'running'}]),
                         ['i-2'])

    def test_a_vm_the_cloud_reports_as_terminated_is_terminated(self):
        self.assertEqual(self.mark(['i-1'], [{'instance_id':'i-1', 'state':'terminated'}]),
                         ['i-1'])

    def test_a_running_vm_is_left_alone(self):
        self.assertEqual(self.mark(['i-1'], [{'instance_id':'i-1', 'state':'running'}]), [])

    def test_each_vm_is_terminated_once(self):
        #a vm can be both absent from one list and terminated in the other
        self.assertEqual(self.mark(['i-1'], [{'instance_id':'i-1', 'state':'terminated'},
                                             {'instance_id':'i-2', 'state':'terminated'}]),
                         ['i-1', 'i-2'])

    def test_an_empty_cloud_terminates_everything_stored(self):
        self.assertEqual(self.mark(['i-1', 'i-2'], []), ['i-1', 'i-2'])

    def test_a_vm_the_db_never_saw_is_not_terminated(self):
        self.assertEqual(self.mark([], [{'instance_id':'i-1', 'state':'running'}]), [])


class UpdateVmsInfoTest(unittest.TestCase):
    '''
    Fills in what the cloud did not report (the node a VM is running on) by
    asking each node what it has.
    '''

    def setUp(self):
        self.real_vm = module.vms.VM
        self.real_infra = module.cluster_config.INFRA
        #eucalyptus takes the plain path; opennebula adds a second pass that
        #talks to the nodes over XML-RPC
        module.cluster_config.INFRA = 'eucalyptus'
        module.vms.VM = FakeVM
        FakeVM.saved = []
        logging.disable(logging.DEBUG)

    def tearDown(self):
        module.vms.VM = self.real_vm
        module.cluster_config.INFRA = self.real_infra
        logging.disable(logging.NOTSET)

    def update(self, rows, on_nodes=None):
        plugin = controller(db=FakeDb(rows=rows))
        plugin.nodes = sorted(on_nodes or {})
        plugin.get_vm_list_running_on_node = lambda node: (on_nodes or {}).get(node, [])
        plugin.update_vms_info()
        return FakeVM.saved

    def test_a_complete_row_needs_no_update(self):
        saved = self.update([{'instance_id':'i-1', 'node_ip':'10.0.0.2', 'node_hostname':'node01'}])
        self.assertEqual(saved, [])

    def test_a_row_missing_its_node_is_filled_in_from_the_node(self):
        saved = self.update([{'instance_id':'i-1', 'node_ip':'', 'node_hostname':''}],
                            on_nodes={'10.0.0.2':[{'instance_id':'i-1', 'node_hostname':'node01'}]})
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]['node_ip'], '10.0.0.2')
        self.assertEqual(saved[0]['node_hostname'], 'node01')

    def test_each_row_is_saved_once(self):
        #the record was built once outside the loop and appended per empty
        #column, so one incomplete row could be saved several times over
        saved = self.update([{'instance_id':'i-1', 'node_ip':'', 'node_hostname':''}],
                            on_nodes={'10.0.0.2':[{'instance_id':'i-1', 'node_hostname':'node01'}]})
        self.assertEqual(len(saved), 1)

    def test_each_row_is_saved_as_itself(self):
        #and every save shared one record, so each row was written with the
        #values of whichever row happened to be processed last
        saved = self.update([{'instance_id':'i-1', 'node_ip':'', 'node_hostname':''},
                             {'instance_id':'i-2', 'node_ip':'', 'node_hostname':''}],
                            on_nodes={'10.0.0.2':[{'instance_id':'i-1', 'node_hostname':'node01'},
                                                  {'instance_id':'i-2', 'node_hostname':'node02'}]})
        self.assertEqual(sorted(row['instance_id'] for row in saved), ['i-1', 'i-2'])
        by_id = dict((row['instance_id'], row['node_hostname']) for row in saved)
        self.assertEqual(by_id, {'i-1':'node01', 'i-2':'node02'})

    def test_a_vm_no_node_claims_is_saved_as_it_stands(self):
        saved = self.update([{'instance_id':'i-1', 'node_ip':'', 'node_hostname':''}],
                            on_nodes={'10.0.0.2':[{'instance_id':'i-9', 'node_hostname':'node01'}]})
        self.assertEqual(len(saved), 1)
        #still blank, and specifically not another vm's node
        self.assertEqual(saved[0]['node_hostname'], '')

    def test_columns_the_record_does_not_have_are_ignored(self):
        #get_running_vms selects *, so a row carries columns VM knows nothing
        #about; they must not end up in the update
        saved = self.update([{'instance_id':'i-1', 'node_ip':'', 'last_check':'2026-08-06'}],
                            on_nodes={'10.0.0.2':[{'instance_id':'i-1', 'node_hostname':'node01'}]})
        self.assertNotIn('last_check', saved[0])

    def test_nothing_running_saves_nothing(self):
        self.assertEqual(self.update([]), [])


class GrepNodesTest(unittest.TestCase):
    """
    Node discovery, which runs in the constructor: whatever it returns is
    stored and iterated by everything else.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.plugin = controller()
        logging.disable(logging.ERROR)

    def tearDown(self):
        shutil.rmtree(self.tmp)
        logging.disable(logging.NOTSET)

    def config(self, contents):
        path = os.path.join(self.tmp, 'eucalyptus.conf')
        f = open(path, 'w')
        f.write(contents)
        f.close()
        return path

    def test_reads_the_nodes_from_the_eucalyptus_config(self):
        path = self.config('# comment\nNODES="10.0.0.2 10.0.0.3"\n')
        self.assertEqual(self.plugin.grepNodes(infra='eucalyptus', file=path),
                         ['10.0.0.2', '10.0.0.3'])

    def test_a_config_without_a_nodes_line_gives_an_empty_list(self):
        #it used to return None implicitly, which is stored as self.nodes and
        #raises TypeError on the next "for node in self.nodes"
        path = self.config('# a cloud with no nodes registered yet\n')
        self.assertEqual(self.plugin.grepNodes(infra='eucalyptus', file=path), [])

    def test_a_nodes_line_with_no_nodes_gives_an_empty_list(self):
        path = self.config('NODES=""\n')
        self.assertEqual(self.plugin.grepNodes(infra='eucalyptus', file=path), [])

    def test_an_unsupported_platform_gives_an_empty_list(self):
        self.assertEqual(self.plugin.grepNodes(infra='vsphere', file=self.config('')), [])

    def test_opennebula_resolves_the_names_onehost_reports(self):
        self.plugin.opennebula_nodes = lambda: ['10.0.0.4']
        self.assertEqual(self.plugin.grepNodes(infra='opennebula'), ['10.0.0.4'])


class GetVmListRunningOnNodeTest(unittest.TestCase):
    """The XML-RPC call out to a node."""

    def setUp(self):
        self.real_xmlrpclib = module.xmlrpclib
        self.plugin = controller()
        logging.disable(logging.ERROR)

    def tearDown(self):
        module.xmlrpclib = self.real_xmlrpclib
        logging.disable(logging.NOTSET)

    def test_returns_what_the_node_reports(self):
        vms = [{'instance_id':'i-1', 'node_hostname':'node01'}]
        module.xmlrpclib = FakeXMLRPC(lambda url: FakeNode(url, vms))
        self.assertEqual(self.plugin.get_vm_list_running_on_node('10.0.0.2'), vms)

    def test_asks_the_node_on_the_configured_port(self):
        module.xmlrpclib = FakeXMLRPC(lambda url: FakeNode(url, []))
        self.plugin.get_vm_list_running_on_node('10.0.0.2')
        self.assertEqual(FakeNode.last.url,
                         'http://10.0.0.2:' + module.cluster_config.PORT_PLUGINS_ON_NODES)

    def test_a_node_that_is_down_reports_nothing(self):
        #one unreachable node must not stop the poll: the others still answer
        module.xmlrpclib = FakeXMLRPC(lambda url: FailingNode(url, []))
        self.assertEqual(self.plugin.get_vm_list_running_on_node('10.0.0.2'), [])


class UpdateOpennebulaVmsInfoTest(unittest.TestCase):
    """The opennebula pass: record where each node says its vms are."""

    def setUp(self):
        self.plugin = controller(db=FakeDb())
        self.plugin.nodes = ['10.0.0.2', '10.0.0.3']
        logging.disable(logging.ERROR)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_records_the_node_each_vm_runs_on(self):
        on_nodes = {'10.0.0.2':[{'instance_id':'i-1', 'node_hostname':'node01'}],
                    '10.0.0.3':[{'instance_id':'i-2', 'node_hostname':'node02'}]}
        self.plugin.get_vm_list_running_on_node = lambda node: on_nodes[node]
        self.plugin.update_opennebula_vms_info()
        self.assertEqual(sorted(self.plugin.db.placed),
                         [('10.0.0.2', 'node01', 'i-1'), ('10.0.0.3', 'node02', 'i-2')])

    def test_a_node_with_no_vms_records_nothing(self):
        self.plugin.get_vm_list_running_on_node = lambda node: []
        self.plugin.update_opennebula_vms_info()
        self.assertEqual(self.plugin.db.placed, [])


if __name__ == '__main__':
    unittest.main()
