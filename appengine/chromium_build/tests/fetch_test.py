#!/usr/bin/env python
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import app

from tests import cb


class FetchTestCase(cb.CbTestCase):
  class FakeResponse(object):
    status_code = 200
    content = None

  def test_fetch_direct(self):
    def fetch_url(url):
      fr = FetchTestCase.FakeResponse()
      if url == 'http://build.chromium.org/p/chromium/console':
        fr.content = self.read_file('in.html')
      return fr

    expected_content = self.read_file('exp.html')
    app.fetch_page(
        localpath='chromium/console',
        remoteurl='http://build.chromium.org/p/chromium/console',
        maxage=0,
        fetch_url=fetch_url)
    page = app.get_and_cache_pagedata('chromium/console')

    # Uncomment if deeper inspection is needed of the returned console.
    # This is also useful if changing the site layout and you need to
    # 'retrain' the test expectations.
    # self.write_file('exp.html', page['content'])

    self.assertEquals(expected_content, page['content'])

  def test_fetch_console(self):
    def fetch_url(url):
      fr = FetchTestCase.FakeResponse()
      if url == 'http://build.chromium.org/p/chromium/console':
        fr.content = self.read_file('in.html')
      return fr

    expected_content = self.read_file('exp.html')
    app.fetch_page(
        localpath='chromium/console',
        remoteurl='http://build.chromium.org/p/chromium/console',
        maxage=0,
        postfetch=app.console_handler,
        fetch_url=fetch_url)
    page = app.get_and_cache_pagedata('chromium/console')

    # Uncomment if deeper inspection is needed of the returned console.
    # This is also useful if changing the site layout and you need to
    # 'retrain' the test expectations.
    # self.write_file('exp.html', page['content'])

    self.assertEquals('interface', page['body_class'])
    self.assertEquals(expected_content, page['content'])
    self.assertEquals(
        'http://build.chromium.org/p/chromium/console/../',
        page['offsite_base'])
    self.assertEquals('BuildBot: Chromium', page['title'])
