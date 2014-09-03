# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from appengine.utils import testing

from appengine.path_mangler_hack import PathMangler
with PathMangler(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))):
  from appengine.test_results import main
  from appengine.test_results.handlers import builderstatehandler

from google.appengine.api import memcache

TEST_BUILDER_STATE = '{"masters":[]}'


class BuilderStateHandlerTest(testing.AppengineTestCase):

  app_module = main.app

  def setUp(self):
    super(BuilderStateHandlerTest, self).setUp()
    self.refresh_called = False
    self.refresh_result = None

    @classmethod
    def mock_refresh(cls):
      self.assertFalse(self.refresh_called)
      self.refresh_called = True
      return self.refresh_result
    self.mock(builderstatehandler.builderstate.BuilderState,
              'refresh_all_data', mock_refresh)

  def test_get_no_cache_refresh_fails(self):
    response = self.test_app.get('/builderstate', expect_errors=True)
    self.assertEqual(response.status_int, 500)
    self.assertTrue(self.refresh_called)

  def test_get_no_cache_refresh_succeeds(self):
    self.refresh_result = TEST_BUILDER_STATE
    response = self.test_app.get('/builderstate')
    self.assertEqual(response.status_int, 200)
    self.assertTrue(self.refresh_called)
    self.assertEqual(response.normal_body, TEST_BUILDER_STATE)
    self.assertEqual(response.content_type, 'application/json')

  def test_get_from_cache(self):
    memcache.set('builder_state', TEST_BUILDER_STATE)
    response = self.test_app.get('/builderstate')
    self.assertEqual(response.status_int, 200)
    self.assertFalse(self.refresh_called)
    self.assertEqual(response.normal_body, TEST_BUILDER_STATE)
    self.assertEqual(response.content_type, 'application/json')

  def test_update_refresh_fails(self):
    response = self.test_app.get('/updatebuilderstate', expect_errors=True)
    self.assertEqual(response.status_int, 500)
    self.assertTrue(self.refresh_called)

  def test_update_refresh_succeeds(self):
    self.refresh_result = TEST_BUILDER_STATE
    response = self.test_app.get('/updatebuilderstate')
    self.assertEqual(response.status_int, 200)
    self.assertTrue(self.refresh_called)
    self.assertEqual(response.normal_body, 'ok')
