'''
Tests for EncryptionMonitor, which reads /etc/crypttab to report whether the
disk is encrypted and with which cipher.
'''
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, 'booting_vms'))

from EncryptionMonitor import EncryptionMonitor

HEADER = '#<target name> <source device> <key file> <options>\n'
ENTRY = 'sda3_crypt /dev/sda3 none aes-xts-plain64,luks\n'


class EncryptionMonitorTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def read(self, contents):
        path = os.path.join(self.tmp, 'crypttab')
        f = open(path, 'w')
        f.write(contents)
        f.close()
        return EncryptionMonitor(crypttab_path=path).get_encryption_info()

    def test_reports_the_cipher_from_the_options_column(self):
        #the options column, not the fourth character of the line, which is
        #what the original slice returned
        info = self.read(HEADER + ENTRY)
        self.assertEqual(info['is_encrypted'], 'yes')
        self.assertEqual(info['cipher'], 'aes-xts-plain64,luks')

    def test_no_entry_means_no_encryption(self):
        info = self.read(HEADER)
        self.assertEqual(info, {'is_encrypted':'no', 'cipher':'-'})

    def test_empty_crypttab_means_no_encryption(self):
        self.assertEqual(self.read(''), {'is_encrypted':'no', 'cipher':'-'})

    def test_entry_without_options_is_skipped(self):
        #a three column entry has no cipher to report, so it must not be
        #mistaken for an encrypted volume
        info = self.read('sda3_crypt /dev/sda3 none\n')
        self.assertEqual(info['is_encrypted'], 'no')

    def test_last_entry_wins(self):
        info = self.read(ENTRY + 'sdb1_crypt /dev/sdb1 none serpent-xts-plain64\n')
        self.assertEqual(info['cipher'], 'serpent-xts-plain64')

    def test_default_path_is_the_ubuntu_crypttab(self):
        self.assertEqual(EncryptionMonitor().crypttab_path, '/etc/crypttab')


if __name__ == '__main__':
    unittest.main()
