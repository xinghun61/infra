# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import json
import mock
import re
import webapp2
import webtest

from google.appengine.api import users

from gae_libs.http.http_client_appengine import HttpClientAppengine
from gae_libs.testcase import TestCase
from handlers.crash import crash_config
from handlers.crash.update_component_config import GetComponentClassifierConfig
from handlers.crash.update_component_config import UpdateComponentConfig
from libs.http.retry_http_client import RetryHttpClient
from model.crash.crash_config import CrashConfig


_MOCK_OWNERS_MAPPINGS = {
  'component-to-team': {
      "compoA": "team1@chromium.org",
      "compoB": "team2@chromium.org",
      "compoD": "team4@chromium.org"
    },
  'dir-to-component': {
      "dirA": "compoA",
      "dirB": "compoB",
      "dirC": "compoB",
      "dirE": "compoE",
    }
}

_MOCK_PREDATOR_MAPPINGS = {
  'path_function_component': [
    [
      "file1",
      "fn_a",
      "compoA"
    ],
    [
      "dirD",
      "",
      "compoD\ncompoA"
    ],
    [
      "file2",
      "",
      "compoF"
    ]
  ]
}

_MOCK_CONFIG = {
    'component_info': [
        {'dirs': ['file2'],
         'component': 'compoF'},
        {'dirs': ['dirD'],
         'component': 'compoD',
         'team': 'team4@chromium.org'},
        {'dirs': ['src/dirE'],
         'component': 'compoE'},
        {'dirs': ['src/dirC', 'src/dirB'],
         'component': 'compoB',
         'team': 'team2@chromium.org'},
        {'dirs': ['src/dirA', 'file1', 'dirD'],
         'function': 'fn_a',
         'component': 'compoA',
         'team': 'team1@chromium.org'}
    ]
}


class DummyHttpClient(HttpClientAppengine):
  def __init__(self):
    super(DummyHttpClient, self).__init__()
    self.requests = []
    self.request_count = 0

  def Get(self, url, params=None, timeout_seconds=60,
          max_retries=5, retry_backoff=1.5, headers=None):
    if url == 'mock_owners_mapping.json':
      return 200, _MOCK_OWNERS_MAPPINGS
    elif url == 'mock_predator_mapping.json':
      return 200, _MOCK_PREDATOR_MAPPINGS
    else:
      return 500, {}


class UpdateComponentConfigTest(TestCase):
  """Tests utility functions and ``CrashConfig`` handler."""
  app_module = webapp2.WSGIApplication([
      ('/crash/update-config', UpdateComponentConfig),
  ], debug=True)

  def setUp(self):
    super(UpdateComponentConfigTest, self).setUp()
    self.http_client_for_git = self.GetMockHttpClient()

  def testGetComponentClassifierConfig(self):
    component_classifier_config = GetComponentClassifierConfig(
        'mock_owners_mapping.json', 'mock_predator_mapping.json',
        DummyHttpClient())
    self.assertEqual(_MOCK_CONFIG, component_classifier_config)

  def testGetComponentClassifierConfigNoOWNERS(self):
    component_classifier_config = GetComponentClassifierConfig(
        'mock_no_owner', 'mock_predator', DummyHttpClient())
    self.assertIsNone(component_classifier_config)

  def testGetComponentClassifierConfigNoPredator(self):
    component_classifier_config = GetComponentClassifierConfig(
        'mock_owners_mapping.json', 'mock_predator', DummyHttpClient())
    self.assertIsNone(component_classifier_config)

  @mock.patch(
      'handlers.crash.update_component_config.GetComponentClassifierConfig')
  def testHandleGet(self, mocked_get_component_classifier_config):
    mocked_get_component_classifier_config.return_value = _MOCK_CONFIG
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)
    self.test_app.get('/crash/update-config')
    self.assertDictEqual(_MOCK_CONFIG, CrashConfig.Get().component_classifier)
