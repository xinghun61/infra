# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import alerts
import annotations
import datetime
import json
import os
import unittest
import webtest

from components import auth
from components import auth_testing

from google.appengine.api import memcache
from google.appengine.ext import testbed

from testing_utils import testing

class AnnotationsTest(testing.AppengineTestCase):
  app_module = annotations.app

  def setUp(self):
    super(AnnotationsTest, self).setUp()

    self.source_ip = '192.168.2.2'
    self.auth_app = webtest.TestApp(
        auth.create_wsgi_application(debug=True),
        extra_environ={
          'REMOTE_ADDR': self.source_ip,
          'SERVER_SOFTWARE': os.environ['SERVER_SOFTWARE'],
        })

  def test_get_no_annotations(self):
    auth_testing.mock_get_current_identity(self)

    res = self.test_app.get('/api/v1/annotations')
    self.assertEqual(res.body, '[]')

  def test_add_snoozetime(self):
    auth_testing.mock_get_current_identity(self)
    self.mock(auth, 'is_group_member', lambda group: True)

    res = self.test_app.post_json(
        '/api/v1/annotations/abc', [{"add":{"snoozeTime":123}}])

    data = res.json
    self.assertEqual(data['snoozeTime'], 123)
    self.assertEqual(data['bugs'], [])
    self.assertEqual(data['key'], 'abc')

  def test_change_snoozetime(self):
    self.test_add_snoozetime()
    res = self.test_app.post_json(
        '/api/v1/annotations/abc', [{"add":{"snoozeTime":234}}])
    data = res.json
    self.assertEqual(data['snoozeTime'], 234)
    self.assertEqual(data['bugs'], [])
    self.assertEqual(data['key'], 'abc')

  def test_remove_snoozetime(self):
    self.test_add_snoozetime()
    res = self.test_app.post_json(
        '/api/v1/annotations/abc', [{"remove":{"snoozeTime":True}}])

    data = res.json
    self.assertEqual(data['snoozeTime'], None)
    self.assertEqual(data['bugs'], [])
    self.assertEqual(data['key'], 'abc')

  def test_add_bugs(self):
    auth_testing.mock_get_current_identity(self)
    self.mock(auth, 'is_group_member', lambda group: True)

    res = self.test_app.post_json(
        '/api/v1/annotations/abc', [{"add":{"bugs":["1","2"]}}])
    data = res.json
    self.assertEqual(data['snoozeTime'], None)
    self.assertEqual(
        sorted(data['bugs']), sorted(
            ["https://crbug.com/1", "https://crbug.com/2"]))
    self.assertEqual(data['key'], 'abc')

  def test_add_bad_bug(self):
    auth_testing.mock_get_current_identity(self)
    self.mock(auth, 'is_group_member', lambda group: True)

    self.test_app.post_json(
        '/api/v1/annotations/abc', [{"add":{"bugs":['wat']}}], status=400)

  def test_update_bugs(self):
    self.test_add_bugs()
    res = self.test_app.post_json(
        '/api/v1/annotations/abc', [
            {"add":{"bugs":["3", "4"]},"remove":{"bugs":["1"]}}])

    data = res.json
    self.assertEqual(data['snoozeTime'], None)
    self.assertEqual(
        sorted(data['bugs']), sorted(
            ["https://crbug.com/2", "https://crbug.com/3",
             "https://crbug.com/4"]))
    self.assertEqual(data['key'], 'abc')

  def test_large_key_still_stores(self):
    auth_testing.mock_get_current_identity(self)
    self.mock(auth, 'is_group_member', lambda group: True)

    # App engine limits keys at 500 bytes. We want to store all of a key, since
    # the end of it is important as well.
    key = 'a'*501

    res = self.test_app.post_json(
        '/api/v1/annotations/%s' % key, [{"add":{"bugs":["1"]}}])

    data = res.json
    self.assertEqual(data['snoozeTime'], None)
    self.assertEqual(data['bugs'], ["https://crbug.com/1"])
    self.assertEqual(data['key'], key)

  def test_get_all(self):
    annotations.Annotation(
        key=annotations.Annotation.annotation_key("testkey"),
        bugs=["https://crbug.com/123"], snooze_time=999,
        alert_key="testkey").put()

    result = self.test_app.get('/api/v1/annotations').json
    self.assertEqual(len(result), 1)
    itm = result[0]
    self.assertEqual(itm['key'], 'testkey')
    self.assertEqual(itm['bugs'], ["https://crbug.com/123"])
    self.assertEqual(itm['snoozeTime'], 999)

  def test_get_only_bugs(self):
    annotations.Annotation(
        key=annotations.Annotation.annotation_key("testkey"),
        bugs=["https://crbug.com/123"], alert_key="testkey").put()

    result = self.test_app.get('/api/v1/annotations').json
    self.assertEqual(len(result), 1)
    itm = result[0]
    self.assertEqual(itm['key'], 'testkey')
    self.assertEqual(itm['bugs'], ["https://crbug.com/123"])
    self.assertEqual(itm['snoozeTime'], None)

  def test_get_only_snooze(self):
    annotations.Annotation(
        key=annotations.Annotation.annotation_key("testkey"),
        snooze_time=999, alert_key="testkey").put()

    result = self.test_app.get('/api/v1/annotations').json
    self.assertEqual(len(result), 1)
    itm = result[0]
    self.assertEqual(itm['key'], 'testkey')
    self.assertEqual(itm['bugs'], [])
    self.assertEqual(itm['snoozeTime'], 999)

  def test_delete_old_annotation(self):
    annotation = annotations.Annotation(
        key=annotations.Annotation.annotation_key("testkey"),
        alert_key="testkey")
    annotation.put()
    annotation.modification_time = (
        datetime.datetime.now() - datetime.timedelta(days=2))
    key = annotation.put()

    self.mock(
        annotations, 'ANNOTATION_EXPIRATION_TIME',
        datetime.timedelta(days=1))

    self.assertIsNotNone(key.get())
    self.test_app.get(
        '/internal/cron/cleanup_old_annotations',
        headers={'X-AppEngine-Cron': 'true'})
    self.assertIsNone(key.get())

  def test_dont_delete_young_annotation(self):
    annotation = annotations.Annotation(
        key=annotations.Annotation.annotation_key("testkey"),
        alert_key="testkey")
    annotation.modification_time = (
        datetime.datetime.now() - datetime.timedelta(hours=1))
    key = annotation.put()

    self.mock(
        annotations, 'ANNOTATION_EXPIRATION_TIME',
        datetime.timedelta(days=1))

    self.assertIsNotNone(key.get())
    self.test_app.get(
        '/internal/cron/cleanup_old_annotations',
        headers={'X-AppEngine-Cron': 'true'})
    self.assertIsNotNone(key.get())

  def test_normal_user_cant_delete_annotations(self):
    self.test_app.get('/internal/cron/cleanup_old_annotations', status=403)

class BugValidationTest(unittest.TestCase):
  def test_is_int(self):
    self.assertEqual(
        annotations.bug_validator(None, 123), "https://crbug.com/123")

  def test_is_crbug(self):
    self.assertIsNone(
        annotations.bug_validator(None, "https://crbug.com/123123"))

  def test_is_bugs_chromium_org(self):
    self.assertIsNone(annotations.bug_validator(
            None, "https://bugs.chromium.org/p/chromium/issues/list"))

  def test_bad_value(self):
    with self.assertRaises(annotations.db.BadValueError):
      annotations.bug_validator(None, "<script>XSS</script>")
