# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from common import acl
from common import constants


class AclTest(unittest.TestCase):

  def testAdminCanTriggerNewAnalysis(self):
    self.assertTrue(acl.CanTriggerNewAnalysis('test@chromium.org', True))

  def testGooglerCanTriggerNewAnalysis(self):
    self.assertTrue(acl.CanTriggerNewAnalysis('test@google.com', False))

  def testWhitelistedServiceAccountCanTriggerNewAnalysis(self):
    for email in constants.WHITELISTED_APP_ACCOUNTS:
      self.assertTrue(acl.CanTriggerNewAnalysis(email, False))
