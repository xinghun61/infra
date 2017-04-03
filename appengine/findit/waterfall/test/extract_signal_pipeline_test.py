# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import os

from common.waterfall import failure_type
from gae_libs.pipeline_wrapper import pipeline_handlers
from model.wf_analysis import WfAnalysis
from model.wf_step import WfStep
from waterfall import buildbot
from waterfall import extract_signal_pipeline
from waterfall.extract_signal_pipeline import ExtractSignalPipeline
from waterfall.test import wf_testcase

ABC_TEST_FAILURE_LOG = """
    ...
    ../../content/common/gpu/media/v4l2_video_encode_accelerator.cc:306:12:
    ...
"""


FAILURE_SIGNALS = {
  'abc_test': {
    'files': {
      'content/common/gpu/media/v4l2_video_encode_accelerator.cc': [306]
    },
    'keywords': {}
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


class ExtractSignalPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def _CreateAndSaveWfAnanlysis(
      self, master_name, builder_name, build_number):
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

  def testExtractStorablePortionOfLogWithSmallLogData(self):
    self.mock(ExtractSignalPipeline, 'LOG_DATA_BYTE_LIMIT', 500)
    lines = [str(i) * 99 for i in range(3)]
    log_data = '\n'.join(lines)
    expected_result = log_data
    result = extract_signal_pipeline._ExtractStorablePortionOfLog(log_data)
    self.assertEqual(expected_result, result)

  def testExtractStorablePortionOfLogWithBigLogData(self):
    self.mock(ExtractSignalPipeline, 'LOG_DATA_BYTE_LIMIT', 500)
    lines = [str(9 - i) * 99 for i in range(9)]
    log_data = '\n'.join(lines)
    expected_result = '\n'.join(lines[-5:])
    result = extract_signal_pipeline._ExtractStorablePortionOfLog(log_data)
    self.assertEqual(expected_result, result)

  @mock.patch.object(buildbot, 'GetStepLog',
                     return_value='If used, test should fail!')
  def testWfStepStdioLogAlreadyDownloaded(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 'abc_test'
    step = WfStep.Create(master_name, builder_name, build_number, step_name)
    step.log_data = ABC_TEST_FAILURE_LOG
    step.put()

    self._CreateAndSaveWfAnanlysis(
        master_name, builder_name, build_number)

    pipeline = ExtractSignalPipeline(FAILURE_INFO)
    signals = pipeline.run(FAILURE_INFO)

    self.assertEqual(FAILURE_SIGNALS, signals)

  @mock.patch.object(buildbot, 'GetStepLog',
                     return_value=ABC_TEST_FAILURE_LOG)
  def testWfStepStdioLogNotDownloadedYet(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 'abc_test'

    self._CreateAndSaveWfAnanlysis(
        master_name, builder_name, build_number)

    pipeline = ExtractSignalPipeline(FAILURE_INFO)
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

    failed_test_log = extract_signal_pipeline._GetReliableTestFailureLog(
        step_log)
    self.assertEqual(expected_failure_log, failed_test_log)

  def testGetTestLevelFailuresFlaky(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    step_name = 'abc_test'

    expected_failure_log = 'flaky'

    step_log = self._GetGtestResultLog(
        master_name, builder_name, build_number, step_name)

    failed_test_log = extract_signal_pipeline._GetReliableTestFailureLog(
        step_log)
    self.assertEqual(expected_failure_log, failed_test_log)

  def testGetTestLevelFailuresInvalid(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 125
    step_name = 'abc_test'

    expected_failure_log = 'invalid'

    step_log = self._GetGtestResultLog(
        master_name, builder_name, build_number, step_name)

    failed_test_log = extract_signal_pipeline._GetReliableTestFailureLog(
        step_log)
    self.assertEqual(expected_failure_log, failed_test_log)

  def MockGetGtestJsonResult(self):
    self.mock(buildbot, 'GetGtestResultLog', self._GetGtestResultLog)

  @mock.patch.object(buildbot, 'GetStepLog',
                     return_value=ABC_TEST_FAILURE_LOG)
  def testGetSignalFromStepLog(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 'abc_test'

    # Mock both stdiolog and gtest json results to test whether Findit will
    # go to step log first when both logs exist.
    self.MockGetGtestJsonResult()
    self._CreateAndSaveWfAnanlysis(
        master_name, builder_name, build_number)

    pipeline = ExtractSignalPipeline(FAILURE_INFO)
    signals = pipeline.run(FAILURE_INFO)

    step = WfStep.Get(master_name, builder_name, build_number, step_name)

    expected_files = {
        'a/b/u2s1.cc': [567],
        'a/b/u3s2.cc': [110]
    }

    self.assertIsNotNone(step)
    self.assertIsNotNone(step.log_data)
    self.assertEqual(expected_files, signals['abc_test']['files'])

  @mock.patch.object(buildbot, 'GetStepLog',
                     return_value=ABC_TEST_FAILURE_LOG)
  def testGetSignalFromStepLogFlaky(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    step_name = 'abc_test'

    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
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

    self.MockGetGtestJsonResult()
    self._CreateAndSaveWfAnanlysis(
        master_name, builder_name, build_number)

    pipeline = ExtractSignalPipeline()
    signals = pipeline.run(failure_info)

    step = WfStep.Get(master_name, builder_name, build_number, step_name)

    self.assertIsNotNone(step)
    self.assertIsNotNone(step.log_data)
    self.assertEqual('flaky', step.log_data)
    self.assertEqual({}, signals['abc_test']['files'])

  @mock.patch.object(buildbot, 'GetStepLog',
                     return_value=ABC_TEST_FAILURE_LOG)
  def testGetSignalFromStepLogInvalid(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 125
    step_name = 'abc_test'

    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed': True,
        'chromium_revision': 'a_git_hash',
        'failed_steps': {
            step_name: {
                'last_pass': 124,
                'current_failure': 125,
                'first_failure': 125,
            }
        }
    }

    self.MockGetGtestJsonResult()
    self._CreateAndSaveWfAnanlysis(
        master_name, builder_name, build_number)

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

  def testBailOutIfInfraFailure(self):
    failure_info = {
        'failed': True,
        'failure_type': failure_type.INFRA,
        'chromium_revision': '00baf00ba',
    }
    expected_signals = {}

    pipeline = ExtractSignalPipeline()
    signals = pipeline.run(failure_info)
    self.assertEqual(expected_signals, signals)

  def testExtractSignalsForTests(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223

    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed': True,
        'chromium_revision': 'a_git_hash',
        'failed_steps': {
            'abc_test': {
                'last_pass': 221,
                'current_failure': 223,
                'first_failure': 222,
                'tests': {
                    'Unittest2.Subtest1': {
                        'current_failure': 223,
                        'first_failure': 222,
                        'last_pass': 221
                    },
                    'Unittest3.Subtest2': {
                        'current_failure': 223,
                        'first_failure': 222,
                        'last_pass': 221
                    }
                }
            }
        }
    }

    step = WfStep.Create(master_name, builder_name, build_number, 'abc_test')
    step.isolated = True
    step.log_data = (
        '{"Unittest2.Subtest1": "RVJST1I6eF90ZXN0LmNjOjEyMzQKYS9iL3UyczEuY2M6N'
        'TY3OiBGYWlsdXJlCkVSUk9SOlsyXTogMjU5NDczNTAwMCBib2dvLW1pY3Jvc2Vjb25kcw'
        'pFUlJPUjp4X3Rlc3QuY2M6MTIzNAphL2IvdTNzMi5jYzoxMjM6IEZhaWx1cmUK"'
        ', "Unittest3.Subtest2": "YS9iL3UzczIuY2M6MTEwOiBGYWlsdXJlCmEvYi91M3My'
        'LmNjOjEyMzogRmFpbHVyZQo="}')
    step.put()

    expected_signals = {
        'abc_test': {
            'files': {
                'a/b/u2s1.cc': [567],
                'a/b/u3s2.cc': [123, 110]
            },
            'keywords': {},
            'tests': {
                'Unittest2.Subtest1': {
                    'files': {
                        'a/b/u2s1.cc': [567],
                        'a/b/u3s2.cc': [123]
                    },
                    'keywords': {}
                },
                'Unittest3.Subtest2': {
                    'files': {
                        'a/b/u3s2.cc': [110, 123]
                    },
                    'keywords': {}
                }
            }
        }
    }

    self._CreateAndSaveWfAnanlysis(
        master_name, builder_name, build_number)

    pipeline = ExtractSignalPipeline()
    signals = pipeline.run(failure_info)
    self.assertEqual(expected_signals, signals)

  def testExtractSignalsForTestsFlaky(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223

    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed': True,
        'chromium_revision': 'a_git_hash',
        'failed_steps': {
            'abc_test': {
                'last_pass': 221,
                'current_failure': 223,
                'first_failure': 222,
                'tests': {
                    'Unittest2.Subtest1': {
                        'current_failure': 223,
                        'first_failure': 222,
                        'last_pass': 221
                    },
                    'Unittest3.Subtest2': {
                        'current_failure': 223,
                        'first_failure': 222,
                        'last_pass': 221
                    }
                }
            }
        }
    }

    step = WfStep.Create(master_name, builder_name, build_number, 'abc_test')
    step.isolated = True
    step.log_data = 'flaky'
    step.put()

    expected_signals = {
        'abc_test': {
            'files': {},
            'keywords': {},
            'tests': {}
        }
    }

    self._CreateAndSaveWfAnanlysis(
        master_name, builder_name, build_number)

    pipeline = ExtractSignalPipeline()
    signals = pipeline.run(failure_info)
    self.assertEqual(expected_signals, signals)

  @mock.patch.object(buildbot, 'GetStepLog',
                     return_value=ABC_TEST_FAILURE_LOG)
  def testBailOutForUnsupportedStep(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    supported_step_name = 'abc_test'
    unsupported_step_name = 'unsupported_step6'
    failure_info = {
        'master_name': master_name,
        'builder_name': 'b',
        'build_number': 123,
        'failed': True,
        'chromium_revision': 'a_git_hash',
        'failed_steps': {
            supported_step_name: {
                'last_pass': 122,
                'current_failure': 123,
                'first_failure': 123,
            },
            unsupported_step_name: {
            }
        }
    }


    def MockGetGtestResultLog(*_):
      return None

    self.mock(buildbot, 'GetGtestResultLog', MockGetGtestResultLog)
    self._CreateAndSaveWfAnanlysis(
        master_name, builder_name, build_number)

    pipeline = ExtractSignalPipeline()
    signals = pipeline.run(failure_info)
    self.assertEqual(FAILURE_SIGNALS, signals)
