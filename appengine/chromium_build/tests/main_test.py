#!/usr/bin/env python
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from tests import cb


class MainTestCase(cb.CbTestCase):
  def test_main_page_redirect(self):
    response = self.test_app.get('/')
    self.assertEquals('302 Moved Temporarily', response.status)
    self.assertEquals('', response.body)
