# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import json
import logging
import mock

from google.appengine.api import app_identity

from analysis import log_util
from analysis.type_enums import CrashClient
from common.appengine_testcase import AppengineTestCase
from common.model.crash_analysis import CrashAnalysis
from libs import analysis_status


class PredatorTest(AppengineTestCase):

  def setUp(self):
    super(PredatorTest, self).setUp()
    self.predator = self.GetMockPredatorApp()

  def testClientConfig(self):
    """Tests ``client_config`` property."""
    config = {'config': 'dummy'}
    with mock.patch(
        'common.model.crash_config.CrashConfig.GetClientConfig') as get_config:
      get_config.side_effect = lambda client_id: config
      self.assertDictEqual(self.predator.client_config, config)

  def testCheckPolicyNoneClientConfig(self):
    unsupported_client = self.GetMockPredatorApp(client_id='unconfiged')
    crash_data = unsupported_client.GetCrashData(
        self.GetDummyChromeCrashData(
            platform = 'canary',
            signature = 'sig',
        ))
    self.assertTrue(unsupported_client._CheckPolicy(crash_data))

  def testCheckPolicyNoBlackList(self):
    """Tests ``_CheckPolicy`` method with no black list configured."""
    crash_data = self.predator.GetCrashData(self.GetDummyChromeCrashData())
    self.assertTrue(self.predator._CheckPolicy(crash_data))

  def testCheckPolicyWithBlackList(self):
    """Tests ``_CheckPolicy`` return false if signature is blacklisted."""
    crash_data = self.predator.GetCrashData(self.GetDummyChromeCrashData(
        client_id=CrashClient.FRACAS,
        signature='Blacklist marker signature'))
    self.assertFalse(self.predator._CheckPolicy(crash_data))

  def testDoesNotNeedNewAnalysisIfCheckPolicyFailed(self):
    """Tests that ``NeedsNewAnalysis`` returns False if policy check failed."""
    raw_crash_data = self.GetDummyChromeCrashData(
        client_id=self.predator.client_id,
        signature='Blacklist marker signature')
    crash_data = self.predator.GetCrashData(raw_crash_data)
    self.assertFalse(self.predator.NeedsNewAnalysis(crash_data))

  def testNeedNewAnalysisRedoIfNoAnalysisYet(self):
    """Tests that ``NeedsNewAnalysis`` returns True if crash is a redo."""
    raw_crash_data = self.GetDummyClusterfuzzData(redo=True)
    crash_data = self.predator.GetCrashData(raw_crash_data)
    self.assertTrue(self.predator.NeedsNewAnalysis(crash_data))

  @mock.patch('common.model.crash_analysis.CrashAnalysis.Initialize')
  def testNeedNewAnalysisRedoAnAnalyzedCrash(self, initialize):
    """Tests that ``NeedsNewAnalysis`` returns True for an analyzed crash."""
    initialize.return_value = None
    raw_crash_data = self.GetDummyClusterfuzzData(redo=True)
    crash_data = self.predator.GetCrashData(raw_crash_data)
    crash_model = self.predator.CreateAnalysis(crash_data.identifiers)
    crash_model.status = analysis_status.COMPLETED
    crash_model.put()
    self.assertTrue(self.predator.NeedsNewAnalysis(crash_data))

  def testDoesNotNeedNewAnalysisIfCrashAnalyzedBefore(self):
    """Tests that ``NeedsNewAnalysis`` returns False if crash analyzed."""
    crash_data = self.predator.GetCrashData(self.GetDummyChromeCrashData())
    crash_analysis_model = self.predator.CreateAnalysis(crash_data.identifiers)
    crash_analysis_model.regression_range = crash_data.regression_range
    crash_analysis_model.put()
    self.assertFalse(self.predator.NeedsNewAnalysis(crash_data))

  @mock.patch('common.model.crash_analysis.CrashAnalysis.Initialize')
  def testNeedsNewAnalysisIfNoAnalysisYet(self, mock_initialize):
    """Tests that ``NeedsNewAnalysis`` returns True if crash not analyzed."""
    crash_data = self.predator.GetCrashData(self.GetDummyChromeCrashData())
    mock_initialize.return_value = None
    self.assertTrue(self.predator.NeedsNewAnalysis(crash_data))

  @mock.patch('common.model.crash_analysis.CrashAnalysis.Initialize')
  def testNeedsNewAnalysisIfLastOneFailed(self, mock_initialize):
    """Tests that ``NeedsNewAnalysis`` returns True if last analysis failed."""
    crash_data = self.predator.GetCrashData(self.GetDummyChromeCrashData())
    crash_analysis_model = self.predator.CreateAnalysis(crash_data.identifiers)
    crash_analysis_model.status = analysis_status.ERROR
    crash_analysis_model.put()
    mock_initialize.return_value = None
    self.assertTrue(self.predator.NeedsNewAnalysis(crash_data))

  @mock.patch('common.predator_app.PredatorApp.PublishResultToClient')
  def testPublishResultDoNothingIfAnalysisFailed(self,
                                                 mock_publish_to_client):
    """Tests that ``PublishResult`` does nothing if analysis failed."""
    crash_identifiers = {
        'testcase_id':
        'predator_app_test_publish_result_do_nothing_if_analysis_failed'
    }
    analysis = self.predator.CreateAnalysis(crash_identifiers)
    analysis.identifiers = crash_identifiers
    analysis.result = None
    analysis.status = analysis_status.ERROR
    analysis.log.Reset()
    analysis.put()

    self.assertIsNone(self.predator.PublishResult(crash_identifiers))
    mock_publish_to_client.assert_not_called()

  def testResultMessageToClientFoundTrue(self):
    analysis_result = {
        'found': True,
        'suspected_cls': [
            {'confidence': 0.21434,
             'reasons': ['reason1', 'reason2'],
             'other': 'data'}
        ],
        'other_data': 'data',
    }

    crash_identifiers = {
        'testcase_id': 'predator_app_test_msg_to_client_found_true'
    }
    analysis = self.predator.CreateAnalysis(crash_identifiers)
    analysis.identifiers = crash_identifiers
    analysis.result = analysis_result
    analysis.status = analysis_status.COMPLETED
    analysis.log.Reset()
    analysis.put()

    processed_analysis_result = copy.deepcopy(analysis_result)
    for cl in processed_analysis_result['suspected_cls']:
      cl['confidence'] = round(cl['confidence'], 2)
    processed_analysis_result['feedback_url'] = analysis.feedback_url

    expected_processed_result = {
        'crash_identifiers': crash_identifiers,
        'client_id': self.predator.client_id,
        'result': processed_analysis_result,
    }
    self.assertDictEqual(self.predator.ResultMessageToClient(crash_identifiers),
                         expected_processed_result)

  def testResultMessageToClientFoundFalse(self):
    analysis_result = {
        'found': False,
        'log': 'Failed to parse stacktrace',
    }
    crash_identifiers = {
        'testcase_id': 'predator_app_test_msg_to_client_found_false'
    }
    analysis = self.predator.CreateAnalysis(crash_identifiers)
    analysis.identifiers = crash_identifiers
    analysis.result = analysis_result
    analysis.status = analysis_status.COMPLETED
    analysis.log.Reset()
    analysis.put()

    result = copy.deepcopy(analysis_result)
    result['feedback_url'] = analysis.feedback_url
    expected_processed_result = {
        'crash_identifiers': crash_identifiers,
        'client_id': self.predator.client_id,
        'result': result,
    }

    self.assertDictEqual(self.predator.ResultMessageToClient(crash_identifiers),
                         expected_processed_result)

  def testResultMessageToClientFailedToFinishAnalysis(self):
    crash_identifiers = {
        'testcase_id':
        'predator_app_test_msg_to_client_failed_to_finish_analysis'
    }
    analysis = self.predator.CreateAnalysis(crash_identifiers)
    analysis.identifiers = crash_identifiers
    analysis.status = analysis_status.PENDING
    analysis.log.Reset()
    analysis.put()

    result = {'found': False,
              'log': [{'level': 'error',
                       'name': 'UnknownError',
                       'message': ('Predator failed to catch the error message '
                                   'for %s' % repr(crash_identifiers))}]}
    result['feedback_url'] = analysis.feedback_url
    expected_processed_result = {
        'crash_identifiers': crash_identifiers,
        'client_id': self.predator.client_id,
        'result': result,
    }

    self.assertDictEqual(self.predator.ResultMessageToClient(crash_identifiers),
                         expected_processed_result)

  def testResultMessageToClientForNonSupportedAnalysis(self):
    crash_identifiers = {
        'testcase_id':
        'predator_app_test_msg_to_client_for_non_supported_analysis'
    }
    analysis = self.predator.CreateAnalysis(crash_identifiers)
    analysis.identifiers = crash_identifiers
    analysis.status = analysis_status.PENDING
    analysis.log.Reset()
    analysis.put()

    log_util.LogInfo(analysis.log, 'Unsupported',
                     'Predator doesn\'t support analysis.')

    result = {'found': False,
              'log': [{'level': 'info',
                       'name': 'Unsupported',
                       'message': 'Predator doesn\'t support analysis.'}]}
    result['feedback_url'] = analysis.feedback_url
    expected_processed_result = {
        'crash_identifiers': crash_identifiers,
        'client_id': self.predator.client_id,
        'result': result,
    }

    self.assertDictEqual(self.predator.ResultMessageToClient(crash_identifiers),
                         expected_processed_result)

  @mock.patch('gae_libs.pubsub_util.PublishMessagesToTopic')
  @mock.patch('common.predator_app.PredatorApp.ResultMessageToClient')
  def testPublishResultToClient(self, message_to_client, publish_to_topic):
    """Tests ``PublishResultToClient`` publish successfully."""
    message = {'result': 'dummy'}
    message_to_client.return_value = message

    identifiers = {
        'testcase_id': 'predator_app_test_publish_result_to_client'
    }
    analysis = self.predator.CreateAnalysis(identifiers)
    analysis.identifiers = identifiers
    analysis.log.Reset()
    analysis.put()

    self.predator.PublishResult(identifiers)
    publish_to_topic.assert_called_with(
        [json.dumps(message)],
        self.predator.client_config['analysis_result_pubsub_topic'])

  def testResultMessageToClientWhenFailedToAnalysis(self):
    """Tests ``ResultMessageToClient`` when the analysis failed."""
    crash_identifiers = {
        'testcase_id':
        'predator_app_test_result_msg_to_client_when_failed_to_analysis'
    }
    analysis = self.predator.CreateAnalysis(crash_identifiers)
    analysis.identifiers = crash_identifiers
    analysis.status = analysis_status.ERROR
    analysis.result = {'found': False,
                       'log': 'Failed to parse stacktrace.'}
    analysis.log.Reset()
    analysis.put()

    processed_analysis_result = {'found': False,
                                 'log': 'Failed to parse stacktrace.'}
    processed_analysis_result['feedback_url'] = analysis.feedback_url

    expected_processed_result = {
        'crash_identifiers': crash_identifiers,
        'client_id': self.predator.client_id,
        'result': processed_analysis_result,
    }

    self.assertDictEqual(self.predator.ResultMessageToClient(crash_identifiers),
                         expected_processed_result)

  @mock.patch('common.appengine_testcase.MockCrashAnalysis.ToCrashReport')
  @mock.patch('analysis.predator.Predator.FindCulprit')
  def testFindCulprit(self, mock_find_culprit, mock_to_crash_report):
    """Tests ``FindCulprit`` called ``FindCulprit`` in ``Predator`` class."""
    crash_identifiers = {
        'testcase_id':
        'predator_app_test_find_culprit'
    }
    predator = self.GetMockPredatorApp()
    analysis = predator.CreateAnalysis(crash_identifiers)
    analysis.identifiers = crash_identifiers
    analysis.status = analysis_status.COMPLETED
    analysis.put()

    predator.FindCulprit(crash_identifiers)
    self.assertTrue(mock_to_crash_report.called)
    self.assertTrue(mock_find_culprit.called)
