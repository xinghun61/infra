# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

import webapp2

from handlers import check_trybot_mapping
from libs.http.retry_http_client import RetryHttpClient
from waterfall import buildbot
from waterfall.test import wf_testcase


class CheckTrybotMappingTest(wf_testcase.WaterfallTestCase):

  app_module = webapp2.WSGIApplication(
      [
          ('/check-trybot-mapping', check_trybot_mapping.CheckTrybotMapping),
      ],
      debug=True)

  def testGetsupportedMasters(self):
    self.UpdateUnitTestConfigSettings(
        config_property='steps_for_masters_rules',
        override_data={'supported_masters': {
            'chromium.linux': {}
        }})
    self.assertEqual(['chromium.linux'],
                     check_trybot_mapping._GetSupportedMasters())

  @mock.patch.object(
      buildbot, 'ListBuildersOnMaster', return_value=['builder1', 'builder2'])
  def testGetBuildersOnMasters(self, _):
    master = 'chromium.linux'
    masters = [master]
    http_client = mock.create_autospec(RetryHttpClient)
    self.assertEqual({
        master: ['builder1', 'builder2']
    }, check_trybot_mapping._GetBuildersOnMasters(masters, http_client))

  def testGetCoveredBuilders(self):
    config = {'master1': {'builder1': {}}, 'master2': {'builder2': {}}}
    expected = {'master1': ['builder1'], 'master2': ['builder2']}
    self.assertEqual(expected, check_trybot_mapping._GetCoveredBuilders(config))

  def testGetDiffBetweenDicts(self):
    dict1 = {
        'master1': ['builder1'],
        'master2': ['builder2', 'builder3'],
        'master3': ['builder4']
    }
    dict2 = {
        'master1': ['builder1'],
        'master2': ['builder2'],
    }
    expected_diff = {'master2': ['builder3'], 'master3': ['builder4']}

    self.assertEqual(expected_diff,
                     check_trybot_mapping._GetDiffBetweenDicts(dict1, dict2))

  def testGetAllTryservers(self):
    config = {
        'master1': {
            'builder1': {
                'mastername': 'tryserver1'
            },
            'builder2': {
                'mastername': 'tryserver2'
            }
        },
        'master2': {
            'builder3': {
                'mastername': 'tryserver2'
            },
            'builder4': {
                'mastername': 'tryserver3'
            }
        }
    }

    expected_result = ['tryserver1', 'tryserver2', 'tryserver3']
    self.assertEqual(expected_result,
                     check_trybot_mapping._GetAllTryservers(config))

  @mock.patch.object(
      buildbot, 'ListBuildersOnMaster', return_value=['variable_builder', 'a'])
  def testGetAllFinditBuildersOnTryservers(self, _):
    tryservers = ['tryserver1']
    http_client = mock.create_autospec(RetryHttpClient)

    expected_result = {'tryserver1': ['variable_builder']}
    self.assertEqual(expected_result,
                     check_trybot_mapping._GetAllFinditBuildersOnTryservers(
                         tryservers, http_client))

  def testGetAllBuildersInConfig(self):
    config = {
        'master1': {
            'builder1': {
                'mastername': 'tryserver1',
                'waterfall_trybot': 'trybot1',
                'flake_trybot': 'trybot2'
            },
            'builder2': {
                'mastername': 'tryserver2',
                'waterfall_trybot': 'trybot1',
                'flake_trybot': 'trybot2',
            }
        },
        'master2': {
            'builder3': {
                'mastername': 'tryserver2',
                'waterfall_trybot': 'trybot3',
                'flake_trybot': 'trybot4'
            },
            'builder4': {
                'mastername': 'tryserver3',
                'waterfall_trybot': 'trybot5',
                'flake_trybot': 'trybot6'
            }
        }
    }

    self.assertEqual(
        ['trybot5', 'trybot4', 'trybot6', 'trybot1', 'trybot3', 'trybot2'],
        check_trybot_mapping._GetAllBuildersInConfig(config))

  @mock.patch.object(
      check_trybot_mapping,
      '_GetAllFinditBuildersOnTryservers',
      return_value={
          'tryserver1': ['trybot3', 'trybot4'],
          'tryserver2': ['trybot3']
      })
  def testGetUnusedVariableBuilders(self, _):
    config = {
        'master1': {
            'builder1': {
                'mastername': 'tryserver1',
                'waterfall_trybot': 'trybot1',
                'flake_trybot': 'trybot2'
            },
        },
        'master2': {
            'builder2': {
                'mastername': 'tryserver2',
                'waterfall_trybot': 'trybot1',
                'flake_trybot': 'trybot3'
            },
        },
    }
    http_client = mock.create_autospec(RetryHttpClient)
    self.assertEqual({
        'tryserver1': ['trybot4']
    }, check_trybot_mapping._GetUnusedVariableBuilders(config, http_client))

  @mock.patch.object(
      check_trybot_mapping, '_GetSupportedMasters', return_value=[])
  @mock.patch.object(
      check_trybot_mapping, '_GetCoveredBuilders', return_value={})
  @mock.patch.object(
      check_trybot_mapping, '_GetDiffBetweenDicts', return_value={})
  @mock.patch.object(
      check_trybot_mapping, '_GetUnusedVariableBuilders', return_value={})
  def testGet(self, *_):
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)
    response = self.test_app.get(
        '/check-trybot-mapping', params={'format': 'json'})
    self.assertEqual(response.status_int, 200)
    expected_response = {
        'missing': {},
        'deprecated': {},
        'unused_variable_builders': {}
    }

    self.assertEqual(expected_response, response.json_body)
