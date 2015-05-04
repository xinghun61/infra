# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for regular (non-endpoints) WSGI app, mostly for code coverage."""

import main

from components import auth_testing
from testing_utils import testing


class TestMainHandlers(testing.AppengineTestCase):
  @property
  def app_module(self):
    return main.create_html_app()

  def test_main_page(self):
    response = self.test_app.get('/')
    self.assertEquals(302, response.status_int)
