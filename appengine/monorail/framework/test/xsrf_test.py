# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for XSRF utility functions."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

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

  def testGenerateToken_AnonUserGetsAToken(self):
    self.assertNotEqual('', xsrf.GenerateToken(0L, '/path'))

  def testGenerateToken_DifferentUsersGetDifferentTokens(self):
    self.assertNotEqual(
        xsrf.GenerateToken(111, '/path'),
        xsrf.GenerateToken(222, '/path'))

    self.assertNotEqual(
        xsrf.GenerateToken(111, '/path'),
        xsrf.GenerateToken(0L, '/path'))

  def testGenerateToken_DifferentPathsGetDifferentTokens(self):
    self.assertNotEqual(
        xsrf.GenerateToken(111, '/path/one'),
        xsrf.GenerateToken(111, '/path/two'))

  @patch('time.time')
  def testGenerateToken_CloseTimesGetSameTokens(self, mockTime):
    test_time = 1526671379

    mockTime.return_value = test_time
    token1 = xsrf.GenerateToken(111, '/path')

    mockTime.return_value = test_time + 1
    token2 = xsrf.GenerateToken(111, '/path')
    self.assertEqual(token1, token2)

    mockTime.return_value = test_time \
        + xsrf.TOKEN_GRANULARITY_SECONDS \
        - xsrf.TOKEN_TIMEOUT_MARGIN_SEC
    token3 = xsrf.GenerateToken(111, '/path')
    self.assertEqual(token1, token3)

    mockTime.return_value = test_time + xsrf.TOKEN_GRANULARITY_SECONDS
    token4 = xsrf.GenerateToken(111, '/path')
    self.assertNotEqual(token1, token4)

  def testValidToken(self):
    token = xsrf.GenerateToken(111, '/path')
    xsrf.ValidateToken(token, 111, '/path')  # no exception raised

  def testMalformedToken(self):
    self.assertRaises(
      xsrf.TokenIncorrect,
      xsrf.ValidateToken, 'bad', 111, '/path')
    self.assertRaises(
      xsrf.TokenIncorrect,
      xsrf.ValidateToken, '', 111, '/path')

    self.assertRaises(
        xsrf.TokenIncorrect,
        xsrf.ValidateToken, '098a08fe08b08c08a05e:9721973123', 111, '/path')

  def testWrongUser(self):
    token = xsrf.GenerateToken(111, '/path')
    self.assertRaises(
      xsrf.TokenIncorrect,
      xsrf.ValidateToken, token, 222, '/path')

  def testWrongPath(self):
    token = xsrf.GenerateToken(111, '/path/one')
    self.assertRaises(
      xsrf.TokenIncorrect,
      xsrf.ValidateToken, token, 111, '/path/two')

  @patch('time.time')
  def testValidateToken_Expiration(self, mockTime):
    test_time = 1526671379
    mockTime.return_value = test_time
    token = xsrf.GenerateToken(111, '/path')
    xsrf.ValidateToken(token, 111, '/path')

    mockTime.return_value = test_time + 1
    xsrf.ValidateToken(token, 111, '/path')

    mockTime.return_value = test_time + xsrf.TOKEN_TIMEOUT_SEC
    xsrf.ValidateToken(token, 111, '/path')

    mockTime.return_value = test_time + xsrf.TOKEN_TIMEOUT_SEC + 1
    self.assertRaises(
      xsrf.TokenIncorrect,
      xsrf.ValidateToken, token, 11L, '/path')

  @patch('time.time')
  def testGetRoundedTime(self, mockTime):
    mockTime.return_value = 1526344117
    self.assertEqual(1526343600, xsrf.GetRoundedTime())

    # When it divides evenly by 10 minutes (600 seconds).
    mockTime.return_value = 1526344200
    self.assertEqual(1526344200, xsrf.GetRoundedTime())
