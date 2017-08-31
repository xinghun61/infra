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


class ExtractSignalTest(wf_testcase.WaterfallTestCase):

  def testExtractStorablePortionOfLogWithSmallLogData(self):
    self.mock(extract_signal, '_LOG_DATA_BYTE_LIMIT', 500)
    lines = [str(i) * 99 for i in range(3)]
    log_data = '\n'.join(lines)
    expected_result = log_data
    result = extract_signal.ExtractStorablePortionOfLog(log_data)
    self.assertEqual(expected_result, result)

  def testExtractStorablePortionOfLogWithBigLogData(self):
    self.mock(extract_signal, '_LOG_DATA_BYTE_LIMIT', 500)
    lines = [str(9 - i) * 99 for i in range(9)]
    log_data = '\n'.join(lines)
    expected_result = '\n'.join(lines[-5:])
    result = extract_signal.ExtractStorablePortionOfLog(log_data)
    self.assertEqual(expected_result, result)

  def testExtractStorablePortionOfNinjaInfoLogWithBigLogData(self):
    self.mock(extract_signal, '_LOG_DATA_BYTE_LIMIT', 500)
    lines = [str(9 - i) * 99 for i in range(9)]
    log_data = '\n'.join(lines)
    result = extract_signal.ExtractStorablePortionOfLog(log_data, True)
    self.assertEqual('', result)

  @mock.patch.object(buildbot, 'GetStepLog')
  def testResponseTooLarge(self, mock_fun):
    mock_fun.side_effect = ResponseTooLargeError('test')

    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 'abc_test'
    log = extract_signal.GetStdoutLog(master_name, builder_name, build_number,
                                      step_name, None)

    self.assertEqual(log, 'Stdio log is too large for urlfetch.')

  def testSaveSignalInAnalysis(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    signals = 'signals'

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

    extract_signal.SaveSignalInAnalysis(master_name, builder_name, build_number,
                                        signals)

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertEqual(signals, analysis.signals)
