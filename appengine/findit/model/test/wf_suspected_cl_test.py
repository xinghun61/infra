# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import textwrap
import unittest

from libs import analysis_status as status
from model.wf_suspected_cl import WfSuspectedCL


class WfSuspectedCLTest(unittest.TestCase):

  def testGetBuildInfo(self):
    repo_name = 'chromium'
    revision = 'rev1'
    commit_position = 1
    build = {'status': None}
    suspected_cl = WfSuspectedCL.Create(repo_name, revision, commit_position)
    suspected_cl.builds = {'m/b/123': build}
    self.assertEqual(build, suspected_cl.GetBuildInfo('m', 'b', 123))

  def testCrNotificationProcessed(self):
    culprit = WfSuspectedCL.Create('chromium', 'r1', 123)
    for s in (status.COMPLETED, status.RUNNING):
      culprit.cr_notification_status = s
      self.assertTrue(culprit.cr_notification_processed)
    for s in (status.ERROR, None):
      culprit.cr_notification_status = s
      self.assertFalse(culprit.cr_notification_processed)

  def testCrNotified(self):
    culprit = WfSuspectedCL.Create('chromium', 'r1', 123)
    culprit.cr_notification_status = status.COMPLETED
    self.assertTrue(culprit.cr_notified)

  def testGetCulpritLink(self):
    culprit = WfSuspectedCL.Create('chromium', 'r1', 123)
    self.assertEqual(
        'https://analysis.chromium.org/waterfall/culprit?key=%s' %
        culprit.key.urlsafe(), culprit.GetCulpritLink())

  def testGenerateRevertReason(self):
    culprit = WfSuspectedCL.Create('chromium', 'r1', 123)

    expected_reason = textwrap.dedent("""
          Findit (https://goo.gl/kROfz5) identified CL at revision %s as the
          culprit for failures in the build cycles as shown on:
          https://analysis.chromium.org/waterfall/culprit?key=%s\n
          Sample Failed Build: %s\n
          Sample Failed Step: %s""") % (
        123, culprit.key.urlsafe(), 'https://ci.chromium.org/buildbot/m/b/2',
        's')

    self.assertEqual(expected_reason,
                     culprit.GenerateRevertReason('m/b/2', 123, 'r123', 's'))
