# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import datetime
import mock

from google.appengine.ext import ndb

from common.waterfall import failure_type
from gae_libs import pipelines
from libs import structured_object
from model.wf_analysis import WfAnalysis
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from pipelines import report_event_pipeline
from services import event_reporting

from waterfall.test.wf_testcase import WaterfallTestCase


class ReportEventPipelineTest(WaterfallTestCase):
  app_module = pipelines.pipeline_handlers._APP

  def testCanReportAnalysis(self):
    analysis = mock.Mock()
    analysis.start_time = datetime.datetime(2018, 1, 1)
    analysis.end_time = datetime.datetime(2018, 1, 2)
    self.assertTrue(report_event_pipeline._CanReportAnalysis(analysis))

    analysis.start_time = datetime.datetime(2018, 1, 1)
    analysis.end_time = None
    self.assertFalse(report_event_pipeline._CanReportAnalysis(analysis))

    analysis.start_time = None
    analysis.end_time = datetime.datetime(2018, 1, 2)
    self.assertFalse(report_event_pipeline._CanReportAnalysis(analysis))

  @mock.patch.object(
      event_reporting,
      'ReportTestFlakeAnalysisCompletionEvent',
      return_value=None)
  def testReportAnalysisEventPipelineTestFlakeAnalysis(self,
                                                       event_reporting_fn):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.start_time = datetime.datetime(2018, 1, 1)
    analysis.end_time = datetime.datetime(2018, 1, 2)
    analysis.put()

    parameters = report_event_pipeline.ReportEventInput(
        analysis_urlsafe_key=analysis.key.urlsafe())
    p = report_event_pipeline.ReportAnalysisEventPipeline(parameters)
    p.start()
    self.execute_queued_tasks()
    self.assertTrue(event_reporting_fn.called)
    args, _ = event_reporting_fn.call_args
    self.assertEqual(args[0], analysis)

  @mock.patch.object(
      event_reporting,
      'ReportTestFailureAnalysisCompletionEvent',
      return_value=None)
  def testReportAnalysisEventPipelineTestFailureAnalysis(
      self, event_reporting_fn):
    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.start_time = datetime.datetime(2018, 1, 1)
    analysis.end_time = datetime.datetime(2018, 1, 2)
    analysis.build_failure_type = failure_type.TEST
    analysis.put()

    parameters = report_event_pipeline.ReportEventInput(
        analysis_urlsafe_key=analysis.key.urlsafe())
    p = report_event_pipeline.ReportAnalysisEventPipeline(parameters)
    p.start()
    self.execute_queued_tasks()
    self.assertTrue(event_reporting_fn.called)
    args, _ = event_reporting_fn.call_args
    self.assertEqual(args[0], analysis)

  @mock.patch.object(
      event_reporting,
      'ReportCompileFailureAnalysisCompletionEvent',
      return_value=None)
  def testReportAnalysisEventPipelineCompileFailureAnalysis(
      self, event_reporting_fn):
    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.start_time = datetime.datetime(2018, 1, 1)
    analysis.end_time = datetime.datetime(2018, 1, 2)
    analysis.build_failure_type = failure_type.COMPILE
    analysis.put()

    parameters = report_event_pipeline.ReportEventInput(
        analysis_urlsafe_key=analysis.key.urlsafe())
    p = report_event_pipeline.ReportAnalysisEventPipeline(parameters)
    p.start()
    self.execute_queued_tasks()
    self.assertTrue(event_reporting_fn.called)
    args, _ = event_reporting_fn.call_args
    self.assertEqual(args[0], analysis)

  @mock.patch.object(
      event_reporting,
      'ReportCompileFailureAnalysisCompletionEvent',
      return_value=None)
  def testReportAnalysisEventPipelineWfAnalysisNoType(self, event_reporting_fn):
    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.start_time = datetime.datetime(2018, 1, 1)
    analysis.end_time = datetime.datetime(2018, 1, 2)
    analysis.build_failure_type = -1
    analysis.put()

    parameters = report_event_pipeline.ReportEventInput(
        analysis_urlsafe_key=analysis.key.urlsafe())
    p = report_event_pipeline.ReportAnalysisEventPipeline(parameters)
    p.start()
    self.execute_queued_tasks()
    self.assertFalse(event_reporting_fn.called)

  @mock.patch.object(event_reporting, 'ReportTestFlakeAnalysisCompletionEvent')
  def testReportAnalysisEventPipelineWithAnalysisThatCannotBeReported(
      self, event_reporting_fn):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.start_time = datetime.datetime(2018, 1, 1)
    analysis.end_time = None
    analysis.put()

    parameters = report_event_pipeline.ReportEventInput(
        analysis_urlsafe_key=analysis.key.urlsafe())
    p = report_event_pipeline.ReportAnalysisEventPipeline(parameters)
    p.start()
    self.execute_queued_tasks()
    self.assertFalse(event_reporting_fn.called)
