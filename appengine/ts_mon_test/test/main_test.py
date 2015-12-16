# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import logging

from testing_utils import testing

import main


class IncrementHandlerTest(testing.AppengineTestCase):
  @property
  def app_module(self):
    return main.app

  def test_get(self):
    response = self.test_app.get('/inc?count=1')
    self.assertEquals(200, response.status_int)
