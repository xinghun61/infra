# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from testing_utils import testing

from model.wf_step import WfStep
from pipeline_wrapper import pipeline_handlers
from waterfall import buildbot
from waterfall import waterfall_config
from waterfall.extract_signal_pipeline import ExtractSignalPipeline


class ExtractSignalPipelineTest(testing.AppengineTestCase):
  app_module = pipeline_handlers._APP

  ABC_TEST_FAILURE_LOG = """
      ...
      ../../content/common/gpu/media/v4l2_video_encode_accelerator.cc:306:12:
      ...
  """

  FAILURE_SIGNALS = {
      "abc_test": {
        "files": {
          "content/common/gpu/media/v4l2_video_encode_accelerator.cc": [306]
        },
        "keywords": {}
      }
  }

  FAILURE_INFO = {
      'master_name': 'm',
      'builder_name': 'b',
      'build_number': 123,
      'failed': True,
      'chromium_revision': 'a_git_hash',
      'failed_steps': {
          'abc_test': {
              'last_pass': 122,
              'current_failure': 123,
              'first_failure': 123,
          }
      }
  }

  UNSUPPORTED_STEPS = {
      'master': ['unsupported_step']
  }

  def testExtractStorablePortionOfLogWithSmallLogData(self):
    self.mock(ExtractSignalPipeline, 'LOG_DATA_BYTE_LIMIT', 500)
    lines = [str(i) * 99 for i in range(3)]
    log_data = '\n'.join(lines)
    expected_result = log_data
    result = ExtractSignalPipeline._ExtractStorablePortionOfLog(log_data)
    self.assertEqual(expected_result, result)

  def testExtractStorablePortionOfLogWithBigLogData(self):
    self.mock(ExtractSignalPipeline, 'LOG_DATA_BYTE_LIMIT', 500)
    lines = [str(9 - i) * 99 for i in range(9)]
    log_data = '\n'.join(lines)
    expected_result = '\n'.join(lines[-5:])
    result = ExtractSignalPipeline._ExtractStorablePortionOfLog(log_data)
    self.assertEqual(expected_result, result)

  def testWfStepStdioLogAlreadyDownloaded(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 'abc_test'
    step = WfStep.Create(master_name, builder_name, build_number, step_name)
    step.log_data = self.ABC_TEST_FAILURE_LOG
    step.put()

    step_log_url = buildbot.CreateStdioLogUrl(
        master_name, builder_name, build_number, step_name)
    with self.mock_urlfetch() as urlfetch:
      urlfetch.register_handler(step_log_url, 'If used, test should fail!')

    pipeline = ExtractSignalPipeline(self.FAILURE_INFO)
    signals = pipeline.run(self.FAILURE_INFO)

    self.assertEqual(self.FAILURE_SIGNALS, signals)

  def MockGetStdiolog(self, master_name, builder_name, build_number, step_name):
    step_log_url = buildbot.CreateStdioLogUrl(
        master_name, builder_name, build_number, step_name)
    with self.mock_urlfetch() as urlfetch:
      urlfetch.register_handler(step_log_url, self.ABC_TEST_FAILURE_LOG)

  def testWfStepStdioLogNotDownloadedYet(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 'abc_test'

    self.MockGetStdiolog(master_name, builder_name, build_number, step_name)

    pipeline = ExtractSignalPipeline(self.FAILURE_INFO)
    pipeline.start()
    self.execute_queued_tasks()

    step = WfStep.Create(master_name, builder_name, build_number, step_name)
    self.assertIsNotNone(step)

  def _GetGtestResultLog(self,
                         master_name, builder_name, build_number, step_name):
    file_name = os.path.join(
        os.path.dirname(__file__), 'data',
        '%s_%s_%d_%s.json' % (master_name,
                              builder_name, build_number, step_name))
    with open(file_name, 'r') as f:
      return f.read()

  def testGetTestLevelFailures(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 'abc_test'

    expected_failure_log = ('ERROR:x_test.cc:1234\na/b/u2s1.cc:567: Failure\n'
                            'ERROR:[2]: 2594735000 bogo-microseconds\n'
                            'ERROR:x_test.cc:1234\na/b/u2s1.cc:567: Failure\n'
                            'ERROR:x_test.cc:1234\na/b/u2s1.cc:567: Failure\n'
                            'a/b/u3s2.cc:110: Failure\n'
                            'a/b/u3s2.cc:110: Failure\n'
                            'a/b/u3s2.cc:110: Failure\n'
                            'a/b/u3s2.cc:110: Failure\n'
                           )

    step_log = self._GetGtestResultLog(
        master_name, builder_name, build_number, step_name)

    failed_test_log = ExtractSignalPipeline._GetReliableTestFailureLog(step_log)
    self.assertEqual(expected_failure_log, failed_test_log)

  def testGetTestLevelFailuresFlaky(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    step_name = 'abc_test'

    expected_failure_log = 'flaky'

    step_log = self._GetGtestResultLog(
        master_name, builder_name, build_number, step_name)

    failed_test_log = ExtractSignalPipeline._GetReliableTestFailureLog(step_log)
    self.assertEqual(expected_failure_log, failed_test_log)

  def testGetTestLevelFailuresInvalid(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 125
    step_name = 'abc_test'

    expected_failure_log = 'invalid'

    step_log = self._GetGtestResultLog(
        master_name, builder_name, build_number, step_name)

    failed_test_log = ExtractSignalPipeline._GetReliableTestFailureLog(step_log)
    self.assertEqual(expected_failure_log, failed_test_log)

  def MockGetGtestJsonResult(self):
    self.mock(buildbot, 'GetGtestResultLog', self._GetGtestResultLog)

  def testGetSignalFromStepLog(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 'abc_test'

    # Mock both stdiolog and gtest json results to test whether Findit will
    # go to step log first when both logs exist.
    self.MockGetStdiolog(master_name, builder_name, build_number, step_name)
    self.MockGetGtestJsonResult()
    pipeline = ExtractSignalPipeline(self.FAILURE_INFO)
    signals = pipeline.run(self.FAILURE_INFO)

    step = WfStep.Get(master_name, builder_name, build_number, step_name)

    expected_files = {
        'a/b/u2s1.cc': [567],
        'a/b/u3s2.cc': [110]
    }

    self.assertIsNotNone(step)
    self.assertIsNotNone(step.log_data)
    self.assertEqual(expected_files, signals['abc_test']['files'])

  def testGetSignalFromStepLogFlaky(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    step_name = 'abc_test'

    failure_info = {
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 124,
        'failed': True,
        'chromium_revision': 'a_git_hash',
        'failed_steps': {
            'abc_test': {
                'last_pass': 123,
                'current_failure': 124,
                'first_failure': 124,
            }
        }
    }

    self.MockGetStdiolog(master_name, builder_name, build_number, step_name)
    self.MockGetGtestJsonResult()
    pipeline = ExtractSignalPipeline()
    signals = pipeline.run(failure_info)

    step = WfStep.Get(master_name, builder_name, build_number, step_name)

    self.assertIsNotNone(step)
    self.assertIsNotNone(step.log_data)
    self.assertEqual('flaky', step.log_data)
    self.assertEqual({}, signals['abc_test']['files'])

  def testGetSignalFromStepLogInvalid(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 125
    step_name = 'abc_test'

    failure_info = {
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 125,
        'failed': True,
        'chromium_revision': 'a_git_hash',
        'failed_steps': {
            'abc_test': {
                'last_pass': 124,
                'current_failure': 125,
                'first_failure': 125,
            }
        }
    }

    self.MockGetStdiolog(master_name, builder_name, build_number, step_name)
    self.MockGetGtestJsonResult()

    pipeline = ExtractSignalPipeline()
    signals = pipeline.run(failure_info)

    step = WfStep.Get(master_name, builder_name, build_number, step_name)

    expected_files = {
        'content/common/gpu/media/v4l2_video_encode_accelerator.cc': [306]
    }

    self.assertIsNotNone(step)
    self.assertIsNotNone(step.log_data)
    self.assertEqual(expected_files, signals['abc_test']['files'])

  def testBailOutIfNotAFailedBuild(self):
    failure_info = {
        'failed': False,
    }
    expected_signals = {}

    pipeline = ExtractSignalPipeline()
    signals = pipeline.run(failure_info)
    self.assertEqual(expected_signals, signals)

  def testBailOutIfNoValidChromiumRevision(self):
    failure_info = {
        'failed': True,
        'chromium_revision': None,
    }
    expected_signals = {}

    pipeline = ExtractSignalPipeline()
    signals = pipeline.run(failure_info)
    self.assertEqual(expected_signals, signals)

  def testExtractSignalsForTests(self):
    failure_info = {
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 223,
        'failed': True,
        'chromium_revision': 'a_git_hash',
        'failed_steps': {
            'abc_test': {
                'last_pass': 221,
                'current_failure': 223,
                'first_failure': 222,
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
    }

    step = WfStep.Create('m', 'b', 223, 'abc_test')
    step.isolated = True
    step.log_data = (
         '{"Unittest2.Subtest1": "RVJST1I6eF90ZXN0LmNjOjEyMzQKYS9iL3UyczEuY2M6N'
         'TY3OiBGYWlsdXJlCkVSUk9SOlsyXTogMjU5NDczNTAwMCBib2dvLW1pY3Jvc2Vjb25kcw'
         'pFUlJPUjp4X3Rlc3QuY2M6MTIzNAphL2IvdTNzMi5jYzoxMjM6IEZhaWx1cmUK"'
         ', "Unittest3.Subtest2": "YS9iL3UzczIuY2M6MTEwOiBGYWlsdXJlCmEvYi91M3My'
         'LmNjOjEyMzogRmFpbHVyZQo="}')
    step.put()

    expected_signals = {
        'abc_test':{
            'files':{
                'a/b/u2s1.cc': [567],
                'a/b/u3s2.cc': [123, 110]
            },
            'keywords':{},
            'tests':{
                'Unittest2.Subtest1':{
                    'files':{
                        'a/b/u2s1.cc': [567],
                        'a/b/u3s2.cc': [123]
                    },
                    'keywords':{}
                },
                'Unittest3.Subtest2':{
                    'files':{
                        'a/b/u3s2.cc': [110, 123]
                    },
                    'keywords':{}
                }
            }
        }
    }

    pipeline = ExtractSignalPipeline()
    signals = pipeline.run(failure_info)
    self.assertEqual(expected_signals, signals)

  def testExtractSignalsForTestsFlaky(self):
    failure_info = {
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 223,
        'failed': True,
        'chromium_revision': 'a_git_hash',
        'failed_steps': {
            'abc_test': {
                'last_pass': 221,
                'current_failure': 223,
                'first_failure': 222,
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
    }

    step = WfStep.Create('m', 'b', 223, 'abc_test')
    step.isolated = True
    step.log_data = 'flaky'
    step.put()

    expected_signals = {
        'abc_test':{
            'files':{},
            'keywords':{},
            'tests':{}
        }
    }
    pipeline = ExtractSignalPipeline()
    signals = pipeline.run(failure_info)
    self.assertEqual(expected_signals, signals)

  def MockIsStepSupportedForMaster(self, step_name, master_name):
    return step_name in self.UNSUPPORTED_STEPS.get(master_name, [])

  def testBailOutForUnsupportedStep(self):
    failure_info = {
        'master_name': 'master',
        'builder_name': 'b',
        'build_number': 123,
        'failed': True,
        'chromium_revision': 'a_git_hash',
        'failed_steps': {
            'not_supported': {}
        }
    }
    expected_signals = {}
    self.mock(waterfall_config, 'IsStepSupportedForMaster',
              self.MockIsStepSupportedForMaster)
    pipeline = ExtractSignalPipeline()
    signals = pipeline.run(failure_info)
    self.assertEqual(expected_signals, signals)
