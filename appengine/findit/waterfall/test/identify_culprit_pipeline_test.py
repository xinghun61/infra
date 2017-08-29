# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
from testing_utils import testing

from common.waterfall import failure_type
from gae_libs.pipeline_wrapper import pipeline_handlers
from libs import analysis_status
from model.wf_analysis import WfAnalysis
from waterfall import build_failure_analysis
from waterfall import identify_culprit_pipeline


class IdentifyCulpritPipelineTest(testing.AppengineTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(build_failure_analysis, 'PullChangeLogs', return_value={})
  @mock.patch.object(build_failure_analysis, 'ExtractDepsInfo', return_value={})
  @mock.patch.object(
      build_failure_analysis,
      'AnalyzeBuildFailure',
      return_value=({
          'failures': []
      }, []))
  def testIdentifyCulpritPipeline(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.result = None
    analysis.status = analysis_status.RUNNING
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
