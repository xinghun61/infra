# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# test_env should be loaded before any other app module.
from . import test_env

from testing_utils import testing
import frontend


class TestFrontendHandlers(testing.AppengineTestCase):
  @property
  def app_module(self):
    return frontend.create_html_app()

  def test_main_page(self):
    """Test that the root page renders."""
    response = self.test_app.get('/')
    self.assertEquals(302, response.status_int)

  def test_warmup(self):
    """Test that warmup works."""
    response = self.test_app.get('/_ah/warmup')
    self.assertEquals(200, response.status_int)
