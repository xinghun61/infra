# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the testing_helpers module."""

import unittest

from testing import testing_helpers


class TestingHelpersTest(unittest.TestCase):

  def testMakeMonorailRequest(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/foo?key1=2&key2=&key3')

    self.assertEqual(None, mr.GetIntParam('foo'))
    self.assertEqual(2, mr.GetIntParam('key1'))
    self.assertEqual(None, mr.GetIntParam('key2'))
    self.assertEqual(None, mr.GetIntParam('key3'))
    self.assertEqual(3, mr.GetIntParam('key2', default_value=3))
    self.assertEqual(3, mr.GetIntParam('foo', default_value=3))

  def testGetRequestObjectsBasics(self):
    request, mr = testing_helpers.GetRequestObjects(
        path='/foo/bar/wee?sna=foo',
        params={'ya': 'hoo'}, method='POST')

    # supplied as part of the url
    self.assertEqual('foo', mr.GetParam('sna'))

    # supplied as a param
    self.assertEqual('hoo', mr.GetParam('ya'))

    # default Host header
    self.assertEqual('127.0.0.1', request.host)

  def testGetRequestObjectsHeaders(self):
    # with some headers
    request, _mr = testing_helpers.GetRequestObjects(
        headers={'Accept-Language': 'en', 'Host': 'pickledsheep.com'},
        path='/foo/bar/wee?sna=foo')

    # default Host header
    self.assertEqual('pickledsheep.com', request.host)

    # user specified headers
    self.assertEqual('en', request.headers['Accept-Language'])

  def testGetRequestObjectsUserInfo(self):
    user_id = '123'

    _request, mr = testing_helpers.GetRequestObjects(
        user_info={'user_id': user_id})

    self.assertEqual(user_id, mr.auth.user_id)


class BlankTest(unittest.TestCase):

  def testBlank(self):
    blank = testing_helpers.Blank(
        foo='foo',
        bar=123,
        inc=lambda x: x + 1)

    self.assertEqual('foo', blank.foo)
    self.assertEqual(123, blank.bar)
    self.assertEqual(5, blank.inc(4))
