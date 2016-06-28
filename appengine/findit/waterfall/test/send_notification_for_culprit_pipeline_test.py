# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.git_repository import GitRepository
from common.rietveld import Rietveld
from model import analysis_status as status
from model.wf_culprit import WfCulprit
from waterfall import send_notification_for_culprit_pipeline
from waterfall.send_notification_for_culprit_pipeline import (
    SendNotificationForCulpritPipeline)
from waterfall.test import wf_testcase


class SendNotificationForCulpritPipelineTest(wf_testcase.WaterfallTestCase):

  def _MockRietveldAndGitRepository(self, mocked_url, rietveld_requests):
    def Mocked_GetChangeLog(*_):
      class MockedChangeLog(object):
        @property
        def code_review_url(self):
          return mocked_url
      return MockedChangeLog()
    self.mock(GitRepository, 'GetChangeLog', Mocked_GetChangeLog)
    def Mocked_Rietveld_PostMessage(_, url, message):
      rietveld_requests.append((url, message))
      return True
    self.mock(Rietveld, 'PostMessage', Mocked_Rietveld_PostMessage)

  def testShouldNotSendNotificationForSingleFailedBuild(self):
    self.assertFalse(
        send_notification_for_culprit_pipeline._ShouldSendNotification(
            'm', 'b1', 1, 'chromium', 'r1'))
    culprit = WfCulprit.Get('chromium', 'r1')
    self.assertIsNotNone(culprit)
    self.assertEqual([['m', 'b1', 1]], culprit.builds)

  def testShouldNotSendNotificationForSameFailedBuild(self):
    self.assertFalse(
        send_notification_for_culprit_pipeline._ShouldSendNotification(
            'm', 'b2', 2, 'chromium', 'r2'))
    self.assertFalse(
        send_notification_for_culprit_pipeline._ShouldSendNotification(
            'm', 'b2', 2, 'chromium', 'r2'))
    culprit = WfCulprit.Get('chromium', 'r2')
    self.assertIsNotNone(culprit)
    self.assertEqual([['m', 'b2', 2]], culprit.builds)

  def testShouldSendNotificationForSecondFailedBuild(self):
    self.assertFalse(
        send_notification_for_culprit_pipeline._ShouldSendNotification(
            'm', 'b31', 31, 'chromium', 'r3'))
    self.assertTrue(
        send_notification_for_culprit_pipeline._ShouldSendNotification(
            'm', 'b32', 32, 'chromium', 'r3'))
    culprit = WfCulprit.Get('chromium', 'r3')
    self.assertIsNotNone(culprit)
    self.assertEqual(status.RUNNING, culprit.cr_notification_status)
    self.assertEqual([['m', 'b31', 31], ['m', 'b32', 32]], culprit.builds)

  def testShouldNotSendNotificationForFirstFailedBuildCycle(self):
    rietveld_requests = []
    self._MockRietveldAndGitRepository('url', rietveld_requests)

    pipeline = SendNotificationForCulpritPipeline()
    self.assertFalse(pipeline.run('m', 'b4', 4, 'chromium', 'r4'))
    self.assertEqual(0, len(rietveld_requests))

  def testShouldNotSendNotificationIfNoCodeReview(self):
    rietveld_requests = []
    self._MockRietveldAndGitRepository(None, rietveld_requests)
    culprit = WfCulprit.Create('chromium', 'r5')
    culprit.builds.append(['m', 'b51', 51])
    culprit.put()

    pipeline = SendNotificationForCulpritPipeline()
    self.assertFalse(pipeline.run('m', 'b52', 52, 'chromium', 'r5'))
    self.assertEqual(0, len(rietveld_requests))

  def testSendNotificationSuccess(self):
    rietveld_requests = []
    self._MockRietveldAndGitRepository('url', rietveld_requests)
    culprit = WfCulprit.Create('chromium', 'r6')
    culprit.builds.append(['m', 'b61', 61])
    culprit.put()

    pipeline = SendNotificationForCulpritPipeline()
    self.assertTrue(pipeline.run('m', 'b62', 62, 'chromium', 'r6'))
    self.assertEqual(1, len(rietveld_requests))
