# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the captcha module."""

import unittest

import mox

from google.appengine.ext import testbed

from framework import captcha


class CaptchaTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_user_stub()
    self.testbed.init_memcache_stub()
    self.testbed.init_datastore_v3_stub()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()
    self.testbed.deactivate()


  def testVerify_NoGuess(self):
    self.mox.StubOutWithMock(captcha, '_AskRecaptcha')
    # We are verifying that _AskRecaptcha is not called.
    self.mox.ReplayAll()
    self.assertEqual(
        (False, 'incorrect-captcha-sol'),
        captcha.Verify('1.2.3.4', ''))
    self.mox.VerifyAll()
    
  def testVerify_NullGuess(self):
    self.mox.StubOutWithMock(captcha, '_AskRecaptcha')
    # We are verifying that _AskRecaptcha is not called.
    self.mox.ReplayAll()
    self.assertEqual(
        (False, 'incorrect-captcha-sol'),
        captcha.Verify('1.2.3.4', None))
    self.mox.VerifyAll()
    
  def testVerify_GotErrorCode(self):
    self.mox.StubOutWithMock(captcha, '_AskRecaptcha')
    captcha._AskRecaptcha(
        '1.2.3.4', 'some challenge').AndReturn(
      {'success': False, 'error-codes': ['invalid-input-response']})
    self.mox.ReplayAll()
    self.assertEqual(
        (False, ['invalid-input-response']),
        captcha.Verify('1.2.3.4', 'some challenge'))
    self.mox.VerifyAll()

  def testVerify_CorrectGuess(self):
    self.mox.StubOutWithMock(captcha, '_AskRecaptcha')
    captcha._AskRecaptcha(
        '1.2.3.4', 'matching').AndReturn({'success':True})
    self.mox.ReplayAll()

    result = captcha.Verify('1.2.3.4', 'matching')

    self.mox.VerifyAll()
    self.assertEqual((True, ''), result)

  def testVerify_WrongGuess(self):
    self.mox.StubOutWithMock(captcha, '_AskRecaptcha')
    captcha._AskRecaptcha(
        '1.2.3.4', 'non-matching').AndReturn({'success': False})
    self.mox.ReplayAll()

    result = captcha.Verify('1.2.3.4', 'non-matching')

    self.mox.VerifyAll()
    self.assertEqual((False, 'incorrect-captcha-sol'), result)
