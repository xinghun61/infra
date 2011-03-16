#!/usr/bin/env python
# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys
import unittest
import urllib

try:
  import simplejson as json
except ImportError:
  import json

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT_DIR, '..'))

import local_gae


class IntegrationTest(unittest.TestCase):
  def setUp(self):
    self.local_gae = local_gae.LocalGae()
    self.local_gae.start_server()
    self.url = 'http://127.0.0.1:%d/' % self.local_gae.port

  def tearDown(self):
    if self.local_gae:
      self.local_gae.stop_server()
    self.local_gae = None

  def test_all_status(self):
    out = urllib.urlopen(self.url + 'allstatus').read()
    self.assertEqual(87, len(out))

  def test_status(self):
    out = urllib.urlopen(self.url + 'status').read()
    self.assertEqual('1', out)

  def test_current(self):
    out = urllib.urlopen(self.url + 'current').read()
    self.assertTrue(100 < len(out))
    self.assertTrue(out.startswith('<html>'))

  def test_current_raw(self):
    out = urllib.urlopen(self.url + 'current?format=raw').read()
    # Default value.
    self.assertEqual('welcome to status', out)

  def test_current_json(self):
    # pylint: disable=E1103
    out = json.load(urllib.urlopen(self.url + 'current?format=json'))
    expected = [
        'date', 'username', 'message', 'general_state', 'can_commit_freely',
    ]
    # TODO(maruel): Test actual values.
    self.assertEqual(sorted(expected), sorted(out.keys()))

  def test_status_push(self):
    # Set a password, force status with password.
    data = {
        'message': 'foo',
        'password': 'bleh',
        'username': 'user1',
    }
    out = urllib.urlopen(self.url + 'status', urllib.urlencode(data)).read()
    # TODO(maruel): Verify content is a redirect to '/'.
    self.assertTrue(100 < len(out))
    # TODO(maruel): THIS IS WRONG. Should have failed.
    out = urllib.urlopen(self.url + 'current?format=raw').read()
    self.assertEqual('foo', out)
    data['message'] = 'bar'
    out = urllib.urlopen(self.url + 'status', urllib.urlencode(data)).read()
    self.assertTrue(100 < len(out))
    out = urllib.urlopen(self.url + 'current?format=raw').read()
    # TODO(maruel): THIS IS WRONG. It should be bar once the password is
    # correctly set.
    self.assertEqual('foo', out)
    #self.assertEqual('bar', out)

  def test_root(self):
    out = urllib.urlopen(self.url).read()
    self.assertTrue(100 < len(out))


if __name__ == '__main__':
  unittest.main()
