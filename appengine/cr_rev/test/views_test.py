# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing
import app


class TestViews(testing.AppengineTestCase):
  app_module = app.app

  def test_main_page(self):
    """Test that the root page renders."""
    response = self.test_app.get('/')
    self.assertEquals('200 OK', response.status)

  def test_warmup(self):
    """Test that the warmup page renders."""
    response = self.test_app.get('/_ah/warmup')
    self.assertEquals('200 OK', response.status)
