# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import json
import re
import webapp2
import webtest

from google.appengine.api import users

from gae_libs.testcase import TestCase
from handlers.crash import crash_config
from handlers.crash.crash_config import CrashConfig as CrashConfigHandler
from model.crash.crash_config import CrashConfig as CrashConfigModel

_MOCK_FRACAS_CONFIG = {
    'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
    'supported_platform_list_by_channel': {
        'canary': ['win', 'mac', 'linux'],
        'supported_channel': ['supported_platform'],
    },
    'platform_rename': {'linux': 'unix'},
    'signature_blacklist_markers': ['Blacklist marker'],
    'top_n': 7
}

_MOCK_COMPONENT_CONFIG = {
    'path_function_component': [
        [
            'src/comp1.*',
            '',
            'Comp1>Dummy'
        ],
        [
            'src/comp2.*',
            'func2.*',
            'Comp2>Dummy'
        ],
    ],
    'top_n': 4
}

_MOCK_PROJECT_CONFIG = {
    'project_path_function_hosts': [
        ['android_os', ['googleplex-android/'], ['android.'], None],
        ['chromium', None, ['org.chromium'], ['src/', 'src/d/dep1', 'src/dep2']]
    ],
    'non_chromium_project_rank_priority': {
        'android_os': '-1',
        'others': '-2',
    },
    'top_n': 4
}

_MOCK_CONFIG = {
    'fracas': _MOCK_FRACAS_CONFIG,
    'cracas': _MOCK_FRACAS_CONFIG,
    'component_classifier': _MOCK_COMPONENT_CONFIG,
    'project_classifier': _MOCK_PROJECT_CONFIG
}


class CrashConfigTest(TestCase):
  """Tests utility functions and ``CrashConfig`` handler."""
  app_module = webapp2.WSGIApplication([
      ('/crash/config', CrashConfigHandler),
  ], debug=True)

  def testSortConfig(self):
    """Tests ``_SortConfig`` function."""
    config = copy.deepcopy(_MOCK_CONFIG)
    crash_config._SortConfig(config)
    expected_config = copy.deepcopy(_MOCK_CONFIG)
    expected_config['project_classifier'][
        'project_path_function_hosts'][1][3] = ['src/d/dep1/', 'src/dep2/',
                                                'src/']
    self.assertDictEqual(expected_config, config)


  def testValidateComponentClassifierConfig(self):
    """Tests ``_ValidateComponentClassifierConfig`` function."""
    # Return False if config is not a dict
    self.assertFalse(crash_config._ValidateComponentClassifierConfig(None))

    # Return False if config dict has not ``path_function_component``.
    self.assertFalse(crash_config._ValidateComponentClassifierConfig({}))

    # Return False if config ``path_function_component`` is not list.
    config = {'path_function_component': {}}
    self.assertFalse(crash_config._ValidateComponentClassifierConfig(config))

    # Return False if config ``top_n`` is not int.
    config = {'path_function_component':
              _MOCK_COMPONENT_CONFIG['path_function_component'],
              'top_n': []}
    self.assertFalse(crash_config._ValidateComponentClassifierConfig(config))

    self.assertTrue(crash_config._ValidateComponentClassifierConfig(
        _MOCK_COMPONENT_CONFIG))

  def testValidateProjectClassifierConfig(self):
    """Tests ``_ValidateProjectClassifierConfig`` function."""
    # Return False if config is not a dict
    self.assertFalse(crash_config._ValidateProjectClassifierConfig(None))

    # Return False if config dict has not ``project_path_function_hosts``.
    self.assertFalse(crash_config._ValidateProjectClassifierConfig({}))

    # Return False if config ``project_path_function_hosts`` is not list.
    config = {'project_path_function_hosts': {}}
    self.assertFalse(crash_config._ValidateProjectClassifierConfig(config))

    # Return False if config ``non_chromium_project_rank_priority`` is not dict.
    config = {'project_path_function_hosts':
              _MOCK_PROJECT_CONFIG['project_path_function_hosts'],
              'non_chromium_project_rank_priority': []}
    self.assertFalse(crash_config._ValidateProjectClassifierConfig(config))

    # Return False if config ``top_n`` is not int.
    config = {'project_path_function_hosts':
              _MOCK_PROJECT_CONFIG['project_path_function_hosts'],
              'non_chromium_project_rank_priority':
              _MOCK_PROJECT_CONFIG['non_chromium_project_rank_priority'],
              'top_n': []}
    self.assertFalse(crash_config._ValidateProjectClassifierConfig(config))

    self.assertTrue(crash_config._ValidateProjectClassifierConfig(
        _MOCK_PROJECT_CONFIG))

  def testConfigurationDictIsValid(self):
    """Tests ``_ConfigurationDictIsValid`` function."""
    # Return False if config is not a dict
    self.assertFalse(crash_config._ConfigurationDictIsValid(None))

    # Return False if there is one configuration failed validation.
    config = {'component_classifier': None}
    self.assertFalse(crash_config._ConfigurationDictIsValid(config))

    self.assertTrue(crash_config._ConfigurationDictIsValid(_MOCK_CONFIG))

  def testHandleGet(self):
    """Tests ``HandleGet`` method of ``CrashConfig`` handler."""
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)

    CrashConfigModel.Get().Update(users.GetCurrentUser(), True, **_MOCK_CONFIG)

    response = self.test_app.get('/crash/config', params={'format': 'json'})
    self.assertEquals(response.status_int, 200)

    self.assertDictEqual(_MOCK_CONFIG, response.json_body)

  def testHandlePost(self):
    """Tests ``HandlePost`` method of ``CrashConfig`` handler."""
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)

    response = self.test_app.post('/crash/config',
                                  params={'data': json.dumps(_MOCK_CONFIG),
                                          'format': 'json'})

    expected_config = copy.deepcopy(_MOCK_CONFIG)
    expected_config['project_classifier'][
        'project_path_function_hosts'][1][3] = ['src/d/dep1/', 'src/dep2/',
                                                'src/']

    self.assertDictEqual(expected_config, response.json_body)

  def testHandlePostMalFormattedData(self):
    """Tests ``HandlePost`` for mal-formatted data."""
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)

    self.assertRaisesRegexp(
        webtest.app.AppError,
        re.compile('New configuration settings are not properly formatted.',
                   re.MULTILINE | re.DOTALL),
        self.test_app.post, '/crash/config', params={'data': json.dumps({}),
                                                     'format': 'json'})
