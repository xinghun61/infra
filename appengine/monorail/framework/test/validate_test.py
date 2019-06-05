# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""This file provides unit tests for Validate functions."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from framework import validate


class ValidateUnitTest(unittest.TestCase):
  """Set of unit tests for validation functions."""

  GOOD_EMAIL_ADDRESSES = [
      'user@example.com',
      'user@e.com',
      'user+tag@example.com',
      'u.ser@example.com',
      'us.er@example.com',
      'u.s.e.r@example.com',
      'user@ex-ample.com',
      'user@ex.ample.com',
      'user@e.x.ample.com',
      'user@exampl.e.com',
      'user@e-x-ample.com',
      'user@e-x-a-m-p-l-e.com',
      'user@e-x.am-ple.com',
      'user@e--xample.com',
  ]

  BAD_EMAIL_ADDRESSES = [
      ' leading.whitespace@example.com',
      'trailing.whitespace@example.com ',
      '(paren.quoted@example.com)',
      '<angle.quoted@example.com>',
      'trailing.@example.com',
      'trailing.dot.@example.com',
      '.leading@example.com',
      '.leading.dot@example.com',
      'user@example.com.',
      'us..er@example.com',
      'user@ex..ample.com',
      'user@example..com',
      'user@ex-.ample.com',
      'user@-example.com',
      'user@.example.com',
      'user@example-.com',
      'user@example',
      'user@example.',
      'user@example.c',
      'user@example.comcomcomc',
      'user@example.co-m',
      'user@exa_mple.com',
      'user@exa-_mple.com',
      'user@example.c0m',
  ]

  def testIsValidEmail(self):
    """Tests the Email validator class."""
    for email in self.GOOD_EMAIL_ADDRESSES:
      self.assertTrue(validate.IsValidEmail(email), msg='Rejected:%r' % email)

    for email in self.BAD_EMAIL_ADDRESSES:
      self.assertFalse(validate.IsValidEmail(email), msg='Accepted:%r' % email)

  def testIsValidMailTo(self):
    for email in self.GOOD_EMAIL_ADDRESSES:
      self.assertTrue(
          validate.IsValidMailTo('mailto:' + email),
          msg='Rejected:%r' % ('mailto:' + email))

    for email in self.BAD_EMAIL_ADDRESSES:
      self.assertFalse(
          validate.IsValidMailTo('mailto:' + email),
          msg='Accepted:%r' % ('mailto:' + email))

  GOOD_URLS = [
      'http://google.com',
      'http://maps.google.com/',
      'https://secure.protocol.com',
      'https://dash-domain.com',
      'http://www.google.com/search?q=foo&hl=en',
      'https://a.very.long.domain.name.net/with/a/long/path/inf0/too',
      'http://funny.ws/',
      'http://we.love.anchors.info/page.html#anchor',
      'http://redundant-slashes.com//in/path//info',
      'http://trailingslashe.com/in/path/info/',
      'http://domain.with.port.com:8080',
      'http://domain.with.port.com:8080/path/info',
      'ftp://ftp.gnu.org',
      'ftp://some.server.some.place.com',
      'http://b/123456',
      'http://cl/123456/',
  ]

  BAD_URLS = [
      ' http://leading.whitespace.com',
      'http://trailing.domain.whitespace.com ',
      'http://trailing.whitespace.com/after/path/info ',
      'http://underscore_domain.com/',
      'http://space in domain.com',
      'http://user@example.com',  # standard, but we purposely don't accept it.
      'http://user:pass@ex.com',  # standard, but we purposely don't accept it.
      'http://:password@ex.com',  # standard, but we purposely don't accept it.
      'missing-http.com',
      'http:missing-slashes.com',
      'http:/only-one-slash.com',
      'http://trailing.dot.',
      'mailto:bad.scheme',
      'javascript:attempt-to-inject',
      'http://short-with-no-final-slash',
      'http:///',
      'http:///no.host.name',
      'http://:8080/',
      'http://badport.com:808a0/ ',
  ]

  def testURL(self):
    for url in self.GOOD_URLS:
      self.assertTrue(validate.IsValidURL(url), msg='Rejected:%r' % url)

    for url in self.BAD_URLS:
      self.assertFalse(validate.IsValidURL(url), msg='Accepted:%r' % url)
