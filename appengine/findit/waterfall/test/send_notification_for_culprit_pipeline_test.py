# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from common.git_repository import GitRepository
from common.rietveld import Rietveld
from model import analysis_status as status
from model.wf_culprit import WfCulprit
from waterfall import send_notification_for_culprit_pipeline
from waterfall.send_notification_for_culprit_pipeline import (
    SendNotificationForCulpritPipeline)
from waterfall.test import wf_testcase


_MOCKED_DATETIME_UTCNOW = datetime.datetime(2016, 06, 28, 12, 44, 00)
_MOCKED_COMMIT_TIME = datetime.datetime(2016, 06, 28, 12, 40, 00)

class SendNotificationForCulpritPipelineTest(wf_testcase.WaterfallTestCase):

  def _MockRietveld(self, rietveld_requests):
    def Mocked_Rietveld_PostMessage(_, url, message):
      rietveld_requests.append((url, message))
      return True
    self.mock(Rietveld, 'PostMessage', Mocked_Rietveld_PostMessage)

  def _MockGitRepository(self, mocked_url):
    def Mocked_GetChangeLog(*_):
      class MockedChangeLog(object):
        @property
        def code_review_url(self):
          return mocked_url
        @property
        def committer_time(self):
          return _MOCKED_COMMIT_TIME
      return MockedChangeLog()
    self.mock(GitRepository, 'GetChangeLog', Mocked_GetChangeLog)

  def _MockDatetimeUtcNow(self):
    class Mocked_Datetime(object):
      @staticmethod
      def utcnow():
        return _MOCKED_DATETIME_UTCNOW
    self.mock(send_notification_for_culprit_pipeline,
              'datetime', Mocked_Datetime)

  def testShouldNotSendNotificationForSingleFailedBuild(self):
    self.assertFalse(
        send_notification_for_culprit_pipeline._ShouldSendNotification(
            'm', 'b1', 1, 'chromium', 'r1', 2, False))
    culprit = WfCulprit.Get('chromium', 'r1')
    self.assertIsNotNone(culprit)
    self.assertEqual([['m', 'b1', 1]], culprit.builds)

  def testShouldNotSendNotificationForSameFailedBuild(self):
    self.assertFalse(
        send_notification_for_culprit_pipeline._ShouldSendNotification(
            'm', 'b2', 2, 'chromium', 'r2', 2, False))
    self.assertFalse(
        send_notification_for_culprit_pipeline._ShouldSendNotification(
            'm', 'b2', 2, 'chromium', 'r2', 2, False))
    culprit = WfCulprit.Get('chromium', 'r2')
    self.assertIsNotNone(culprit)
    self.assertEqual([['m', 'b2', 2]], culprit.builds)

  def testShouldSendNotificationForSecondFailedBuild(self):
    self.assertFalse(
        send_notification_for_culprit_pipeline._ShouldSendNotification(
            'm', 'b31', 31, 'chromium', 'r3', 2, False))
    self.assertTrue(
        send_notification_for_culprit_pipeline._ShouldSendNotification(
            'm', 'b32', 32, 'chromium', 'r3', 2, False))
    culprit = WfCulprit.Get('chromium', 'r3')
    self.assertIsNotNone(culprit)
    self.assertEqual(status.RUNNING, culprit.cr_notification_status)
    self.assertEqual([['m', 'b31', 31], ['m', 'b32', 32]], culprit.builds)

  def testShouldNotSendNotificationForFirstFailedBuildCycle(self):
    rietveld_requests = []
    self._MockRietveld(rietveld_requests)
    self._MockGitRepository('url')
    self._MockDatetimeUtcNow()

    pipeline = SendNotificationForCulpritPipeline()
    self.assertFalse(pipeline.run('m', 'b4', 4, 'chromium', 'r4'))
    self.assertEqual(0, len(rietveld_requests))

  def testShouldNotSendNotificationIfNoCodeReview(self):
    rietveld_requests = []
    self._MockRietveld(rietveld_requests)
    self._MockGitRepository(None)
    self._MockDatetimeUtcNow()
    culprit = WfCulprit.Create('chromium', 'r5')
    culprit.builds.append(['m', 'b51', 51])
    culprit.put()

    pipeline = SendNotificationForCulpritPipeline()
    self.assertFalse(pipeline.run('m', 'b52', 52, 'chromium', 'r5'))
    self.assertEqual(0, len(rietveld_requests))

  def testSendNotificationSuccess(self):
    rietveld_requests = []
    self._MockRietveld(rietveld_requests)
    self._MockGitRepository('url')
    self._MockDatetimeUtcNow()
    culprit = WfCulprit.Create('chromium', 'r6')
    culprit.builds.append(['m', 'b61', 61])
    culprit.put()

    pipeline = SendNotificationForCulpritPipeline()
    self.assertTrue(pipeline.run('m', 'b62', 62, 'chromium', 'r6'))
    self.assertEqual(1, len(rietveld_requests))
