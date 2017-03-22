# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from model.wf_step import WfStep


class WfStepTest(unittest.TestCase):

  def testStepName(self):
    step = WfStep.Create('m', 'b', 34, 's')
    self.assertEqual('s', step.step_name)
