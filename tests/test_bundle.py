'''
Tests for build_monitoring_bundle.sh, which packs the agent into the tar that
Startup.sh unpacks into /opt/monitoring on a booting VM.

The bundle lists its contents by hand, so a probe added to booting_vms/ and not
to that list ships an agent that cannot import itself -- which is the state the
repository was in for years. These tests compare the list against the sources.

The script is run against a copy, so nothing is written to the working tree.
'''
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
AGENT = os.path.join(ROOT, 'booting_vms')


class BundleTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        agent = os.path.join(cls.tmp, 'booting_vms')
        shutil.copytree(AGENT, agent)
        script = os.path.join(agent, 'build_monitoring_bundle.sh')
        os.chmod(script, 0o755)
        cls.output = subprocess.check_output([script], stderr=subprocess.STDOUT)
        cls.archive = os.path.join(agent, 'monitoring.tar')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def members(self):
        tar = tarfile.open(self.archive)
        try:
            return sorted(tar.getnames())
        finally:
            tar.close()

    def test_the_bundle_is_built(self):
        self.assertTrue(os.path.exists(self.archive))

    def test_it_ships_every_agent_source(self):
        sources = sorted(name for name in os.listdir(AGENT) if name.endswith('.py'))
        self.assertEqual(self.members(), sources)

    def test_it_ships_everything_the_agent_imports(self):
        #the check that matters: Monitor.py imports its probes by name, and an
        #import that is not in the bundle is a crash on the first boot
        source = open(os.path.join(AGENT, 'Monitor.py')).read()
        imported = re.findall(r'^from (\w+) import|^import (\w+)$', source, re.M)
        modules = set(name for pair in imported for name in pair if name)
        shipped = set(name[:-3] for name in self.members())
        for module in modules:
            if module in ('commands', 'logging', 'time', 'xmlrpclib', 'datetime', 'socket'):
                continue  #standard library, already on the VM
            self.assertIn(module, shipped)

    def test_it_ships_the_settings_the_agent_reads(self):
        self.assertIn('settings.py', self.members())

    def test_it_carries_no_directories(self):
        #Startup.sh untars straight into /opt/monitoring and runs Monitor.py
        #from there, so the layout has to be flat
        for name in self.members():
            self.assertNotIn('/', name)

    def test_it_carries_no_macos_metadata(self):
        #bsdtar adds AppleDouble ._ entries unless COPYFILE_DISABLE is set,
        #and they end up in the VM image
        for name in self.members():
            self.assertFalse(name.startswith('._'), name)

    def test_the_bundled_sources_match_the_repository(self):
        #a stale bundle is worse than none: it boots and reports old readings
        tar = tarfile.open(self.archive)
        try:
            for name in tar.getnames():
                bundled = tar.extractfile(name).read()
                current = open(os.path.join(AGENT, name), 'rb').read()
                self.assertEqual(bundled, current, name)
        finally:
            tar.close()


if __name__ == '__main__':
    unittest.main()
