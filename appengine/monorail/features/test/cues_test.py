# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittest for the cues module."""

import unittest

from features import cues
from services import service_manager
from testing import fake
from testing import testing_helpers


class CuesTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        user=fake.UserService())
    self.servlet = cues.SetCuesFeed('req', 'res', services=self.services)
    self.services.user.TestAddUser('a@example.com', 111L)

  def testHandleRequest(self):
    _request, mr = testing_helpers.GetRequestObjects(
        path='/hosting/cues?cue_id=42', user_info={'user_id': 111L})

    self.servlet.HandleRequest(mr)
    user = self.services.user.test_users[111L]
    self.assertTrue(user is not None)
    dismissed_cues = user.dismissed_cues
    self.assertTrue(dismissed_cues is not None)
    self.assertIn('42', dismissed_cues)
    self.assertNotIn('1492', dismissed_cues)


