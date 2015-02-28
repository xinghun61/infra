# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from pipeline_utils.appengine_third_party_pipeline_src_pipeline import handlers
from testing_utils import testing

from model.wf_analysis import WfAnalysis
from model import wf_analysis_status
from waterfall import build_failure_analysis
from waterfall.identify_culprit_pipeline import IdentifyCulpritPipeline


class PullChangelogPipelineTest(testing.AppengineTestCase):
  app_module = handlers._APP

  def testPullChangelogs(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.result = None
    analysis.status = wf_analysis_status.ANALYZING
    analysis.put()

    failure_info = {
      'master_name': master_name,
      'builder_name': builder_name,
      'build_number': build_number,
    }
    change_logs = {}
    signals = {}

    dummy_result = ['dummy_result']
    def _MockAnalyzeBuildFailure(*_):
      return dummy_result

    self.mock(build_failure_analysis,
              'AnalyzeBuildFailure', _MockAnalyzeBuildFailure)

    pipeline = IdentifyCulpritPipeline(failure_info, change_logs, signals)
    pipeline.start()
    self.execute_queued_tasks()

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertIsNotNone(analysis)
    self.assertEqual(dummy_result, analysis.result)
    self.assertEqual(wf_analysis_status.ANALYZED, analysis.status)
