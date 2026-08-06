'''
One reading, all the way through.

Every other test in this directory fakes the seam it is not testing: the
notification server tests stub the interfaces, the mail tests fake the
database, and the payload contract test compares names without ever putting a
reading through. So nothing so far shows that the pieces fit together.

That is worth a test here in particular. The two worst bugs this repository
ever had -- the class-level dictionary every VM record shared, and the config
generator deleting i-10's graphs when i-1 terminated -- were both seam bugs,
invisible to a unit test of either side. The seam has since grown a registry,
a second interface and a history layer.

So this builds a payload the way the agent builds one, hands it to a real
notification server, and lets it reach a real Nagios interface, a real mail
interface and a real history. The only fakes are the true edges: the shell,
the mail server and the database.
'''
import logging
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'booting_vms'))

import running_vms.cluster.cluster_config as cluster_config
cluster_config.PATH_TO_LOG_FILE = '/tmp/pcmons-end-to-end-test.log'

from Monitor import Monitor
from running_vms import Notification_Server
from running_vms.cluster.history import History
from interface.nagios import NagiosPassiveServer as nagios_module
from interface.nagios import services

VM = {'user':'oneadmin', 'instance_id':'i-42', 'node_hostname':'node01'}
ADDRESS = '150.162.63.90'

#what a healthy vm reports, in the shape each probe returns
HEALTHY = {
    'memory': {'total':2048, 'used':1024, 'free':1024, 'cache':128},
    'loadavg': {'1':0.5, '5':0.4, '10':0.3},
    'http': {'connections':'7'},
    'sshattempts': {'valid':'2', 'invalid':'3'},
    'availability': {'uptime':'3 days, 2:11'},
    'backup': {'last_performed':'2026/08/06 02:01:19'},
    'encryption': {'is_encrypted':'yes', 'cipher':'aes-xts-plain64'},
    'integrity': {'last_performed':'Thu Aug  6 03:00:12 2026'},
    'malware': {'detected':0, 'last_scan':'2026-08-06'},
    'password': {'max_age':90},
    'vulnerability': {'warn':0, 'fail':0},
}


def collect(readings):
    '''
    a notification, built by the agent's own Monitor with its probes replaced.
    Going through Monitor rather than writing the payload out by hand means
    the keys are the ones the agent really sends: a probe renamed on the agent
    reaches this test as a missing metric, which is the whole point
    '''
    monitor = Monitor()
    for attribute in dir(monitor):
        if attribute.endswith('Monitor'):
            setattr(monitor, attribute, CannedProbe(readings))
    return monitor.get_monitoring_data()


#the method each probe class exposes, and the reading it answers with. Which
#of these Monitor calls, and what it files the answer under, is Monitor's
#business -- that is what going through it rather than writing out a payload
#by hand is for
PROBE_METHODS = {
    'get_meminfo': 'memory',
    'get_loadavg': 'loadavg',
    'get_http_connections': 'http',
    'get_ssh_access_attempts': 'sshattempts',
    'get_availability_info': 'availability',
    'get_backup_info': 'backup',
    'get_encryption_info': 'encryption',
    'get_integrity_info': 'integrity',
    'get_malware_info': 'malware',
    'get_password_security': 'password',
    'get_vulnerability_info': 'vulnerability',
}


class CannedProbe:
    '''
    stands in for any probe class: the method asked for answers with the
    reading for that probe, or raises the way a probe with no log file to read
    would, which is how a metric goes missing from a notification
    '''

    def __init__(self, readings):
        self.readings = readings

    def __getattr__(self, name):
        return lambda: self.reading_for(name)

    def reading_for(self, method):
        return self.readings[PROBE_METHODS[method]]


class FakeCommands:
    '''the shell the nagios interface files its check results through'''

    def __init__(self):
        self.run = []

    def getstatusoutput(self, command):
        self.run.append(command)
        return 0, ''

    def checks(self):
        '''(host, service, status, output) for each check registered'''
        registered = []
        for command in self.run:
            #./send_passive_check_nagios.sh <host> <service> <status> "<output>"
            head, output = command.split('"', 1)
            script, host, service, status = head.split()
            registered.append((host, service, int(status), output.rstrip('"')))
        return registered

    def services(self):
        return [service for host, service, status, output in self.checks()]


class FakeMailer:

    def __init__(self):
        self.sent = []

    def send(self, sender, recipients, message):
        self.sent.append(message)


class FakeDb:
    '''
    the database, which is the far edge of all three paths: the interfaces
    look a vm up in it and the history writes readings to it
    '''

    def __init__(self, vm=VM):
        self.vm = vm
        self.readings = []

    def get_vm_by_ip(self, ip):
        return self.vm

    def get_id_by_ip(self, ip):
        if self.vm is None:
            return None
        return {'instance_id':self.vm['instance_id']}

    def get_vm_info(self, instance_id):
        return self.vm

    def insert_readings(self, rows):
        self.readings.extend(rows)
        return len(rows)


class EndToEndTest(unittest.TestCase):

    def setUp(self):
        self.commands = FakeCommands()
        self.mailer = FakeMailer()
        self.db = FakeDb()

        #the nagios interface reaches the shell through its module
        self.real_commands = nagios_module.commands
        nagios_module.commands = self.commands

        self.real_interfaces = cluster_config.INTERFACES
        cluster_config.INTERFACES = ('nagios', 'email')

        self.server = Notification_Server.NotificationServer(
            db=self.db, history=History(db=self.db))
        #build them now so the mailer can be put in before anything is sent
        for name, interface in self.server.active_interfaces():
            if name == 'email':
                interface.mailer = self.mailer
                self.mail = interface

        logging.disable(logging.ERROR)

    def tearDown(self):
        nagios_module.commands = self.real_commands
        cluster_config.INTERFACES = self.real_interfaces
        logging.disable(logging.NOTSET)

    def send(self, readings=None):
        if readings is None:
            readings = HEALTHY
        return self.server.handle_notification(collect(readings), ADDRESS)

    def stored(self):
        return set((metric, field) for vm, metric, field, value, when in self.db.readings)

    def value(self, metric, field):
        for vm, stored_metric, stored_field, value, when in self.db.readings:
            if (stored_metric, stored_field) == (metric, field):
                return value
        return None


class NotificationTest(EndToEndTest):

    def test_the_agent_is_told_the_reading_was_taken(self):
        self.assertTrue(self.send())

    def test_both_interfaces_were_built(self):
        self.assertEqual([name for name, interface in self.server.active_interfaces()],
                         ['nagios', 'email'])

    def test_every_metric_the_agent_collected_reaches_nagios(self):
        #the check the payload contract test cannot make: it compares names,
        #this puts a reading through and sees what comes out the far side
        self.send()
        self.assertEqual(sorted(self.commands.services()),
                         sorted(services.service_names()))

    def test_every_check_names_the_vm_the_way_nagios_knows_it(self):
        self.send()
        for host, service, status, output in self.commands.checks():
            self.assertEqual(host, 'oneadmin_i-42_node01')

    def test_a_healthy_vm_registers_nothing_alarming(self):
        self.send()
        for host, service, status, output in self.commands.checks():
            self.assertEqual(status, 0, '%s reported %s'%(service, status))

    def test_the_memory_check_carries_the_line_nagiosgrapher_parses(self):
        #the reading arrives as the agent's dict and leaves as this string
        self.send()
        memory = [output for host, service, status, output in self.commands.checks()
                  if service == 'RAM']
        self.assertEqual(memory, ['50;1/2'])


class HistoryPathTest(EndToEndTest):

    def test_every_field_of_every_metric_is_kept(self):
        self.send()
        expected = set()
        for metric, reading in HEALTHY.items():
            for field in reading:
                expected.add((metric, field))
        self.assertEqual(self.stored(), expected)

    def test_the_readings_are_filed_against_the_vm_at_that_address(self):
        self.send()
        self.assertEqual(set(vm for vm, m, f, v, w in self.db.readings), set(['i-42']))

    def test_a_load_average_survives_the_trip(self):
        self.send()
        self.assertEqual(float(self.value('loadavg', '1')), 0.5)

    def test_history_is_kept_as_well_as_reported(self):
        #the two paths are independent: neither may cost the other
        self.send()
        self.assertTrue(self.db.readings)
        self.assertTrue(self.commands.checks())


class MailPathTest(EndToEndTest):

    def test_a_healthy_vm_is_not_worth_mail(self):
        self.send()
        self.assertEqual(self.mailer.sent, [])

    def test_an_infected_vm_reaches_the_administrators(self):
        readings = dict(HEALTHY)
        readings['malware'] = {'detected':2, 'last_scan':'2026-08-06'}
        self.send(readings)
        self.assertEqual(len(self.mailer.sent), 1)
        self.assertIn('Malware', self.mailer.sent[0])

    def test_the_dashboard_and_the_mail_agree(self):
        #the reason the judgement was moved out of the nagios interface: an
        #operator must not get mail about a vm whose dashboard is green
        readings = dict(HEALTHY)
        readings['malware'] = {'detected':2, 'last_scan':'2026-08-06'}
        self.send(readings)
        malware = [status for host, service, status, output in self.commands.checks()
                   if service == 'Malware']
        self.assertEqual(malware, [2])
        self.assertIn('CRITICAL', self.mailer.sent[0])

    def test_the_check_is_still_filed_when_the_mail_server_is_down(self):
        self.mail.mailer = BrokenMailer()
        readings = dict(HEALTHY)
        readings['malware'] = {'detected':2, 'last_scan':'2026-08-06'}
        self.assertTrue(self.send(readings))
        self.assertIn('Malware', self.commands.services())


class BrokenMailer:

    def send(self, sender, recipients, message):
        raise IOError('connection refused')


class PartialNotificationTest(EndToEndTest):

    def missing(self, metric):
        readings = dict(HEALTHY)
        del readings[metric]
        return readings

    def test_a_probe_that_failed_costs_only_its_own_check(self):
        #the agent leaves out a probe that raised, so a metric can be absent
        #from an otherwise good notification
        self.send(self.missing('malware'))
        registered = self.commands.services()
        self.assertNotIn('Malware', registered)
        self.assertIn('RAM', registered)

    def test_a_probe_that_failed_costs_only_its_own_history(self):
        self.send(self.missing('malware'))
        self.assertNotIn(('malware', 'detected'), self.stored())
        self.assertIn(('memory', 'used'), self.stored())

    def test_a_reading_that_cannot_be_read_costs_only_its_own_check(self):
        #a probe that reports something unexpected, rather than nothing
        readings = dict(HEALTHY)
        readings['memory'] = {'total':0, 'used':1024, 'free':0, 'cache':0}
        self.send(readings)
        registered = self.commands.services()
        self.assertNotIn('RAM', registered)
        self.assertIn('Cpu_Load', registered)

    def test_a_reading_that_cannot_be_read_is_still_kept(self):
        #history stores what arrived; whether it makes sense is the
        #interface's question, and the answer is worth keeping either way
        readings = dict(HEALTHY)
        readings['memory'] = {'total':0, 'used':1024, 'free':0, 'cache':0}
        self.send(readings)
        self.assertIn(('memory', 'total'), self.stored())

    def test_an_empty_notification_is_still_taken(self):
        self.assertTrue(self.send({}))
        self.assertEqual(self.commands.checks(), [])


class UnknownVmTest(EndToEndTest):

    def setUp(self):
        EndToEndTest.setUp(self)
        self.db.vm = None

    def test_a_notification_from_an_address_no_vm_has_is_dropped(self):
        self.assertFalse(self.send())

    def test_nothing_is_filed_against_a_vm_that_is_not_there(self):
        self.send()
        self.assertEqual(self.commands.checks(), [])
        self.assertEqual(self.db.readings, [])


class RepeatedNotificationTest(EndToEndTest):

    def test_the_interfaces_are_built_once_and_kept(self):
        #they were rebuilt per notification, which opened a database
        #connection every five minutes per vm
        self.send()
        first = self.server.active_interfaces()
        self.send()
        self.assertTrue(self.server.active_interfaces()[0][1] is first[0][1])

    def test_each_round_files_its_own_checks(self):
        self.send()
        self.send()
        self.assertEqual(len(self.commands.checks()), 2*len(services.service_names()))

    def test_each_round_is_kept_apart_in_the_history(self):
        self.send()
        self.send()
        self.assertEqual(len([r for r in self.db.readings if r[1:3] == ('memory', 'used')]), 2)

    def test_a_problem_that_has_not_changed_is_mailed_about_once(self):
        #the state is kept on the interface, which only survives because the
        #interfaces are built once
        readings = dict(HEALTHY)
        readings['malware'] = {'detected':2, 'last_scan':'2026-08-06'}
        self.send(readings)
        self.send(readings)
        self.assertEqual(len(self.mailer.sent), 1)

    def test_a_vm_that_recovers_is_mailed_about_again(self):
        readings = dict(HEALTHY)
        readings['malware'] = {'detected':2, 'last_scan':'2026-08-06'}
        self.send(readings)
        self.send(HEALTHY)
        self.assertEqual(len(self.mailer.sent), 2)


if __name__ == '__main__':
    unittest.main()
