# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common.findit_http_client import FinditHttpClient
from common.waterfall import failure_type
from pipelines.compile_failure import extract_signal_for_compile_pipeline
from pipelines.compile_failure.extract_signal_for_compile_pipeline import (
    ExtractSignalForCompilePipeline)
from services.compile_failure import extract_compile_signal
from waterfall.test import wf_testcase

_HTTP_CLIENT = FinditHttpClient()


class ExtractSignalForCompilePipelineTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(
      extract_signal_for_compile_pipeline,
      'FinditHttpClient',
      autospec=True,
      return_value=_HTTP_CLIENT)
  @mock.patch.object(extract_compile_signal, 'ExtractSignalsForCompileFailure')
  def testExtractSignalsForCompile(self, mock_signal, _):
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

    pipeline = ExtractSignalForCompilePipeline()
    signals = pipeline.run(failure_info)
    self.assertEqual(expected_signals, signals)
    mock_signal.assert_called_with(failure_info, _HTTP_CLIENT)
