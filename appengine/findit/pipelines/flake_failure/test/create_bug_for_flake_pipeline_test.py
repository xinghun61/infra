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
      create_bug_for_flake_pipeline, '_HasPreviousAttempt', return_value=False)
  @mock.patch.object(
      create_bug_for_flake_pipeline,
      '_HasSufficientConfidenceInCulprit',
      return_value=True)
  @mock.patch.object(
      issue_tracking_service, 'BugAlreadyExistsForId', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'BugAlreadyExistsForLabel', return_value=False)
  @mock.patch.object(  # 123 is the bug_number.
      issue_tracking_service,
      'CreateBugForTest',
      return_value=123)
  def testCreateBugForFlakePipeline(self, create_bug_fn, label_exists_fn,
                                    id_exists_fn, *_):
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
    self.assertTrue(label_exists_fn.called)
    self.assertTrue(id_exists_fn.called)

    self.assertEqual(analysis.bug_id, bug_id)
    self.assertEqual(request.bug_id, bug_id)
    self.assertEqual(request.bug_reported_by,
                     triggering_sources.FINDIT_PIPELINE)
    self.assertTrue(analysis.has_attempted_filing)

  @mock.patch.object(
      create_bug_for_flake_pipeline, '_HasPreviousAttempt', return_value=False)
  @mock.patch.object(
      create_bug_for_flake_pipeline,
      '_HasSufficientConfidenceInCulprit',
      return_value=True)
  @mock.patch.object(
      issue_tracking_service, 'BugAlreadyExistsForLabel', return_value=False)
  @mock.patch.object(  # 123 is the bug_number.
      issue_tracking_service,
      'CreateBugForTest',
      return_value=123)
  @mock.patch.object(
      issue_tracking_service, 'BugAlreadyExistsForId', return_value=True)
  def testCreateBugForFlakePipelineWhenBugIdExists(self, id_exists_fn, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    # Create a flake analysis with no bug.
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.bug_id = 1
    analysis.Save()

    # Create a flake analysis request with no bug.
    request = FlakeAnalysisRequest.Create(test_name, False, None)
    request.bug_id = 1
    request.Save()

    create_bug_input = CreateInputObjectInstance(
        CreateBugForFlakePipelineInputObject,
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        test_location={'file': '/foo/bar',
                       'line': '1'})
    pipeline_job = CreateBugForFlakePipeline(create_bug_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertTrue(id_exists_fn.called)
    call_args, _ = id_exists_fn.call_args
    self.assertEqual(call_args, (1,))

    self.assertFalse(analysis.has_attempted_filing)

  @mock.patch.object(
      create_bug_for_flake_pipeline, '_HasPreviousAttempt', return_value=False)
  @mock.patch.object(
      create_bug_for_flake_pipeline,
      '_HasSufficientConfidenceInCulprit',
      return_value=True)
  @mock.patch.object(  # 123 is the bug_number.
      issue_tracking_service,
      'CreateBugForTest',
      return_value=123)
  @mock.patch.object(
      issue_tracking_service, 'BugAlreadyExistsForId', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'BugAlreadyExistsForLabel', return_value=True)
  def testCreateBugForFlakePipelineWhenTestLabelExists(self, label_exists_fn,
                                                       *_):
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

    input_obj = CreateInputObjectInstance(
        CreateBugForFlakePipelineInputObject,
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        test_location={'file': '/foo/bar',
                       'line': '1'})
    pipeline_job = CreateBugForFlakePipeline(input_obj)
    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertTrue(label_exists_fn.called)
    call_args, _ = label_exists_fn.call_args
    self.assertEqual(call_args, (test_name,))

    self.assertFalse(analysis.has_attempted_filing)

  @mock.patch.object(
      create_bug_for_flake_pipeline, '_HasPreviousAttempt', return_value=False)
  @mock.patch.object(
      create_bug_for_flake_pipeline,
      '_HasSufficientConfidenceInCulprit',
      return_value=True)
  @mock.patch.object(
      issue_tracking_service, 'BugAlreadyExistsForId', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'BugAlreadyExistsForLabel', return_value=False)
  @mock.patch.object(  # 123 is the bug_number.
      issue_tracking_service,
      'CreateBugForTest',
      return_value=None)
  def testCreateBugForFlakePipelineWhenCreateBugFails(self, create_bug_fn, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    # Create a flake analysis with no bug.
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.confidence_in_culprit = 1.0
    analysis.Save()

    # Create a flake analysis request with no bug.
    request = FlakeAnalysisRequest.Create(test_name, False, None)
    request.Save()

    input_obj = CreateInputObjectInstance(
        CreateBugForFlakePipelineInputObject,
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        test_location={'file': '/foo/bar',
                       'line': '1'})
    pipeline_job = CreateBugForFlakePipeline(input_obj)
    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertTrue(create_bug_fn.called)
    call_args, _ = create_bug_fn.call_args
    expected_subject = '%s is Flaky' % test_name

    analysis_link = ('https://findit-for-me.appspot.com/waterfall/flake?key=%s'
                     % analysis.key.urlsafe())
    expected_body = ('Findit has detected a flake at test %s. Track this'
                     'analysis here:\n%s' % (test_name, analysis_link))
    self.assertEqual(call_args, (test_name, expected_subject, expected_body))

    self.assertTrue(analysis.has_attempted_filing)

  @mock.patch.object(
      create_bug_for_flake_pipeline, '_HasPreviousAttempt', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'BugAlreadyExistsForId', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'BugAlreadyExistsForLabel', return_value=False)
  @mock.patch.object(  # 123 is the bug_number.
      issue_tracking_service,
      'CreateBugForTest',
      return_value=123)
  @mock.patch.object(
      create_bug_for_flake_pipeline,
      '_HasSufficientConfidenceInCulprit',
      return_value=False)
  def testCreateBugForFlakePipelineWithLowConfidence(self, mock_confidence_fn,
                                                     *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    # Create a flake analysis with no bug.
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.confidence_in_culprit = 0.0
    analysis.Save()

    # Create a flake analysis request with no bug.
    request = FlakeAnalysisRequest.Create(test_name, False, None)
    request.Save()

    input_obj = CreateInputObjectInstance(
        CreateBugForFlakePipelineInputObject,
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        test_location={'file': '/foo/bar',
                       'line': '1'})
    pipeline_job = CreateBugForFlakePipeline(input_obj)
    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertTrue(mock_confidence_fn.called)
    self.assertFalse(analysis.has_attempted_filing)

  @mock.patch.object(
      create_bug_for_flake_pipeline,
      '_HasSufficientConfidenceInCulprit',
      return_value=True)
  @mock.patch.object(
      issue_tracking_service, 'BugAlreadyExistsForId', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'BugAlreadyExistsForLabel', return_value=False)
  @mock.patch.object(  # 123 is the bug_number.
      issue_tracking_service,
      'CreateBugForTest',
      return_value=123)
  @mock.patch.object(
      create_bug_for_flake_pipeline, '_HasPreviousAttempt', return_value=True)
  def testCreateBugForFlakePipelineWhenAPreviousAttemptExists(
      self, mock_prev_attempt_fn, *_):
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

    self.assertTrue(mock_prev_attempt_fn.called)
    self.assertFalse(analysis.has_attempted_filing)

  # Unit tests.

  def testHasPreviousAttempt(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.has_attempted_filing = True
    analysis.Save()
    self.assertTrue(create_bug_for_flake_pipeline._HasPreviousAttempt(analysis))

    analysis.has_attempted_filing = False
    analysis.put()
    self.assertFalse(
        create_bug_for_flake_pipeline._HasPreviousAttempt(analysis))

  def testHasSufficientConfidenceInCulprit(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)

    analysis.confidence_in_culprit = None
    analysis.Save()
    self.assertFalse(
        create_bug_for_flake_pipeline._HasSufficientConfidenceInCulprit(
            analysis))

    analysis.confidence_in_culprit = 1.0
    analysis.Save()
    self.assertTrue(
        create_bug_for_flake_pipeline._HasSufficientConfidenceInCulprit(
            analysis))

    analysis.confidence_in_culprit = .9
    analysis.put()
    self.assertFalse(
        create_bug_for_flake_pipeline._HasSufficientConfidenceInCulprit(
            analysis))