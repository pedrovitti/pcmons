'''
Tests for the configuration check.

The three config modules are plain Python, so nothing stops a port being
quoted or an interface being spelt wrong -- it is found later, by a component
failing somewhere that names neither the setting nor the file. These are the
mistakes worth catching before anything starts, and the tests below are
mostly about the ones that used to be found the expensive way.

Each case builds a config that is fine and then breaks one thing in it, so a
failure names the check that fired rather than the fixture that drifted.
'''
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
sys.path.insert(0, ROOT)

import config_check as module


class Config:
    '''A stand-in for a config module: settings and nothing else.'''

    def __init__(self, **settings):
        for name, value in settings.items():
            setattr(self, name, value)


class ConfigCheckTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.log = os.path.join(self.tmp, 'pcmons.log')
        #a file that is really there, for the checks that ask whether a path
        #exists on this machine
        self.present = os.path.join(self.tmp, 'oned.conf')
        open(self.present, 'w').close()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def settings(self):
        '''a cluster config with nothing wrong with it'''
        return dict(
            PATH_TO_LOG_FILE=self.log,
            LISTEN_IP='0.0.0.0', LISTEN_PORT=60001,
            VM_TABLE='vmmonitor_vm', READING_TABLE='vmmonitor_reading',
            HISTORY_RETENTION_DAYS=30, KEEP_HISTORY=True,
            DATABASES={'default':{'NAME':'manager', 'USER':'manager',
                                  'PASSWORD':'secret', 'HOST':'localhost',
                                  'PORT':3306}},
            INFRA='opennebula', PATH_TO_OPENNEBULA_CONFIG_FILE=self.present,
            INTERFACES=('nagios',), INTERFACE='nagios',
            VMS_NAGIOS_FILE=os.path.join(self.tmp, 'vms_nagios.cfg'),
            NAGIOS_TEMP_CONF=os.path.join(self.tmp, 'vms_nagios'),
            COMMAND_TO_RELOAD_NAGIOS='/etc/init.d/nagios3 reload',
            USING_NAGIOSGRAPHER=False,
            MAIL_FROM='pcmons@localhost', MAIL_TO=('ops@example.org',),
            SMTP_HOST='localhost', SMTP_PORT=25, MAIL_REPEAT_MINUTES=60,
            ADMINS=(('Someone', 'someone@example.org'),),
        )

    def cluster(self, **changes):
        settings = self.settings()
        settings.update(changes)
        return module.check_cluster(Config(**settings))

    def settings_for(self, problems):
        return [problem.setting for problem in problems]

    def assertComplains(self, problems, setting):
        self.assertIn(setting, self.settings_for(problems))

    def assertQuiet(self, problems):
        self.assertEqual([str(problem) for problem in problems], [])


class HealthyConfigTest(ConfigCheckTest):

    def test_a_config_with_nothing_wrong_reports_nothing(self):
        #every other test breaks one thing in this, so it has to be quiet
        self.assertQuiet(self.cluster())

    def test_the_shipped_node_config_is_read(self):
        config = Config(PATH_TO_LOG_FILE=self.log, LISTEN_IP='0.0.0.0', LISTEN_PORT=60000)
        self.assertQuiet(module.check_node(config))

    def test_the_shipped_agent_config_is_read(self):
        config = Config(SERVER='http://10.0.0.1', SERVER_PORT='60001')
        self.assertQuiet(module.check_agent(config))


class DatabaseTest(ConfigCheckTest):

    def test_a_quoted_port_is_an_error(self):
        #the setting that has carried a warning comment in the config file
        #since 2010, because mysql refuses it with an unrelated message
        problems = self.cluster(DATABASES={'default':{'NAME':'m', 'USER':'m',
                                                      'PASSWORD':'s', 'HOST':'h',
                                                      'PORT':'3306'}})
        self.assertComplains(problems, 'DATABASES.PORT')

    def test_a_port_that_is_a_number_is_accepted(self):
        self.assertQuiet(self.cluster())

    def test_a_missing_database_name_is_an_error(self):
        problems = self.cluster(DATABASES={'default':{'NAME':'', 'USER':'m',
                                                      'PASSWORD':'s', 'HOST':'h',
                                                      'PORT':3306}})
        self.assertComplains(problems, 'DATABASES.NAME')

    def test_a_missing_user_is_an_error(self):
        problems = self.cluster(DATABASES={'default':{'NAME':'m', 'USER':'',
                                                      'PASSWORD':'s', 'HOST':'h',
                                                      'PORT':3306}})
        self.assertComplains(problems, 'DATABASES.USER')

    def test_an_empty_password_is_only_a_warning(self):
        #a database reachable without one is a decision somebody may have made
        problems = self.cluster(DATABASES={'default':{'NAME':'m', 'USER':'m',
                                                      'PASSWORD':'', 'HOST':'h',
                                                      'PORT':3306}})
        self.assertEqual(module.errors(problems), [])
        self.assertComplains(module.warnings(problems), 'DATABASES.PASSWORD')

    def test_a_config_with_no_default_connection_is_an_error(self):
        self.assertComplains(self.cluster(DATABASES={}), 'DATABASES')

    def test_a_config_without_databases_at_all_is_an_error(self):
        settings = self.settings()
        del settings['DATABASES']
        self.assertComplains(module.check_cluster(Config(**settings)), 'DATABASES')


class PathTest(ConfigCheckTest):

    def test_a_log_in_a_directory_that_does_not_exist_is_an_error(self):
        #found today by a server that has already stopped logging
        problems = self.cluster(PATH_TO_LOG_FILE='/nowhere/at/all/pcmons.log')
        self.assertComplains(problems, 'PATH_TO_LOG_FILE')

    def test_a_log_the_directory_will_not_take_is_an_error(self):
        if os.geteuid() == 0:
            #root is allowed to write to a directory that forbids it, so
            #there is nothing here to detect
            return
        locked = os.path.join(self.tmp, 'locked')
        os.mkdir(locked, 0o500)
        try:
            problems = self.cluster(PATH_TO_LOG_FILE=os.path.join(locked, 'p.log'))
            self.assertComplains(problems, 'PATH_TO_LOG_FILE')
        finally:
            os.chmod(locked, 0o700)

    def test_the_log_file_itself_need_not_exist_yet(self):
        #it is created on the first write
        self.assertQuiet(self.cluster(PATH_TO_LOG_FILE=os.path.join(self.tmp, 'new.log')))

    def test_a_cloud_config_that_is_not_on_this_machine_is_a_warning(self):
        #the check may be run from somewhere that is not the cluster controller
        problems = self.cluster(PATH_TO_OPENNEBULA_CONFIG_FILE='/nowhere/oned.conf')
        self.assertEqual(module.errors(problems), [])
        self.assertComplains(module.warnings(problems), 'PATH_TO_OPENNEBULA_CONFIG_FILE')


class PortTest(ConfigCheckTest):

    def test_a_quoted_listen_port_is_an_error(self):
        self.assertComplains(self.cluster(LISTEN_PORT='60001'), 'LISTEN_PORT')

    def test_a_port_outside_the_range_is_an_error(self):
        self.assertComplains(self.cluster(LISTEN_PORT=70000), 'LISTEN_PORT')

    def test_port_zero_is_an_error(self):
        self.assertComplains(self.cluster(LISTEN_PORT=0), 'LISTEN_PORT')

    def test_a_port_that_is_true_is_an_error(self):
        #a bool is an int in python, and True is not a port
        self.assertComplains(self.cluster(LISTEN_PORT=True), 'LISTEN_PORT')


class InterfaceTest(ConfigCheckTest):

    def test_an_interface_name_that_does_not_exist_is_an_error(self):
        #it reports into nothing, and only the log says so
        self.assertComplains(self.cluster(INTERFACES=('nagois',)), 'INTERFACES')

    def test_configuring_no_interface_at_all_is_an_error(self):
        problems = self.cluster(INTERFACES=(), INTERFACE='')
        self.assertComplains(problems, 'INTERFACES')

    def test_the_older_single_setting_is_accepted(self):
        self.assertQuiet(self.cluster(INTERFACES=(), INTERFACE='nagios'))

    def test_the_name_is_matched_regardless_of_case(self):
        self.assertQuiet(self.cluster(INTERFACES=('NAGIOS',)))

    def test_the_nagios_settings_are_only_checked_when_it_is_configured(self):
        #a cluster reporting by mail alone has no nagios paths to get wrong
        problems = self.cluster(INTERFACES=('email',), VMS_NAGIOS_FILE='/nowhere/x.cfg')
        self.assertQuiet(problems)

    def test_a_nagios_file_that_cannot_be_written_is_an_error(self):
        self.assertComplains(self.cluster(VMS_NAGIOS_FILE='/nowhere/vms.cfg'),
                             'VMS_NAGIOS_FILE')

    def test_the_grapher_path_is_only_checked_when_it_is_in_use(self):
        self.assertQuiet(self.cluster(USING_NAGIOSGRAPHER=False,
                                      PATH_SERVICEEXT_NAGIOSGRAPHER='/nowhere'))

    def test_a_missing_grapher_path_is_a_warning_when_it_is_in_use(self):
        problems = self.cluster(USING_NAGIOSGRAPHER=True,
                                PATH_SERVICEEXT_NAGIOSGRAPHER='/nowhere')
        self.assertComplains(module.warnings(problems), 'PATH_SERVICEEXT_NAGIOSGRAPHER')


class MailTest(ConfigCheckTest):

    def mail(self, **changes):
        changes.setdefault('INTERFACES', ('email',))
        return self.cluster(**changes)

    def test_the_mail_settings_are_checked_when_it_is_configured(self):
        self.assertComplains(self.mail(SMTP_PORT='25'), 'SMTP_PORT')

    def test_alerts_with_nowhere_to_go_are_an_error(self):
        self.assertComplains(self.mail(MAIL_TO=(), ADMINS=()), 'MAIL_TO')

    def test_the_admins_count_as_recipients(self):
        #the list the rest of the cluster already keeps
        self.assertQuiet(self.mail(MAIL_TO=(), ADMINS=(('A', 'a@example.org'),)))

    def test_something_that_is_not_an_address_is_a_warning(self):
        problems = self.mail(MAIL_TO=('ops',))
        self.assertEqual(module.errors(problems), [])
        self.assertComplains(module.warnings(problems), 'MAIL_TO')

    def test_a_negative_repeat_window_is_an_error(self):
        self.assertComplains(self.mail(MAIL_REPEAT_MINUTES=-5), 'MAIL_REPEAT_MINUTES')

    def test_no_repeating_is_allowed(self):
        #0 reports each state once, until it changes
        self.assertQuiet(self.mail(MAIL_REPEAT_MINUTES=0))


class InfraTest(ConfigCheckTest):

    def test_a_cloud_platform_that_is_not_supported_is_an_error(self):
        self.assertComplains(self.cluster(INFRA='openstack'), 'INFRA')

    def test_eucalyptus_is_supported(self):
        self.assertQuiet(self.cluster(INFRA='eucalyptus',
                                      PATH_TO_EUCALYPTUS_CONFIG_FILE=self.present))


class AgentTest(ConfigCheckTest):

    def test_a_server_without_a_scheme_is_an_error(self):
        #xmlrpclib refuses it with an error naming neither setting
        problems = module.check_agent(Config(SERVER='10.0.0.1', SERVER_PORT='60001'))
        self.assertComplains(problems, 'SERVER')

    def test_https_is_accepted(self):
        self.assertQuiet(module.check_agent(Config(SERVER='https://10.0.0.1',
                                                   SERVER_PORT='60001')))

    def test_a_port_that_is_not_a_number_is_an_error(self):
        problems = module.check_agent(Config(SERVER='http://10.0.0.1',
                                             SERVER_PORT='sixty thousand'))
        self.assertComplains(problems, 'SERVER_PORT')

    def test_the_port_may_be_a_string_of_digits(self):
        #it is read from the environment, so that is what it usually is
        self.assertQuiet(module.check_agent(Config(SERVER='http://10.0.0.1',
                                                   SERVER_PORT='60001')))


class MissingSettingTest(ConfigCheckTest):

    def test_a_setting_that_is_not_in_the_file_is_reported_once(self):
        #a config file older than the code
        settings = self.settings()
        del settings['LISTEN_PORT']
        problems = module.check_cluster(Config(**settings))
        self.assertEqual(self.settings_for(problems).count('LISTEN_PORT'), 1)

    def test_it_says_the_setting_is_absent_rather_than_wrong(self):
        settings = self.settings()
        del settings['READING_TABLE']
        problems = module.check_cluster(Config(**settings))
        self.assertIn('not set', str(problems[0]))

    def test_the_rest_of_the_config_is_still_checked(self):
        settings = self.settings()
        del settings['LISTEN_PORT']
        settings['INFRA'] = 'openstack'
        self.assertComplains(module.check_cluster(Config(**settings)), 'INFRA')


class ReportingTest(ConfigCheckTest):

    def test_errors_and_warnings_are_told_apart(self):
        problems = self.cluster(LISTEN_PORT='60001',
                                PATH_TO_OPENNEBULA_CONFIG_FILE='/nowhere')
        self.assertEqual(self.settings_for(module.errors(problems)), ['LISTEN_PORT'])
        self.assertEqual(self.settings_for(module.warnings(problems)),
                         ['PATH_TO_OPENNEBULA_CONFIG_FILE'])

    def test_a_problem_reads_as_a_line(self):
        problem = module.Problem(module.ERROR, 'LISTEN_PORT', 'must be a number')
        self.assertIn('ERROR', str(problem))
        self.assertIn('LISTEN_PORT', str(problem))
        self.assertIn('must be a number', str(problem))

    def test_the_real_config_modules_are_found(self):
        #the check has to be able to load what the repository ships, whatever
        #it then says about it
        self.assertEqual([name for name, problems in module.check_all()],
                         ['cluster', 'node', 'agent'])


if __name__ == '__main__':
    unittest.main()
