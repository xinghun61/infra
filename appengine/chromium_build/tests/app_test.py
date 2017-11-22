#!/usr/bin/env python
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from tests import cb


class AppTestCase(cb.CbTestCase):
  def test_app_main(self):
    localpath = 'test'  # The app prepends /p/.
    content = 'Test.'
    self.save_page(localpath=localpath, content=content)
    response = self.test_app.get('/p/test')
    self.assertEquals('200 OK', response.status)
    self.assertEquals('Test.', response.body)

  def test_app_blob(self):
    localpath = 'testfoo'  # The app prepends /p/.
    content = 'a' * 10**6  # ~1MB of a single character (ASCII).
    self.save_page(localpath=localpath, content=content)
    response = self.test_app.get('/p/testfoo')
    self.assertEquals('200 OK', response.status)
    self.assertEquals(content, response.body)

  def test_app_unicode(self):
    localpath = 'testfoo'  # The app prepends /p/.
    content = u'\ua000'  # A single character Unicode character.
    self.save_page(localpath=localpath, content=content)
    response = self.test_app.get('/p/testfoo')
    self.assertEquals('200 OK', response.status)
    # u'\ua000'.encode('utf-8') == '\xea\x80\x80'
    self.assertEquals('\xea\x80\x80', response.body)

  def test_app_unicode_blob(self):
    times = 2 * 10**6  # ~2 MB worth.
    localpath = 'testfoo'  # The app prepends /p/.
    content = u'\ua000' * times  # Lots of a single Unicode character.
    self.save_page(localpath=localpath, content=content)
    response = self.test_app.get('/p/testfoo')
    self.assertEquals('200 OK', response.status)
    # u'\ua000'.encode('utf-8') == '\xea\x80\x80'
    self.assertEquals('\xea\x80\x80' * times, response.body)

  def test_app_cp1252(self):
    localpath = 'testfoo'  # The app prepends /p/.
    content = '\xe2'
    self.save_page(localpath=localpath, content=content)
    response = self.test_app.get('/p/testfoo')
    self.assertEquals('200 OK', response.status)
    # '\xe2'.decode('utf-8', 'replace').encode('utf-8') == '\xef\xbf\xbd'
    self.assertEquals('\xef\xbf\xbd', response.body)

  def test_app_cp1252_blob(self):
    times = 2 * 10**6  # ~2 MB worth.
    localpath = 'testfoo'  # The app prepends /p/.
    content = '\xe2' * times
    self.save_page(localpath=localpath, content=content)
    response = self.test_app.get('/p/testfoo')
    self.assertEquals('200 OK', response.status)
    # Note that content is not equal to '\xef\xbf\xbd'*times.
    self.assertEquals(content.decode('utf-8', 'replace').encode('utf-8'),
                      response.body)
