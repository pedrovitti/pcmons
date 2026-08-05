'''
Tests for the mail interface, the second consumer of the shared judgement.

Nagios answers "what is the state of everything"; this answers "something
changed and you were not looking". Most of these are therefore about what is
NOT sent: a healthy vm, and a vm that has been broken since yesterday, should
both be silent. An alert that arrives every five minutes is one nobody reads.
'''
import datetime
import logging
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
sys.path.insert(0, ROOT)

import running_vms.cluster.cluster_config as cluster_config
cluster_config.PATH_TO_LOG_FILE = '/tmp/pcmons-mail-test.log'

from interface.mail import MailInterface as module

NOW = datetime.datetime(2026, 8, 6, 12, 0, 0)
VM = {'user':'oneadmin', 'instance_id':'i-42', 'node_hostname':'node01'}

HEALTHY = {'malware':{'detected':0, 'last_scan':'today'},
           'memory':{'used':512, 'total':1024}}
INFECTED = {'malware':{'detected':2, 'last_scan':'today'},
            'memory':{'used':512, 'total':1024}}


def later(minutes):
    return NOW + datetime.timedelta(minutes=minutes)


class FakeDb:

    def __init__(self, vm=VM):
        self.vm = vm

    def get_vm_by_ip(self, ip):
        self.ip = ip
        return self.vm


class FakeMailer:

    def __init__(self):
        self.sent = []

    def send(self, sender, recipients, message):
        self.sent.append((sender, recipients, message))


class BrokenMailer:

    def send(self, sender, recipients, message):
        raise IOError('connection refused')


class MailInterfaceTest(unittest.TestCase):

    def setUp(self):
        self.mailer = FakeMailer()
        self.interface = module.MailInterface(db=FakeDb(), mailer=self.mailer)
        self.repeat = cluster_config.MAIL_REPEAT_MINUTES
        logging.disable(logging.ERROR)

    def tearDown(self):
        cluster_config.MAIL_REPEAT_MINUTES = self.repeat
        logging.disable(logging.NOTSET)

    def process(self, data, when=NOW):
        return self.interface.process_notification(data, '10.0.0.10', now=when)

    def message(self, index=0):
        return self.mailer.sent[index][2]


class SilenceTest(MailInterfaceTest):

    def test_a_healthy_vm_is_not_worth_mail(self):
        self.process(HEALTHY)
        self.assertEqual(self.mailer.sent, [])

    def test_a_healthy_vm_is_still_a_notification_taken(self):
        #nothing to say is not a failure to take the readings
        self.assertTrue(self.process(HEALTHY))

    def test_the_same_problem_is_not_reported_twice(self):
        cluster_config.MAIL_REPEAT_MINUTES = 60
        self.process(INFECTED)
        self.process(INFECTED, when=later(5))
        self.assertEqual(len(self.mailer.sent), 1)

    def test_a_problem_that_will_not_go_away_is_repeated_eventually(self):
        cluster_config.MAIL_REPEAT_MINUTES = 60
        self.process(INFECTED)
        self.process(INFECTED, when=later(61))
        self.assertEqual(len(self.mailer.sent), 2)

    def test_repeating_can_be_turned_off(self):
        #0 reports each state once, until it changes
        cluster_config.MAIL_REPEAT_MINUTES = 0
        self.process(INFECTED)
        self.process(INFECTED, when=later(60*24*7))
        self.assertEqual(len(self.mailer.sent), 1)

    def test_a_vm_that_never_reported_from_here_is_not_mailed_about(self):
        self.interface.db = FakeDb(vm=None)
        self.assertFalse(self.process(INFECTED))
        self.assertEqual(self.mailer.sent, [])


class ChangeTest(MailInterfaceTest):

    def test_a_metric_turning_bad_is_reported(self):
        self.process(INFECTED)
        self.assertEqual(len(self.mailer.sent), 1)

    def test_a_metric_recovering_is_reported(self):
        #without it an operator has to go and look to find out it is over
        self.process(INFECTED)
        self.process(HEALTHY, when=later(5))
        self.assertEqual(len(self.mailer.sent), 2)
        self.assertIn('OK', self.message(1))

    def test_recovery_is_reported_once(self):
        self.process(INFECTED)
        self.process(HEALTHY, when=later(5))
        self.process(HEALTHY, when=later(10))
        self.assertEqual(len(self.mailer.sent), 2)

    def test_a_metric_getting_worse_is_reported_again(self):
        #warning to critical is news even inside the repeat window
        cluster_config.MAIL_REPEAT_MINUTES = 60
        self.process({'vulnerability':{'warn':1, 'fail':0}})
        self.process({'vulnerability':{'warn':1, 'fail':1}}, when=later(5))
        self.assertEqual(len(self.mailer.sent), 2)

    def test_one_vm_does_not_silence_another(self):
        #the state is kept per vm, not per metric
        self.process(INFECTED)
        self.interface.db = FakeDb(vm={'user':'oneadmin', 'instance_id':'i-99',
                                       'node_hostname':'node02'})
        self.process(INFECTED, when=later(5))
        self.assertEqual(len(self.mailer.sent), 2)

    def test_a_reading_that_cannot_be_judged_is_not_mailed_about(self):
        self.process({'malware':{'detected':'lots'}})
        self.assertEqual(self.mailer.sent, [])


class MessageTest(MailInterfaceTest):

    def test_the_subject_names_the_vm_and_the_worst_state(self):
        self.process(INFECTED)
        self.assertIn('CRITICAL', self.message())
        self.assertIn('i-42', self.message())

    def test_the_worst_state_wins_the_subject(self):
        self.process({'malware':{'detected':2, 'last_scan':'today'},
                      'backup':{'last_performed':''}})
        subject = [line for line in self.message().splitlines()
                   if line.startswith('Subject:')][0]
        self.assertIn('CRITICAL', subject)
        self.assertNotIn('WARNING', subject)

    def test_the_subject_counts_the_rest(self):
        self.process({'malware':{'detected':2, 'last_scan':'today'},
                      'backup':{'last_performed':''}})
        subject = [line for line in self.message().splitlines()
                   if line.startswith('Subject:')][0]
        self.assertIn('1 more', subject)

    def test_the_body_carries_a_line_per_problem(self):
        self.process({'malware':{'detected':2, 'last_scan':'today'},
                      'backup':{'last_performed':''}})
        self.assertIn('Malware', self.message())
        self.assertIn('Backup', self.message())

    def test_the_body_says_which_vm_and_when(self):
        self.process(INFECTED)
        self.assertIn('i-42', self.message())
        self.assertIn('node01', self.message())
        self.assertIn('06-08-2026', self.message())

    def test_only_the_metrics_that_changed_are_in_the_mail(self):
        #the memory reading in this payload is fine, and an alert listing it
        #teaches the reader to skim
        self.process(INFECTED)
        self.assertNotIn('RAM', self.message())

    def test_the_headers_come_before_the_body(self):
        self.process(INFECTED)
        headers, body = self.message().split('\n\n', 1)
        self.assertIn('From:', headers)
        self.assertIn('To:', headers)
        self.assertIn('Subject:', headers)
        self.assertIn('Malware', body)


class RecipientTest(MailInterfaceTest):

    def setUp(self):
        MailInterfaceTest.setUp(self)
        self.real_to = cluster_config.MAIL_TO

    def tearDown(self):
        cluster_config.MAIL_TO = self.real_to
        MailInterfaceTest.tearDown(self)

    def test_the_configured_recipients_are_used(self):
        cluster_config.MAIL_TO = ('ops@example.org',)
        self.assertEqual(self.interface.recipients(), ['ops@example.org'])

    def test_the_admins_hear_about_it_when_nobody_else_is_named(self):
        #ADMINS is the list the rest of the cluster already keeps
        cluster_config.MAIL_TO = ()
        self.assertEqual(self.interface.recipients(),
                         [address for name, address in cluster_config.ADMINS])

    def test_the_recipients_are_on_the_message(self):
        cluster_config.MAIL_TO = ('ops@example.org',)
        self.process(INFECTED)
        self.assertIn('ops@example.org', self.message())

    def test_nothing_is_sent_when_nobody_would_receive_it(self):
        cluster_config.MAIL_TO = ()
        real_admins = cluster_config.ADMINS
        cluster_config.ADMINS = ()
        try:
            self.process(INFECTED)
        finally:
            cluster_config.ADMINS = real_admins
        self.assertEqual(self.mailer.sent, [])


class FailureTest(MailInterfaceTest):

    def test_a_mail_server_that_is_down_does_not_fail_the_notification(self):
        #the readings are already kept and already on the dashboard
        self.interface.mailer = BrokenMailer()
        self.assertTrue(self.process(INFECTED))


if __name__ == '__main__':
    unittest.main()
