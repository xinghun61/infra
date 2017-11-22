# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import re

import gae_ts_mon
from google.appengine.api import users

from analysis.analysis_testcase import AnalysisTestCase
from analysis.crash_data import CrashData
from analysis.type_enums import CrashClient
from common.predator_app import PredatorApp
from common.model.crash_config import CrashConfig
from common.model.crash_analysis import CrashAnalysis
from common.model.fracas_crash_analysis import FracasCrashAnalysis
from gae_libs.testcase import TestCase
from libs.gitiles.change_log import ChangeLog
from libs.gitiles.gitiles_repository import GitilesRepository
from libs.http import retry_http_client


DEFAULT_CONFIG_DATA = {
    'fracas': {
        'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
        'supported_platform_list_by_channel': {
            'canary': ['win', 'mac', 'linux'],
            'supported_channel': ['supported_platform'],
        },
        'platform_rename': {'linux': 'unix'},
        'signature_blacklist_markers': ['Blacklist marker'],
        'top_n': 7
    },
    'cracas': {
        'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
        'supported_platform_list_by_channel': {
            'canary': ['win', 'mac', 'linux'],
            'supported_channel': ['supported_platform'],
        },
        'platform_rename': {'linux': 'unix'},
        'signature_blacklist_markers': ['Blacklist marker'],
        'top_n': 7
    },
    'clusterfuzz': {
      'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
      'blacklist_crash_type': [
        'out-of-memory'
      ],
      'signature_blacklist_markers': [],
      'top_n': 7,
      'try_bot_supported_platforms': [
        'linux'
      ],
      'try_bot_topic': 'projects/project-name/topics/try-bot-message'
    },
    'component_classifier': {
        'component_info': [
            {
                'dirs': ['src/comp1'],
                'component': 'Comp1>Dummy'
            },
            {
                'dirs': ['src/comp2'],
                'function': 'func2.*',
                'component': 'Comp2>Dummy',
                'team': 'comp2-team'
            }
        ],
        'owner_mapping_url': 'https://owner_mapping_url',
        'top_n': 4
    },
    'project_classifier': {
        'project_path_function_hosts': [
            ['android_os', ['googleplex-android/'], ['android.'], None],
            ['chromium', None, ['org.chromium'], ['src/']]
        ],
        'non_chromium_project_rank_priority': {
            'android_os': '-1',
            'others': '-2',
        },
        'top_n': 4
    },
    'feature_options': {
        'TouchCrashedComponent': {
            'blacklist': ['Internals>Core'],
        },
        'TouchCrashedDirectory': {
            'blacklist': ['base'],
        }
    }
}


class MockCrashAnalysis(CrashAnalysis):  # pragma: no cover

  @property
  def client_id(self):
    return 'mock_client'


class AppengineTestCase(AnalysisTestCase, TestCase):  # pragma: no cover

  def setUp(self):
    super(AppengineTestCase, self).setUp()
    CrashConfig.Get().Update(
        users.User(email='admin@chromium.org'), True, **DEFAULT_CONFIG_DATA)
    gae_ts_mon.reset_for_unittest(disable=True)

  def GetMockPredatorApp(self, get_repository=None, config=None,
                         client_id=CrashClient.FRACAS):
    get_repository = (get_repository or
                      GitilesRepository.Factory(self.GetMockHttpClient()))
    config = config or CrashConfig.Get()
    log = self.GetMockLog()

    class MockPredatorApp(PredatorApp):  # pylint: disable=W0223
      """Overwrite abstract method of PredatorApp for testing."""
      def __init__(self):
        super(MockPredatorApp, self).__init__(
            get_repository, config, log=log)

      @classmethod
      def _ClientID(cls):
        return client_id

      def ProcessResultForPublishing(self, result, key): # pylint: disable=W0613
        return result

      def GetCrashData(self, crash_data):

        class MockCrashData(CrashData):
          @property
          def regression_range(self):
            return crash_data.get('regression_range')

          @property
          def stacktrace(self):
            return None

          @property
          def dependencies(self):
            return {}

          @property
          def dependency_rolls(self):
            return {}

          @property
          def identifiers(self):
            return crash_data.get('crash_identifiers')

        return MockCrashData(crash_data)

      def GetAnalysis(self, crash_identifiers):
        return MockCrashAnalysis.Get(crash_identifiers)

      def CreateAnalysis(self, crash_identifiers):
        return MockCrashAnalysis.Create(crash_identifiers)

    return MockPredatorApp()
