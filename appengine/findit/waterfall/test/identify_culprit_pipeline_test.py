# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock
from testing_utils import testing

from common.waterfall import failure_type
from gae_libs.pipelines import pipeline_handlers
from libs import analysis_status
from model.wf_analysis import WfAnalysis
from services import deps
from services import git
from services.compile_failure import compile_failure_analysis
from services.test_failure import test_failure_analysis
from waterfall import identify_culprit_pipeline


class IdentifyCulpritPipelineTest(testing.AppengineTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(git, 'PullChangeLogs', return_value={})
  @mock.patch.object(deps, 'ExtractDepsInfo', return_value={})
  @mock.patch.object(
      compile_failure_analysis,
      'AnalyzeCompileFailure',
      return_value=({
          'failures': []
      }, []))
  def testIdentifyCulpritPipelineForCompile(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.result = None
    analysis.status = analysis_status.RUNNING
    analysis.start_time = datetime(2017, 6, 26, 23)
    analysis.put()

    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failure_type': failure_type.COMPILE
    }
    signals = {}

    pipeline = identify_culprit_pipeline.IdentifyCulpritPipeline(
        failure_info, signals, True)
    pipeline.start()
    self.execute_queued_tasks()

    expected_suspected_cls = []

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertTrue(analysis.build_completed)
    self.assertIsNotNone(analysis)
    self.assertEqual({'failures': []}, analysis.result)
    self.assertEqual(analysis_status.COMPLETED, analysis.status)
    self.assertIsNone(analysis.result_status)
    self.assertEqual(expected_suspected_cls, analysis.suspected_cls)

  @mock.patch.object(git, 'PullChangeLogs', return_value={})
  @mock.patch.object(deps, 'ExtractDepsInfo', return_value={})
  @mock.patch.object(
      test_failure_analysis,
      'AnalyzeTestFailure',
      return_value=({
          'failures': []
      }, []))
  def testIdentifyCulpritPipelineForTest(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.result = None
    analysis.status = analysis_status.RUNNING
    analysis.start_time = datetime(2017, 6, 26, 23)
    analysis.put()

    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failure_type': failure_type.TEST
    }
    signals = {}

    pipeline = identify_culprit_pipeline.IdentifyCulpritPipeline(
        failure_info, signals, True)
    pipeline.start()
    self.execute_queued_tasks()

    expected_suspected_cls = []

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertTrue(analysis.build_completed)
    self.assertIsNotNone(analysis)
    self.assertEqual({'failures': []}, analysis.result)
    self.assertEqual(analysis_status.COMPLETED, analysis.status)
    self.assertIsNone(analysis.result_status)
    self.assertEqual(expected_suspected_cls, analysis.suspected_cls)
