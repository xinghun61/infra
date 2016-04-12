# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for URL handler registration helper functions."""

import unittest

import webapp2

from framework import registerpages_helpers


class SendRedirectInScopeTest(unittest.TestCase):

  def testMakeRedirectInScope_Error(self):
    self.assertRaises(
        AssertionError,
        registerpages_helpers.MakeRedirectInScope, 'no/initial/slash', 'p')
    self.assertRaises(
        AssertionError,
        registerpages_helpers.MakeRedirectInScope, '', 'p')

  def testMakeRedirectInScope_Normal(self):
    factory = registerpages_helpers.MakeRedirectInScope('/', 'p')
    # Non-dasher, normal case
    request = webapp2.Request.blank(
        path='/p/foo', headers={'Host': 'example.com'})
    response = webapp2.Response()
    redirector = factory(request, response)
    redirector.get()
    self.assertEqual(response.location, '//example.com/p/foo/')
    self.assertEqual(response.status, '301 Moved Permanently')

  def testMakeRedirectInScope_Temporary(self):
    factory = registerpages_helpers.MakeRedirectInScope(
        '/', 'p', permanent=False)
    request = webapp2.Request.blank(
        path='/p/foo', headers={'Host': 'example.com'})
    response = webapp2.Response()
    redirector = factory(request, response)
    redirector.get()
    self.assertEqual(response.location, '//example.com/p/foo/')
    self.assertEqual(response.status, '302 Moved Temporarily')


if __name__ == '__main__':
  unittest.main()
