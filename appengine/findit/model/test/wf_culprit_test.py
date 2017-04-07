# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from libs import analysis_status as status
from model.wf_culprit import WfCulprit


class WfCulpritTest(unittest.TestCase):
  def testCrNotificationProcessed(self):
    culprit = WfCulprit.Create('chromium', 'r1', 123)
    for s in (status.COMPLETED, status.RUNNING):
      culprit.cr_notification_status = s
      self.assertTrue(culprit.cr_notification_processed)
    for s in (status.ERROR, None):
      culprit.cr_notification_status = s
      self.assertFalse(culprit.cr_notification_processed)

  def testCrNotified(self):
    culprit = WfCulprit.Create('chromium', 'r1', 123)
    culprit.cr_notification_status = status.COMPLETED
    self.assertTrue(culprit.cr_notified)
