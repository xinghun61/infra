# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
from datetime import timedelta
import mock

from analysis.culprit import Culprit
from analysis.suspect import Suspect
from analysis.type_enums import CrashClient
from common import crash_pipeline
from common.appengine_testcase import AppengineTestCase
from common.findit_for_chromecrash import FinditForFracas
from common.model.fracas_crash_analysis import FracasCrashAnalysis
from gae_libs.pipeline_wrapper import pipeline_handlers
from libs import analysis_status
from libs.gitiles.change_log import ChangeLog
from libs.gitiles.change_log import Contributor


class CrashPipelineTest(AppengineTestCase):
  app_module = pipeline_handlers._APP

  def testAnalysisAborted(self):
    crash_identifiers = self.GetDummyChromeCrashData()['crash_identifiers']
    analysis = FracasCrashAnalysis.Create(crash_identifiers)
    analysis.status = analysis_status.RUNNING
    analysis.put()

    pipeline = crash_pipeline.CrashAnalysisPipeline(
        CrashClient.FRACAS,
        crash_identifiers)
    pipeline._PutAbortedError()
    analysis = FracasCrashAnalysis.Get(crash_identifiers)
    self.assertEqual(analysis_status.ERROR, analysis.status)

  @mock.patch('common.findit_for_chromecrash.FinditForFracas.FindCulprit')
  def testFindCulpritFails(self, mock_find_culprit):
    crash_identifiers = self.GetDummyChromeCrashData()['crash_identifiers']
    analysis = FracasCrashAnalysis.Create(crash_identifiers)
    analysis.status = analysis_status.RUNNING
    analysis.put()

    mock_find_culprit.return_value = None
    pipeline = crash_pipeline.CrashAnalysisPipeline(
        CrashClient.FRACAS,
        crash_identifiers)
    pipeline.run()

    analysis = FracasCrashAnalysis.Get(crash_identifiers)
    self.assertEqual(analysis_status.COMPLETED, analysis.status)
    self.assertFalse(analysis.result['found'])
    self.assertFalse(analysis.found_suspects)
    self.assertFalse(analysis.found_project)
    self.assertFalse(analysis.found_components)

  @mock.patch('common.findit_for_chromecrash.FinditForFracas.FindCulprit')
  def testFindCulpritSucceeds(self, mock_find_culprit):
    crash_identifiers = self.GetDummyChromeCrashData()['crash_identifiers']
    analysis = FracasCrashAnalysis.Create(crash_identifiers)
    analysis.status = analysis_status.RUNNING
    analysis.put()

    dummy_cl = ChangeLog(
        Contributor('AUTHOR_NAME', 'AUTHOR_EMAIL', 'AUTHOR_TIME'),
        Contributor('COMITTER_NAME', 'COMITTER_EMAIL', 'COMITTER_TIME'),
        'REVISION',
        'COMMIT_POSITION',
        'MESSAGE',
        'TOUCHED_FILES',
        'COMMIT_URL',
    )
    dummy_project_path = 'PROJECT_PATH'
    dummy_suspect = Suspect(dummy_cl, dummy_project_path)
    dummy_culprit = Culprit(
        project = 'PROJECT',
        components = ['COMPONENT_1', 'CPOMPONENT_2'],
        cls = [dummy_suspect],
        # N.B., we must use a list here for the assertion to work
        # TODO(wrengr): fix that.
        regression_range = ['VERSION_0', 'VERSION_1'],
        algorithm = 'ALGORITHM',
    )
    mock_find_culprit.return_value = dummy_culprit
    pipeline = crash_pipeline.CrashAnalysisPipeline(CrashClient.FRACAS,
                                                    crash_identifiers)
    pipeline.run()

    analysis = FracasCrashAnalysis.Get(crash_identifiers)
    self.assertEqual(analysis_status.COMPLETED, analysis.status)
    self.assertTrue(analysis.result['found'])
    self.assertTrue(analysis.found_suspects)
    self.assertTrue(analysis.found_project)
    self.assertTrue(analysis.found_components)
    dummy_suspect, dummy_tags = dummy_culprit.ToDicts()
    self.assertDictEqual(analysis.result, dummy_suspect)


class RerunPipelineTest(AppengineTestCase):
  app_module = pipeline_handlers._APP

  def testRunForUnsupportClient(self):
    client = 'dummy_client'
    start_date = datetime(2017, 5, 19, 0, 0, 0)
    end_date = datetime(2017, 5, 20, 0, 0, 0)

    self.MockPipeline(crash_pipeline.RerunPipeline, None,
                      [client, start_date, end_date])
    rerun_pipeline = crash_pipeline.RerunPipeline(client, start_date, end_date)
    rerun_pipeline.start_test()
    self.assertIsNone(rerun_pipeline.outputs.default.value, None)

  @mock.patch('common.crash_pipeline.FinditForClientID')
  def testRun(self, mock_findit_for_client):
    mock_findit_for_client.return_value = None

    client = CrashClient.CRACAS
    start_date = datetime(2017, 5, 19, 0, 0, 0)
    end_date = datetime(2017, 5, 20, 0, 0, 0)

    self.MockPipeline(crash_pipeline.RerunPipeline, None,
                      [client, start_date, end_date])
    rerun_pipeline = crash_pipeline.RerunPipeline(client, start_date, end_date)
    rerun_pipeline.start_test()
