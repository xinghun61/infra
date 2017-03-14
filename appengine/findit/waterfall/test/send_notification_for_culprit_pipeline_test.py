# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from infra_api_clients.codereview.rietveld import Rietveld
from libs.gitiles.gitiles_repository import GitilesRepository
from model import analysis_status as status
from model.wf_culprit import WfCulprit
from waterfall import build_util
from waterfall import send_notification_for_culprit_pipeline
from waterfall.send_notification_for_culprit_pipeline import (
    SendNotificationForCulpritPipeline)
from waterfall.test import wf_testcase


_MOCKED_DATETIME_UTCNOW = datetime.datetime(2016, 06, 28, 12, 44, 00)
_MOCKED_BUILD_END_TIME = datetime.datetime(2016, 06, 28, 12, 40, 00)

class SendNotificationForCulpritPipelineTest(wf_testcase.WaterfallTestCase):

  def _MockRietveld(self, requests):
    def Mocked_Rietveld_PostMessage(_, change_id, message):
      requests.append((change_id, message))
      return True
    self.mock(Rietveld, 'PostMessage', Mocked_Rietveld_PostMessage)

  def _MockGitRepository(self, mocked_url):
    def Mocked_GetChangeLog(*_):
      class MockedChangeLog(object):
        @property
        def code_review_url(self):
          return mocked_url

        @property
        def commit_position(self):
          return 123

      return MockedChangeLog()
    self.mock(GitilesRepository, 'GetChangeLog', Mocked_GetChangeLog)

  def _MockBuildEndTime(self):
    def Mocked_GetBuildEndTime(*_):
      return _MOCKED_BUILD_END_TIME
    self.mock(build_util, 'GetBuildEndTime', Mocked_GetBuildEndTime)

  def testShouldNotSendNotificationForSingleFailedBuild(self):
    additional_criteria = {
        'within_time_limit': True
    }
    self.assertFalse(
        send_notification_for_culprit_pipeline._ShouldSendNotification(
            'm', 'b1', 1, 'chromium', 'r1', 123, 2, additional_criteria, False))
    culprit = WfCulprit.Get('chromium', 'r1')
    self.assertIsNotNone(culprit)
    self.assertEqual([['m', 'b1', 1]], culprit.builds)

  def testShouldNotSendNotificationForSameFailedBuild(self):
    additional_criteria = {
        'within_time_limit': True
    }
    self.assertTrue(
        send_notification_for_culprit_pipeline._ShouldSendNotification(
            'm', 'b2', 2, 'chromium', 'r2', 123, 2, additional_criteria, True))
    self.assertFalse(
        send_notification_for_culprit_pipeline._ShouldSendNotification(
            'm', 'b2', 2, 'chromium', 'r2', 123, 2, additional_criteria, True))
    culprit = WfCulprit.Get('chromium', 'r2')
    self.assertIsNotNone(culprit)
    self.assertEqual([['m', 'b2', 2]], culprit.builds)
    self.assertEqual(status.RUNNING, culprit.cr_notification_status)

  def testShouldSendNotificationForSecondFailedBuild(self):
    additional_criteria = {
      'within_time_limit': True
    }
    self.assertFalse(
        send_notification_for_culprit_pipeline._ShouldSendNotification(
            'm', 'b31', 31, 'chromium', 'r3', 123, 2, additional_criteria,
            False))
    self.assertTrue(
        send_notification_for_culprit_pipeline._ShouldSendNotification(
            'm', 'b32', 32, 'chromium', 'r3', 123, 2, additional_criteria,
            False))
    culprit = WfCulprit.Get('chromium', 'r3')
    self.assertIsNotNone(culprit)
    self.assertEqual(status.RUNNING, culprit.cr_notification_status)
    self.assertEqual([['m', 'b31', 31], ['m', 'b32', 32]], culprit.builds)

  def testShouldNotSendNotificationIfTimePassed(self):
    additional_criteria = {
        'within_time_limit': False
    }
    self.assertFalse(
      send_notification_for_culprit_pipeline._ShouldSendNotification(
        'm', 'b2', 2, 'chromium', 'r2', 123, 2, additional_criteria, True))

  def testShouldNotSendNotificationIfNoCodeReview(self):
    rietveld_requests = []
    self._MockRietveld(rietveld_requests)
    self._MockGitRepository(None)
    self.MockUTCNow(_MOCKED_DATETIME_UTCNOW)
    self._MockBuildEndTime()
    culprit = WfCulprit.Create('chromium', 'r5', 123)
    culprit.builds.append(['m', 'b51', 51])
    culprit.put()

    pipeline = SendNotificationForCulpritPipeline()
    self.assertFalse(pipeline.run('m', 'b52', 52, 'chromium', 'r5', False))
    self.assertEqual(0, len(rietveld_requests))

  def testShouldNotSendNotificationIfUnknownReviewServer(self):
    rietveld_requests = []
    self._MockRietveld(rietveld_requests)
    self._MockGitRepository('https://unknown.codeReview.server/123')
    self.MockUTCNow(_MOCKED_DATETIME_UTCNOW)
    self._MockBuildEndTime()
    culprit = WfCulprit.Create('chromium', 'r5', 123)
    culprit.builds.append(['m', 'b51', 51])
    culprit.put()

    pipeline = SendNotificationForCulpritPipeline()
    self.assertFalse(pipeline.run('m', 'b52', 52, 'chromium', 'r5', False))
    self.assertEqual(0, len(rietveld_requests))

  def testSendNotificationSuccess(self):
    rietveld_requests = []
    self._MockRietveld(rietveld_requests)
    self._MockGitRepository('https://codereview.chromium.org/123')
    self.MockUTCNow(_MOCKED_DATETIME_UTCNOW)
    self._MockBuildEndTime()
    culprit = WfCulprit.Create('chromium', 'r6', 123)
    culprit.builds.append(['m', 'b61', 61])
    culprit.put()

    pipeline = SendNotificationForCulpritPipeline()
    self.assertTrue(pipeline.run('m', 'b62', 62, 'chromium', 'r6', False))
    self.assertEqual(1, len(rietveld_requests))

  def testDontSendNotificationIfShouldNot(self):
    rietveld_requests = []
    self._MockRietveld(rietveld_requests)
    self._MockGitRepository('https://codeReview.chromium.org/123')
    self.MockUTCNow(_MOCKED_DATETIME_UTCNOW)
    self._MockBuildEndTime()
    culprit = WfCulprit.Create('chromium', 'r7', 123)
    culprit.builds.append(['m', 'b71', 71])
    culprit.put()

    pipeline = SendNotificationForCulpritPipeline()
    self.assertFalse(pipeline.run('m', 'b71', 71, 'chromium', 'r7', False))
    self.assertEqual(0, len(rietveld_requests))
