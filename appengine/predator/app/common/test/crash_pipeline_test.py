# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
from datetime import timedelta
import mock

from google.appengine.ext import ndb

from analysis.culprit import Culprit
from analysis.suspect import Suspect
from analysis.type_enums import CrashClient
from common import crash_pipeline
from common.appengine_testcase import AppengineTestCase
from common.predator_for_chromecrash import PredatorForFracas
from common.model.fracas_crash_analysis import FracasCrashAnalysis
from gae_libs.pipeline_wrapper import pipeline_handlers
from libs import analysis_status
from libs.gitiles.change_log import ChangeLog
from libs.gitiles.change_log import Contributor


class CrashAnalysisPipelineTest(AppengineTestCase):
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

  @mock.patch('analysis.predator.Predator._FindCulprit')
  def testFindCulpritFails(self, mock_find_culprit):
    crash_identifiers = self.GetDummyChromeCrashData()['crash_identifiers']
    analysis = FracasCrashAnalysis.Create(crash_identifiers)
    analysis.status = analysis_status.RUNNING
    analysis.put()

    mock_find_culprit.side_effect = Exception()
    pipeline = crash_pipeline.CrashAnalysisPipeline(
        CrashClient.FRACAS,
        crash_identifiers)
    pipeline.run()

    analysis = FracasCrashAnalysis.Get(crash_identifiers)
    self.assertEqual(analysis_status.ERROR, analysis.status)
    self.assertFalse(analysis.result['found'])
    self.assertFalse(analysis.found_suspects)
    self.assertFalse(analysis.found_project)
    self.assertFalse(analysis.found_components)

  @mock.patch('common.predator_for_chromecrash.PredatorForFracas.FindCulprit')
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
        suspected_cls = [dummy_suspect],
        # N.B., we must use a list here for the assertion to work
        # TODO(wrengr): fix that.
        regression_range = ['VERSION_0', 'VERSION_1'],
        algorithm = 'ALGORITHM',
    )
    mock_find_culprit.return_value = True, dummy_culprit
    pipeline = crash_pipeline.CrashAnalysisPipeline(CrashClient.FRACAS,
                                                    crash_identifiers)
    pipeline.start()
    self.execute_queued_tasks()

    analysis = FracasCrashAnalysis.Get(crash_identifiers)
    self.assertEqual(analysis_status.COMPLETED, analysis.status)
    self.assertTrue(analysis.result['found'])
    self.assertTrue(analysis.found_suspects)
    self.assertTrue(analysis.found_project)
    self.assertTrue(analysis.found_components)
    dummy_suspect, dummy_tags = dummy_culprit.ToDicts()
    self.assertDictEqual(analysis.result, dummy_suspect)


class CrashWrapperPipelineTest(AppengineTestCase):
  app_module = pipeline_handlers._APP

  def testPipelineRun(self):
    """Tests ``CrashWrapperPipeline`` runs as expected."""
    client = CrashClient.FRACAS
    crash_identifiers = {'sig': 'signature'}
    self.MockPipeline(crash_pipeline.CrashAnalysisPipeline, None,
                      [client, crash_identifiers])
    self.MockPipeline(crash_pipeline.PublishResultPipeline, None,
                      [client, crash_identifiers])
    pipeline = crash_pipeline.CrashWrapperPipeline(client, crash_identifiers)
    pipeline.start()
    self.execute_queued_tasks()


class RerunPipelineTest(AppengineTestCase):
  app_module = pipeline_handlers._APP

  def setUp(self):
    super(RerunPipelineTest, self).setUp()
    self.crash_analyses = [FracasCrashAnalysis.Create({'signature': 'sig1'}),
                           FracasCrashAnalysis.Create({'signature': 'sig2'}),
                           FracasCrashAnalysis.Create({'signature': 'sig3'})]
    self.crash_analyses[0].requested_time = datetime(2017, 6, 1, 2, 0, 0)
    self.crash_analyses[1].requested_time = datetime(2017, 6, 5, 9, 0, 0)
    self.crash_analyses[2].requested_time = datetime(2017, 6, 10, 3, 0, 0)

    self.crash_analyses[0].identifiers = 'sig1'
    self.crash_analyses[1].identifiers = 'sig2'
    self.crash_analyses[2].identifiers = 'sig3'

    ndb.put_multi(self.crash_analyses)

  @mock.patch('common.model.fracas_crash_analysis.'
              'FracasCrashAnalysis.ReInitialize')
  @mock.patch('common.crash_pipeline.PredatorForClientID')
  def testPipelineRunNotPublish(self, mock_predator_for_client,
                                mock_reinitialize):
    """Test ``RerunPipeline`` runs as expected."""
    client = CrashClient.FRACAS
    crash_keys = [self.crash_analyses[0].key.urlsafe()]
    self.MockPipeline(crash_pipeline.CrashAnalysisPipeline, None,
                      [client, self.crash_analyses[0].identifiers])
    pipeline = crash_pipeline.RerunPipeline(client, crash_keys,
                                            publish_to_client=False)
    pipeline.start()
    self.execute_queued_tasks()
    self.assertTrue(mock_predator_for_client.called)
    self.assertEqual(mock_reinitialize.call_count, 1)

  @mock.patch('common.model.fracas_crash_analysis.'
              'FracasCrashAnalysis.ReInitialize')
  @mock.patch('common.crash_pipeline.PredatorForClientID')
  def testPipelineRunPublish(self, mock_predator_for_client, mock_reinitialize):
    """Test ``RerunPipeline`` runs as expected."""
    client = CrashClient.FRACAS
    crash_keys = [self.crash_analyses[0].key.urlsafe()]
    self.MockPipeline(crash_pipeline.CrashWrapperPipeline, None,
                      [client, self.crash_analyses[0].identifiers])
    pipeline = crash_pipeline.RerunPipeline(client, crash_keys,
                                            publish_to_client=True)
    pipeline.start()
    self.execute_queued_tasks()
    self.assertTrue(mock_predator_for_client.called)
    self.assertEqual(mock_reinitialize.call_count, 1)
