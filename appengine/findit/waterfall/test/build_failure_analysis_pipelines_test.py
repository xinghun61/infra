# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from pipeline_utils.appengine_third_party_pipeline_src_pipeline import handlers
from testing_utils import testing

from model.build_analysis import BuildAnalysis
from model.build_analysis_status import BuildAnalysisStatus
from waterfall import build_failure_analysis_pipelines
from waterfall import buildbot
from waterfall import lock_util


class BuildFailureAnalysisPipelinesTest(testing.AppengineTestCase):
  app_module = handlers._APP

  def _CreateAndSaveBuildAnanlysis(
      self, master_name, builder_name, build_number, status):
    analysis = BuildAnalysis.CreateBuildAnalysis(
        master_name, builder_name, build_number)
    analysis.status = status
    analysis.put()

  def testAnanlysIsNeededWhenBuildWasNeverAnalyzed(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123

    need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, False)

    self.assertTrue(need_analysis)

  def testNewAnalysisIsNotNeededWhenNotForced(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    self._CreateAndSaveBuildAnanlysis(master_name, builder_name, build_number,
                             BuildAnalysisStatus.ANALYZED)

    need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, False)

    self.assertFalse(need_analysis)

  def testNewAnanlysIsNeededWhenForced(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    self._CreateAndSaveBuildAnanlysis(master_name, builder_name, build_number,
                             BuildAnalysisStatus.ANALYZED)

    need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, True)

    self.assertTrue(need_analysis)

  def testSuccessfulAnalysisOfBuildFailure(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123

    def _WaitUntilDownloadAllowed(*_):
      return True

    self.mock(lock_util, 'WaitUntilDownloadAllowed', _WaitUntilDownloadAllowed)

    # Mock build data in urlfetch.
    with self.mock_urlfetch() as urlfetch:
      for i in range(3):
        build_url = buildbot.CreateBuildUrl(
                  master_name, builder_name, build_number - i, json_api=True)
        file_name = os.path.join(os.path.dirname(__file__), 'data',
                                 'm_b_%s.json' % (build_number - i))
        with open(file_name, 'r') as f:
          urlfetch.register_handler(build_url, f.read())

    build_failure_analysis_pipelines.ScheduleAnalysisIfNeeded(
        master_name, builder_name, build_number, False, 'default')

    self.execute_queued_tasks()

    analysis = BuildAnalysis.GetBuildAnalysis(
        master_name, builder_name, build_number)
    self.assertIsNotNone(analysis)
    self.assertEqual(BuildAnalysisStatus.ANALYZED, analysis.status)
