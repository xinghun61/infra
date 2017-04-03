# Copyright 2014 The Chromium Authors. All rights reserved.
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
from gae_libs.pipeline_wrapper import pipeline_handlers
from model import analysis_status
from model.wf_analysis import WfAnalysis
from model.wf_build import WfBuild
from model.wf_step import WfStep
from waterfall import buildbot
from waterfall import detect_first_failure_pipeline
from waterfall import lock_util
from waterfall.build_info import BuildInfo
from waterfall.detect_first_failure_pipeline import DetectFirstFailurePipeline
from waterfall.test import wf_testcase


class DetectFirstFailureTest(wf_testcase.WaterfallTestCase):
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

  @mock.patch.object(buildbot, 'GetBuildDataFromBuildMaster')
  def testLookBackUntilGreenBuild(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123

    self._CreateAndSaveWfAnanlysis(
        master_name, builder_name, build_number, analysis_status.RUNNING)

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

    mock_fn.side_effect = [
        self._GetBuildData(master_name, builder_name, 123),
        self._GetBuildData(master_name, builder_name, 121)
    ]
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

  @mock.patch.object(buildbot, 'GetBuildDataFromBuildMaster')
  def testFirstFailureLastPassUpdating(self, mock_fn):
    """last pass always should just be updated once."""
    master_name = 'm'
    builder_name = 'b'
    build_number = 100

    self._CreateAndSaveWfAnanlysis(
        master_name, builder_name, build_number, analysis_status.RUNNING)

    # Setup build data for builds:
    # 100: net_unitests failed, unit_tests failed.
    # 99: net_unitests passed, unit_tests failed.
    # 98: net_unitests passed, unit_tests failed.
    # 97: net_unitests failed, unit_tests failed.
    # 96: net_unitests passed, unit_tests passed.
    side_effects = []
    for i in range(5):
      side_effects.append(
          self._GetBuildData(master_name, builder_name, 100 - i))
    mock_fn.side_effect = side_effects

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

  @mock.patch.object(buildbot, 'GetBuildDataFromBuildMaster')
  def testStopLookingBackIfAllFailedStepsPassedInLastBuild(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124

    self._CreateAndSaveWfAnanlysis(
        master_name, builder_name, build_number, analysis_status.RUNNING)

    # Setup build data for builds:
    mock_fn.side_effect = [
        self._GetBuildData(master_name, builder_name, 124),
        self._GetBuildData(master_name, builder_name, 123)
    ]

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

  @mock.patch.object(buildbot, 'GetBuildDataFromBuildMaster')
  def testAnalyzeSuccessfulBuild(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 121

    self._CreateAndSaveWfAnanlysis(
        master_name, builder_name, build_number, analysis_status.RUNNING)

    # Setup build data for builds:
    mock_fn.return_value = self._GetBuildData(master_name, builder_name, 121)

    pipeline = DetectFirstFailurePipeline()
    failure_info = pipeline.run(master_name, builder_name, build_number)

    self.assertFalse(failure_info['failed'])

  @mock.patch.object(buildbot, 'GetBuildDataFromBuildMaster')
  def testAnalyzeInfraExceptionBuild(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 120

    self._CreateAndSaveWfAnanlysis(
        master_name, builder_name, build_number, analysis_status.RUNNING)

    # Setup build data for builds:
    mock_fn.return_value = self._GetBuildData(master_name, builder_name, 120)

    pipeline = DetectFirstFailurePipeline()
    failure_info = pipeline.run(master_name, builder_name, build_number)

    self.assertEqual(failure_info['failure_type'], failure_type.INFRA)

  @mock.patch.object(buildbot, 'GetBuildDataFromBuildMaster')
  def testStopLookingBackIfFindTheFirstBuild(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 2

    self._CreateAndSaveWfAnanlysis(
        master_name, builder_name, build_number, analysis_status.RUNNING)

    # Setup build data for builds:
    mock_fn.side_effect = [
        self._GetBuildData(master_name, builder_name, 2),
        self._GetBuildData(master_name, builder_name, 1),
        self._GetBuildData(master_name, builder_name, 0)
    ]

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
      file_name=None, build_number=None):
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
        url, content,
        data=(json.dumps(post_data, sort_keys=True, separators=(',', ':'))
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

  @mock.patch.object(detect_first_failure_pipeline, 'swarming_util')
  def testCheckFirstKnownFailureForSwarmingTestsFoundFlaky(self, mock_module):
    master_name = 'm'
    builder_name = 'b'
    build_number = 221
    step_name = 'abc_test'
    failed_steps = {
        'abc_test': {
            'current_failure': 221,
            'first_failure': 221,
            'list_isolated_data': [
                {
                    'isolatedserver': 'https://isolateserver.appspot.com',
                    'namespace': 'default-gzip',
                    'digest': 'isolatedhashabctest-223'
                }
            ]
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
      json.loads(self._GetSwarmingData(
          'isolated-plain', 'm_b_223_abc_test_flaky.json')))

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
        'tests': {
            'Unittest2.Subtest1': {
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': 223,
                'base_test_name': 'Unittest2.Subtest1'
            },
            'Unittest3.Subtest2': {
                'current_failure': 223,
                'first_failure': 223,
                'base_test_name': 'Unittest3.Subtest2'
            }
        }
    }

    for n in xrange(222, 220, -1):
      # Mock retrieving data from swarming server for a single step.
      self._MockUrlFetchWithSwarmingData(
          master_name, builder_name, n, 'abc_test')

      # Mock retrieving hash to output.json from isolated server.
      isolated_data = {
          'isolatedserver': 'https://isolateserver.appspot.com',
          'namespace': {
              'namespace': 'default-gzip'
          },
          'digest': 'isolatedhashabctest-%d' % n
      }
      self._MockUrlfetchWithIsolatedData(
          isolated_data, build_number=n)
      # Mock retrieving url to output.json from isolated server.
      file_hash_data = {
          'isolatedserver': 'https://isolateserver.appspot.com',
          'namespace': {
              'namespace': 'default-gzip'
          },
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
        HttpClientAppengine())

    expected_failed_step = {
        'current_failure': 223,
        'first_failure': 221,
        'tests': {
            'Unittest2.Subtest1': {
                'current_failure': 223,
                'first_failure': 222,
                'last_pass': 221,
                'base_test_name': 'Unittest2.Subtest1'
            },
            'Unittest3.Subtest2': {
                'current_failure': 223,
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

    pipeline = DetectFirstFailurePipeline()
    pipeline._UpdateFirstFailureOnTestLevel(
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
            'current_failure': 223,
            'first_failure': 222,
            'last_pass': 221,
            'list_isolated_data': [
                {
                    'isolatedserver': 'https://isolateserver.appspot.com',
                    'namespace': 'default-gzip',
                    'digest': 'isolatedhashabctest-223'
                }
            ],
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

    pipeline = DetectFirstFailurePipeline()
    pipeline._UpdateFailureInfoBuilds(failed_steps, builds)
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

  @mock.patch.object(buildbot, 'GetBuildDataFromBuildMaster')
  def testTestLevelFailedInfo(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223

    self._CreateAndSaveWfAnanlysis(
        master_name, builder_name, build_number, analysis_status.RUNNING)

    # Mock data for retrieving data from swarming server for a build.
    self._MockUrlFetchWithSwarmingData(master_name, builder_name, 223)

    mock_fn.side_effect = [
      self._GetBuildData( master_name, builder_name, 223),
      self._GetBuildData(master_name, builder_name, 222),
      self._GetBuildData(master_name, builder_name, 221),
      self._GetBuildData(master_name, builder_name, 220)
    ]
    for n in xrange(223, 219, -1):  # pragma: no branch.
      # Setup build data for builds:

      if n == 220:
        break

      # Mock data for retrieving data from swarming server for a single step.
      self._MockUrlFetchWithSwarmingData(
          master_name, builder_name, n, 'abc_test')

      # Mock data for retrieving hash to output.json from isolated server.
      isolated_data = {
          'isolatedserver': 'https://isolateserver.appspot.com',
          'namespace': {
              'namespace': 'default-gzip'
          },
          'digest': 'isolatedhashabctest-%d' % n
      }
      self._MockUrlfetchWithIsolatedData(isolated_data, build_number=n)
      # Mock data for retrieving url to output.json from isolated server.
      file_hash_data = {
          'isolatedserver': 'https://isolateserver.appspot.com',
          'namespace': {
              'namespace': 'default-gzip'
          },
          'digest': 'abctestoutputjsonhash-%d' % n
      }
      self._MockUrlfetchWithIsolatedData(file_hash_data, build_number=n)

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
        'abc_test': {
            'current_failure': 223,
            'first_failure': 222,
            'last_pass': 221,
            'list_isolated_data': [
                {
                    'isolatedserver': 'https://isolateserver.appspot.com',
                    'namespace': 'default-gzip',
                    'digest': 'isolatedhashabctest-223'
                }
            ],
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

  def testRunPipelineForCompileFailure(self):
    def _MockExtractBuildInfo(*_):
      build_info = BuildInfo('m', 'b', 25409)
      build_info.failed_steps = {
          'compile': {
              'last_pass': '25408',
              'current_failure': '25409',
              'first_failure': '25409'
          }
      }
      return build_info

    self.mock(DetectFirstFailurePipeline, '_ExtractBuildInfo',
              _MockExtractBuildInfo)

    self._CreateAndSaveWfAnanlysis('m', 'b', 25409, analysis_status.RUNNING)
    pipeline = DetectFirstFailurePipeline()
    failure_info = pipeline.run('m', 'b', 25409)

    expected_failure_info = {
        'failed': True,
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 25409,
        'chromium_revision': None,
        'builds': {
            25409: {
                'blame_list': [],
                'chromium_revision': None
            }
        },
        'failed_steps': {
            'compile': {
                'current_failure': 25409,
                'first_failure': 25409
            }
        },
        'failure_type': failure_type.COMPILE
    }

    self.assertEqual(failure_info, expected_failure_info)

  def testGetFailureType(self):
    cases = {
        failure_type.UNKNOWN: [],
        failure_type.COMPILE: ['compile', 'slave_steps'],
        failure_type.TEST: ['browser_tests'],
    }
    for expected_type, failed_steps in cases.iteritems():
      build_info = BuildInfo('m', 'b', 123)
      build_info.failed_steps = failed_steps
      self.assertEqual(
          expected_type,
          detect_first_failure_pipeline._GetFailureType(build_info))

  def testRemoveAllPrefixes(self):
    test_smaples = {
        'test1': 'test1',
        'PRE_t': 'PRE_t',
        'TestSuite1.Test1': 'TestSuite1.Test1',
        'TestSuite1.PRE_Test1': 'TestSuite1.Test1',
        'TestSuite1.PRE_PRE_Test1': 'TestSuite1.Test1',
        'PRE_TestSuite1.Test1': 'PRE_TestSuite1.Test1'
    }

    for test, expected_base_test in test_smaples.iteritems():
      base_test = detect_first_failure_pipeline._RemoveAllPrefixes(test)
      self.assertEqual(base_test, expected_base_test)
