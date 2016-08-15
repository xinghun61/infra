# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from model.wf_suspected_cl import WfSuspectedCL


class WfSuspectedCLTest(unittest.TestCase):
  def testProjectName(self):
    culprit = WfSuspectedCL.Create('chromium', 'r1', 123)
    self.assertEqual('chromium', culprit.project_name)
