# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the client config service."""

import unittest

from services import client_config_svc


class ClientConfigServiceTest(unittest.TestCase):

  def setUp(self):
    self.client_config_svc = client_config_svc.GetClientConfigSvc()
    self.client_email = '123456789@developer.gserviceaccount.com'
    self.client_id = '123456789.apps.googleusercontent.com'

  def testGetDisplayNames(self):
    display_names_map = self.client_config_svc.GetDisplayNames()
    self.assertIn(self.client_email, display_names_map)
    self.assertEquals('johndoe@example.com',
                      display_names_map[self.client_email])

  def testGetClientIDEmails(self):
    auth_client_ids, auth_emails = self.client_config_svc.GetClientIDEmails()
    self.assertIn(self.client_id, auth_client_ids)
    self.assertIn(self.client_email, auth_emails)
