# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import mock
import os

from common.findit_http_client import FinditHttpClient
from infra_api_clients.swarming.swarming_task_data import SwarmingTaskData
from model.wf_step import WfStep
from services import swarmed_test_util
from services import swarming
from services.parameters import TestFailureInfo
from services.parameters import TestFailedStep
from services.parameters import TestFailedSteps
from services.parameters import FailureInfoBuilds
from services.test_failure import ci_test_failure
from waterfall import waterfall_config
from waterfall.test import wf_testcase


class CITestFailureTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(CITestFailureTest, self).setUp()

    with self.mock_urlfetch() as urlfetch:
      self.mocked_urlfetch = urlfetch

  def _GetSwarmingData(self, data_type, file_name=None):
    file_name_map = {
        'build': 'sample_swarming_build_tasks.json',
        'step': 'sample_swarming_build_abctest_tasks.json'
    }
    file_name = file_name_map.get(data_type, file_name)
    swarming_tasks_file = os.path.join(
        os.path.dirname(__file__), os.pardir, os.pardir, 'test', 'data',
        file_name)
    with open(swarming_tasks_file, 'r') as f:
      return f.read()

  def testInitiateTestLevelFirstFailureAndSaveLog(self):
    json_data = json.loads(
        self._GetSwarmingData('isolated-plain', 'm_b_223_abc_test.json'))

    step = WfStep.Create('m', 'b', 223, 'abc_test')
    step.isolated = True
    step.put()

    failed_step = {
        'current_failure': 223,
        'first_failure': 221,
        'supported': True
    }
    failed_step = TestFailedStep.FromSerializable(failed_step)

    ci_test_failure._InitiateTestLevelFirstFailureAndSaveLog(
        json_data, step, failed_step)

    expected_failed_step = {
        'current_failure': 223,
        'first_failure': 221,
        'last_pass': None,
        'supported': True,
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
        'supported': True,
        'tests': {}
    }
    failed_step = TestFailedStep.FromSerializable(failed_step)

    ci_test_failure._InitiateTestLevelFirstFailureAndSaveLog(
        json_data, step, failed_step)

    expected_failed_step = {
        'current_failure': 223,
        'first_failure': 221,
        'last_pass': 220,
        'supported': True,
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

  @mock.patch.object(ci_test_failure, 'UpdateSwarmingSteps', return_value=True)
  @mock.patch.object(ci_test_failure, 'swarmed_test_util')
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
            'supported':
                True,
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

    mock_module.GetFailedTestsInformation.return_value = ({}, {})

    ci_test_failure.CheckFirstKnownFailureForSwarmingTests(
        master_name, builder_name, build_number, failure_info)

    self.assertEqual(expected_failed_steps,
                     failure_info.failed_steps.ToSerializable())

  @mock.patch.object(ci_test_failure, 'FinditHttpClient', return_value=None)
  @mock.patch.object(ci_test_failure, 'UpdateSwarmingSteps', return_value=True)
  @mock.patch.object(
      ci_test_failure, '_StartTestLevelCheckForFirstFailure', return_value=True)
  @mock.patch.object(ci_test_failure, '_UpdateFirstFailureOnTestLevel')
  def testBackwardTraverseBuildsWhenGettingTestLevelFailureInfo(
      self, mock_fun, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 221
    step_name = 'abc_test'
    failed_steps = {
        'abc_test': {
            'current_failure':
                223,
            'first_failure':
                223,
            'supported':
                True,
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

    ci_test_failure.CheckFirstKnownFailureForSwarmingTests(
        master_name, builder_name, build_number, failure_info)
    mock_fun.assert_called_once_with(master_name, builder_name, build_number,
                                     step_name,
                                     TestFailedStep.FromSerializable(
                                         failed_steps[step_name]),
                                     ['223', '222', '221'], None)

  @mock.patch.object(ci_test_failure, 'UpdateSwarmingSteps', return_value=False)
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

  @mock.patch.object(ci_test_failure, '_GetSameStepFromBuild')
  def testUpdateFirstFailureOnTestLevelThenUpdateStepLevel(self, mock_steps):
    master_name = 'm'
    builder_name = 'b'
    build_number = 224
    step_name = 'abc_test'
    failed_step = {
        'current_failure': 224,
        'first_failure': 221,
        'last_pass': 220,
        'supported': True,
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
    step_223 = WfStep.Create(master_name, builder_name, 223, step_name)
    step_223.isolated = True
    step_223.log_data = 'log'
    step_223.put()

    step_222 = WfStep.Create(master_name, builder_name, 222, step_name)
    step_222.isolated = True
    log_data_222 = {
        'Unittest2.Subtest1': 'test_failure_log',
        'Unittest3.Subtest2': 'test_failure_log'
    }
    step_222.log_data = json.dumps(log_data_222)
    step_222.put()

    step_221 = WfStep.Create(master_name, builder_name, 221, step_name)
    step_221.isolated = True
    log_data_221 = {
        'Unittest3.Subtest1': 'test_failure_log',
        'Unittest3.Subtest2': 'test_failure_log'
    }
    step_221.log_data = json.dumps(log_data_221)
    step_221.put()

    mock_steps.side_effect = [step_223, step_222, step_221]

    ci_test_failure._UpdateFirstFailureOnTestLevel(
        master_name, builder_name, build_number, step_name, failed_step,
        [224, 223, 222, 221, 220], FinditHttpClient())

    expected_failed_step = {
        'current_failure': 224,
        'first_failure': 221,
        'last_pass': 220,
        'supported': True,
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
        'supported': True,
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

    ci_test_failure._UpdateFirstFailureOnTestLevel(master_name, builder_name,
                                                   build_number, step_name,
                                                   failed_step, [223, 222, 221],
                                                   FinditHttpClient())

    expected_failed_step = {
        'current_failure': 223,
        'first_failure': 223,
        'last_pass': 222,
        'supported': True,
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

  def testUpdateFirstFailureOnTestLevelFailedToGetStep(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    step_name = 'abc_test'
    failed_step_serializable = {
        'current_failure': 223,
        'first_failure': 221,
        'supported': True,
        'tests': {
            'Unittest2.Subtest1': {
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': 221,
                'base_test_name': 'Unittest2.Subtest1'
            }
        }
    }
    failed_step = TestFailedStep.FromSerializable(failed_step_serializable)
    with self.assertRaises(Exception):
      ci_test_failure._UpdateFirstFailureOnTestLevel(
          master_name, builder_name, build_number, step_name, failed_step,
          [223, 222, 221], FinditHttpClient())

  def testUpdateFailureInfoBuildsUpdateBuilds(self):
    failed_steps = {
        'compile': {
            'current_failure': 223,
            'first_failure': 222,
            'last_pass': 221,
            'supported': True
        },
        'abc_test': {
            'current_failure':
                223,
            'first_failure':
                222,
            'last_pass':
                221,
            'supported':
                True,
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
      swarmed_test_util,
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

  @mock.patch.object(swarming, 'GetIsolatedDataForStep', return_value=None)
  def testGetSameStepFromBuildNotIsolated(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 121
    step_name = 'atest'
    self.assertIsNone(
        ci_test_failure._GetSameStepFromBuild(master_name, builder_name,
                                              build_number, step_name, None))

  @mock.patch.object(
      swarmed_test_util,
      'RetrieveShardedTestResultsFromIsolatedServer',
      return_value={
          'per_iteration_data': 'invalid'
      })
  @mock.patch.object(swarming, 'GetIsolatedDataForStep')
  def testGetSameStepFromBuildReslutLogInvalid(self, mock_isolated_data, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 121
    step_name = 'atest'

    mock_isolated_data.return_value = [{
        'isolatedserver': 'https://isolateserver.appspot.com',
        'namespace': {
            'namespace': 'default-gzip'
        },
        'digest': 'isolatedhashabctest'
    }]
    self.assertIsNone(
        ci_test_failure._GetSameStepFromBuild(master_name, builder_name,
                                              build_number, step_name, None))

  @mock.patch.object(swarming, 'GetIsolatedDataForStep')
  @mock.patch.object(swarmed_test_util,
                     'RetrieveShardedTestResultsFromIsolatedServer')
  def testGetSameStepFromBuild(self, mock_step_log, mock_isolated_data):
    master_name = 'm'
    builder_name = 'b'
    build_number = 222
    step_name = 'abc_test'

    mock_isolated_data.return_value = [{
        'isolatedserver': 'https://isolateserver.appspot.com',
        'namespace': {
            'namespace': 'default-gzip'
        },
        'digest': 'isolatedhashabctest'
    }]

    mock_step_log.return_value = json.loads(
        self._GetSwarmingData('isolated-plain',
                              '%s_%s_%d_%s.json' % (master_name, builder_name,
                                                    build_number, step_name)))

    step = ci_test_failure._GetSameStepFromBuild(master_name, builder_name,
                                                 build_number, step_name, None)

    self.assertIsNotNone(step)
    self.assertTrue(step.isolated)

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

  @mock.patch.object(swarming, 'GetIsolatedDataForFailedStepsInABuild')
  def testUpdateSwarmingSteps(self, mock_data):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failed_steps = {
        'a_tests': {
            'current_failure': 2,
            'first_failure': 0,
            'supported': True
        },
        'unit_tests': {
            'current_failure': 2,
            'first_failure': 0,
            'supported': True
        },
        'compile': {
            'current_failure': 2,
            'first_failure': 0,
            'supported': True
        }
    }
    failed_steps = TestFailedSteps.FromSerializable(failed_steps)

    mock_data.return_value = {
        'a_tests': [{
            'isolatedserver': 'https://isolateserver.appspot.com',
            'namespace': 'default-gzip',
            'digest': 'isolatedhashatests'
        }],
        'unit_tests': [{
            'isolatedserver': 'https://isolateserver.appspot.com',
            'namespace': 'default-gzip',
            'digest': 'isolatedhashunittests1'
        }]
    }
    result = ci_test_failure.UpdateSwarmingSteps(
        master_name, builder_name, build_number, failed_steps, None)

    expected_failed_steps = {
        'a_tests': {
            'current_failure':
                2,
            'first_failure':
                0,
            'supported':
                True,
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
            'supported':
                True,
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
            'supported': True,
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

  @mock.patch.object(swarming, 'ListSwarmingTasksDataByTags', return_value=[])
  def testUpdateSwarmingStepsDownloadFailed(self, _):
    master_name = 'm'
    builder_name = 'download_failed'
    build_number = 223
    failed_steps = {
        'a_tests': {
            'current_failure': 2,
            'first_failure': 0,
            'supported': True
        },
        'unit_tests': {
            'current_failure': 2,
            'first_failure': 0,
            'supported': True
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
            'supported': True,
            'tests': None,
            'list_isolated_data': None
        },
        'unit_tests': {
            'current_failure': 2,
            'first_failure': 0,
            'last_pass': None,
            'supported': True,
            'tests': None,
            'list_isolated_data': None
        }
    }
    self.assertFalse(result)
    self.assertEqual(expected_failed_steps, failed_steps.ToSerializable())
