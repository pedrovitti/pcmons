'''
Tests for the interface registry, which turns the names in the config into the
interfaces a notification is handed to.

This is the seam a misconfigured cluster fails at, so most of these are about
what a bad name costs: a typo should cost that one interface and nothing else.
'''
import logging
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
sys.path.insert(0, ROOT)

import running_vms.cluster.cluster_config as cluster_config
cluster_config.PATH_TO_LOG_FILE = '/tmp/pcmons-registry-test.log'

from interface import registry


class RegistryTest(unittest.TestCase):

    def setUp(self):
        self.real_build = registry.build
        logging.disable(logging.ERROR)

    def tearDown(self):
        registry.build = self.real_build
        logging.disable(logging.NOTSET)


class BuildTest(RegistryTest):

    def test_it_builds_the_nagios_interface(self):
        self.assertTrue(hasattr(registry.build('nagios'), 'process_notification'))

    def test_a_name_that_is_not_an_interface_builds_nothing(self):
        self.assertIsNone(registry.build('zabbix'))

    def test_the_name_is_matched_regardless_of_case(self):
        #it is typed into a config file by hand
        self.assertIsNotNone(registry.build('Nagios'))

    def test_surrounding_space_is_ignored(self):
        self.assertIsNotNone(registry.build(' nagios '))

    def test_an_empty_name_builds_nothing(self):
        self.assertIsNone(registry.build(''))

    def test_the_known_names_are_listed(self):
        #the error message for a bad name quotes this, so it has to be right
        self.assertIn('nagios', registry.names())


class BuildAllTest(RegistryTest):

    def test_it_builds_each_configured_interface(self):
        registry.build = lambda name: name.upper()
        self.assertEqual(registry.build_all(['nagios', 'email']),
                         [('nagios', 'NAGIOS'), ('email', 'EMAIL')])

    def test_the_configured_order_is_kept(self):
        registry.build = lambda name: name.upper()
        self.assertEqual([name for name, built in registry.build_all(['email', 'nagios'])],
                         ['email', 'nagios'])

    def test_a_name_that_is_not_an_interface_is_left_out(self):
        self.assertEqual(registry.build_all(['zabbix']), [])

    def test_a_typo_does_not_cost_the_names_spelled_right(self):
        #one bad line in a config file must not cost every notification the
        #cluster receives
        built = registry.build_all(['nagois', 'nagios'])
        self.assertEqual([name for name, interface in built], ['nagios'])

    def test_an_interface_that_will_not_build_is_left_out(self):
        #a missing client library, or a server that is down
        def broken(name):
            raise ImportError('no module named smtplib')
        registry.build = broken
        self.assertEqual(registry.build_all(['email']), [])

    def test_one_that_will_not_build_does_not_stop_the_others(self):
        def sometimes(name):
            if name == 'email':
                raise ImportError('no module named smtplib')
            return name.upper()
        registry.build = sometimes
        self.assertEqual(registry.build_all(['email', 'nagios']), [('nagios', 'NAGIOS')])

    def test_configuring_nothing_builds_nothing(self):
        self.assertEqual(registry.build_all([]), [])


if __name__ == '__main__':
    unittest.main()
