# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for ../git_cache_updater.py"""

import argparse
import unittest
import mock
import os
import subprocess

from infra_libs import utils
from infra.services.git_cache_updater import git_cache_updater


fake_cookie = '\t'.join([
    '.googlesource.com', 'TRUE', '/', 'TRUE', '2147483647', 'o', 'foo=barbaz'])


class CacheUpdaterTest(unittest.TestCase):
  def test_arguments(self):
    parser = argparse.ArgumentParser()
    git_cache_updater.add_argparse_options(parser)
    args = parser.parse_args(['--project', 'http://asdf.com'])
    self.assertEqual(args.project, 'http://asdf.com')
    self.assertRaises(SystemExit, parser.parse_args, [])

  def test_get_cookies(self):
    with utils.temporary_directory() as tempdir:
      fake_cookie_file = os.path.join(tempdir, 'gitcookie')
      with open(fake_cookie_file, 'wb') as f:
        f.write(fake_cookie)

      with mock.patch.object(subprocess, 'check_output',
                             return_value=fake_cookie_file) as _:
        return git_cache_updater.get_cookies()

  def test_get_no_cookies(self):
    with utils.temporary_directory() as tempdir:
      fake_cookie_file = os.path.join(tempdir, 'gitcookie')
      with open(fake_cookie_file, 'wb') as f:
        f.write(fake_cookie)

      with mock.patch.object(subprocess, 'check_output',
                             return_value=None) as _:
        return git_cache_updater.get_cookies()

  @mock.patch('requests.get')
  def test_get_proj_list(self, req_get):
    req_get.return_value = mock.Mock(
        text='foo\nbar\nbaz\nall-projects',
        status_code=200)
    with mock.patch.object(
          git_cache_updater, 'get_cookies', return_value=None) as _:
      result = git_cache_updater.get_project_list('proj')
    self.assertEquals(result, ['projfoo', 'projbar', 'projbaz'])
    req_get.assert_called_with('proj?format=TEXT', cookies=None)

  @mock.patch('requests.get')
  def test_get_proj_list_403(self, req_get):
    req_get.return_value = mock.Mock(
        text='foo\nbar\nbaz\nall-projects',
        status_code=403)
    with mock.patch.object(
          git_cache_updater, 'get_cookies', return_value=None) as _:
      self.assertRaises(
          git_cache_updater.FailedToFetchProjectList,
          git_cache_updater.get_project_list, 'proj')

  def test_run(self):
    with mock.patch.object(
        git_cache_updater, 'get_project_list', return_value=['a', 'b']) as _:
      with utils.temporary_directory() as tempdir:
        workdir = os.path.join(tempdir, 'workdir')
        with mock.patch.object(subprocess, 'call') as sub_m:
          git_cache_updater.run('aproj', workdir)
          self.assertTrue(os.path.isdir(workdir))
          self.assertEquals(sub_m.call_count, 2)

  def test_run2(self):
    with mock.patch.object(
        git_cache_updater, 'get_project_list', return_value=['a', 'b']) as _:
      with utils.temporary_directory() as tempdir:
        with mock.patch.object(subprocess, 'call') as sub_m:
          git_cache_updater.run('aproj', tempdir)
          self.assertEquals(sub_m.call_count, 2)

