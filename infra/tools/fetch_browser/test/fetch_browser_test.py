# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for ../fetch_browser.py"""

import argparse
import mock
import os
import requests
import sys
import time
import unittest
import zipfile

from infra.tools.fetch_browser import chrome
from infra.tools.fetch_browser import fetch_browser

from infra_libs.utils import temporary_directory


class FakeRequest(object):
  def __init__(self, content):
    self.content = content
    self.text = content

  def iter_content(self, size):
    index = 0
    while True:
      if index == len(self.content):
        return
      until = min(index + size, len(self.content))
      yield self.content[index:until]
      index = until


class FetchBrowserTests(unittest.TestCase):

  def test_arguments(self):
    parser = argparse.ArgumentParser()
    fetch_browser.add_argparse_options(parser)
    args = parser.parse_args(['firefox', '--output-json', 'some_path'])
    self.assertEqual(args.output_json, 'some_path')
    self.assertEqual(args.browser, ['firefox'])

  def test_omaha(self):
    text = ('os,channel,current_version,previous_version,current_reldate,'
            'previous_reldate,branch_base_commit,branch_base_position,'
            'branch_commit,base_webkit_position,true_branch,v8_version\n'
            'linux,stable,43.0.2357.134,43.0.2357.132,07/14/15,07/07/15,'
            '59d4494849b405682265ed5d3f5164573b9a939b,323860,'
            '1bceb284c5249ef7f5cda9e45cbeed43fbec9fa0,193137,master,'
            '4.3.61.38')
    req = FakeRequest(text)
    with mock.patch.object(requests, 'get', return_value=req) as mock_get:
      self.assertEqual(
          chrome.get_version_from_omaha('stable', 'linux2'), '43.0.2357.134')
    mock_get.assert_called_once_with(
        'https://omahaproxy.appspot.com/all?os=linux&channel=stable')

  def test_garbage_collect(self):
    with temporary_directory() as tmp:
      test_dir = os.path.join(tmp, 'somedir')
      os.mkdir(test_dir)
      fetch_browser.garbage_collect(tmp)
      self.assertTrue(os.path.isdir(test_dir))

      two_months_ago = time.time() - (60 * 60 * 24 * 30 * 2)
      os.utime(test_dir, (two_months_ago, two_months_ago))
      fetch_browser.garbage_collect(tmp)
      self.assertFalse(os.path.isdir(test_dir))
      fetch_browser.garbage_collect(tmp)

  def test_fetch_chrome(self):
    fake_version = '43.0.2357.134'
    with temporary_directory() as tmp:
      cache_dir = os.path.join(tmp, 'cache_dir')
      fake_zip = os.path.join(tmp, 'fake.zip')
      with zipfile.ZipFile(fake_zip, 'w') as zf:
        fake_chrome = os.path.join(tmp, 'fake_chrome')
        with open(fake_chrome, 'w') as f:
          f.write('foobar')
        zf.write(fake_chrome, 'chrome-precise64/chrome')
      with open(fake_zip, 'rb') as f:
        with mock.patch.object(
            requests, 'get', return_value=FakeRequest(f.read())) as mock_get:
          chrome_path, version = chrome.fetch_chrome(
              cache_dir, fake_version, 'linux2')
      mock_get.assert_called_once_with(
          'https://storage.googleapis.com/chrome-unsigned/desktop-W15K3Y/'
          '%s/precise64/chrome-precise64.zip' % fake_version)

      self.assertEquals(
          chrome_path, os.path.join(
              cache_dir, 'chrome-linux-%s' % fake_version,
              'chrome-precise64', 'chrome'))
      self.assertEquals(version, fake_version)
      self.assertTrue(os.path.isdir(cache_dir))
      self.assertTrue(os.path.isfile(chrome_path))
      with open(chrome_path, 'r') as f:
        self.assertEquals(f.read(), 'foobar')
