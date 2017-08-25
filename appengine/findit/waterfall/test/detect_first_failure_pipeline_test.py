# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import mock
import os
import urllib
import zlib

from common.waterfall import failure_type
from gae_libs.pipeline_wrapper import pipeline_handlers
from libs import analysis_status
from model.wf_analysis import WfAnalysis
from model.wf_step import WfStep
from waterfall import buildbot
from waterfall import build_failure
from waterfall.detect_first_failure_pipeline import DetectFirstFailurePipeline
from waterfall.test import wf_testcase


class DetectFirstFailureTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def setUp(self):
    super(DetectFirstFailureTest, self).setUp()

    with self.mock_urlfetch() as urlfetch:
      self.mocked_urlfetch = urlfetch

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

  @mock.patch.object(buildbot, 'GetBuildDataFromMilo')
  def testFirstFailureLastPassUpdating(self, mock_fn):
    """last pass always should just be updated once."""
    master_name = 'm'
    builder_name = 'b'
    build_number = 100

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.RUNNING)

    # Setup build data for builds:
    # 100: net_unitests failed, unit_tests failed.
    # 99: net_unitests passed, unit_tests failed.
    # 98: net_unitests passed, unit_tests failed.
    # 97: net_unitests failed, unit_tests failed.
    # 96: net_unitests passed, unit_tests passed.
    side_effects = []
    for i in xrange(1, 5):
      side_effects.append(
          self._GetBuildData(master_name, builder_name, 100 - i))
    mock_fn.side_effect = side_effects

    current_build_failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'builds': {
            100: {
                'chromium_revision':
                    '64c72819e898e952103b63eabc12772f9640af07',
                'blame_list': ['64c72819e898e952103b63eabc12772f9640af07']
            }
        },
        'failed_steps': {
            'net_unittests': {
                'current_failure': 100,
                'first_failure': 100
            },
            'unit_tests': {
                'current_failure': 100,
                'first_failure': 100
            }
        },
        'failed': True,
        'chromium_revision': '64c72819e898e952103b63eabc12772f9640af07',
        'failure_type': failure_type.TEST
    }

    pipeline = DetectFirstFailurePipeline()
    failure_info = pipeline.run(current_build_failure_info)

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

  @mock.patch.object(build_failure, 'CheckForFirstKnownFailure')
  def testRunPipelineForCompileFailure(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 25409

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.RUNNING)

    current_build_failure_info = {
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
        'failure_type': failure_type.COMPILE,
        'parent_mastername': None,
        'parent_buildername': None,
    }

    pipeline = DetectFirstFailurePipeline()
    failure_info = pipeline.run(current_build_failure_info)

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
        'failure_type': failure_type.COMPILE,
        'parent_mastername': None,
        'parent_buildername': None,
    }

    self.assertEqual(failure_info, expected_failure_info)

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

  def _MockUrlFetchWithSwarmingData(self,
                                    master_name,
                                    builder_name,
                                    build_number,
                                    step_name=None):
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

  @mock.patch.object(buildbot, 'GetBuildDataFromMilo')
  def testTestLevelFailedInfo(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    current_build_failure_info = {
        'failed': True,
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'chromium_revision': None,
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

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.RUNNING)

    # Mock data for retrieving data from swarming server for a build.
    self._MockUrlFetchWithSwarmingData(master_name, builder_name, 223)

    mock_fn.side_effect = [
        self._GetBuildData(master_name, builder_name, 223),
        self._GetBuildData(master_name, builder_name, 222),
        self._GetBuildData(master_name, builder_name, 221),
        self._GetBuildData(master_name, builder_name, 220)
    ]
    for n in xrange(223, 219, -1):  # pragma: no branch.
      # Setup build data for builds:

      if n == 220:
        break

      # Mock data for retrieving data from swarming server for a single step.
      self._MockUrlFetchWithSwarmingData(master_name, builder_name, n,
                                         'abc_test')

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
          None, ('https://isolateserver.storage.googleapis.com/default-gzip/'
                 'm_b_%d_abc_test' % n),
          '%s_%s_%d_%s.json' % (master_name, builder_name, n, 'abc_test'))

    step_221 = WfStep.Create(master_name, builder_name, 221, 'abc_test')
    step_221.isolated = True
    step_221.log_data = (
        '{"Unittest3.Subtest3": "YS9iL3UzczIuY2M6MTEwOiBGYWlsdXJlCg=="}')
    step_221.put()

    pipeline = DetectFirstFailurePipeline()
    failure_info = pipeline.run(current_build_failure_info)

    expected_failed_steps = {
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
        221:
            '{"Unittest3.Subtest3": "YS9iL3UzczIuY2M6MTEwOiBGYWlsdXJlCg=="}'
    }

    for n in xrange(223, 220, -1):
      step = WfStep.Get(master_name, builder_name, n, 'abc_test')
      self.assertIsNotNone(step)
      self.assertTrue(step.isolated)
      self.assertEqual(expected_step_log_data[n], step.log_data)

    self.assertEqual(expected_failed_steps, failure_info['failed_steps'])
