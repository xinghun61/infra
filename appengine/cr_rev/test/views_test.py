# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from appengine.utils import testing_support
from appengine.cr_rev import app


class TestViews(testing_support.AppengineTestCase):
  app_module = app.app

  def test_main_page(self):
    """Test that the root page renders."""
    response = self.testapp.get('/')
    self.assertEquals('200 OK', response.status)

  def test_warmup(self):
    """Test that the warmup page renders."""
    response = self.testapp.get('/_ah/warmup')
    self.assertEquals('200 OK', response.status)
