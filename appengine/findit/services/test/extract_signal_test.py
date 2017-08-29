# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import mock
import os

from google.appengine.api.urlfetch import ResponseTooLargeError

from model.wf_analysis import WfAnalysis
from model.wf_step import WfStep
from services import extract_signal
from waterfall import buildbot
from waterfall.test import wf_testcase

ABC_TEST_FAILURE_LOG = """
    ...
    ../../content/common/gpu/media/v4l2_video_encode_accelerator.cc:306:12:
    ...
"""

COMPILE_FAILURE_LOG = json.dumps({
    'failures': [{
        'output_nodes': ['a/b.o'],
        'rule': 'CXX',
        'output': '',
        'dependencies': ['../../b.h', '../../b.c']
    }]
})

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

COMPILE_FAILURE_INFO = {
    'master_name': 'm',
    'builder_name': 'b',
    'build_number': 123,
    'failed': True,
    'chromium_revision': 'a_git_hash',
    'failed_steps': {
        'compile': {
            'last_pass': 122,
            'current_failure': 123,
            'first_failure': 123,
        }
    }
}


class FailureSignalTest(wf_testcase.WaterfallTestCase):

  def _CreateAndSaveWfAnanlysis(self, master_name, builder_name, build_number):
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

  def _GetGtestResultLog(self, master_name, builder_name, build_number,
                         step_name):
    file_name = os.path.join(
        os.path.dirname(__file__), 'data', '%s_%s_%d_%s.json' %
        (master_name, builder_name, build_number, step_name))
    with open(file_name, 'r') as f:
      return f.read()

  def MockGetGtestJsonResult(self):
    self.mock(buildbot, 'GetGtestResultLog', self._GetGtestResultLog)

  def testExtractStorablePortionOfLogWithSmallLogData(self):
    self.mock(extract_signal, 'LOG_DATA_BYTE_LIMIT', 500)
    lines = [str(i) * 99 for i in range(3)]
    log_data = '\n'.join(lines)
    expected_result = log_data
    result = extract_signal._ExtractStorablePortionOfLog(log_data)
    self.assertEqual(expected_result, result)

  def testExtractStorablePortionOfLogWithBigLogData(self):
    self.mock(extract_signal, 'LOG_DATA_BYTE_LIMIT', 500)
    lines = [str(9 - i) * 99 for i in range(9)]
    log_data = '\n'.join(lines)
    expected_result = '\n'.join(lines[-5:])
    result = extract_signal._ExtractStorablePortionOfLog(log_data)
    self.assertEqual(expected_result, result)

  def testExtractStorablePortionOfNinjaInfoLogWithBigLogData(self):
    self.mock(extract_signal, 'LOG_DATA_BYTE_LIMIT', 500)
    lines = [str(9 - i) * 99 for i in range(9)]
    log_data = '\n'.join(lines)
    result = extract_signal._ExtractStorablePortionOfLog(log_data, True)
    self.assertEqual('', result)

  @mock.patch.object(buildbot, 'GetStepLog')
  def testResponseTooLarge(self, mock_fun):
    mock_fun.side_effect = ResponseTooLargeError('test')

    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 'abc_test'
    log = extract_signal._GetStdoutLog(master_name, builder_name, build_number,
                                       step_name, None)

    self.assertEqual(log, 'Stdio log is too large for urlfetch.')

  @mock.patch.object(buildbot, 'GetStepLog', return_value=ABC_TEST_FAILURE_LOG)
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
            unsupported_step_name: {}
        }
    }

    def MockGetGtestResultLog(*_):
      return None

    self.mock(buildbot, 'GetGtestResultLog', MockGetGtestResultLog)
    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number)

    signals = extract_signal.ExtractSignals(failure_info, None)
    self.assertEqual(FAILURE_SIGNALS, signals)

  @mock.patch.object(buildbot, 'GetStepLog', return_value=ABC_TEST_FAILURE_LOG)
  def testGetSignalFromStepLog(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 'abc_test'

    # Mock both stdiolog and gtest json results to test whether Findit will
    # go to step log first when both logs exist.
    self.MockGetGtestJsonResult()
    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number)

    signals = extract_signal.ExtractSignals(FAILURE_INFO, None)

    step = WfStep.Get(master_name, builder_name, build_number, step_name)

    expected_files = {'a/b/u2s1.cc': [567], 'a/b/u3s2.cc': [110]}

    self.assertIsNotNone(step)
    self.assertIsNotNone(step.log_data)
    self.assertEqual(expected_files, signals['abc_test']['files'])

  @mock.patch.object(buildbot, 'GetStepLog', return_value=COMPILE_FAILURE_LOG)
  def testGetCompileStepSignalFromStepLog(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number)

    signals = extract_signal.ExtractSignals(COMPILE_FAILURE_INFO, None)

    expected_failed_edges = [{
        'output_nodes': ['a/b.o'],
        'rule': 'CXX',
        'dependencies': ['b.h', 'b.c']
    }]

    self.assertEqual(expected_failed_edges, signals['compile']['failed_edges'])

  @mock.patch.object(buildbot, 'GetStepLog', return_value=ABC_TEST_FAILURE_LOG)
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
    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number)

    signals = extract_signal.ExtractSignals(failure_info, None)

    step = WfStep.Get(master_name, builder_name, build_number, step_name)

    self.assertIsNotNone(step)
    self.assertIsNotNone(step.log_data)
    self.assertEqual('flaky', step.log_data)
    self.assertEqual({}, signals['abc_test']['files'])

  @mock.patch.object(buildbot, 'GetStepLog', return_value=ABC_TEST_FAILURE_LOG)
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
    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number)

    signals = extract_signal.ExtractSignals(failure_info, None)

    step = WfStep.Get(master_name, builder_name, build_number, step_name)

    expected_files = {
        'content/common/gpu/media/v4l2_video_encode_accelerator.cc': [306]
    }

    self.assertIsNotNone(step)
    self.assertIsNotNone(step.log_data)
    self.assertEqual(expected_files, signals['abc_test']['files'])

  @mock.patch.object(
      buildbot, 'GetStepLog', return_value='If used, test should fail!')
  def testWfStepStdioLogAlreadyDownloaded(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 'abc_test'
    step = WfStep.Create(master_name, builder_name, build_number, step_name)
    step.log_data = ABC_TEST_FAILURE_LOG
    step.put()

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number)

    signals = extract_signal.ExtractSignals(FAILURE_INFO, None)

    self.assertEqual(FAILURE_SIGNALS, signals)

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertEqual(FAILURE_SIGNALS, analysis.signals)

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

    expected_signals = {'abc_test': {'files': {}, 'keywords': {}, 'tests': {}}}

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number)

    signals = extract_signal.ExtractSignals(failure_info, None)
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

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number)

    signals = extract_signal.ExtractSignals(failure_info, None)
    self.assertEqual(expected_signals, signals)

  def testLogNotJsonLoadable(self):
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
    step.log_data = "Not Json loadable"
    step.put()

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number)

    expected_signals = {'abc_test': {'files': {}, 'keywords': {}, 'tests': {}}}

    signals = extract_signal.ExtractSignals(failure_info, None)
    self.assertEqual(expected_signals, signals)

  @mock.patch.object(buildbot, 'GetGtestResultLog', return_value=None)
  @mock.patch.object(extract_signal, '_GetStdoutLog', return_value=None)
  def testExtractSignalsNoFailureLog(self, *_):
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

    with self.assertRaises(Exception):
      extract_signal.ExtractSignals(failure_info, None)
