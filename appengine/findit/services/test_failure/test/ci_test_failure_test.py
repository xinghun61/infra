# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import mock
import os
import urllib
import zlib

from common.findit_http_client import FinditHttpClient
from model.wf_step import WfStep
from services.test_failure import ci_test_failure
from waterfall import swarming_util
from waterfall.test import wf_testcase


class CITestFailureServicesTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(CITestFailureServicesTest, self).setUp()

    with self.mock_urlfetch() as urlfetch:
      self.mocked_urlfetch = urlfetch

  def _GetSwarmingData(self, data_type, file_name=None, build_number=None):
    file_name_map = {
        'build': 'sample_swarming_build_tasks.json',
        'step': 'sample_swarming_build_abctest_tasks.json'
    }
    file_name = file_name_map.get(data_type, file_name)
    swarming_tasks_file = os.path.join(
        os.path.dirname(__file__), os.pardir, os.pardir, 'test', 'data',
        file_name)
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

    ci_test_failure._InitiateTestLevelFirstFailureAndSaveLog(
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

    ci_test_failure._InitiateTestLevelFirstFailureAndSaveLog(
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

  @mock.patch.object(ci_test_failure, 'swarming_util')
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

    ci_test_failure.CheckFirstKnownFailureForSwarmingTests(
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
    ci_test_failure.CheckFirstKnownFailureForSwarmingTests(
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

    ci_test_failure._UpdateFirstFailureOnTestLevel(
        master_name, builder_name, build_number, step_name, failed_step,
        FinditHttpClient())

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

    ci_test_failure._UpdateFirstFailureOnTestLevel(
        master_name, builder_name, build_number, step_name, failed_step,
        FinditHttpClient())

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

    ci_test_failure._UpdateFailureInfoBuilds(failed_steps, builds)
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
        ci_test_failure._StartTestLevelCheckForFirstFailure(
            master_name, builder_name, build_number, step_name, failed_step,
            None))

  @mock.patch.object(swarming_util, 'GetIsolatedDataForStep', return_value=None)
  def testGetSameStepFromBuild(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 121
    step_name = 'atest'
    self.assertIsNone(
        ci_test_failure._GetSameStepFromBuild(master_name, builder_name,
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
        ci_test_failure._GetSameStepFromBuild(master_name, builder_name,
                                              build_number, step_name, None))

  def testStepNotHaveFirstTimeFailure(self):
    build_number = 1
    tests = {'test1': {'first_failure': 0}}
    self.assertFalse(
        ci_test_failure.AnyTestHasFirstTimeFailure(tests, build_number))

  def testAnyTestHasFirstTimeFailure(self):
    build_number = 1
    tests = {'test1': {'first_failure': 1}}
    self.assertTrue(
        ci_test_failure.AnyTestHasFirstTimeFailure(tests, build_number))
