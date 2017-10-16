# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import mock
import datetime

from google.appengine.ext import ndb
from gae_libs.pipeline_wrapper import pipeline_handlers
from gae_libs.pipelines import CreateInputObjectInstance
from model.flake.flake_analysis_request import FlakeAnalysisRequest
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from pipelines.flake_failure import create_bug_for_flake_pipeline
from pipelines.flake_failure.create_bug_for_flake_pipeline import (
    CreateBugForFlakePipeline)
from pipelines.flake_failure.create_bug_for_flake_pipeline import (
    CreateBugForFlakePipelineInputObject)
from services.flake_failure import issue_tracking_service

from waterfall.flake import triggering_sources
from waterfall.test.wf_testcase import WaterfallTestCase


class CreateBugForFlakePipelineTest(WaterfallTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(
      issue_tracking_service, 'ShouldFileBugForAnalysis', return_value=True)
  @mock.patch.object(  # 123 is the bug_number.
      issue_tracking_service,
      'CreateBugForTest',
      return_value=123)
  def testCreateBugForFlakePipeline(self, create_bug_fn, should_file_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    bug_id = 123

    # Create a flake analysis with no bug.
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    # Create a flake analysis request with no bug.
    request = FlakeAnalysisRequest.Create(test_name, False, None)
    request.Save()

    create_bug_input = CreateInputObjectInstance(
        CreateBugForFlakePipelineInputObject,
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        test_location={'file': '/foo/bar',
                       'line': '1'})
    pipeline_job = CreateBugForFlakePipeline(create_bug_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertTrue(create_bug_fn.called)
    self.assertTrue(should_file_fn.called)

    self.assertEqual(analysis.bug_id, bug_id)
    self.assertEqual(request.bug_id, bug_id)
    self.assertEqual(request.bug_reported_by,
                     triggering_sources.FINDIT_PIPELINE)
    self.assertTrue(analysis.has_attempted_filing)

  @mock.patch.object(
      issue_tracking_service, 'ShouldFileBugForAnalysis', return_value=True)
  @mock.patch.object(  # 123 is the bug_number.
      issue_tracking_service,
      'CreateBugForTest',
      return_value=None)
  def testCreateBugForFlakePipelineWhenCreateBugReturnsNone(
      self, create_bug_fn, should_file_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    # Create a flake analysis with no bug.
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    # Create a flake analysis request with no bug.
    request = FlakeAnalysisRequest.Create(test_name, False, None)
    request.Save()

    create_bug_input = CreateInputObjectInstance(
        CreateBugForFlakePipelineInputObject,
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        test_location={'file': '/foo/bar',
                       'line': '1'})
    pipeline_job = CreateBugForFlakePipeline(create_bug_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertTrue(create_bug_fn.called)
    self.assertTrue(should_file_fn.called)

    self.assertTrue(analysis.has_attempted_filing)

  @mock.patch.object(
      issue_tracking_service, 'ShouldFileBugForAnalysis', return_value=False)
  @mock.patch.object(  # 123 is the bug_number.
      issue_tracking_service,
      'CreateBugForTest',
      return_value=123)
  def testCreateBugForFlakePipelineWhenShouldFileReturnsFalse(
      self, create_bug_fn, should_file_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    # Create a flake analysis with no bug.
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    # Create a flake analysis request with no bug.
    request = FlakeAnalysisRequest.Create(test_name, False, None)
    request.Save()

    create_bug_input = CreateInputObjectInstance(
        CreateBugForFlakePipelineInputObject,
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        test_location={'file': '/foo/bar',
                       'line': '1'})
    pipeline_job = CreateBugForFlakePipeline(create_bug_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertFalse(create_bug_fn.called)
    self.assertTrue(should_file_fn.called)
    self.assertFalse(analysis.has_attempted_filing)