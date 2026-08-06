'''
Tests for the three configuration modules.

They are plain Python, so there is little to get wrong -- except that the
environment overrides are the interface anyone deploying this actually uses,
and the README documents both the variable names and the defaults. These tests
are what keeps those two in step.

The modules read the environment at import time, so each case re-imports the
module under a set variable.
'''
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
for path in (ROOT,
             os.path.join(ROOT, 'booting_vms'),
             os.path.join(ROOT, 'running_vms', 'node'),
             os.path.join(ROOT, 'running_vms', 'cluster')):
    sys.path.insert(0, path)


def reimport(name, **environment):
    '''Import a config module afresh with the given variables set.'''
    saved = dict((key, os.environ.get(key)) for key in environment)
    try:
        for key, value in environment.items():
            os.environ[key] = value
        sys.modules.pop(name, None)
        module = __import__(name)
        return module
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        sys.modules.pop(name, None)


class AgentSettingsTest(unittest.TestCase):
    '''booting_vms/settings.py -- travels inside the VM image.'''

    def test_defaults_match_the_documented_ones(self):
        settings = reimport('settings')
        self.assertEqual(settings.SERVER, 'http://150.162.63.32')
        self.assertEqual(settings.SERVER_PORT, '60001')

    def test_the_server_can_be_set_from_the_environment(self):
        #this is why it is an override: the address is baked into an image
        settings = reimport('settings', PCMONS_SERVER='http://10.0.0.1',
                            PCMONS_SERVER_PORT='7000')
        self.assertEqual(settings.SERVER, 'http://10.0.0.1')
        self.assertEqual(settings.SERVER_PORT, '7000')

    def test_the_port_stays_a_string(self):
        #it is interpolated into the server url, never used as a number
        settings = reimport('settings', PCMONS_SERVER_PORT='7000')
        self.assertIsInstance(settings.SERVER_PORT, str)


class ClusterConfigTest(unittest.TestCase):
    '''running_vms/cluster/cluster_config.py -- the controller.'''

    def test_defaults_match_the_documented_ones(self):
        config = reimport('cluster_config')
        self.assertEqual(config.LISTEN_IP, '150.162.63.32')
        self.assertEqual(config.LISTEN_PORT, 60001)

    def test_the_listen_address_can_be_set_from_the_environment(self):
        config = reimport('cluster_config', PCMONS_LISTEN_IP='0.0.0.0',
                          PCMONS_LISTEN_PORT='7001')
        self.assertEqual(config.LISTEN_IP, '0.0.0.0')
        self.assertEqual(config.LISTEN_PORT, 7001)

    def test_the_port_is_a_number(self):
        #SimpleXMLRPCServer binds (host, port) and rejects a string
        config = reimport('cluster_config', PCMONS_LISTEN_PORT='7001')
        self.assertIsInstance(config.LISTEN_PORT, int)


class NodeConfigTest(unittest.TestCase):
    '''running_vms/node/node_config.py -- copied to every node host.'''

    def test_defaults_match_the_documented_ones(self):
        config = reimport('node_config')
        self.assertEqual(config.LISTEN_IP, 'stratus.lrg.ufsc.br')
        self.assertEqual(config.LISTEN_PORT, 60000)
        self.assertEqual(config.PATH_TO_LOG_FILE, '/var/log/Monitoring_Cloud_Client.log')

    def test_every_setting_can_be_set_from_the_environment(self):
        #the point of the overrides: this file is copied to every node, and
        #editing it on each one is how they drift apart
        config = reimport('node_config', PCMONS_NODE_LISTEN_IP='0.0.0.0',
                          PCMONS_NODE_LISTEN_PORT='7002',
                          PCMONS_NODE_LOG_FILE='/tmp/node.log')
        self.assertEqual(config.LISTEN_IP, '0.0.0.0')
        self.assertEqual(config.LISTEN_PORT, 7002)
        self.assertEqual(config.PATH_TO_LOG_FILE, '/tmp/node.log')

    def test_the_port_is_a_number(self):
        config = reimport('node_config', PCMONS_NODE_LISTEN_PORT='7002')
        self.assertIsInstance(config.LISTEN_PORT, int)


class DocumentedVariablesTest(unittest.TestCase):

    def test_the_readme_documents_every_override(self):
        #the table in the README is the only place these are listed together
        readme = open(os.path.join(ROOT, 'README.md')).read()
        for variable in ('PCMONS_SERVER', 'PCMONS_SERVER_PORT',
                         'PCMONS_LISTEN_IP', 'PCMONS_LISTEN_PORT',
                         'PCMONS_NODE_LISTEN_IP', 'PCMONS_NODE_LISTEN_PORT',
                         'PCMONS_NODE_LOG_FILE'):
            self.assertIn(variable, readme)


if __name__ == '__main__':
    unittest.main()
