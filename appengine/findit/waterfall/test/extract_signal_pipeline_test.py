# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from pipeline_utils.appengine_third_party_pipeline_src_pipeline import handlers
from testing_utils import testing

from model.wf_step import WfStep
from waterfall import buildbot
from waterfall import extractors
from waterfall.extract_signal_pipeline import ExtractSignalPipeline


class ExtractSignalPipelineTest(testing.AppengineTestCase):
  app_module = handlers._APP

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
        "keywords": {},
        "tests": []
      }
    }

  FAILURE_INFO = {
      'master_name': 'm',
      'builder_name': 'b',
      'build_number': 123,
      'failed_steps': {
          'abc_test': {
              'last_pass': 122,
              'current_failure': 123,
              'first_failure': 123,
          }
      }
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

  def testWfStepStdioLogNotDownloadedYet(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 'abc_test'

    step_log_url = buildbot.CreateStdioLogUrl(
        master_name, builder_name, build_number, step_name)
    with self.mock_urlfetch() as urlfetch:
      urlfetch.register_handler(step_log_url, self.ABC_TEST_FAILURE_LOG)

    pipeline = ExtractSignalPipeline(self.FAILURE_INFO)
    pipeline.start()
    self.execute_queued_tasks()

    step = WfStep.Create(master_name, builder_name, build_number, step_name)
    self.assertIsNotNone(step)
