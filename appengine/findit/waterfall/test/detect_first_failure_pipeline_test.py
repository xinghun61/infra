# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import os
import urllib
import zlib

from testing_utils import testing

from common.http_client_appengine import HttpClientAppengine as HttpClient
from model import wf_analysis_status
from model.wf_analysis import WfAnalysis
from model.wf_build import WfBuild
from model.wf_step import WfStep
from pipeline_wrapper import pipeline_handlers
from waterfall import buildbot
from waterfall.detect_first_failure_pipeline import DetectFirstFailurePipeline
from waterfall import lock_util
from waterfall import swarming_util


class DetectFirstFailureTest(testing.AppengineTestCase):
  app_module = pipeline_handlers._APP

  def setUp(self):
    super(DetectFirstFailureTest, self).setUp()

    with self.mock_urlfetch() as urlfetch:
      self.mocked_urlfetch = urlfetch

    def _WaitUntilDownloadAllowed(*_):
      return True

    self.mock(lock_util, 'WaitUntilDownloadAllowed', _WaitUntilDownloadAllowed)

  def _TimeBeforeNowBySeconds(self, seconds):
    return datetime.datetime.utcnow() - datetime.timedelta(0, seconds, 0)

  def _CreateAndSaveWfAnanlysis(
      self, master_name, builder_name, build_number, status):
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.status = status
    analysis.put()

  def _GetBuildData(self, master_name, builder_name, build_number):
    file_name = os.path.join(
        os.path.dirname(__file__), 'data',
        '%s_%s_%d.json' % (master_name, builder_name, build_number))
    with open(file_name, 'r') as f:
      return f.read()

  def _MockUrlfetchWithBuildData(
      self, master_name, builder_name, build_number, build_data=None):
    """If build data is None, use json file in waterfall/test/data."""
    if build_data is None:
      build_data = self._GetBuildData(master_name, builder_name, build_number)

    build_url = buildbot.CreateBuildUrl(
        master_name, builder_name, build_number, json_api=True)
    self.mocked_urlfetch.register_handler(build_url, build_data)

  def testLookBackUntilGreenBuild(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123

    self._CreateAndSaveWfAnanlysis(
        master_name, builder_name, build_number, wf_analysis_status.ANALYZING)

    # Setup build data for builds:
    # 123: mock urlfetch to ensure it is fetched.
    self._MockUrlfetchWithBuildData(master_name, builder_name, 123)
    # 122: mock a build in datastore to ensure it is not fetched again.
    build = WfBuild.Create(master_name, builder_name, 122)
    build.data = self._GetBuildData(master_name, builder_name, 122)
    build.completed = True
    build.put()
    self._MockUrlfetchWithBuildData(
        master_name, builder_name, 122, build_data='Blow up if used!')
    # 121: mock a build in datastore to ensure it is updated.
    build = WfBuild.Create(master_name, builder_name, 121)
    build.data = 'Blow up if used!'
    build.last_crawled_time = self._TimeBeforeNowBySeconds(7200)
    build.completed = False
    build.put()
    self._MockUrlfetchWithBuildData(master_name, builder_name, 121)

    pipeline = DetectFirstFailurePipeline()
    failure_info = pipeline.run(master_name, builder_name, build_number)

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

    self.assertEqual(expected_failed_steps, failure_info['failed_steps'])

  def testFirstFailureLastPassUpdating(self):
    """last pass always should just be updated once."""
    master_name = 'm'
    builder_name = 'b'
    build_number = 100

    self._CreateAndSaveWfAnanlysis(
        master_name, builder_name, build_number, wf_analysis_status.ANALYZING)
    # Setup build data for builds:
    # 100: net_unitests failed, unit_tests failed.
    # 99: net_unitests passed, unit_tests failed.
    # 98: net_unitests passed, unit_tests failed.
    # 97: net_unitests failed, unit_tests failed.
    # 96: net_unitests passed, unit_tests passed.
    for i in range(5):
      self._MockUrlfetchWithBuildData(master_name, builder_name, 100 - i)

    pipeline = DetectFirstFailurePipeline()
    failure_info = pipeline.run(master_name, builder_name, build_number)

    expected_failed_steps = {
        'net_unittests': {
            'last_pass': 99,
            'current_failure': 100,
            'first_failure': 100
        },
        'unit_tests': {
            'last_pass': 96,
            'current_failure': 100,
            'first_failure': 97
        }
    }

    self.assertEqual(expected_failed_steps, failure_info['failed_steps'])

  def testStopLookingBackIfAllFailedStepsPassedInLastBuild(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124

    self._CreateAndSaveWfAnanlysis(
        master_name, builder_name, build_number, wf_analysis_status.ANALYZING)

    # Setup build data for builds:
    self._MockUrlfetchWithBuildData(master_name, builder_name, 124)
    self._MockUrlfetchWithBuildData(master_name, builder_name, 123,
                                    build_data=None)
    self._MockUrlfetchWithBuildData(
        master_name, builder_name, 122, build_data='Blow up if used!')

    pipeline = DetectFirstFailurePipeline()
    failure_info = pipeline.run(master_name, builder_name, build_number)

    expected_failed_steps = {
        'a': {
            'last_pass': 123,
            'current_failure': 124,
            'first_failure': 124
        }
    }

    self.assertEqual(expected_failed_steps, failure_info['failed_steps'])

  def testAnalyzeSuccessfulBuild(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 121

    self._CreateAndSaveWfAnanlysis(
        master_name, builder_name, build_number, wf_analysis_status.ANALYZING)

    # Setup build data for builds:
    self._MockUrlfetchWithBuildData(master_name, builder_name, 121)
    self._MockUrlfetchWithBuildData(
        master_name, builder_name, 120, build_data='Blow up if used!')

    pipeline = DetectFirstFailurePipeline()
    failure_info = pipeline.run(master_name, builder_name, build_number)

    self.assertFalse(failure_info['failed'])

  def testStopLookingBackIfFindTheFirstBuild(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 2

    self._CreateAndSaveWfAnanlysis(
        master_name, builder_name, build_number, wf_analysis_status.ANALYZING)

    # Setup build data for builds:
    self._MockUrlfetchWithBuildData(master_name, builder_name, 2)
    self._MockUrlfetchWithBuildData(master_name, builder_name, 1)
    self._MockUrlfetchWithBuildData(master_name, builder_name, 0)

    pipeline = DetectFirstFailurePipeline()
    failure_info = pipeline.run(master_name, builder_name, build_number)

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

    self.assertEqual(expected_failed_steps, failure_info['failed_steps'])

  def _MockGetAuthToken(self):
    return '123456'

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
      if data_type =='isolated':
        return zlib.compress(f.read())
      return f.read()

  def _MockUrlFetchWithSwarmingData(
      self, master_name, builder_name, build_number, step_name=None):
    url = ('https://chromium-swarm.appspot.com/_ah/api/swarming/v1/tasks/'
           'list?tags=%s&tags=%s&tags=%s') % (
               urllib.quote('master:%s' % master_name),
               urllib.quote('buildername:%s' % builder_name),
               urllib.quote('buildnumber:%d' % build_number))

    if step_name:
      url += '&tags=%s' % urllib.quote('stepname:%s' % step_name)
      response = self._GetSwarmingData('step', build_number=build_number)
    else:
      response = self._GetSwarmingData('build')

    cursor_swarming_data = {
      'cursor': None,
      'items': [],
      'state': 'all',
      'limit': 100,
      'sort': 'created_ts'
    }
    cursor_url = ('%s&cursor=thisisacursor') % url

    self.mocked_urlfetch.register_handler(url, response)
    self.mocked_urlfetch.register_handler(
        cursor_url, json.dumps(cursor_swarming_data))

  def _MockUrlfetchWithIsolatedData(
      self, isolated_data=None, file_url=None,
      file_name=None, build_number=None):  # pragma: no cover
    if isolated_data:  # Mocks POST requests to isolated server.
      url = '%s/_ah/api/isolateservice/v2/retrieve' %(
          isolated_data['isolatedserver'])
      post_data = {
          'digest': isolated_data['digest'],
          'namespace': isolated_data['namespace']
      }
      file_name = isolated_data['digest']
      if build_number:
        file_name = isolated_data['digest'][:-4]
      content = self._GetSwarmingData('isolated', file_name, build_number)

    elif file_url and file_name:  # Mocks GET requests to isolated server.
      url = file_url
      post_data = None
      content = self._GetSwarmingData('isolated', file_name)

    self.mocked_urlfetch.register_handler(
        url, content,
        data=(json.dumps(post_data, sort_keys=True,separators=(',', ':'))
            if post_data else None))

  def testAnalyzeSwarmingTestResultsInitiateLastPassForTests(self):
    json_data = json.loads(
        self._GetSwarmingData('isolated-plain', 'm_b_223_abc_test.json'))

    step = WfStep.Create('m', 'b', 223, 'abc_test')
    step.isolated = True
    step.put()

    failed_step = {
        'current_failure': 223,
        'first_failure': 221,
        'tests': {}
    }

    pipeline = DetectFirstFailurePipeline()
    pipeline._InitiateTestLevelFirstFailureAndSaveLog(
        json_data, step, failed_step)

    expected_failed_step = {
        'current_failure': 223,
        'first_failure': 221,
        'tests':{
            'Unittest2.Subtest1':{
              'current_failure': 223,
              'first_failure': 223
            },
            'Unittest3.Subtest2':{
              'current_failure': 223,
              'first_failure': 223,
            }
        }
    }

    self.assertEqual(expected_failed_step, failed_step)

  def testCheckFirstKnownFailureForSwarmingTestsFoundFlaky(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 221
    step_name = 'abc_test'
    failed_steps = {
        'abc_test': {
            'current_failure': 221,
            'first_failure': 221,
            'list_isolated_data':[
                {
                    'isolatedserver': 'https://isolateserver.appspot.com',
                    'namespace': 'default-gzip',
                    'digest': 'isolatedhashabctest-223'
                }
            ]
        }
    }
    builds = {
        '221':{
            'blame_list': ['commit1'],
            'chromium_revision': 'commit1'
        },
        '222':{
            'blame_list': ['commit2'],
            'chromium_revision': 'commit2'
        },
        '223':{
            'blame_list': ['commit3', 'commit4'],
            'chromium_revision': 'commit4'
        }
    }
    expected_failed_steps = failed_steps
    step = WfStep.Create(master_name, builder_name, build_number, step_name)
    step.isolated = True
    step.put()

    self.mock(
      DetectFirstFailurePipeline, '_GetAuthToken', self._MockGetAuthToken)
    def MockGetIsolatedDataForFailedBuild(*_):
      return True
    self.mock(
        swarming_util, 'GetIsolatedDataForFailedBuild',
        MockGetIsolatedDataForFailedBuild)

    def MockRetrieveShardedTestResultsFromIsolatedServer(*_):
      return json.loads(
          self._GetSwarmingData(
              'isolated-plain', 'm_b_223_abc_test_flaky.json'))
    self.mock(
        swarming_util, 'RetrieveShardedTestResultsFromIsolatedServer',
        MockRetrieveShardedTestResultsFromIsolatedServer)

    pipeline = DetectFirstFailurePipeline()
    pipeline._CheckFirstKnownFailureForSwarmingTests(
        master_name, builder_name, build_number, failed_steps, builds)

    self.assertEqual(expected_failed_steps, failed_steps)

  def testUpdateFirstFailureOnTestLevelThenUpdateStepLevel(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    step_name = 'abc_test'
    failed_step = {
        'current_failure': 223,
        'first_failure': 221,
        'tests':{
            'Unittest2.Subtest1':{
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': 223
            },
            'Unittest3.Subtest2':{
                'current_failure': 223,
                'first_failure': 223
            }
        }
    }

    self.mock(
      DetectFirstFailurePipeline, '_GetAuthToken', self._MockGetAuthToken)
    for n in xrange(222, 220, -1):
      # Mock retrieving data from swarming server for a single step.
      self._MockUrlFetchWithSwarmingData(
          master_name, builder_name, n, 'abc_test')

      # Mock retrieving hash to output.json from isolated server.
      isolated_data = {
          'isolatedserver': 'https://isolateserver.appspot.com',
          'namespace': 'default-gzip',
          'digest': 'isolatedhashabctest-%d' % n
      }
      self._MockUrlfetchWithIsolatedData(
          isolated_data, build_number=n)
      # Mock retrieving url to output.json from isolated server.
      file_hash_data = {
          'isolatedserver': 'https://isolateserver.appspot.com',
          'namespace': 'default-gzip',
          'digest': 'abctestoutputjsonhash-%d' % n
      }
      self._MockUrlfetchWithIsolatedData(
          file_hash_data, build_number=n)

      # Mock downloading output.json from isolated server.
      self._MockUrlfetchWithIsolatedData(
          None,
          ('https://isolateserver.storage.googleapis.com/default-gzip/'
           'm_b_%d_abc_test' % n),
          '%s_%s_%d_%s.json' % (master_name, builder_name, n, 'abc_test'))

    pipeline = DetectFirstFailurePipeline()
    pipeline._UpdateFirstFailureOnTestLevel(
        master_name, builder_name, build_number, step_name, failed_step,
        HttpClient(), '1234567')

    expected_failed_step = {
        'current_failure': 223,
        'first_failure': 221,
        'tests':{
            'Unittest2.Subtest1':{
                'current_failure': 223,
                'first_failure': 222,
                'last_pass': 221
            },
            'Unittest3.Subtest2':{
                'current_failure': 223,
                'first_failure': 221
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
        'tests':{
            'Unittest2.Subtest1':{
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': 223
            }
        }
    }
    self.mock(
      DetectFirstFailurePipeline, '_GetAuthToken', self._MockGetAuthToken)
    step = WfStep.Create(master_name, builder_name, 222, step_name)
    step.isolated = True
    step.log_data = 'flaky'
    step.put()

    pipeline = DetectFirstFailurePipeline()
    pipeline._UpdateFirstFailureOnTestLevel(
        master_name, builder_name, build_number, step_name, failed_step,
        HttpClient(), '1234567')

    expected_failed_step = {
        'current_failure': 223,
        'first_failure': 223,
        'last_pass': 222,
        'tests':{
            'Unittest2.Subtest1':{
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': 222
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
            'current_failure': 223,
            'first_failure': 222,
            'last_pass': 221,
            'list_isolated_data':[
                {
                    'isolatedserver': 'https://isolateserver.appspot.com',
                    'namespace': 'default-gzip',
                    'digest': 'isolatedhashabctest-223'
                }
            ],
            'tests':{
                'Unittest2.Subtest1':{
                  'current_failure': 223,
                  'first_failure': 222,
                  'last_pass': 221
                },
                'Unittest3.Subtest2':{
                  'current_failure': 223,
                  'first_failure': 222,
                  'last_pass': 221
                }
            }
        }
    }

    builds = {
        '220':{
            'blame_list': ['commit0'],
            'chromium_revision': 'commit0'
        },
        '221':{
            'blame_list': ['commit1'],
            'chromium_revision': 'commit1'
        },
        '222':{
            'blame_list': ['commit2'],
            'chromium_revision': 'commit2'
        },
        '223':{
            'blame_list': ['commit3', 'commit4'],
            'chromium_revision': 'commit4'
        }
    }

    pipeline = DetectFirstFailurePipeline()
    pipeline._UpdateFailureInfoBuilds(failed_steps, builds)
    expected_builds = {
        '221':{
            'blame_list': ['commit1'],
            'chromium_revision': 'commit1'
        },
        '222':{
            'blame_list': ['commit2'],
            'chromium_revision': 'commit2'
        },
        '223':{
            'blame_list': ['commit3', 'commit4'],
            'chromium_revision': 'commit4'
        }
    }
    self.assertEqual(builds, expected_builds)

  def testTestLevelFailedInfo(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223

    self._CreateAndSaveWfAnanlysis(
        master_name, builder_name, build_number, wf_analysis_status.ANALYZING)

    self.mock(
      DetectFirstFailurePipeline, '_GetAuthToken', self._MockGetAuthToken)
    # Mock data for retrieving data from swarming server for a build.
    self._MockUrlFetchWithSwarmingData(master_name, builder_name, 223)

    for n in xrange(223, 219, -1):  #pragma: no cover
      # Setup build data for builds:
      self._MockUrlfetchWithBuildData(master_name, builder_name, n)
      if n == 220:
        break

      # Mock data for retrieving data from swarming server for a single step.
      self._MockUrlFetchWithSwarmingData(
          master_name, builder_name, n, 'abc_test')

      # Mock data for retrieving hash to output.json from isolated server.
      isolated_data = {
          'isolatedserver': 'https://isolateserver.appspot.com',
          'namespace': 'default-gzip',
          'digest': 'isolatedhashabctest-%d' % n
      }
      self._MockUrlfetchWithIsolatedData(
          isolated_data, build_number=n)
      # Mock data for retrieving url to output.json from isolated server.
      file_hash_data = {
          'isolatedserver': 'https://isolateserver.appspot.com',
          'namespace': 'default-gzip',
          'digest': 'abctestoutputjsonhash-%d' % n
      }
      self._MockUrlfetchWithIsolatedData(
          file_hash_data, build_number=n)

      # Mock data for downloading output.json from isolated server.
      self._MockUrlfetchWithIsolatedData(
          None,
          ('https://isolateserver.storage.googleapis.com/default-gzip/'
           'm_b_%d_abc_test' % n),
          '%s_%s_%d_%s.json' % (master_name, builder_name, n, 'abc_test'))

    step_221 = WfStep.Create(master_name, builder_name, 221, 'abc_test')
    step_221.isolated = True
    step_221.log_data = (
        '{"Unittest3.Subtest3": "YS9iL3UzczIuY2M6MTEwOiBGYWlsdXJlCg=="}')
    step_221.put()

    pipeline = DetectFirstFailurePipeline()
    failure_info = pipeline.run(master_name, builder_name, build_number)

    expected_failed_steps = {
        'compile': {
            'current_failure': 223,
            'first_failure': 221,
            'last_pass': 220
        },
        'abc_test': {
            'current_failure': 223,
            'first_failure': 222,
            'last_pass': 221,
            'list_isolated_data':[
                {
                    'isolatedserver': 'https://isolateserver.appspot.com',
                    'namespace': 'default-gzip',
                    'digest': 'isolatedhashabctest-223'
                }
            ],
            'tests':{
                'Unittest2.Subtest1':{
                  'current_failure': 223,
                  'first_failure': 222,
                  'last_pass': 221
                },
                'Unittest3.Subtest2':{
                  'current_failure': 223,
                  'first_failure': 222,
                  'last_pass': 221
                }
            }
        }
    }

    expected_step_log_data = {
        223: ('{"Unittest2.Subtest1": "RVJST1I6eF90ZXN0LmNjOjEyMzRcbmEvYi91Mn'
              'MxLmNjOjU2NzogRmFpbHVyZVxuRVJST1I6WzJdOiAyNTk0NzM1MDAwIGJvZ28tb'
              'Wljcm9zZWNvbmRzXG5FUlJPUjp4X3Rlc3QuY2M6MTIzNAphL2IvdTJzMS5jYzo1'
              'Njc6IEZhaWx1cmUK", '
              '"Unittest3.Subtest2": "YS9iL3UzczIuY2M6MTEwOiBGYWlsdXJlCg=="}'),
        222: ('{"Unittest2.Subtest1": "RVJST1I6eF90ZXN0LmNjOjEyMzRcbmEvYi91Mn'
              'MxLmNjOjU2NzogRmFpbHVyZVxuRVJST1I6WzJdOiAyNTk0NzM1MDAwIGJvZ28tb'
              'Wljcm9zZWNvbmRzXG5FUlJPUjp4X3Rlc3QuY2M6MTIzNAphL2IvdTJzMS5jYzo1'
              'Njc6IEZhaWx1cmUK", '
             '"Unittest3.Subtest2": "YS9iL3UzczIuY2M6MTEwOiBGYWlsdXJlCg=="}'),
        221: '{"Unittest3.Subtest3": "YS9iL3UzczIuY2M6MTEwOiBGYWlsdXJlCg=="}'
    }

    for n in xrange(223, 220, -1):
      step = WfStep.Get(master_name, builder_name, n, 'abc_test')
      self.assertIsNotNone(step)
      self.assertTrue(step.isolated)
      self.assertEqual(expected_step_log_data[n], step.log_data)

    self.assertEqual(expected_failed_steps, failure_info['failed_steps'])
