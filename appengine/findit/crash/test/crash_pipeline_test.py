# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.pipeline_wrapper import pipeline_handlers
from crash import crash_pipeline
from crash.culprit import Culprit
from crash.findit_for_chromecrash import FinditForFracas
from crash.results import Result
from crash.test.crash_testcase import CrashTestCase
from crash.type_enums import CrashClient
from libs.gitiles.change_log import ChangeLog
from model import analysis_status
from model.crash.fracas_crash_analysis import FracasCrashAnalysis


def DummyCrashData(
    client_id=None,
    version='1',
    signature='signature',
    platform='win',
    stack_trace=None,
    regression_range=None,
    channel='canary',
    historical_metadata=None,
    crash_identifiers=True,
    process_type='browser'):
  if crash_identifiers is True: # pragma: no cover
    crash_identifiers = {
        'chrome_version': version,
        'signature': signature,
        'channel': channel,
        'platform': platform,
        'process_type': process_type,
    }
  crash_data = {
      'crashed_version': version,
      'signature': signature,
      'platform': platform,
      'stack_trace': stack_trace,
      'regression_range': regression_range,
      'crash_identifiers': crash_identifiers,
      'customized_data': {
          'historical_metadata': historical_metadata,
          'channel': channel,
      },
  }
  # This insertion of client_id is used for debugging ScheduleNewAnalysis.
  if client_id is not None: # pragma: no cover
    crash_data['client_id'] = client_id
  return crash_data


class CrashPipelineTest(CrashTestCase):
  app_module = pipeline_handlers._APP

  def testAnalysisAborted(self):
    crash_identifiers = DummyCrashData()['crash_identifiers']
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
    crash_identifiers = DummyCrashData()['crash_identifiers']
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
    crash_identifiers = DummyCrashData()['crash_identifiers']
    analysis = FracasCrashAnalysis.Create(crash_identifiers)
    analysis.status = analysis_status.RUNNING
    analysis.put()

    dummy_cl = ChangeLog(
        'AUTHOR_NAME',
        'AUTHOR_EMAIL',
        'AUTHOR_TIME',
        'COMITTER_NAME',
        'COMITTER_EMAIL',
        'COMITTER_TIME',
        'REVISION',
        'COMMIT_POSITION',
        'MESSAGE',
        'TOUCHED_FILES',
        'COMMIT_URL',
    )
    dummy_project_path = 'PROJECT_PATH'
    dummy_result = Result(dummy_cl, dummy_project_path)
    dummy_culprit = Culprit(
        project = 'PROJECT',
        components = ['COMPONENT_1', 'CPOMPONENT_2'],
        cls = [dummy_result],
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
    dummy_result, dummy_tags = dummy_culprit.ToDicts()
    self.assertDictEqual(analysis.result, dummy_result)
