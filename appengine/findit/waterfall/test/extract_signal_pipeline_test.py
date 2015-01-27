# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from pipeline_utils.appengine_third_party_pipeline_src_pipeline import handlers
from testing_utils import testing

from model.step import Step
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



  def testStepStdioLogAlreadyDownloaded(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 'abc_test'
    step = Step.CreateStep(master_name, builder_name, build_number, step_name)
    step.log_data = self.ABC_TEST_FAILURE_LOG
    step.put()

    step_log_url = buildbot.CreateStdioLogUrl(
        master_name, builder_name, build_number, step_name)
    with self.mock_urlfetch() as urlfetch:
      urlfetch.register_handler(step_log_url, 'If used, test should fail!')

    pipeline = ExtractSignalPipeline(self.FAILURE_INFO)
    signals = pipeline.run(self.FAILURE_INFO)

    self.assertEqual(self.FAILURE_SIGNALS, signals)

  def testStepStdioLogNotDownloadedYet(self):
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

    step = Step.CreateStep(master_name, builder_name, build_number, step_name)
    self.assertIsNotNone(step)
