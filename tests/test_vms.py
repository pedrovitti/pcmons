'''
Tests for vms.VM, the record the cluster controller fills in and saves when it
learns something new about a running VM.
'''
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, 'running_vms', 'cluster'))

from vms import VM


class FakeDb:

    def __init__(self):
        self.saved = []

    def update_vm_info(self, attributes):
        #the controller reuses the record it is given, so keep a copy
        self.saved.append(dict(attributes))


class VMTest(unittest.TestCase):

    def test_two_vms_do_not_share_their_attributes(self):
        #`attributes` used to be defined on the class, so every VM in the
        #process wrote into one dict: filling in a second overwrote the first,
        #and both saved the same row
        first = VM(db=FakeDb())
        second = VM(db=FakeDb())
        first.attributes['instance_id'] = 'i-1'
        second.attributes['instance_id'] = 'i-2'
        self.assertEqual(first.attributes['instance_id'], 'i-1')

    def test_a_new_vm_starts_empty(self):
        #and does not inherit what an earlier one was given, which is the same
        #bug seen from the other side: the class dict outlived the instance
        VM(db=FakeDb()).attributes['node_hostname'] = 'node01'
        self.assertIsNone(VM(db=FakeDb()).attributes['node_hostname'])

    def test_carries_the_columns_the_table_stores(self):
        self.assertEqual(sorted(VM(db=FakeDb()).attributes.keys()),
                         ['availability_zone', 'dns_name', 'instance_id', 'instance_type',
                          'kernel', 'last_check', 'launch_time', 'node_hostname', 'node_ip',
                          'private_dns_name', 'public_dns_name', 'ramdisk', 'reservation',
                          'state', 'user'])

    def test_saving_writes_the_attributes(self):
        db = FakeDb()
        vm = VM(db=db)
        vm.attributes['instance_id'] = 'i-42'
        vm.attributes['node_hostname'] = 'node01'
        vm.save()
        self.assertEqual(db.saved[0]['instance_id'], 'i-42')
        self.assertEqual(db.saved[0]['node_hostname'], 'node01')

    def test_saving_two_vms_writes_two_different_rows(self):
        db = FakeDb()
        for instance_id in ('i-1', 'i-2'):
            vm = VM(db=db)
            vm.attributes['instance_id'] = instance_id
            vm.save()
        self.assertEqual([row['instance_id'] for row in db.saved], ['i-1', 'i-2'])


if __name__ == '__main__':
    unittest.main()
