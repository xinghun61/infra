# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import unittest

from common import acl
from common import constants


class AclTest(unittest.TestCase):
  def testAdminIsPrivilegedUser(self):
    self.assertTrue(acl.IsPrivilegedUser('test@chromium.org', True))

  def testGooglerIsPrivilegedUser(self):
    self.assertTrue(acl.IsPrivilegedUser('test@google.com', False))

  def testUnknownUserIsNotPrivilegedUser(self):
    self.assertFalse(acl.IsPrivilegedUser('test@gmail.com', False))

  def testAdminCanTriggerNewAnalysis(self):
    self.assertTrue(acl.CanTriggerNewAnalysis('test@chromium.org', True))

  def testGooglerCanTriggerNewAnalysis(self):
    self.assertTrue(acl.CanTriggerNewAnalysis('test@google.com', False))

  @mock.patch.object(acl.appengine_util, 'IsStaging', return_value=False)
  def testWhitelistedAppAccountCanTriggerNewAnalysis(self, _):
    for email in constants.WHITELISTED_APP_ACCOUNTS:
      self.assertTrue(acl.CanTriggerNewAnalysis(email, False))

  @mock.patch.object(acl.appengine_util, 'IsStaging', return_value=True)
  def testWhitelistedStagingAppAccountCanTriggerNewAnalysis(self, _):
    for email in constants.WHITELISTED_STAGING_APP_ACCOUNTS:
      self.assertTrue(acl.CanTriggerNewAnalysis(email, False))

  def testUnkownUserCanNotTriggerNewAnalysis(self):
    self.assertFalse(acl.CanTriggerNewAnalysis('test@gmail.com', False))
