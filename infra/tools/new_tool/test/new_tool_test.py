# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import os
import unittest

from infra.tools.new_tool import new_tool
import infra_libs


DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')


class TestArgParseOptions(unittest.TestCase):
  def test_add_argparse_options_smoke(self):
    parser = argparse.ArgumentParser()
    new_tool.add_argparse_options(parser)


class TestGenerateToolFiles(unittest.TestCase):
  def test_generate(self):
    with infra_libs.temporary_directory(prefix='new-tool-test-') as tempdir:
      toolname = 'test_tool'
      new_tool.generate_tool_files('test_tool', tempdir)
      self.assertTrue(os.path.isdir(os.path.join(tempdir, toolname)))
      self.assertTrue(os.path.isfile(os.path.join(tempdir, toolname,
                                                  '__init__.py')))
      self.assertTrue(os.path.isfile(os.path.join(tempdir, toolname,
                                                  '__main__.py')))
      self.assertTrue(os.path.isdir(os.path.join(tempdir, toolname, 'test')))
      self.assertTrue(os.path.isfile(os.path.join(tempdir, toolname, 'test',
                                                  '__init__.py')))

  def test_no_overwrite_tool(self):
    with infra_libs.temporary_directory(prefix='new-tool-test-') as tempdir:
      self.assertFalse(new_tool.generate_tool_files('test_tool', tempdir))
      self.assertTrue(new_tool.generate_tool_files('test_tool', tempdir))

  def test_missing_destination_dir(self):
    with infra_libs.temporary_directory(prefix='new-tool-test-') as tempdir:
      # When destination directory does not exist, just do nothing and return
      # a non-zero value.
      self.assertTrue(new_tool.generate_tool_files(
        'test_tool', os.path.join(tempdir, 'missing-directory')))


class TestGeneratePythonFile(unittest.TestCase):
  def test_generate_empty_file(self):
    with infra_libs.temporary_directory(prefix='new-tool-test-') as tempdir:
      filename = new_tool.generate_python_file(tempdir, 'test.py', None)
      self.assertTrue(os.path.isfile(filename))
      # Read the content and do some basic check
      with open(filename, 'r') as f:
        content = f.read()
      self.assertTrue(content.startswith(new_tool.COPYRIGHT_NOTICE))

      # Now make sure the file is not overwritten
      new_content = 'other content'
      with open(filename, 'w') as f:
        f.write(new_content)
      filename2 = new_tool.generate_python_file(tempdir, 'test.py', None)
      self.assertEqual(filename, filename2)
      with open(filename, 'r') as f:
        content = f.read()
      self.assertEqual(content, new_content)

  def test_generate_file_from_template(self):
    with infra_libs.temporary_directory(prefix='new-tool-test-') as tempdir:
      filename = new_tool.generate_python_file(
        tempdir, 'test.py', 'test_template', template_dir=DATA_DIR,
        value='Passed string.')
      self.assertTrue(os.path.isfile(filename))

      # Read the content
      with open(filename, 'r') as f:
        content = f.read()

      expected_content = (new_tool.COPYRIGHT_NOTICE
                          + 'This is a template used by the test suite.\n'
                          'Passed string.\n')
      self.assertEqual(content, expected_content)
