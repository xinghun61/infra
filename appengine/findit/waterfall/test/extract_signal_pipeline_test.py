# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common.waterfall import failure_type
from gae_libs.pipeline_wrapper import pipeline_handlers
from services.compile_failure import extract_compile_signal
from services.test_failure import extract_test_signal
from waterfall.extract_signal_pipeline import ExtractSignalPipeline
from waterfall.test import wf_testcase


class ExtractSignalPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(extract_test_signal, 'ExtractSignalsForTestFailure')
  def testExtractSignalsForTests(self, mock_signal):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    expected_signals = 'test signals'

    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failure_type': failure_type.TEST,
    }

    mock_signal.return_value = expected_signals

    pipeline = ExtractSignalPipeline()
    signals = pipeline.run(failure_info)
    self.assertEqual(expected_signals, signals)
    mock_signal.assert_called_with(failure_info, pipeline.HTTP_CLIENT)

  @mock.patch.object(extract_compile_signal, 'ExtractSignalsForCompileFailure')
  def testExtractSignalsForCompile(self, mock_signal):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    expected_signals = 'compile signals'

    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failure_type': failure_type.COMPILE,
    }

    mock_signal.return_value = expected_signals

    pipeline = ExtractSignalPipeline()
    signals = pipeline.run(failure_info)
    self.assertEqual(expected_signals, signals)
    mock_signal.assert_called_with(failure_info, pipeline.HTTP_CLIENT)
