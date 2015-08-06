# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import subprocess
import sys
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, 'third_party'))

from glucose import util


class _UtilTestException(Exception):
  """Exception used inside tests."""


class TemporaryDirectoryTest(unittest.TestCase):
  def test_tempdir_no_error(self):
    with util.temporary_directory() as tempdir:
      self.assertTrue(os.path.isdir(tempdir))
      # This should work.
      with open(os.path.join(tempdir, 'test_tempdir_no_error.txt'), 'w') as f:
        f.write('nonsensical content')
    # And everything should have been cleaned up afterward
    self.assertFalse(os.path.isdir(tempdir))


  def test_tempdir_with_exception(self):
    try:
      with util.temporary_directory() as tempdir:
        self.assertTrue(os.path.isdir(tempdir))
        # Create a non-empty file to check that tempdir deletion works.
        with open(os.path.join(tempdir, 'test_tempdir_no_error.txt'), 'w') as f:
          f.write('nonsensical content')
        raise _UtilTestException()

    except _UtilTestException:
      pass  # this is supposed to happen
    else:
      raise AssertionError('No exception was raised')

    # And everything should have been cleaned up afterward
    self.assertFalse(os.path.isdir(tempdir))


def get_venv_python_path(env_path):
  # TODO: make that work on windows
  return os.path.join(env_path, 'bin', 'python')


# These tests are rather slow, because it's integration testing.
class VirtualEnvSetupTest(unittest.TestCase):
  def test_setup_virtualenv(self):
    with util.temporary_directory() as tempdir:
      util.setup_virtualenv(tempdir, relocatable=False)
      # Use a separate process instead of activating the virtualenv for
      # test isolation.

      # Check that modules from the virtualenv are used.
      output = subprocess.check_output(
        [get_venv_python_path(tempdir), '-c',
         'import wheel; print wheel.__file__'])
      self.assertTrue(output.startswith(tempdir))

  def test_setup_virtualenv_relocatable(self):
    with util.temporary_directory() as tempdir:
      util.setup_virtualenv(tempdir, relocatable=True)
      # Use a separate process instead of activating the virtualenv for
      # test isolation.

      # Check that modules from the virtualenv are used.
      output = subprocess.check_output(
        [get_venv_python_path(tempdir), '-c',
         'import wheel; print wheel.__file__'])
      self.assertTrue(output.startswith(tempdir))



class VirtualenvTest(unittest.TestCase):
  def test_check_venv_location(self):
    with util.Virtualenv(prefix='glyco-venv-test-') as venv:
      output = venv.check_output(['python', '-c',
                                  'import wheel; print wheel.__file__'])
      self.assertTrue(output.startswith(venv._venvdir))

  def test_check_pip_works(self):
    with util.Virtualenv(prefix='glyco-venv-test-') as venv:
      output = venv.check_output(['pip', '--version'])
      # 'pip --version' prints the full path to pip itself:
      # example: "pip 1.5.4 from /usr/lib/python2.7/dist-packages (python 2.7)"
      self.assertTrue(venv._venvdir in output)

  def test_check_call_smoke(self):
    with util.Virtualenv(prefix='glyco-venv-test-') as venv:
      venv.check_call(['pip', '--version'])


class Url2PathTest(unittest.TestCase):
  def test_path_to_url_to_path(self):
    # Use an existing file as a way to get an OS-specific absolute path.
    path = util.fileurl2path(util.path2fileurl(ROOT_DIR))
    self.assertEqual(path, ROOT_DIR)

  def test_url_to_path_to_url(self):
    url1 = 'file:///this/is/a/path'
    url2 = util.path2fileurl(util.fileurl2path(url1))
    self.assertEqual(url1, url2)

  def test_url_to_path_to_url_with_spaces(self):
    url1 = 'file:///absolute/path/with%20spaces'
    url2 = util.path2fileurl(util.fileurl2path(url1))
    self.assertEqual(url1, url2)

  def test_url_to_path_to_url_absolute_path(self):
    url1 = 'file:///absolutely/normal/path/'
    url2 = util.path2fileurl(util.fileurl2path(url1))
    self.assertEqual(url1, url2)

  def test_errors_out_with_relative_path(self):
    path = os.path.join('part', 'of', 'path')
    with self.assertRaises(ValueError):
      util.path2fileurl(path)


if __name__ == '__main__':
  unittest.main()
