# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import mock

from analysis import chromecrash_parser
from analysis import detect_regression_range
from analysis.clusterfuzz_parser import ClusterfuzzParser
from analysis.crash_report import CrashReport
from analysis.type_enums import CrashClient
from common import predator_app
from common import predator_for_chromecrash
from common.appengine_testcase import AppengineTestCase
from common.predator_for_clusterfuzz import PredatorForClusterfuzz
from common.model.crash_analysis import CrashAnalysis
from common.model.crash_config import CrashConfig
from common.model.fracas_crash_analysis import FracasCrashAnalysis
from gae_libs.http.http_client_appengine import HttpClientAppengine
from libs import analysis_status
from libs.deps import chrome_dependency_fetcher
from libs.deps.dependency import DependencyRoll
from libs.gitiles.gitiles_repository import GitilesRepository


class PredatorForClusterfuzzTest(AppengineTestCase):

  def setUp(self):
    super(PredatorForClusterfuzzTest, self).setUp()
    self._client = PredatorForClusterfuzz(self.GetMockRepoFactory(),
                                          CrashConfig.Get())

  def testCheckPolicy(self):
    crash_data = self._client.GetCrashData(self.GetDummyClusterfuzzData(
        client_id = CrashClient.CLUSTERFUZZ))
    self.assertTrue(self._client._CheckPolicy(crash_data))

  def testCreateAnalysis(self):
    self.assertIsNotNone(self._client.CreateAnalysis({'testcase': '341335434'}))

  def testGetAnalysis(self):
    crash_identifiers = {'testcase': '341335434'}
    analysis = self._client.CreateAnalysis(crash_identifiers)
    analysis.put()
    self.assertEqual(self._client.GetAnalysis(crash_identifiers), analysis)

  @mock.patch('common.predator_for_clusterfuzz.PredatorForClusterfuzz.'
              'PublishResultToTryBot')
  @mock.patch('common.predator_app.PredatorApp.PublishResultToClient')
  def testPublishResultDoNothingIfAnalysisFailed(self,
                                                 mock_publish_to_client,
                                                 mock_publish_to_try_bot):
    """Tests that ``PublishResult`` does nothing if analysis failed."""
    crash_identifiers = {'signature': 'sig'}
    analysis = self._client.CreateAnalysis(crash_identifiers)
    analysis.identifiers = crash_identifiers
    analysis.result = None
    analysis.status = analysis_status.ERROR
    analysis.put()

    self.assertIsNone(self._client.PublishResult(crash_identifiers))
    mock_publish_to_client.assert_not_called()
    mock_publish_to_try_bot.assert_not_called()

  @mock.patch('common.predator_for_clusterfuzz.PredatorForClusterfuzz.'
              'PublishResultToTryBot')
  @mock.patch('common.predator_app.PredatorApp.PublishResultToClient')
  def testPublishResultDoNothingIfTestcasePlatformIsNotLinux(
      self, mock_publish_to_client, mock_publish_to_try_bot):
    """Tests ``PublishResult`` does nothing if the platform is not supported."""
    identifiers = {'testcase': '1234'}
    analysis = self._client.CreateAnalysis(identifiers)
    analysis.result = {'found': False}
    analysis.status = analysis_status.COMPLETED
    analysis.platform = 'win'
    analysis.put()

    self.assertIsNone(self._client.PublishResult(identifiers))
    mock_publish_to_client.assert_called_with(analysis)
    mock_publish_to_try_bot.assert_not_called()

  @mock.patch('libs.gitiles.gitiles_repository.GitilesRepository.'
              'GetCommitsBetweenRevisions')
  def testMessageToTryBotIfThereAreSuspects(self, get_commits):
    """Tests ``MessgeToTryBot`` format if analysis succeeded."""
    analysis_result = {
        'found': True,
        'suspected_cls': [
            {'confidence': 0.21434,
             'reasons': ['reason1', 'reason2'],
             'other': 'data'}
        ],
        'other_data': 'data',
    }
    identifiers = {'testcase': '1234'}
    analysis = self._client.CreateAnalysis(identifiers)
    analysis.testcase = '1234'
    analysis.dependency_rolls = {'src/': DependencyRoll('src/', 'https://repo',
                                                        'old_rev', 'new_rev')}
    analysis.platform = 'linux'
    analysis.result = analysis_result
    analysis.status = analysis_status.COMPLETED
    analysis.put()

    commits = ['git_hash1', 'git_hash2']
    get_commits.return_value = commits
    feedback_url = 'https://feedback'

    expected_message = {
        'regression_ranges': [{'path': 'src/', 'repo_url': 'https://repo',
                               'old_revision': 'old_rev',
                               'new_revision': 'new_rev', 'commits': commits}],
        'testcase_id': analysis.testcase,
        'suspected_cls': analysis_result['suspected_cls'],
        'feedback_url': feedback_url,
    }
    with mock.patch('common.model.crash_analysis.CrashAnalysis.feedback_url',
                    new_callable=mock.PropertyMock) as mock_feedback:
      mock_feedback.return_value = feedback_url
      self.assertDictEqual(self._client.MessageToTryBot(analysis),
                           expected_message)

  @mock.patch('libs.gitiles.gitiles_repository.GitilesRepository.'
              'GetCommitsBetweenRevisions')
  def testMessageToTryBotIfThereIsNoSuspect(self, get_commits):
    """Tests ``MessgeToTryBot`` format if analysis succeeded."""
    analysis_result = {
        'found': False,
        'other_data': 'data',
    }
    identifiers = {'testcase': '1234'}
    analysis = self._client.CreateAnalysis(identifiers)
    analysis.testcase = '1234'
    analysis.dependency_rolls = {'src/': DependencyRoll('src/', 'https://repo',
                                                        'old_rev', 'new_rev')}
    analysis.platform = 'linux'
    analysis.result = analysis_result
    analysis.status = analysis_status.COMPLETED
    analysis.put()

    commits = ['git_hash1', 'git_hash2']
    get_commits.return_value = commits
    feedback_url = 'https://feedback'

    expected_message = {
        'regression_ranges': [{'path': 'src/', 'repo_url': 'https://repo',
                               'old_revision': 'old_rev',
                               'new_revision': 'new_rev', 'commits': commits}],
        'testcase_id': analysis.testcase,
        'feedback_url': feedback_url,
    }

    with mock.patch('common.model.crash_analysis.CrashAnalysis.feedback_url',
                    new_callable=mock.PropertyMock) as mock_feedback:
      mock_feedback.return_value = feedback_url
      self.assertDictEqual(self._client.MessageToTryBot(analysis),
                           expected_message)

  @mock.patch('gae_libs.pubsub_util.PublishMessagesToTopic')
  @mock.patch('common.predator_for_clusterfuzz.PredatorForClusterfuzz.'
              'MessageToTryBot')
  def testPublishResultToTryBot(self, message_to_try_bot, publish_message):
    """Tests ``PublishResultToTryBot`` publish message to try bot."""
    message = 'blabla'
    message_to_try_bot.return_value = message
    analysis = self._client.CreateAnalysis({'signature': 'sig'})
    self._client.PublishResultToTryBot(analysis)
    publish_message.assert_called_with(
        [json.dumps(message)], self._client.client_config['try_bot_topic'])

  @mock.patch('common.predator_for_clusterfuzz.PredatorForClusterfuzz.'
              'PublishResultToTryBot')
  @mock.patch('common.predator_for_clusterfuzz.PredatorForClusterfuzz.'
              'PublishResultToClient')
  def testPublishResult(self, publish_to_client, publish_to_try_bot):
    """Tests ``PublishResult`` publish message to all topics."""
    identifiers = {'signature': 'sig'}
    analysis = self._client.CreateAnalysis(identifiers)
    analysis.platform = 'linux'
    analysis.put()
    self._client.PublishResult(identifiers)
    publish_to_client.assert_called_with(analysis)
    publish_to_try_bot.assert_called_with(analysis)
