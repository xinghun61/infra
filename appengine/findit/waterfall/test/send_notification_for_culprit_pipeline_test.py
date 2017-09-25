# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import urlparse

from infra_api_clients.codereview.rietveld import Rietveld
from libs import analysis_status as status
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from model.wf_suspected_cl import WfSuspectedCL
from services import revert
from waterfall import send_notification_for_culprit_pipeline
from waterfall.send_notification_for_culprit_pipeline import (
    SendNotificationForCulpritPipeline)
from waterfall.test import wf_testcase

_MOCKED_DATETIME_UTCNOW = datetime.datetime(2016, 06, 28, 12, 44, 00)


class SendNotificationForCulpritPipelineTest(wf_testcase.WaterfallTestCase):

  def _MockRietveld(self, requests):

    def Mocked_Rietveld_PostMessage(_, change_id, message, should_email):
      requests.append((change_id, message, should_email))
      return True

    self.mock(Rietveld, 'PostMessage', Mocked_Rietveld_PostMessage)

  def _MockGitRepository(self, mocked_url):

    def Mocked_GetChangeLog(*_):

      class MockedAuthor(object):
        name = 'author'

        def ToDict(self):
          return {'name': self.name}

      class MockedChangeLog(object):
        commit_position = 123
        change_id = '123'
        author = MockedAuthor()

        @property
        def code_review_url(self):
          return mocked_url

        @property
        def commit_position(self):
          return 123

        @property
        def review_server_host(self):
          return urlparse.urlparse(mocked_url).netloc if mocked_url else None

        @property
        def review_change_id(self):
          return (urlparse.urlparse(mocked_url).path.split('/')[-1]
                  if mocked_url else None)

      return MockedChangeLog()

    self.mock(CachedGitilesRepository, 'GetChangeLog', Mocked_GetChangeLog)

  def testShouldNotSendNotificationForSingleFailedBuild(self):
    culprit = WfSuspectedCL.Create('chromium', 'r1', 1)
    culprit.builds['m/b1/1'] = {}
    culprit.put()

    self.assertFalse(
        send_notification_for_culprit_pipeline._ShouldSendNotification(
            'chromium', 'r1', 2, False))
    self.assertFalse(culprit.cr_notification_processed)

  def testShouldNotSendNotificationForSameFailedBuild(self):
    culprit = WfSuspectedCL.Create('chromium', 'r2', 1)
    culprit.builds['m/b2/2'] = {}
    culprit.put()
    self.assertTrue(
        send_notification_for_culprit_pipeline._ShouldSendNotification(
            'chromium', 'r2', 2, True))
    self.assertFalse(
        send_notification_for_culprit_pipeline._ShouldSendNotification(
            'chromium', 'r2', 2, True))
    culprit = WfSuspectedCL.Get('chromium', 'r2')
    self.assertEqual(status.RUNNING, culprit.cr_notification_status)

  def testShouldSendNotificationForSecondFailedBuild(self):
    culprit = WfSuspectedCL.Create('chromium', 'r3', 1)
    culprit.builds['m/b31/31'] = {}
    culprit.put()
    self.assertFalse(
        send_notification_for_culprit_pipeline._ShouldSendNotification(
            'chromium', 'r3', 2, False))
    culprit = WfSuspectedCL.Get('chromium', 'r3')
    culprit.builds['m/b32/32'] = {}
    culprit.put()
    self.assertTrue(
        send_notification_for_culprit_pipeline._ShouldSendNotification(
            'chromium', 'r3', 2, False))
    culprit = WfSuspectedCL.Get('chromium', 'r3')
    self.assertEqual(status.RUNNING, culprit.cr_notification_status)

  def testShouldNotSendNotificationIfNoCodeReview(self):
    rietveld_requests = []
    self._MockRietveld(rietveld_requests)
    self._MockGitRepository(None)
    self.MockUTCNow(_MOCKED_DATETIME_UTCNOW)
    culprit = WfSuspectedCL.Create('chromium', 'r5', 123)
    culprit.builds['m/b51/51'] = {}
    culprit.builds['m/b52/52'] = {}
    culprit.put()

    pipeline = SendNotificationForCulpritPipeline()
    self.assertFalse(pipeline.run('m', 'b51', 51, 'chromium', 'r5', False))
    self.assertEqual(0, len(rietveld_requests))

  def testShouldNotSendNotificationIfUnknownReviewServer(self):
    rietveld_requests = []
    self._MockRietveld(rietveld_requests)
    self._MockGitRepository('https://unknown.codeReview.server/123')
    self.MockUTCNow(_MOCKED_DATETIME_UTCNOW)
    culprit = WfSuspectedCL.Create('chromium', 'r5', 123)
    culprit.builds['m/b51/51'] = {}
    culprit.builds['m/b52/52'] = {}
    culprit.put()

    pipeline = SendNotificationForCulpritPipeline()
    self.assertFalse(pipeline.run('m', 'b52', 52, 'chromium', 'r5', False))
    self.assertEqual(0, len(rietveld_requests))

  def testSendNotificationSuccess(self):
    rietveld_requests = []
    self._MockRietveld(rietveld_requests)
    self._MockGitRepository('https://codereview.chromium.org/123')
    self.MockUTCNow(_MOCKED_DATETIME_UTCNOW)
    culprit = WfSuspectedCL.Create('chromium', 'r6', 123)
    culprit.builds['m/b61/61'] = {}
    culprit.builds['m/b62/62'] = {}
    culprit.put()

    pipeline = SendNotificationForCulpritPipeline()
    self.assertTrue(pipeline.run('m', 'b61', 61, 'chromium', 'r6', False))
    self.assertEqual(1, len(rietveld_requests))

  def testDontSendNotificationIfShouldNot(self):
    rietveld_requests = []
    self._MockRietveld(rietveld_requests)
    self._MockGitRepository('https://codeReview.chromium.org/123')
    self.MockUTCNow(_MOCKED_DATETIME_UTCNOW)
    culprit = WfSuspectedCL.Create('chromium', 'r7', 123)
    culprit.builds['m/b71/71'] = {}
    culprit.put()

    pipeline = SendNotificationForCulpritPipeline()
    self.assertFalse(pipeline.run('m', 'b71', 71, 'chromium', 'r7', False))
    self.assertEqual(0, len(rietveld_requests))

  def testDontSendNotificationIfFinditRevertedCulprit(self):
    pipeline = SendNotificationForCulpritPipeline()
    self.assertFalse(
        pipeline.run('m', 'b71', 71, 'chromium', 'r7', False,
                     revert.CREATED_BY_FINDIT))

  def testSendConfirmMessage(self):
    rietveld_requests = []
    self._MockRietveld(rietveld_requests)
    self._MockGitRepository('https://codereview.chromium.org/123')
    self.MockUTCNow(_MOCKED_DATETIME_UTCNOW)
    culprit = WfSuspectedCL.Create('chromium', 'r6', 123)
    culprit.builds['m/b61/61'] = {}
    culprit.builds['m/b62/62'] = {}
    culprit.put()

    pipeline = SendNotificationForCulpritPipeline()
    self.assertTrue(
        pipeline.run('m', 'b61', 61, 'chromium', 'r6', False,
                     revert.CREATED_BY_SHERIFF))
    self.assertEqual(1, len(rietveld_requests))
