# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for XSRF utility functions."""

import time
import unittest

from mock import patch

from google.appengine.ext import testbed

import settings
from framework import xsrf


class XsrfTest(unittest.TestCase):
  """Set of unit tests for blocking XSRF attacks."""

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()
    self.testbed.init_datastore_v3_stub()

  def tearDown(self):
    self.testbed.deactivate()

  def testGenerateToken_AnonUserGetsNoToken(self):
    self.assertEqual('', xsrf.GenerateToken(0L, '/path'))

  def testGenerateToken_DifferentUsersGetDifferentTokens(self):
    self.assertNotEqual(
        xsrf.GenerateToken(111L, '/path'),
        xsrf.GenerateToken(222L, '/path'))

  def testGenerateToken_DifferentPathsGetDifferentTokens(self):
    self.assertNotEqual(
        xsrf.GenerateToken(111L, '/path/one'),
        xsrf.GenerateToken(111L, '/path/two'))

  def testGenerateToken_DifferentTimesGetDifferentTokens(self):
    test_time = int(time.time())
    # TODO(jeffcarp): Remove token_time testing arg and use mock.patch.
    self.assertNotEqual(
        xsrf.GenerateToken(111L, '/path', token_time=test_time),
        xsrf.GenerateToken(111L, '/path', token_time=test_time + 1))

  def testValidToken(self):
    token = xsrf.GenerateToken(111L, '/path')
    xsrf.ValidateToken(token, 111L, '/path')  # no exception raised

  def testMalformedToken(self):
    self.assertRaises(
      xsrf.TokenIncorrect,
      xsrf.ValidateToken, 'bad', 111L, '/path')
    self.assertRaises(
      xsrf.TokenIncorrect,
      xsrf.ValidateToken, '', 111L, '/path')

    self.assertRaises(
        xsrf.TokenIncorrect,
        xsrf.ValidateToken, '098a08fe08b08c08a05e:9721973123', 111L, '/path')

  def testWrongUser(self):
    token = xsrf.GenerateToken(111L, '/path')
    self.assertRaises(
      xsrf.TokenIncorrect,
      xsrf.ValidateToken, token, 222L, '/path')

  def testWrongPath(self):
    token = xsrf.GenerateToken(111L, '/path/one')
    self.assertRaises(
      xsrf.TokenIncorrect,
      xsrf.ValidateToken, token, 111L, '/path/two')

  def testValidateToken_Expiration(self):
    test_time = int(time.time())
    token = xsrf.GenerateToken(111L, '/path', token_time=test_time)
    xsrf.ValidateToken(token, 111L, '/path', now=test_time)
    xsrf.ValidateToken(token, 111L, '/path', now=test_time + 1)
    xsrf.ValidateToken(
        token, 111L, '/path', now=test_time + xsrf.TOKEN_TIMEOUT_SEC)

    self.assertRaises(
      xsrf.TokenIncorrect,
      xsrf.ValidateToken, token, 11L, '/path',
      now=test_time + xsrf.TOKEN_TIMEOUT_SEC + 1)

  @patch('time.time')
  def testGetRoundedTime(self, mockTime):
    mockTime.return_value = 1526344117
    self.assertEqual(1526343600, xsrf.GetRoundedTime())

    # When it divides evenly by 10 minutes (600 seconds).
    mockTime.return_value = 1526344200
    self.assertEqual(1526344200, xsrf.GetRoundedTime())
