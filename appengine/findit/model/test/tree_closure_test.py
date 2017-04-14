# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from model.tree_closure import TreeStatus


class TreeStatusTest(unittest.TestCase):

  def testClosedStatus(self):
    status = TreeStatus(state='closed')
    self.assertTrue(status.closed)

  def testOpenedStatus(self):
    status = TreeStatus(state='open')
    self.assertFalse(status.closed)

  def testAutomaticStatus(self):
    status = TreeStatus(username='buildbot@chromium.org')
    self.assertTrue(status.automatic)

  def testManualStatus(self):
    status = TreeStatus(username='test@chromium.org')
    self.assertFalse(status.automatic)
