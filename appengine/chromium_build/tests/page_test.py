#!/usr/bin/env python
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

import app

from tests import cb


class PageTestCase(cb.CbTestCase):
  def test_creation(self):
    fetch_timestamp = datetime.datetime.now()
    localpath = 'test'  # The app prepends /p/.
    content = 'Test.'
    model = app.Page(fetch_timestamp=fetch_timestamp,
                     localpath=localpath, content=content)
    model.put()
    fetched_model = app.Page.all().filter('localpath =', localpath).fetch(1)[0]
    self.assertEquals(fetched_model.content, content)
