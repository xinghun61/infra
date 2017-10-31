# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import json
import re
import webapp2
import webtest

from google.appengine.api import users

from common.model.crash_config import CrashConfig as CrashConfigModel
from frontend.handlers import crash_config
from frontend.handlers.crash_config import CrashConfig as CrashConfigHandler
from gae_libs.testcase import TestCase

_MOCK_FRACAS_CONFIG = {
    'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
    'supported_platform_list_by_channel': {
        'canary': ['win', 'mac', 'linux'],
        'supported_channel': ['supported_platform'],
    },
    'signature_blacklist_markers': ['Blacklist marker'],
    'top_n': 7
}

_MOCK_CLUSTERFUZZ_CONFIG = {
    'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
    'try_bot_topic': 'projects/project-name/topics/name',
    'try_bot_supported_platforms': ['linux'],
    'signature_blacklist_markers': ['Blacklist marker'],
    'blacklist_crash_type': ['out-of-memory'],
    'top_n': 7
}

_MOCK_UMA_SAMPLING_PROFILER_CONFIG = {
    'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
    'signature_blacklist_markers': ['Blacklist marker'],
}

_MOCK_COMPONENT_CONFIG = {
    'component_info': [
        {
            'dirs': ['src/comp1'],
            'component': 'Comp1>Dummy'
        },
        {
            'dirs': ['src/comp2'],
            'function': 'func2.*',
            'component': 'Comp2>Dummy'
        },
    ],
    'owner_mapping_url': 'http://owner_mapping_url',
    'top_n': 4
}

_MOCK_PROJECT_CONFIG = {
    'project_path_function_hosts': [
        ['android_os', ['googleplex-android'], ['android.'], None],
        ['chromium', None, ['org.chromium'], ['src/', 'src/d/dep1', 'src/dep2']]
    ],
    'non_chromium_project_rank_priority': {
        'android_os': '-1',
        'others': '-2',
    },
    'top_n': 4
}

_MOCK_REPO_TO_DEP_PATH = {
    'https://chromium_repo.git': 'src',
    'https://chromium.v8.git': 'src/v8',
}

_MOCK_FEATURE_OPTIONS = {
    'TouchCrashedComponent': {
        'blacklist': ['Internals>Core'],
    },
    'TouchCrashedDirectory': {
        'blacklist': ['base'],
    }
}

_MOCK_CONFIG = {
    'fracas': _MOCK_FRACAS_CONFIG,
    'cracas': _MOCK_FRACAS_CONFIG,
    'clusterfuzz': _MOCK_CLUSTERFUZZ_CONFIG,
    'uma_sampling_profiler': _MOCK_UMA_SAMPLING_PROFILER_CONFIG,
    'component_classifier': _MOCK_COMPONENT_CONFIG,
    'project_classifier': _MOCK_PROJECT_CONFIG,
    'repo_to_dep_path': _MOCK_REPO_TO_DEP_PATH,
    'feature_options': _MOCK_FEATURE_OPTIONS,
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
        'project_path_function_hosts'][1][3] = ['src/d/dep1', 'src/dep2',
                                                'src']
    self.assertDictEqual(expected_config, config)

  def testValidateChromeCrashConfig(self):
    """Tests ``_ValidateChromeCrashConfig`` function."""
    # Return False if config is not a dict
    self.assertFalse(crash_config._ValidateChromeCrashConfig(None))

    # Return False if config doesn't have "analysis_result_pubsub_topic".
    self.assertFalse(crash_config._ValidateChromeCrashConfig({}))

    config = {
        'analysis_result_pubsub_topic': 'projects/project-name/topics/name'
    }

    # Return False if config doesn't have "signature_blacklist_markers".
    config = {
        'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
    }
    self.assertFalse(crash_config._ValidateChromeCrashConfig(config))

    # Return False if entries of "signature_blacklist_markers" are not strs.
    config = {
        'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
        'signature_blacklist_markers': [None]
    }
    self.assertFalse(crash_config._ValidateChromeCrashConfig(config))

    # Return False if config doesn't have
    # "supported_platform_list_by_channel".
    config = {
        'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
        'signature_blacklist_markers': []
    }
    self.assertFalse(crash_config._ValidateChromeCrashConfig(config))

    # Return False if "supported_platform_list_by_channel" is not well
    # formatted.
    config = {
        'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
        'signature_blacklist_markers': [],
        'supported_platform_list_by_channel': {None: None}
    }
    self.assertFalse(crash_config._ValidateChromeCrashConfig(config))

    # Return False if "supported_platform_list_by_channel" is not well
    # formatted.
    config = {
        'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
        'signature_blacklist_markers': [],
        'supported_platform_list_by_channel': {'canary': None}
    }
    self.assertFalse(crash_config._ValidateChromeCrashConfig(config))

    # Return False if config doesn't have "top_n".
    config = {
        'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
        'signature_blacklist_markers': [],
        'supported_platform_list_by_channel': {}
    }
    self.assertFalse(crash_config._ValidateChromeCrashConfig(config))

    self.assertTrue(crash_config._ValidateChromeCrashConfig(
        _MOCK_FRACAS_CONFIG))

  def testValidateClusterfuzzConfig(self):
    """Tests ``_ValidateClusterfuzzConfig`` function."""
    # Return False if config is not a dict
    self.assertFalse(crash_config._ValidateClusterfuzzConfig(None))

    # Return False if config doesn't have "analysis_result_pubsub_topic".
    self.assertFalse(crash_config._ValidateClusterfuzzConfig({}))

    # Return False if "analysis_result_pubsub_topic" is not a string.
    config = {
        'analysis_result_pubsub_topic': 0
    }
    self.assertFalse(crash_config._ValidateClusterfuzzConfig(config))

    # Return False if config doesn't have "try_bot_topic".
    config = {
        'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
    }
    self.assertFalse(crash_config._ValidateClusterfuzzConfig(config))

    # Return False if config doesn't have "try_bot_supported_platforms".
    config = {
        'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
        'try_bot_topic': 'projects/project-name/topics/name',
    }
    self.assertFalse(crash_config._ValidateClusterfuzzConfig(config))

    # Return False if config doesn't have "signature_blacklist_markers".
    config = {
        'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
        'try_bot_topic': 'projects/project-name/topics/name',
        'try_bot_supported_platforms': ['linux']
    }
    self.assertFalse(crash_config._ValidateClusterfuzzConfig(config))

    # Return False if entries of "signature_blacklist_markers" are not strs.
    config = {
        'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
        'try_bot_topic': 'projects/project-name/topics/name',
        'try_bot_supported_platforms': ['linux'],
        'signature_blacklist_markers': [None]
    }
    self.assertFalse(crash_config._ValidateClusterfuzzConfig(config))

    # Return False if config doesn't have
    # "blacklist_crash_type".
    config = {
        'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
        'try_bot_topic': 'projects/project-name/topics/name',
        'try_bot_supported_platforms': ['linux'],
        'signature_blacklist_markers': []
    }
    self.assertFalse(crash_config._ValidateClusterfuzzConfig(config))

    # Return False if "blacklist_crash_type" is not well
    # formatted.
    config = {
        'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
        'try_bot_topic': 'projects/project-name/topics/name',
        'try_bot_supported_platforms': ['linux'],
        'signature_blacklist_markers': [],
        'blacklist_crash_type': {}
    }
    self.assertFalse(crash_config._ValidateClusterfuzzConfig(config))

    # Return False if config doesn't have "top_n".
    config = {
        'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
        'try_bot_topic': 'projects/project-name/topics/name',
        'try_bot_supported_platforms': ['linux'],
        'signature_blacklist_markers': [],
        'blacklist_crash_type': []
    }
    self.assertFalse(crash_config._ValidateClusterfuzzConfig(config))

    self.assertTrue(crash_config._ValidateClusterfuzzConfig(
        _MOCK_CLUSTERFUZZ_CONFIG))

  def testValidateUMASamplingProfilerConfig(self):
    """Tests ``_ValidateUMASamplingProfilerConfig`` function."""
    # Return False if config is not a dict
    self.assertFalse(crash_config._ValidateUMASamplingProfilerConfig(None))

    # Return False if config doesn't have "analysis_result_pubsub_topic".
    self.assertFalse(crash_config._ValidateUMASamplingProfilerConfig({}))

    config = {
        'analysis_result_pubsub_topic': 'projects/project-name/topics/name'
    }

    # Return False if config doesn't have "signature_blacklist_markers".
    self.assertFalse(crash_config._ValidateUMASamplingProfilerConfig(config))

    # Return False if entries of "signature_blacklist_markers" are not strs.
    config = {
        'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
        'signature_blacklist_markers': [None]
    }
    self.assertFalse(crash_config._ValidateUMASamplingProfilerConfig(config))

    self.assertTrue(crash_config._ValidateUMASamplingProfilerConfig(
        _MOCK_UMA_SAMPLING_PROFILER_CONFIG))

  def testValidateComponentClassifierConfig(self):
    """Tests ``_ValidateComponentClassifierConfig`` function."""
    # Return False if config is not a dict
    self.assertFalse(crash_config._ValidateComponentClassifierConfig(None))

    # Return False if config dict has not "component_info".
    self.assertFalse(crash_config._ValidateComponentClassifierConfig({}))

    # Return False if config "component_info" is not list.
    config = {'component_info': {}}
    self.assertFalse(crash_config._ValidateComponentClassifierConfig(config))

    # Return False if config "component_info" is not a list of strings.
    config = {'component_info': [None]}
    self.assertFalse(crash_config._ValidateComponentClassifierConfig(config))

    # Return False if config "owner_mapping_url" is not string.
    config = {'component_info':
              _MOCK_COMPONENT_CONFIG['component_info'],
              'owner_mapping_url': None}
    self.assertFalse(crash_config._ValidateComponentClassifierConfig(config))

    # Return False if config "top_n" is not int.
    config = {'component_info':
              _MOCK_COMPONENT_CONFIG['component_info'],
              'owner_mapping_url': 'http://owner_mapping_url',
              'top_n': []}
    self.assertFalse(crash_config._ValidateComponentClassifierConfig(config))

    self.assertTrue(crash_config._ValidateComponentClassifierConfig(
        _MOCK_COMPONENT_CONFIG))

  def testValidateProjectClassifierConfig(self):
    """Tests ``_ValidateProjectClassifierConfig`` function."""
    # Return False if config is not a dict
    self.assertFalse(crash_config._ValidateProjectClassifierConfig(None))

    # Return False if config dict has not "project_path_function_hosts".
    self.assertFalse(crash_config._ValidateProjectClassifierConfig({}))

    # Return False if config "project_path_function_hosts" is not list.
    config = {'project_path_function_hosts': {}}
    self.assertFalse(crash_config._ValidateProjectClassifierConfig(config))

    # Return False if config "non_chromium_project_rank_priority" is not dict.
    config = {'project_path_function_hosts':
              _MOCK_PROJECT_CONFIG['project_path_function_hosts'],
              'non_chromium_project_rank_priority': []}
    self.assertFalse(crash_config._ValidateProjectClassifierConfig(config))

    # Return False if config "top_n" is not int.
    config = {'project_path_function_hosts':
              _MOCK_PROJECT_CONFIG['project_path_function_hosts'],
              'non_chromium_project_rank_priority':
              _MOCK_PROJECT_CONFIG['non_chromium_project_rank_priority'],
              'top_n': []}
    self.assertFalse(crash_config._ValidateProjectClassifierConfig(config))

    self.assertTrue(crash_config._ValidateProjectClassifierConfig(
        _MOCK_PROJECT_CONFIG))

  def testValidateRepoToDepPathConfig(self):
    """Tests ``_ValidateRepoToDepPathConfig`` function."""
    self.assertFalse(crash_config._ValidateRepoToDepPathConfig(None))
    self.assertTrue(crash_config._ValidateRepoToDepPathConfig({}))

  def testValidateFeatureOptions(self):
    """Tests ``_ValidateFeatureOptions`` function."""
    self.assertFalse(crash_config._ValidateFeatureOptions(None))
    self.assertFalse(crash_config._ValidateFeatureOptions({}))
    self.assertFalse(crash_config._ValidateFeatureOptions({
        'TouchCrashedDirectory': []
    }))
    self.assertFalse(crash_config._ValidateFeatureOptions({
        'TouchCrashedDirectory': {}
    }))

    self.assertFalse(crash_config._ValidateFeatureOptions({
        'TouchCrashedDirectory': {'blacklist': []}
    }))

    self.assertFalse(crash_config._ValidateFeatureOptions({
        'TouchCrashedDirectory': {'blacklist': []},
        'TouchCrashedComponent': []
    }))

    self.assertFalse(crash_config._ValidateFeatureOptions({
        'TouchCrashedDirectory': {'blacklist': []},
        'TouchCrashedComponent': {}
    }))
    self.assertTrue(crash_config._ValidateFeatureOptions(_MOCK_FEATURE_OPTIONS))

  def testConfigurationDictIsValid(self):
    """Tests ``_ConfigurationDictIsValid`` function."""
    # Return False if config is not a dict
    self.assertFalse(crash_config._ConfigurationDictIsValid(None))

    # Return False if there is one configuration failed validation.
    config = {
        'fracas': None,
        'cracas': None,
        'clusterfuzz': None,
        'uma_sampling_profiler': None,
        'component_classifier': None
    }
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
        'project_path_function_hosts'][1][3] = ['src/d/dep1', 'src/dep2',
                                                'src']

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
