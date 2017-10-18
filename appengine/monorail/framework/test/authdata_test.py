# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for the authdata module."""

import unittest

import mox


class AuthDataTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()

  def tearDown(self):
    self.mox.UnsetStubs()

  def testGetUserID(self):
    pass  # TODO(jrobbins): re-impement

  def testExamineRequestUserID(self):
    pass  # TODO(jrobbins): re-implement


