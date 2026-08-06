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
import sys
import types
import unittest

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

    def __init__(self, stored=(), running=()):
        self.stored = list(stored)
        self.running = list(running)
        self.inserted = []
        self.updated = []
        self.terminated = []

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


if __name__ == '__main__':
    unittest.main()
