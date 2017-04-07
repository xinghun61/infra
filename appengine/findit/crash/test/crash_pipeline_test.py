# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from crash import crash_pipeline
from crash.culprit import Culprit
from crash.findit_for_chromecrash import FinditForFracas
from crash.suspect import Suspect
from crash.test.predator_testcase import PredatorTestCase
from crash.type_enums import CrashClient
from gae_libs.pipeline_wrapper import pipeline_handlers
from libs import analysis_status
from libs.gitiles.change_log import ChangeLog
from libs.gitiles.change_log import Contributor
from model.crash.fracas_crash_analysis import FracasCrashAnalysis


class CrashPipelineTest(PredatorTestCase):
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

  def testFindCulpritFails(self):
    crash_identifiers = self.GetDummyChromeCrashData()['crash_identifiers']
    analysis = FracasCrashAnalysis.Create(crash_identifiers)
    analysis.status = analysis_status.RUNNING
    analysis.put()

    self.mock(FinditForFracas, 'FindCulprit', lambda *_: None)
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

  def testFindCulpritSucceeds(self):
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
    self.mock(FinditForFracas, 'FindCulprit', lambda *_: dummy_culprit)
    pipeline = crash_pipeline.CrashAnalysisPipeline(
        CrashClient.FRACAS,
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
