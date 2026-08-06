'''
Tests for Generate_VMs_Nagios_Conf, which turns the VM inventory into a Nagios
configuration file and reloads Nagios when it changes.

This is the only component whose failure hides every other one: a malformed
file here and Nagios does not come back, so nothing is monitored at all. The
tests assert on the generated text rather than on the file writing.
'''
import logging
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
sys.path.insert(0, ROOT)

import running_vms.cluster.cluster_config as cluster_config

#interface/nagios/cron is a directory of scripts cron runs, not a package
sys.path.insert(0, os.path.join(ROOT, 'interface', 'nagios', 'cron'))

import Generate_VMs_Nagios_Conf as module
from interface.nagios import services


def vm(instance_id, user='oneadmin', node='node01', node_ip='10.0.0.2',
       address='150.162.63.90'):
    #the columns get_info_for_monitoring_running_Vms selects
    return {'instance_id':instance_id, 'user':user, 'node_hostname':node,
            'node_ip':node_ip, 'public_dns_name':address}


class FakeDb:

    def __init__(self, running=(), terminated=()):
        self.running = list(running)
        self.terminated = list(terminated)

    def get_info_for_monitoring_running_Vms(self):
        return self.running

    def get_info_for_monitoring_old_Vms(self):
        return [{'instance_id':id} for id in self.terminated]


class BuildConfTest(unittest.TestCase):

    def setUp(self):
        self.generator = module.Generate_VMs_Nagios_Conf(db=FakeDb())

    def conf(self, vms):
        return self.generator.build_conf(vms)

    def test_defines_a_host_per_vm(self):
        conf = self.conf([vm('i-1'), vm('i-2')])
        self.assertEqual(conf.count('define host {'), 2)

    def test_the_host_carries_the_address_nagios_must_reach(self):
        self.assertIn('150.162.63.90', self.conf([vm('i-1')]))

    def test_names_the_host_as_the_interface_does(self):
        #NagiosPassiveServer builds the same name when it reports a passive
        #check; if the two disagree the checks arrive for an unknown host
        self.assertIn('oneadmin_i-1_node01', self.conf([vm('i-1')]))

    def test_the_alias_shows_where_the_vm_runs(self):
        self.assertIn('oneadmin/i-1(node01-10.0.0.2)', self.conf([vm('i-1')]))

    def test_defines_the_active_ping_check(self):
        self.assertIn('check_ping!100.0,20%!500.0,60%', self.conf([vm('i-1')]))

    def test_defines_a_passive_service_for_each_reported_metric(self):
        #every metric the agent collects, not just the three the interface
        #used to read: a service Nagios does not know about is discarded
        conf = self.conf([vm('i-1')])
        for service in services.service_names():
            self.assertIn('service_description\t%s'%service, conf)

    def test_defines_the_security_services(self):
        conf = self.conf([vm('i-1')])
        for service in ('Malware', 'Vulnerabilities', 'Encryption', 'Backup',
                        'Integrity', 'Password_Policy', 'SSH_Attempts', 'Availability'):
            self.assertIn('service_description\t%s'%service, conf)

    def test_still_checks_ssh_reachability_actively(self):
        #nagios checks this itself; it is not reported by the vm
        conf = self.conf([vm('i-1')])
        self.assertIn('check_ssh!', conf)
        self.assertIn('active_checks_enabled 1', conf)

    def test_defines_one_service_per_name(self):
        conf = self.conf([vm('i-1')])
        self.assertEqual(conf.count('define service {'), len(services.service_names()) + 2)

    def test_the_passive_services_do_not_check_actively(self):
        #they are filled in by the agents' notifications; Nagios polling them
        #would report them down between reports
        self.assertIn('active_checks_enabled 0', self.conf([vm('i-1')]))

    def test_a_vm_without_an_address_is_left_out(self):
        #0.0.0.0 means the cloud never gave it one, so there is nothing to
        #monitor -- and a host block with that address would fail every check
        conf = self.conf([vm('i-1', address='0.0.0.0'), vm('i-2')])
        self.assertEqual(conf.count('define host {'), 1)
        self.assertNotIn('oneadmin_i-1_node01', conf)

    def test_every_vm_joins_the_vm_hostgroup(self):
        conf = self.conf([vm('i-1'), vm('i-2')])
        self.assertIn('hostgroup_name\tVirtual Machines', conf)
        members = conf.split('hostgroup_name\tVirtual Machines')[1]
        self.assertIn('oneadmin_i-1_node01', members)
        self.assertIn('oneadmin_i-2_node01', members)

    def test_vms_on_one_node_share_that_node_s_hostgroup(self):
        conf = self.conf([vm('i-1', node_ip='10.0.0.2'), vm('i-2', node_ip='10.0.0.2')])
        self.assertEqual(conf.count('hostgroup_name Node\t10.0.0.2'), 1)

    def test_each_node_gets_its_own_hostgroup(self):
        conf = self.conf([vm('i-1', node_ip='10.0.0.2'), vm('i-2', node_ip='10.0.0.3')])
        self.assertIn('hostgroup_name Node\t10.0.0.2', conf)
        self.assertIn('hostgroup_name Node\t10.0.0.3', conf)

    def test_a_vm_with_no_node_yet_is_still_configured(self):
        #the node is filled in later by update_vms_info; until then the vm
        #still needs its host definition, or it is monitored by nothing
        conf = self.conf([vm('i-1', node='', node_ip='')])
        self.assertIn('define host {', conf)

    def test_an_empty_inventory_produces_the_groups_and_no_hosts(self):
        conf = self.conf([])
        self.assertNotIn('define host {', conf)
        self.assertIn('hostgroup_name\tVirtual Machines', conf)

    def test_every_block_is_closed(self):
        #an unbalanced brace is the failure that stops nagios from starting
        conf = self.conf([vm('i-1'), vm('i-2', node_ip='10.0.0.3')])
        self.assertEqual(conf.count('{'), conf.count('}'))


class ReloadIfNecessaryTest(unittest.TestCase):
    """
    Puts the generated file in place and reloads Nagios. Both halves fail
    quietly if they go wrong: Nagios keeps serving the configuration it already
    has, and the run looks like it worked.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.generated = os.path.join(self.tmp, 'vms_nagios')
        self.live = os.path.join(self.tmp, 'vms_nagios.cfg')
        self.real_temp = cluster_config.NAGIOS_TEMP_CONF
        self.real_live = cluster_config.VMS_NAGIOS_FILE
        cluster_config.NAGIOS_TEMP_CONF = self.generated
        cluster_config.VMS_NAGIOS_FILE = self.live

        self.generator = module.Generate_VMs_Nagios_Conf(db=FakeDb())
        self.reloads = []
        self.generator.reload_nagios = lambda: self.reloads.append(True)
        logging.disable(logging.ERROR)

    def tearDown(self):
        cluster_config.NAGIOS_TEMP_CONF = self.real_temp
        cluster_config.VMS_NAGIOS_FILE = self.real_live
        shutil.rmtree(self.tmp)
        logging.disable(logging.NOTSET)

    def write(self, path, contents):
        f = open(path, 'w')
        f.write(contents)
        f.close()

    def test_a_first_run_puts_the_file_in_place_and_reloads(self):
        self.write(self.generated, 'define host {}\n')
        self.assertTrue(self.generator.reload_nagios_if_necessary())
        self.assertEqual(self.reloads, [True])
        self.assertEqual(open(self.live).read(), 'define host {}\n')

    def test_a_changed_configuration_is_moved_and_reloaded(self):
        self.write(self.live, 'define host { old }\n')
        self.write(self.generated, 'define host { new }\n')
        self.assertTrue(self.generator.reload_nagios_if_necessary())
        self.assertEqual(open(self.live).read(), 'define host { new }\n')

    def test_an_unchanged_configuration_does_not_reload(self):
        #the vm list barely changes, and reloading nagios on every cron run
        #drops the check state it holds in memory
        self.write(self.live, 'same\n')
        self.write(self.generated, 'same\n')
        self.assertFalse(self.generator.reload_nagios_if_necessary())
        self.assertEqual(self.reloads, [])

    def test_the_generated_file_is_consumed_once_moved(self):
        #it is a temp file; leaving it behind means the next run compares
        #against a stale generation
        self.write(self.generated, 'new\n')
        self.generator.reload_nagios_if_necessary()
        self.assertFalse(os.path.exists(self.generated))

    def test_nothing_generated_means_nothing_to_reload(self):
        #create_nagios_conf_running_vms failed; nagios must keep what it has
        self.write(self.live, 'still good\n')
        self.assertFalse(self.generator.reload_nagios_if_necessary())
        self.assertEqual(self.reloads, [])
        self.assertEqual(open(self.live).read(), 'still good\n')

    def test_a_file_that_cannot_be_moved_does_not_reload(self):
        #reloading here would tell nagios to re-read the old file and the run
        #would report success
        self.write(self.generated, 'new\n')
        cluster_config.VMS_NAGIOS_FILE = os.path.join(self.tmp, 'no_such_dir', 'vms.cfg')
        self.assertFalse(self.generator.reload_nagios_if_necessary())
        self.assertEqual(self.reloads, [])

    def test_a_whitespace_difference_still_counts_as_a_change(self):
        #the comparison is over the bytes, not a parse of the file
        self.write(self.live, 'define host {}\n')
        self.write(self.generated, 'define host {}\n\n')
        self.assertTrue(self.generator.reload_nagios_if_necessary())


class RemoveOldConfTest(unittest.TestCase):
    '''
    Deletes the nagiosgrapher files belonging to VMs that are gone. It removes
    files, so what it does NOT match matters as much as what it does.
    '''

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.real_path = cluster_config.PATH_SERVICEEXT_NAGIOSGRAPHER
        self.real_flag = cluster_config.USING_NAGIOSGRAPHER
        cluster_config.PATH_SERVICEEXT_NAGIOSGRAPHER = self.tmp
        cluster_config.USING_NAGIOSGRAPHER = True

    def tearDown(self):
        cluster_config.PATH_SERVICEEXT_NAGIOSGRAPHER = self.real_path
        cluster_config.USING_NAGIOSGRAPHER = self.real_flag
        shutil.rmtree(self.tmp)

    def touch(self, *names):
        for name in names:
            open(os.path.join(self.tmp, name), 'w').close()

    def remaining(self, terminated):
        module.Generate_VMs_Nagios_Conf(db=FakeDb(terminated=terminated)).remove_old_conf()
        return sorted(os.listdir(self.tmp))

    def test_removes_the_files_of_a_terminated_vm(self):
        #nagiosgrapher writes the instance id with underscores
        self.touch('oneadmin_i_1_node01-RAM.ncfg', 'oneadmin_i_2_node01-RAM.ncfg')
        self.assertEqual(self.remaining(['i-1']), ['oneadmin_i_2_node01-RAM.ncfg'])

    def test_leaves_a_running_vm_alone(self):
        self.touch('oneadmin_i_2_node01-RAM.ncfg')
        self.assertEqual(self.remaining([]), ['oneadmin_i_2_node01-RAM.ncfg'])

    def test_removes_every_file_belonging_to_the_vm(self):
        self.touch('oneadmin_i_1_node01-RAM.ncfg', 'oneadmin_i_1_node01-Cpu_Load.ncfg')
        self.assertEqual(self.remaining(['i-1']), [])

    def test_does_not_match_a_longer_id_that_starts_the_same(self):
        #terminating i-1 used to delete i-10's graph history too, since the id
        #was matched anywhere in the file name
        self.touch('oneadmin_i_1_node01-RAM.ncfg', 'oneadmin_i_10_node01-RAM.ncfg')
        self.assertEqual(self.remaining(['i-1']), ['oneadmin_i_10_node01-RAM.ncfg'])

    def test_does_nothing_when_nagiosgrapher_is_not_in_use(self):
        cluster_config.USING_NAGIOSGRAPHER = False
        self.touch('oneadmin_i_1_node01-RAM.ncfg')
        self.assertEqual(self.remaining(['i-1']), ['oneadmin_i_1_node01-RAM.ncfg'])


if __name__ == '__main__':
    unittest.main()
