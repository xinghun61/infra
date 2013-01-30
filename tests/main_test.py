#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib
import json
import logging
import os
import re
import sys
import unittest
import urllib2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

import fill
import local_gae


class TestCase(unittest.TestCase):
  def setUp(self):
    super(TestCase, self).setUp()
    # Restart the server on each test. It's a bit slow but safer.
    self.local_gae = local_gae.LocalGae()
    self.local_gae.start_server(logging.getLogger().isEnabledFor(logging.DEBUG))
    self.url = 'http://127.0.0.1:%d/' % self.local_gae.port

  def tearDown(self):
    if self.local_gae:
      self.local_gae.stop_server()
    self.local_gae = None
    super(TestCase, self).tearDown()

  def get(self, suburl):
    return self.local_gae.get(suburl)

  def post(self, suburl, data):
    return self.local_gae.post(suburl, data)

  def set_admin_pwd(self, password):
    # There will be no entities until main() has been called. So do a dummy
    # request first.
    hashvalue = hashlib.sha1(password).hexdigest()
    self.get('doesnt_exist')

    # First verify the default value exists and then override its value.
    count = self.local_gae.query(
        'import base_page\n'
        'print db.GqlQuery("SELECT * FROM Passwords").count()\n')
    assert int(count) == 1
    count = self.local_gae.query(
        'import base_page\n'
        'p = db.GqlQuery("SELECT * FROM Passwords").get()\n'
        + ('p.password_sha1 = %r\n' % hashvalue) +
        'p.put()\n')
    count = self.local_gae.query(
        'import base_page\n'
        'print db.GqlQuery("SELECT * FROM Passwords").count()\n')
    assert int(count) == 1


class StatusTest(TestCase):
  def test_all_status(self):
    out = self.get('allstatus').splitlines()
    out = [i for i in out if i]
    self.assertEquals(2, len(out))
    self.assertEquals('Who,When,GeneralStatus,Message', out[0])
    self.assertTrue(
        re.match('none,.+?, \d+?, .+?,open,welcome to status', out[1]), out[1])

  def test_status(self):
    self.assertEqual('1', self.get('status'))

  def test_current(self):
    out = self.get('current')
    self.assertTrue(100 < len(out))
    self.assertTrue(out.startswith('<html>'))

  def test_current_raw(self):
    # Default value.
    self.assertEqual('welcome to status', self.get('current?format=raw'))

  def test_current_json(self):
    # pylint: disable=E1103
    out = json.loads(self.get('current?format=json'))
    expected = [
        'date', 'username', 'message', 'general_state', 'can_commit_freely',
    ]
    # TODO(maruel): Test actual values.
    self.assertEqual(sorted(expected), sorted(out.keys()))

  def test_status_push(self):
    self.assertEqual('welcome to status', self.get('current?format=raw'))
    self.assertEqual('welcome to status', self.get('current?format=raw'))
    # Set a password, force status with password.
    self.set_admin_pwd('bleh')
    data = {
        'message': 'foo',
        'password': 'bleh',
        'username': 'user1',
    }
    self.assertEqual('OK', self.post('status', data))
    self.assertEqual('foo', self.get('current?format=raw'))
    data['message'] = 'bar'
    data['password'] = 'wrong password'
    self.assertEqual('', self.post('status', data))
    # Wasn't updated since the password was wrong.
    self.assertEqual('foo', self.get('current?format=raw'))
    data['message'] = 'boo'
    data['password'] = 'bleh'
    self.assertEqual('OK', self.post('status', data))
    self.assertEqual('boo', self.get('current?format=raw'))

  def test_root(self):
    self.assertTrue(100 < len(self.get('')))


class LkgrTest(TestCase):
  def test_lkgr(self):
    self.assertEqual('', self.get('lkgr'))

  def test_lkgr_set(self):
    self.set_admin_pwd('bleh')
    data = {
        'revision': 42,
        'password': 'bleh',
        'success': '1',
        'steps': '',
    }
    out = self.post('revisions', data)
    self.assertEqual('', out)
    self.assertEqual('42', self.get('lkgr'))
    data['password'] = 'wrongpassword'
    data['revision'] = 23
    out = self.post('revisions', data)
    self.assertEqual('', out)
    self.assertEqual('42', self.get('lkgr'))
    data['password'] = 'bleh'
    data['revision'] = 31337
    out = self.post('revisions', data)
    self.assertEqual('', out)
    self.assertEqual('31337', self.get('lkgr'))


class CommitQueueTest(TestCase):
  def _fill(self):
    # Example dump taken from a run.
    total = 0
    for packet in fill.load_packets():
      total += int(self.post('cq/receiver', packet))
    self.assertEquals(9, total)

  def test_summary_json(self):
    self._fill()
    self.assertEquals(7, len(json.loads(self.get('cq/?format=json'))))
    self.assertEquals([], json.loads(self.get('cq/doesntexist?format=json')))
    self.assertEquals(
        4,
        len(json.loads(self.get(
          urllib2.quote('cq/bar@chromium.org') + '?format=json'))))
    self.assertEquals(
        3,
        len(json.loads(self.get(
          urllib2.quote('cq/joe@chromium.org') + '?format=json'))))


if __name__ == '__main__':
  logging.basicConfig(level=
      [logging.WARNING, logging.INFO, logging.DEBUG][
        min(2, sys.argv.count('-v'))])
  unittest.main()
