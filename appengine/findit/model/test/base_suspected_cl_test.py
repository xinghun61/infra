# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from libs import analysis_status
from model.base_suspected_cl import BaseSuspectedCL
from model.base_suspected_cl import RevertCL
from waterfall.test import wf_testcase


class BaseSuspectedCLTest(wf_testcase.WaterfallTestCase):

  def testProjectName(self):
    culprit = BaseSuspectedCL.Create('chromium', 'r1', 123)
    self.assertEqual('chromium', culprit.project_name)

  def testRevertCLUrl(self):
    culprit = BaseSuspectedCL.Create('chromium', 'r1', 123)
    revert_cl = RevertCL()
    revert_cl.revert_cl_url = 'review_url'
    culprit.revert_cl = revert_cl
    self.assertEqual('review_url', culprit.revert_cl_url)

  def testCrNotificationStatusRunning(self):
    culprit = BaseSuspectedCL.Create('repo', 'revision', 123)
    culprit.cr_notification_status = analysis_status.RUNNING
    self.assertTrue(culprit.cr_notification_processed)

  def testCrNotificationStatusNotSet(self):
    culprit = BaseSuspectedCL.Create('repo', 'revision', 123)
    self.assertFalse(culprit.cr_notification_processed)

  def testCrNotificationStatus(self):
    culprit = BaseSuspectedCL.Create('repo', 'revision', 123)
    culprit.cr_notification_status = analysis_status.COMPLETED
    self.assertTrue(culprit.cr_notified)
