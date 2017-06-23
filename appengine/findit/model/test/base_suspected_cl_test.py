# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from model.base_suspected_cl import BaseSuspectedCL
from model.base_suspected_cl import RevertCL


class BaseSuspectedCLTest(unittest.TestCase):

  def testProjectName(self):
    culprit = BaseSuspectedCL.Create('chromium', 'r1', 123)
    self.assertEqual('chromium', culprit.project_name)

  def testRevertCLUrl(self):
    culprit = BaseSuspectedCL.Create('chromium', 'r1', 123)
    revert_cl = RevertCL()
    revert_cl.revert_cl_url = 'review_url'
    culprit.revert_cl = revert_cl
    self.assertEqual('review_url', culprit.revert_cl_url)
