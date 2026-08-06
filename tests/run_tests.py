'''
Runs the unit test suite.

    $ docker compose -f docker/docker-compose.yml run --rm tests
    $ docker compose -f docker/docker-compose.yml run --rm tests \
          python tests/run_tests.py test_ssh_access_monitor

Unlike docker/smoke_test.py, which runs the probes against the fixtures baked
into the image, these tests build their own input in a temporary directory and
assert on the parsed result. They need no fixtures, no database and no cloud.
'''
import os
import sys
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS)

#the tree is laid out for deployment rather than for import: booting_vms is
#tarred into the VM image and running_vms/node is copied to the node hosts on
#its own, so neither is a package. Put the directories on the path instead.
for path in (ROOT,
             os.path.join(ROOT, 'booting_vms'),
             os.path.join(ROOT, 'running_vms', 'node'),
             os.path.join(ROOT, 'running_vms', 'cluster')):
    sys.path.insert(0, path)


def build_suite(names):
    loader = unittest.TestLoader()
    if names:
        return loader.loadTestsFromNames(names)
    return loader.discover(TESTS, pattern='test_*.py', top_level_dir=TESTS)


if __name__ == '__main__':
    suite = build_suite(sys.argv[1:])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
