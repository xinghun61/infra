# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for user_pb2 functions."""

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from proto import user_pb2


class UserPb2Test(unittest.TestCase):

  def testUser_Defaults(self):
    user = user_pb2.MakeUser(111)
    self.assertEqual(111, user.user_id)
    self.assertFalse(user.obscure_email)
    self.assertIsNone(user.email)

  def testUser_Everything(self):
    user = user_pb2.MakeUser(111, email='user@example.com', obscure_email=True)
    self.assertEqual(111, user.user_id)
    self.assertTrue(user.obscure_email)
    self.assertEqual('user@example.com', user.email)
