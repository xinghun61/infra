# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from google.appengine.api import datastore_errors

from common.findit_http_client import FinditHttpClient
from model.wf_step import WfStep
from services import ci_failure
from services import constants
from services import swarmed_test_util
from services import swarming
from services.parameters import FailureInfoBuilds
from services.parameters import FailureToCulpritMap
from services.parameters import TestFailureInfo
from services.parameters import TestFailedStep
from services.parameters import TestFailedSteps
from services.test_failure import ci_test_failure
from waterfall import waterfall_config
from waterfall.test import wf_testcase


class CITestFailureTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(CITestFailureTest, self).setUp()

    with self.mock_urlfetch() as urlfetch:
      self.mocked_urlfetch = urlfetch

  def testInitiateTestLevelFirstFailureAndSaveLog(self):
    reliable_failed_tests = {
        'Unittest2.Subtest1': 'Unittest2.Subtest1',
        'Unittest3.Subtest2': 'Unittest3.Subtest2'
    }
    failed_step = {
        'current_failure': 223,
        'first_failure': 221,
        'supported': True
    }
    failed_step = TestFailedStep.FromSerializable(failed_step)

    ci_test_failure._InitiateTestLevelFirstFailure(reliable_failed_tests,
                                                   failed_step)

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
    reliable_failed_tests = {
        'Unittest2.Subtest1': 'Unittest2.Subtest1',
        'Unittest3.Subtest2': 'Unittest3.Subtest2'
    }

    failed_step = {
        'current_failure': 223,
        'first_failure': 221,
        'last_pass': 220,
        'supported': True,
        'tests': {}
    }
    failed_step = TestFailedStep.FromSerializable(failed_step)

    ci_test_failure._InitiateTestLevelFirstFailure(reliable_failed_tests,
                                                   failed_step)

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

    mock_module.RetrieveShardedTestResultsFromIsolatedServer.return_value = {
        'disabled_tests': [],
        'all_tests': [
            'Unittest1.Subtest1',
            'Unittest1.Subtest2',
            'Unittest2.Subtest1',
        ],
        'per_iteration_data': [{
            'Unittest1.Subtest1': [{
                'elapsed_time_ms': 1,
                'losless_snippet': True,
                'output_snippet': '[       OK ]\\n',
                'status': 'SUCCESS',
                'output_snippet_base64': 'WyAgICAgICBPSyBdCg=='
            }],
            'Unittest1.Subtest2': [{
                'elapsed_time_ms': 66,
                'losless_snippet': True,
                'output_snippet': 'a/b/u1s2.cc:1234: Failure\\n',
                'status': 'FAILURE',
                'output_snippet_base64': 'YS9iL3UxczIuY2M6MTIzNDogRmF'
            }, {
                'elapsed_time_ms': 50,
                'losless_snippet': True,
                'output_snippet': '[       OK ]\\n',
                'status': 'SUCCESS',
                'output_snippet_base64': 'WyAgICAgICBPSyBdCg=='
            }],
            'Unittest2.Subtest1': [{
                'elapsed_time_ms': 56,
                'losless_snippet': True,
                'output_snippet': 'ERROR',
                'status': 'FAILURE',
                'output_snippet_base64': 'RVJST1I6eF90ZXN0LmN'
            }, {
                'elapsed_time_ms': 1,
                'losless_snippet': True,
                'output_snippet': '[       OK ]\\n',
                'status': 'SUCCESS',
                'output_snippet_base64': 'WyAgICAgICBPSyBdCg=='
            }],
        }]
    }

    mock_module.GetFailedTestsInformation.return_value = ({}, {})

    ci_test_failure.CheckFirstKnownFailureForSwarmingTests(
        master_name, builder_name, build_number, failure_info)

    self.assertEqual(expected_failed_steps,
                     failure_info.failed_steps.ToSerializable())

  @mock.patch.object(ci_test_failure, '_HTTP_CLIENT', None)
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
    mock_fun.assert_called_once_with(
        master_name, builder_name, build_number, step_name,
        TestFailedStep.FromSerializable(failed_steps[step_name]),
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

  @mock.patch.object(ci_test_failure, '_GetTestLevelLogForAStep')
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
    log_data_222 = {
        'Unittest2.Subtest1': 'test_failure_log',
        'Unittest3.Subtest2': 'test_failure_log'
    }
    log_data_221 = {
        'Unittest3.Subtest1': 'test_failure_log',
        'Unittest3.Subtest2': 'test_failure_log'
    }

    mock_steps.side_effect = [None, log_data_222, log_data_221]

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
    ci_test_failure._UpdateFirstFailureOnTestLevel(master_name, builder_name,
                                                   build_number, step_name,
                                                   failed_step, [223, 222, 221],
                                                   FinditHttpClient())
    expected_failed_step = {
        'current_failure': 223,
        'first_failure': 223,
        'last_pass': 221,
        'supported': True,
        'list_isolated_data': None,
        'tests': {
            'Unittest2.Subtest1': {
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': 221,
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

  def testSaveLogToStepLogTooBig(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 250
    step_name = 'atest'

    original_step_put = WfStep.put
    calls = []

    def MockNdbTransaction(func, **options):
      if len(calls) < 1:
        calls.append(1)
        raise datastore_errors.BadRequestError('log_data is too long')
      return original_step_put(func, **options)

    self.mock(WfStep, 'put', MockNdbTransaction)

    ci_test_failure._SaveIsolatedResultToStep(master_name, builder_name,
                                              build_number, step_name, {})
    step = WfStep.Get(master_name, builder_name, build_number, step_name)
    self.assertEqual(step.log_data, constants.TOO_LARGE_LOG)

  def testSaveLogToStepLogFailForSomethingElse(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 250
    step_name = 'atest'

    original_step_put = WfStep.put
    calls = []

    def MockNdbTransaction(func, **options):
      if len(calls) < 1:
        calls.append(1)
        raise datastore_errors.BadRequestError('Other reason')
      return original_step_put(func, **options)

    self.mock(WfStep, 'put', MockNdbTransaction)

    ci_test_failure._SaveIsolatedResultToStep(master_name, builder_name,
                                              build_number, step_name, {})
    step = WfStep.Get(master_name, builder_name, build_number, step_name)
    self.assertEqual(constants.TOO_LARGE_LOG, step.log_data)
    self.assertTrue(step.isolated)

  @mock.patch.object(swarming, 'GetIsolatedDataForStep', return_value=None)
  def testGetLogForTheSameStepFromBuildNotIsolated(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 121
    step_name = 'atest'
    self.assertIsNone(
        ci_test_failure._GetTestLevelLogForAStep(master_name, builder_name,
                                                 build_number, step_name, None))

  @mock.patch.object(
      swarmed_test_util,
      'RetrieveShardedTestResultsFromIsolatedServer',
      return_value={'per_iteration_data': 'invalid'})
  @mock.patch.object(swarming, 'GetIsolatedDataForStep')
  def testGetLogForTheSameStepFromBuildReslutLogInvalid(self,
                                                        mock_isolated_data, _):
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
        ci_test_failure._GetTestLevelLogForAStep(master_name, builder_name,
                                                 build_number, step_name, None))

  def testGetLogForTheSameStepFromBuildNotNotJsonLoadable(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 121
    step_name = 'atest'

    step = WfStep.Create(master_name, builder_name, build_number, step_name)
    step.isolated = True
    step.log_data = 'log'
    step.put()

    self.assertIsNone(
        ci_test_failure._GetTestLevelLogForAStep(master_name, builder_name,
                                                 build_number, step_name, None))

  @mock.patch.object(swarming, 'GetIsolatedDataForStep')
  @mock.patch.object(swarmed_test_util,
                     'RetrieveShardedTestResultsFromIsolatedServer')
  def testGetLogForTheSameStepFromBuild(self, mock_step_log,
                                        mock_isolated_data):
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

    mock_step_log.return_value = {
        'disabled_tests': [],
        'global_tags': [],
        'all_tests': [
            'Unittest1.Subtest1', 'Unittest1.Subtest2', 'Unittest2.Subtest1',
            'Unittest2.Subtest2', 'Unittest3.Subtest1', 'Unittest3.Subtest2',
            'Unittest3.Subtest3'
        ],
        'per_iteration_data': [{
            'Unittest2.Subtest1': [{
                'elapsed_time_ms':
                    56,
                'losless_snippet':
                    True,
                'output_snippet': ('ERROR:x_test.cc:1234\\na/b/u2s1.cc'
                                   ':567: Failure\\n'),
                'status':
                    'FAILURE',
                'output_snippet_base64': (
                    'RVJST1I6eF90ZXN0LmNjOjEyMzRcbmEvYi91MnMxLmNj'
                    'OjU2NzogRmFpbHVyZVxu')
            }],
            'Unittest3.Subtest2': [{
                'elapsed_time_ms': 80,
                'losless_snippet': True,
                'output_snippet': 'a/b/u3s2.cc:110: Failure\\n',
                'status': 'FAILURE',
                'output_snippet_base64': 'YS9iL3UzczIuY2M6MTEwOiBGYWlsdXJlXG4='
            }]
        }]
    }

    expected_failure_log = {
        'Unittest2.Subtest1': (
            'RVJST1I6eF90ZXN0LmNjOjEyMzRcbmEvYi91MnMxLmNjOjU2NzogRmFpbHVyZVxu'),
        'Unittest3.Subtest2':
            'YS9iL3UzczIuY2M6MTEwOiBGYWlsdXJlXG4='
    }

    failure_log = ci_test_failure._GetTestLevelLogForAStep(
        master_name, builder_name, build_number, step_name, None)

    self.assertEqual(failure_log, expected_failure_log)

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

  @mock.patch.object(
      ci_failure,
      'GetLaterBuildsWithAnySameStepFailure',
      return_value={
          124: ['a', 'b'],
          125: ['a']
      })
  @mock.patch.object(ci_test_failure, '_GetTestLevelLogForAStep')
  def testGetLaterBuildsWithSameTestFailures(self, mock_log, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    failure_to_culprit_map = FailureToCulpritMap.FromSerializable({
        'a': {
            't1': 'r1',
            't2': 'r1',
            't3': 'r2',
            't4': 'r2'
        },
        'b': {
            't1': 'r3'
        }
    })

    mock_log.side_effect = [{
        't1': 'log',
        't2': 'log',
        't3': 'log'
    }, {
        't1': 'log'
    }, {
        't1': 'log',
        't2': 'log',
    }]

    expected_result = {'a': set(['t1', 't2'])}

    self.assertEqual(
        expected_result,
        ci_test_failure.GetContinuouslyFailedTestsInLaterBuilds(
            master_name, builder_name, build_number, failure_to_culprit_map))

  @mock.patch.object(
      ci_failure,
      'GetLaterBuildsWithAnySameStepFailure',
      return_value={
          124: ['a', 'b'],
          125: ['a']
      })
  @mock.patch.object(ci_test_failure, '_GetTestLevelLogForAStep')
  def testGetLaterBuildsWithSameTestFailuresAllTestPass(self, mock_log, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    failure_to_culprit_map = FailureToCulpritMap.FromSerializable({
        'a': {
            't1': 'r1',
            't2': 'r1',
            't3': 'r2',
            't4': 'r2'
        },
        'b': {
            't1': 'r3'
        }
    })

    mock_log.side_effect = [{'t5': 'log'}, None]

    self.assertEqual({},
                     ci_test_failure.GetContinuouslyFailedTestsInLaterBuilds(
                         master_name, builder_name, build_number,
                         failure_to_culprit_map))

  @mock.patch.object(
      ci_failure, 'GetLaterBuildsWithAnySameStepFailure', return_value={})
  def testGetLaterBuildsWithSameTestFailuresAllStepsPass(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    failure_to_culprit_map = FailureToCulpritMap.FromSerializable({
        'a': {
            't1': 'r1',
            't2': 'r1',
            't3': 'r2',
            't4': 'r2'
        },
        'b': {
            't1': 'r3'
        }
    })

    self.assertEqual({},
                     ci_test_failure.GetContinuouslyFailedTestsInLaterBuilds(
                         master_name, builder_name, build_number,
                         failure_to_culprit_map))
