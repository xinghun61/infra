# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from tests.testing_utils import testing

import highend


class TestLogin(testing.AppengineTestCase):
  app_module = highend.app

  def test_login(self):
    response = self.test_app.get('/login')
    self.assertEquals(302, response.status_code)
    self.assertEquals(
        ('https://www.google.com/accounts/Login?' +
         'continue=http%3A//testbed.example.com/'),
        response.location)
