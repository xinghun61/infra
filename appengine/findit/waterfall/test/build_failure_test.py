# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import mock
import os
import urllib
import zlib

from common.waterfall import failure_type
from gae_libs.http.http_client_appengine import HttpClientAppengine
from libs import analysis_status
from model.wf_analysis import WfAnalysis
from model.wf_build import WfBuild
from model.wf_step import WfStep
from waterfall import buildbot
from waterfall import build_failure
from waterfall import build_util
from waterfall import swarming_util
from waterfall.test import wf_testcase


class BuildFailureServicesTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(BuildFailureServicesTest, self).setUp()

    with self.mock_urlfetch() as urlfetch:
      self.mocked_urlfetch = urlfetch

  def _TimeBeforeNowBySeconds(self, seconds):
    return datetime.datetime.utcnow() - datetime.timedelta(0, seconds, 0)

  def _CreateAndSaveWfAnanlysis(self, master_name, builder_name, build_number,
                                status):
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.status = status
    analysis.put()

  def _GetBuildData(self, master_name, builder_name, build_number):
    file_name = os.path.join(
        os.path.dirname(__file__), 'data',
        '%s_%s_%d.json' % (master_name, builder_name, build_number))
    with open(file_name, 'r') as f:
      return f.read()

  def _GetSwarmingData(self, data_type, file_name=None, build_number=None):
    file_name_map = {
        'build': 'sample_swarming_build_tasks.json',
        'step': 'sample_swarming_build_abctest_tasks.json'
    }
    file_name = file_name_map.get(data_type, file_name)
    swarming_tasks_file = os.path.join(
        os.path.dirname(__file__), 'data', file_name)
    with open(swarming_tasks_file, 'r') as f:
      if build_number:
        return json.dumps(json.loads(f.read())[str(build_number)])
      if data_type == 'isolated':
        return zlib.compress(f.read())
      return f.read()

  def _MockUrlFetchWithSwarmingData(self, master_name, builder_name,
                                    build_number, step_name):
    url = ('https://chromium-swarm.appspot.com/_ah/api/swarming/v1/tasks/'
           'list?tags=%s&tags=%s&tags=%s&tags=%s') % (
               urllib.quote('master:%s' % master_name),
               urllib.quote('buildername:%s' % builder_name),
               urllib.quote('buildnumber:%d' % build_number),
               urllib.quote('stepname:%s' % step_name))

    response = self._GetSwarmingData('step', build_number=build_number)

    cursor_swarming_data = {
        'cursor': None,
        'items': [],
        'state': 'all',
        'limit': 100,
        'sort': 'created_ts'
    }
    cursor_url = ('%s&cursor=thisisacursor') % url

    self.mocked_urlfetch.register_handler(url, response)
    self.mocked_urlfetch.register_handler(cursor_url,
                                          json.dumps(cursor_swarming_data))

  def _MockUrlfetchWithIsolatedData(self,
                                    isolated_data=None,
                                    file_url=None,
                                    file_name=None,
                                    build_number=None):
    if isolated_data:  # Mocks POST requests to isolated server.
      url = '%s/_ah/api/isolateservice/v1/retrieve' % (
          isolated_data['isolatedserver'])
      post_data = {
          'digest': isolated_data['digest'],
          'namespace': isolated_data['namespace']
      }
      file_name = isolated_data['digest']
      if build_number:  # pragma: no branch
        file_name = isolated_data['digest'][:-4]
      content = self._GetSwarmingData('isolated', file_name, build_number)

    elif file_url and file_name:  # pragma: no branch.
      # Mocks GET requests to isolated server.
      url = file_url
      post_data = None
      content = self._GetSwarmingData('isolated', file_name)

    self.mocked_urlfetch.register_handler(
        url,
        content,
        data=(json.dumps(post_data, sort_keys=True, separators=(',', ':'))
              if post_data else None))

  def testInitiateTestLevelFirstFailureAndSaveLog(self):
    json_data = json.loads(
        self._GetSwarmingData('isolated-plain', 'm_b_223_abc_test.json'))

    step = WfStep.Create('m', 'b', 223, 'abc_test')
    step.isolated = True
    step.put()

    failed_step = {'current_failure': 223, 'first_failure': 221, 'tests': {}}

    build_failure._InitiateTestLevelFirstFailureAndSaveLog(
        json_data, step, failed_step)

    expected_failed_step = {
        'current_failure': 223,
        'first_failure': 221,
        'tests': {
            'Unittest2.Subtest1': {
                'current_failure': 223,
                'first_failure': 223,
                'base_test_name': 'Unittest2.Subtest1'
            },
            'Unittest3.Subtest2': {
                'current_failure': 223,
                'first_failure': 223,
                'base_test_name': 'Unittest3.Subtest2'
            }
        }
    }
    self.assertEqual(expected_failed_step, failed_step)

  def testInitiateTestLevelFirstFailureAndSaveLogwithLastPass(self):
    json_data = json.loads(
        self._GetSwarmingData('isolated-plain', 'm_b_223_abc_test.json'))

    step = WfStep.Create('m', 'b', 223, 'abc_test')
    step.isolated = True
    step.put()

    failed_step = {
        'current_failure': 223,
        'first_failure': 221,
        'last_pass': 220,
        'tests': {}
    }

    build_failure._InitiateTestLevelFirstFailureAndSaveLog(
        json_data, step, failed_step)

    expected_failed_step = {
        'current_failure': 223,
        'first_failure': 221,
        'last_pass': 220,
        'tests': {
            'Unittest2.Subtest1': {
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': 220,
                'base_test_name': 'Unittest2.Subtest1'
            },
            'Unittest3.Subtest2': {
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': 220,
                'base_test_name': 'Unittest3.Subtest2'
            }
        }
    }
    self.assertEqual(expected_failed_step, failed_step)

  @mock.patch.object(build_failure, 'swarming_util')
  def testCheckFirstKnownFailureForSwarmingTestsFoundFlaky(self, mock_module):
    master_name = 'm'
    builder_name = 'b'
    build_number = 221
    step_name = 'abc_test'
    failed_steps = {
        'abc_test': {
            'current_failure':
                221,
            'first_failure':
                221,
            'list_isolated_data': [{
                'isolatedserver': 'https://isolateserver.appspot.com',
                'namespace': 'default-gzip',
                'digest': 'isolatedhashabctest-223'
            }]
        }
    }
    builds = {
        '221': {
            'blame_list': ['commit1'],
            'chromium_revision': 'commit1'
        },
        '222': {
            'blame_list': ['commit2'],
            'chromium_revision': 'commit2'
        },
        '223': {
            'blame_list': ['commit3', 'commit4'],
            'chromium_revision': 'commit4'
        }
    }
    expected_failed_steps = failed_steps
    step = WfStep.Create(master_name, builder_name, build_number, step_name)
    step.isolated = True
    step.put()

    mock_module.GetIsolatedDataForFailedBuild.return_value = True
    mock_module.RetrieveShardedTestResultsFromIsolatedServer.return_value = (
        json.loads(
            self._GetSwarmingData('isolated-plain',
                                  'm_b_223_abc_test_flaky.json')))

    build_failure.CheckFirstKnownFailureForSwarmingTests(
        master_name, builder_name, build_number, failed_steps, builds)

    self.assertEqual(expected_failed_steps, failed_steps)

  @mock.patch.object(
      swarming_util, 'GetIsolatedDataForFailedBuild', return_value=None)
  def testCheckFirstKnownFailureForSwarmingTestsNoResult(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 224
    failed_steps = {}
    builds = {}
    build_failure.CheckFirstKnownFailureForSwarmingTests(
        master_name, builder_name, build_number, failed_steps, builds)
    self.assertEqual({}, failed_steps)

  def testUpdateFirstFailureOnTestLevelThenUpdateStepLevel(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 224
    step_name = 'abc_test'
    failed_step = {
        'current_failure': 224,
        'first_failure': 221,
        'last_pass': 220,
        'tests': {
            'Unittest2.Subtest1': {
                'current_failure': 224,
                'first_failure': 223,
                'last_pass': 223,
                'base_test_name': 'Unittest2.Subtest1'
            },
            'Unittest3.Subtest2': {
                'current_failure': 224,
                'first_failure': 223,
                'base_test_name': 'Unittest3.Subtest2'
            }
        }
    }

    step = WfStep.Create(master_name, builder_name, 223, step_name)
    step.isolated = True
    step.log_data = 'log'
    step.put()

    for n in xrange(222, 220, -1):
      # Mock retrieving data from swarming server for a single step.
      self._MockUrlFetchWithSwarmingData(master_name, builder_name, n,
                                         'abc_test')

      # Mock retrieving hash to output.json from isolated server.
      isolated_data = {
          'isolatedserver': 'https://isolateserver.appspot.com',
          'namespace': {
              'namespace': 'default-gzip'
          },
          'digest': 'isolatedhashabctest-%d' % n
      }
      self._MockUrlfetchWithIsolatedData(isolated_data, build_number=n)
      # Mock retrieving url to output.json from isolated server.
      file_hash_data = {
          'isolatedserver': 'https://isolateserver.appspot.com',
          'namespace': {
              'namespace': 'default-gzip'
          },
          'digest': 'abctestoutputjsonhash-%d' % n
      }
      self._MockUrlfetchWithIsolatedData(file_hash_data, build_number=n)

      # Mock downloading output.json from isolated server.
      self._MockUrlfetchWithIsolatedData(
          None, ('https://isolateserver.storage.googleapis.com/default-gzip/'
                 'm_b_%d_abc_test' % n),
          '%s_%s_%d_%s.json' % (master_name, builder_name, n, 'abc_test'))

    build_failure._UpdateFirstFailureOnTestLevel(
        master_name, builder_name, build_number, step_name, failed_step,
        HttpClientAppengine())

    expected_failed_step = {
        'current_failure': 224,
        'first_failure': 221,
        'last_pass': 220,
        'tests': {
            'Unittest2.Subtest1': {
                'current_failure': 224,
                'first_failure': 222,
                'last_pass': 221,
                'base_test_name': 'Unittest2.Subtest1'
            },
            'Unittest3.Subtest2': {
                'current_failure': 224,
                'first_failure': 221,
                'base_test_name': 'Unittest3.Subtest2'
            }
        }
    }
    self.assertEqual(expected_failed_step, failed_step)

  def testUpdateFirstFailureOnTestLevelFlaky(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    step_name = 'abc_test'
    failed_step = {
        'current_failure': 223,
        'first_failure': 221,
        'tests': {
            'Unittest2.Subtest1': {
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': 223,
                'base_test_name': 'Unittest2.Subtest1'
            }
        }
    }
    step = WfStep.Create(master_name, builder_name, 222, step_name)
    step.isolated = True
    step.log_data = 'flaky'
    step.put()

    build_failure._UpdateFirstFailureOnTestLevel(
        master_name, builder_name, build_number, step_name, failed_step,
        HttpClientAppengine())

    expected_failed_step = {
        'current_failure': 223,
        'first_failure': 223,
        'last_pass': 222,
        'tests': {
            'Unittest2.Subtest1': {
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': 222,
                'base_test_name': 'Unittest2.Subtest1'
            }
        }
    }
    self.assertEqual(expected_failed_step, failed_step)

  def testUpdateFailureInfoBuildsUpdateBuilds(self):
    failed_steps = {
        'compile': {
            'current_failure': 223,
            'first_failure': 222,
            'last_pass': 221
        },
        'abc_test': {
            'current_failure':
                223,
            'first_failure':
                222,
            'last_pass':
                221,
            'list_isolated_data': [{
                'isolatedserver': 'https://isolateserver.appspot.com',
                'namespace': 'default-gzip',
                'digest': 'isolatedhashabctest-223'
            }],
            'tests': {
                'Unittest2.Subtest1': {
                    'current_failure': 223,
                    'first_failure': 222,
                    'last_pass': 221,
                    'base_test_name': 'Unittest2.Subtest1'
                },
                'Unittest3.Subtest2': {
                    'current_failure': 223,
                    'first_failure': 222,
                    'last_pass': 221,
                    'base_test_name': 'Unittest3.Subtest2'
                }
            }
        }
    }

    builds = {
        '220': {
            'blame_list': ['commit0'],
            'chromium_revision': 'commit0'
        },
        '221': {
            'blame_list': ['commit1'],
            'chromium_revision': 'commit1'
        },
        '222': {
            'blame_list': ['commit2'],
            'chromium_revision': 'commit2'
        },
        '223': {
            'blame_list': ['commit3', 'commit4'],
            'chromium_revision': 'commit4'
        }
    }

    build_failure._UpdateFailureInfoBuilds(failed_steps, builds)
    expected_builds = {
        '221': {
            'blame_list': ['commit1'],
            'chromium_revision': 'commit1'
        },
        '222': {
            'blame_list': ['commit2'],
            'chromium_revision': 'commit2'
        },
        '223': {
            'blame_list': ['commit3', 'commit4'],
            'chromium_revision': 'commit4'
        }
    }
    self.assertEqual(builds, expected_builds)

  @mock.patch.object(build_failure, '_ExtractBuildInfo', return_value=None)
  def testFailedToExtractBuildInfo(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    failed_steps = {'a': {'current_failure': 124, 'first_failure': 124}}
    builds = {
        124: {
            'chromium_revision': 'some_git_hash',
            'blame_list': ['some_git_hash']
        }
    }

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.RUNNING)

    build_failure.CheckForFirstKnownFailure(master_name, builder_name,
                                            build_number, failed_steps, builds)

    self.assertEqual(failed_steps, failed_steps)

  @mock.patch.object(buildbot, 'GetBuildDataFromMilo')
  def testStopLookingBackIfAllFailedStepsPassedInLastBuild(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    failed_steps = {'a': {'current_failure': 124, 'first_failure': 124}}
    builds = {
        124: {
            'chromium_revision': 'some_git_hash',
            'blame_list': ['some_git_hash']
        }
    }

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.RUNNING)

    # Setup build data for builds:
    mock_fn.side_effect = [self._GetBuildData(master_name, builder_name, 123)]

    expected_failed_steps = {
        'a': {
            'last_pass': 123,
            'current_failure': 124,
            'first_failure': 124
        }
    }

    expected_builds = {
        124: {
            'chromium_revision': 'some_git_hash',
            'blame_list': ['some_git_hash']
        },
        123: {
            'chromium_revision': '64c72819e898e952103b63eabc12772f9640af07',
            'blame_list': ['64c72819e898e952103b63eabc12772f9640af07']
        }
    }

    build_failure.CheckForFirstKnownFailure(master_name, builder_name,
                                            build_number, failed_steps, builds)

    self.assertEqual(expected_failed_steps, failed_steps)
    self.assertEqual(expected_builds, builds)

  @mock.patch.object(buildbot, 'GetBuildDataFromMilo')
  def testStopLookingBackIfFindTheFirstBuild(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 2
    failed_steps = {
        'a_tests': {
            'current_failure': 2,
            'first_failure': 2
        },
        'unit_tests': {
            'current_failure': 2,
            'first_failure': 2
        }
    }
    builds = {
        2: {
            'chromium_revision': '5934404dc5392ab3ae2c82b52b366889fb858d91',
            'blame_list': ['5934404dc5392ab3ae2c82b52b366889fb858d91']
        }
    }

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.RUNNING)

    # Setup build data for builds:
    mock_fn.side_effect = [
        self._GetBuildData(master_name, builder_name, 1),
        self._GetBuildData(master_name, builder_name, 0)
    ]

    expected_failed_steps = {
        'a_tests': {
            'current_failure': 2,
            'first_failure': 0
        },
        'unit_tests': {
            'current_failure': 2,
            'first_failure': 0
        }
    }

    expected_builds = {
        2: {
            'chromium_revision': '5934404dc5392ab3ae2c82b52b366889fb858d91',
            'blame_list': ['5934404dc5392ab3ae2c82b52b366889fb858d91']
        },
        1: {
            'chromium_revision': '5934404dc5392ab3ae2c82b52b366889fb858d91',
            'blame_list': ['5934404dc5392ab3ae2c82b52b366889fb858d91']
        },
        0: {
            'chromium_revision': '5934404dc5392ab3ae2c82b52b366889fb858d91',
            'blame_list': ['5934404dc5392ab3ae2c82b52b366889fb858d91']
        },
    }

    build_failure.CheckForFirstKnownFailure(master_name, builder_name,
                                            build_number, failed_steps, builds)

    self.assertEqual(expected_failed_steps, failed_steps)
    self.assertEqual(expected_builds, builds)

  @mock.patch.object(buildbot, 'GetBuildDataFromMilo')
  def testLookBackUntilGreenBuild(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    failed_steps = {
        'net_unittests': {
            'current_failure': 123,
            'first_failure': 123
        },
        'unit_tests': {
            'current_failure': 123,
            'first_failure': 123
        }
    }
    builds = {
        123: {
            'chromium_revision': '64c72819e898e952103b63eabc12772f9640af07',
            'blame_list': ['64c72819e898e952103b63eabc12772f9640af07']
        }
    }

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.RUNNING)

    # Setup build data for builds:
    # 122: mock a build in datastore to ensure it is not fetched again.
    build = WfBuild.Create(master_name, builder_name, 122)
    build.data = self._GetBuildData(master_name, builder_name, 122)
    build.completed = True
    build.put()
    # 121: mock a build in datastore to ensure it is updated.
    build = WfBuild.Create(master_name, builder_name, 121)
    build.data = 'Blow up if used!'
    build.last_crawled_time = self._TimeBeforeNowBySeconds(7200)
    build.completed = False
    build.put()

    mock_fn.side_effect = [self._GetBuildData(master_name, builder_name, 121)]

    expected_failed_steps = {
        'net_unittests': {
            'last_pass': 122,
            'current_failure': 123,
            'first_failure': 123
        },
        'unit_tests': {
            'last_pass': 121,
            'current_failure': 123,
            'first_failure': 122
        }
    }

    expected_builds = {
        123: {
            'chromium_revision': '64c72819e898e952103b63eabc12772f9640af07',
            'blame_list': ['64c72819e898e952103b63eabc12772f9640af07']
        },
        122: {
            'chromium_revision': '5934404dc5392ab3ae2c82b52b366889fb858d91',
            'blame_list': ['5934404dc5392ab3ae2c82b52b366889fb858d91']
        },
        121: {
            'chromium_revision':
                '5934404dc5392ab3ae2c82b52b366889fb858d91',
            'blame_list': [
                '2fe8767f011a20ed8079d3aba7008acd95842f79',
                'c0ed134137c98c2935bf32e85f74d4e94c2b980d',
                '63820a74b4b5a3e6707ab89f92343e7fae7104f0'
            ]
        }
    }

    build_failure.CheckForFirstKnownFailure(master_name, builder_name,
                                            build_number, failed_steps, builds)
    self.assertEqual(expected_failed_steps, failed_steps)
    self.assertEqual(expected_builds, builds)

  @mock.patch.object(buildbot, 'GetBuildDataFromMilo')
  def testGetBuildFailureInfo(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.PENDING)

    mock_fn.return_value = self._GetBuildData(master_name, builder_name,
                                              build_number)

    failure_info = build_failure.GetBuildFailureInfo(master_name, builder_name,
                                                     build_number)

    expected_failure_info = {
        'failed': True,
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'chromium_revision': '64c72819e898e952103b63eabc12772f9640af07',
        'builds': {
            build_number: {
                'blame_list': ['64c72819e898e952103b63eabc12772f9640af07'],
                'chromium_revision': '64c72819e898e952103b63eabc12772f9640af07'
            }
        },
        'failed_steps': {
            'abc_test': {
                'current_failure': build_number,
                'first_failure': build_number
            }
        },
        'failure_type': failure_type.TEST,
        'parent_mastername': None,
        'parent_buildername': None,
    }

    self.assertEqual(expected_failure_info, failure_info)

  @mock.patch.object(build_failure, '_ExtractBuildInfo', return_value=None)
  def testGetBuildFailureInfoFailedGetBuildInfo(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = build_failure.GetBuildFailureInfo(master_name, builder_name,
                                                     build_number)

    self.assertEqual({}, failure_info)

  @mock.patch.object(buildbot, 'GetBuildDataFromMilo')
  def testGetBuildFailureInfoBuildSuccess(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 121

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.PENDING)

    mock_fn.return_value = self._GetBuildData(master_name, builder_name,
                                              build_number)

    failure_info = build_failure.GetBuildFailureInfo(master_name, builder_name,
                                                     build_number)

    expected_failure_info = {
        'failed': False,
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'chromium_revision': '5934404dc5392ab3ae2c82b52b366889fb858d91',
        'builds': {},
        'failed_steps': {},
        'failure_type': failure_type.UNKNOWN,
        'parent_mastername': None,
        'parent_buildername': None,
    }

    self.assertEqual(expected_failure_info, failure_info)

  @mock.patch.object(build_util, 'DownloadBuildData', return_value=None)
  def testExtractBuildInfo(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 121

    with self.assertRaises(Exception):
      build_failure._ExtractBuildInfo(master_name, builder_name, build_number)

  @mock.patch.object(
      swarming_util,
      'RetrieveShardedTestResultsFromIsolatedServer',
      return_value=None)
  def testStartTestLevelCheckForFirstFailure(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 121
    step_name = 'atest'
    failed_step = {'list_isolated_data': ''}
    self.assertFalse(
        build_failure._StartTestLevelCheckForFirstFailure(
            master_name, builder_name, build_number, step_name, failed_step,
            None))

  @mock.patch.object(swarming_util, 'GetIsolatedDataForStep', return_value=None)
  def testGetSameStepFromBuild(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 121
    step_name = 'atest'
    self.assertIsNone(
        build_failure._GetSameStepFromBuild(master_name, builder_name,
                                            build_number, step_name, None))

  @mock.patch.object(
      swarming_util,
      'GetIsolatedDataForStep',
      return_value='step_isolated_data')
  @mock.patch.object(
      swarming_util,
      'RetrieveShardedTestResultsFromIsolatedServer',
      return_value={'per_iteration_data': 'invalid'})
  def testGetSameStepFromBuildReslutLogInvalid(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 121
    step_name = 'atest'
    self.assertIsNone(
        build_failure._GetSameStepFromBuild(master_name, builder_name,
                                            build_number, step_name, None))
