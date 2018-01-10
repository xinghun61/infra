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
from services.parameters import TestFailureInfo
from services.parameters import TestFailedStep
from services.parameters import TestFailedSteps
from services.parameters import FailureInfoBuilds
from services.test_failure import ci_test_failure
from waterfall import swarming_util
from waterfall import waterfall_config
from waterfall.test import wf_testcase


class CITestFailureTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(CITestFailureTest, self).setUp()

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

    failed_step = {'current_failure': 223, 'first_failure': 221}
    failed_step = TestFailedStep.FromSerializable(failed_step)

    ci_test_failure._InitiateTestLevelFirstFailureAndSaveLog(
        json_data, step, failed_step)

    expected_failed_step = {
        'current_failure': 223,
        'first_failure': 221,
        'last_pass': None,
        'list_isolated_data': None,
        'tests': {
            'Unittest2.Subtest1': {
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': None,
                'base_test_name': 'Unittest2.Subtest1'
            },
            'Unittest3.Subtest2': {
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': None,
                'base_test_name': 'Unittest3.Subtest2'
            }
        }
    }

    self.assertEqual(expected_failed_step, failed_step.ToSerializable())

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
    failed_step = TestFailedStep.FromSerializable(failed_step)

    ci_test_failure._InitiateTestLevelFirstFailureAndSaveLog(
        json_data, step, failed_step)

    expected_failed_step = {
        'current_failure': 223,
        'first_failure': 221,
        'last_pass': 220,
        'list_isolated_data': None,
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
    self.assertEqual(expected_failed_step, failed_step.ToSerializable())

  @mock.patch.object(
      ci_test_failure, 'UpdateSwarmingSteps', return_value=True)
  @mock.patch.object(ci_test_failure, 'swarming_util')
  def testCheckFirstKnownFailureForSwarmingTestsFoundFlaky(
      self, mock_module, _):
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

    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed_steps': failed_steps,
        'builds': builds
    }
    failure_info = TestFailureInfo.FromSerializable(failure_info)

    expected_failed_steps = failed_steps
    expected_failed_steps['abc_test']['tests'] = None
    expected_failed_steps['abc_test']['last_pass'] = None
    step = WfStep.Create(master_name, builder_name, build_number, step_name)
    step.isolated = True
    step.put()

    mock_module.RetrieveShardedTestResultsFromIsolatedServer.return_value = (
        json.loads(
            self._GetSwarmingData('isolated-plain',
                                  'm_b_223_abc_test_flaky.json')))

    ci_test_failure.CheckFirstKnownFailureForSwarmingTests(
        master_name, builder_name, build_number, failure_info)

    self.assertEqual(expected_failed_steps,
                     failure_info.failed_steps.ToSerializable())

  @mock.patch.object(
      ci_test_failure, 'UpdateSwarmingSteps', return_value=False)
  def testCheckFirstKnownFailureForSwarmingTestsNoResult(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 224
    failed_steps = {}
    builds = {}
    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed_steps': failed_steps,
        'builds': builds
    }
    failure_info = TestFailureInfo.FromSerializable(failure_info)

    ci_test_failure.CheckFirstKnownFailureForSwarmingTests(
        master_name, builder_name, build_number, failure_info)
    self.assertEqual({}, failure_info.failed_steps.ToSerializable())

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
    failed_step = TestFailedStep.FromSerializable(failed_step)
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
        'list_isolated_data': None,
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
                'base_test_name': 'Unittest3.Subtest2',
                'last_pass': None
            }
        }
    }
    self.assertEqual(expected_failed_step, failed_step.ToSerializable())

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
    failed_step = TestFailedStep.FromSerializable(failed_step)
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
        'list_isolated_data': None,
        'tests': {
            'Unittest2.Subtest1': {
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': 222,
                'base_test_name': 'Unittest2.Subtest1'
            }
        }
    }
    self.assertEqual(expected_failed_step, failed_step.ToSerializable())

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
    failed_steps = TestFailedSteps.FromSerializable(failed_steps)

    builds = {
        220: {
            'blame_list': ['commit0'],
            'chromium_revision': 'commit0'
        },
        221: {
            'blame_list': ['commit1'],
            'chromium_revision': 'commit1'
        },
        222: {
            'blame_list': ['commit2'],
            'chromium_revision': 'commit2'
        },
        223: {
            'blame_list': ['commit3', 'commit4'],
            'chromium_revision': 'commit4'
        }
    }
    builds = FailureInfoBuilds.FromSerializable(builds)

    ci_test_failure._UpdateFailureInfoBuilds(failed_steps, builds)
    expected_builds = {
        221: {
            'blame_list': ['commit1'],
            'chromium_revision': 'commit1'
        },
        222: {
            'blame_list': ['commit2'],
            'chromium_revision': 'commit2'
        },
        223: {
            'blame_list': ['commit3', 'commit4'],
            'chromium_revision': 'commit4'
        }
    }
    self.assertEqual(expected_builds, builds.ToSerializable())

  @mock.patch.object(
      swarming_util,
      'RetrieveShardedTestResultsFromIsolatedServer',
      return_value=None)
  def testStartTestLevelCheckForFirstFailure(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 121
    step_name = 'atest'
    failed_step = {
        'list_isolated_data': [{
            'isolatedserver': 'https://isolateserver.appspot.com',
            'namespace': 'default-gzip',
            'digest': 'isolatedhashabctest-223'
        }]
    }
    failed_step = TestFailedStep.FromSerializable(failed_step)
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

  @mock.patch.object(swarming_util, 'ListSwarmingTasksDataByTags')
  def testUpdateSwarmingSteps(self, mock_data):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failed_steps = {
        'a_tests': {
            'current_failure': 2,
            'first_failure': 0
        },
        'unit_tests': {
            'current_failure': 2,
            'first_failure': 0
        },
        'compile': {
            'current_failure': 2,
            'first_failure': 0
        }
    }
    failed_steps = TestFailedSteps.FromSerializable(failed_steps)

    mock_data.return_value = [{
        'failure': True,
        'internal_failure': False,
        'tags': ['stepname:net_unittests'],
        'outputs_ref': {
            'isolatedserver': 'https://isolateserver.appspot.com',
            'namespace': 'default-gzip',
            'isolated': 'isolatedhashnetunittests'
        }
    }, {
        'failure': False,
        'internal_failure': False,
        'tags': ['stepname:unit_tests'],
        'outputs_ref': {
            'isolatedserver': 'https://isolateserver.appspot.com',
            'namespace': 'default-gzip',
            'isolated': 'isolatedhashunittests'
        }
    }, {
        'failure': True,
        'internal_failure': False,
        'tags': ['stepname:unit_tests'],
        'outputs_ref': {
            'isolatedserver': 'https://isolateserver.appspot.com',
            'namespace': 'default-gzip',
            'isolated': 'isolatedhashunittests1'
        }
    }, {
        'failure': True,
        'internal_failure': False,
        'tags': ['stepname:a'],
        'outputs_ref': {
            'isolatedserver': 'https://isolateserver.appspot.com',
            'namespace': 'default-gzip',
            'isolated': 'isolatedhasha'
        }
    }, {
        'failure': True,
        'internal_failure': False,
        'tags': ['stepname:a_tests'],
        'outputs_ref': {
            'isolatedserver': 'https://isolateserver.appspot.com',
            'namespace': 'default-gzip',
            'isolated': 'isolatedhashatests'
        }
    }, {
        'failure': True,
        'internal_failure': False,
        'tags': ['stepname:abc_test'],
        'outputs_ref': {
            'isolatedserver': 'https://isolateserver.appspot.com',
            'namespace': 'default-gzip',
            'isolated': 'isolatedhashabctest-223'
        }
    }, {
        'failure': True,
        'internal_failure': True
    }]
    result = ci_test_failure.UpdateSwarmingSteps(
        master_name, builder_name, build_number, failed_steps, None)

    expected_failed_steps = {
        'a_tests': {
            'current_failure':
                2,
            'first_failure':
                0,
            'last_pass':
                None,
            'tests':
                None,
            'list_isolated_data': [{
                'digest':
                    'isolatedhashatests',
                'namespace':
                    'default-gzip',
                'isolatedserver': (waterfall_config.GetSwarmingSettings().get(
                    'isolated_server'))
            }]
        },
        'unit_tests': {
            'current_failure':
                2,
            'first_failure':
                0,
            'last_pass':
                None,
            'tests':
                None,
            'list_isolated_data': [{
                'digest':
                    'isolatedhashunittests1',
                'namespace':
                    'default-gzip',
                'isolatedserver': (waterfall_config.GetSwarmingSettings().get(
                    'isolated_server'))
            }]
        },
        'compile': {
            'current_failure': 2,
            'first_failure': 0,
            'last_pass': None,
            'tests': None,
            'list_isolated_data': None
        }
    }

    for step_name in failed_steps:
      step = WfStep.Get(master_name, builder_name, build_number, step_name)
      if step_name == 'compile':
        self.assertIsNone(step)
      else:
        self.assertIsNotNone(step)

    self.assertTrue(result)
    self.assertEqual(expected_failed_steps, failed_steps.ToSerializable())

  @mock.patch.object(
      swarming_util, 'ListSwarmingTasksDataByTags', return_value=[])
  def testUpdateSwarmingStepsDownloadFailed(self, _):
    master_name = 'm'
    builder_name = 'download_failed'
    build_number = 223
    failed_steps = {
        'a_tests': {
            'current_failure': 2,
            'first_failure': 0
        },
        'unit_tests': {
            'current_failure': 2,
            'first_failure': 0
        }
    }
    failed_steps = TestFailedSteps.FromSerializable(failed_steps)

    result = ci_test_failure.UpdateSwarmingSteps(
        master_name, builder_name, build_number, failed_steps, None)
    expected_failed_steps = {
        'a_tests': {
            'current_failure': 2,
            'first_failure': 0,
            'last_pass': None,
            'tests': None,
            'list_isolated_data': None
        },
        'unit_tests': {
            'current_failure': 2,
            'first_failure': 0,
            'last_pass': None,
            'tests': None,
            'list_isolated_data': None
        }
    }
    self.assertFalse(result)
    self.assertEqual(expected_failed_steps, failed_steps.ToSerializable())
