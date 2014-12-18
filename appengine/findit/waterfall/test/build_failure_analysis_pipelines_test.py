# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from pipeline_utils.appengine_third_party_pipeline_src_pipeline import handlers
from testing_utils import testing

from model.build import Build
from model.build_analysis_status import BuildAnalysisStatus
from waterfall import build_failure_analysis_pipelines


class BuildFailureAnalysisPipelinesTest(testing.AppengineTestCase):
  app_module = handlers._APP

  def _CreateAndSaveBuild(self, master_name, builder_name, build_number,
                          analysis_status):
    build = Build.CreateBuild(master_name, builder_name, build_number)
    build.analysis_status = analysis_status
    build.put()

  def testAnanlysIsNeededWhenBuildWasNeverAnalyzed(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123

    _, need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, False)

    self.assertTrue(need_analysis)

  def testNewAnalysisIsNotNeededWhenNotForced(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    self._CreateAndSaveBuild(master_name, builder_name, build_number,
                             BuildAnalysisStatus.ANALYZED)

    build, need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, False)

    self.assertFalse(need_analysis)
    self.assertEqual(BuildAnalysisStatus.ANALYZED, build.analysis_status)

  def testNewAnanlysIsNeededWhenForced(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    self._CreateAndSaveBuild(master_name, builder_name, build_number,
                             BuildAnalysisStatus.ANALYZED)

    _, need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, True)

    self.assertTrue(need_analysis)

  def testAnalysisScheduled(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123

    build_failure_analysis_pipelines.ScheduleAnalysisIfNeeded(
        master_name, builder_name, build_number, False, 'default')

    self.execute_queued_tasks()

    build = Build.GetBuild(master_name, builder_name, build_number)
    self.assertIsNotNone(build)
    self.assertEqual(BuildAnalysisStatus.ANALYZED, build.analysis_status)
