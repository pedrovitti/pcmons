'''
Every source file parses.

Most modules are imported by some other test, which already proves they parse,
but not all are -- and this repository has a history of shipping files that do
not: an "else if", tabs and spaces mixed in one block, a monitor with 20KB of
tar appended to it. Those only surfaced when a VM booted.

Nothing here needs a fake, a fixture or a database. If this fails, something is
broken in a way no other test will explain clearly.
'''
import os
import py_compile
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)

SKIP = ('.git', 'monitoring.tar')


def sources(extension):
    found = []
    for directory, subdirectories, names in os.walk(ROOT):
        subdirectories[:] = [name for name in subdirectories
                             if not name.startswith('.') and name not in SKIP]
        for name in names:
            if name.endswith(extension):
                found.append(os.path.join(directory, name))
    return sorted(found)


class SyntaxTest(unittest.TestCase):

    def setUp(self):
        #compile to a temp file so no .pyc lands next to the sources
        handle, self.compiled = tempfile.mkstemp(suffix='.pyc')
        os.close(handle)

    def tearDown(self):
        os.remove(self.compiled)

    def test_every_python_file_compiles(self):
        files = sources('.py')
        #a walk that finds nothing would pass this test silently
        self.assertGreater(len(files), 20)
        for path in files:
            try:
                py_compile.compile(path, cfile=self.compiled, doraise=True)
            except py_compile.PyCompileError, error:
                self.fail('%s: %s'%(os.path.relpath(path, ROOT), error))

    def test_every_shell_script_parses(self):
        files = sources('.sh')
        self.assertGreater(len(files), 2)
        for path in files:
            #sh -n parses without running: these scripts move files about and
            #reload services, so running them is not an option
            process = subprocess.Popen(['sh', '-n', path], stderr=subprocess.PIPE)
            stderr = process.communicate()[1]
            self.assertEqual(process.returncode, 0,
                             '%s: %s'%(os.path.relpath(path, ROOT), stderr.strip()))

    def test_the_python_files_are_free_of_mixed_indentation(self):
        #a block indented with tabs in one line and spaces in the next parses
        #differently under python 2 and 3, and reads the same either way. Three
        #of the security monitors arrived like that.
        for path in sources('.py'):
            handle = open(path, 'rb')
            try:
                lines = handle.readlines()
            finally:
                handle.close()
            for number, line in enumerate(lines, 1):
                indent = line[:len(line) - len(line.lstrip())]
                self.assertFalse('\t' in indent and ' ' in indent,
                                 '%s:%d mixes tabs and spaces'%(os.path.relpath(path, ROOT), number))


if __name__ == '__main__':
    unittest.main()
