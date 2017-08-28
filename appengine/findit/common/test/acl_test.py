# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import unittest

import endpoints

from common import acl
from common import constants
from common import exceptions


class AclTest(unittest.TestCase):
  def testAdminIsPrivilegedUser(self):
    self.assertTrue(acl.IsPrivilegedUser('test@chromium.org', True))

  def testGooglerIsPrivilegedUser(self):
    self.assertTrue(acl.IsPrivilegedUser('test@google.com', False))

  def testUnknownUserIsNotPrivilegedUser(self):
    self.assertFalse(acl.IsPrivilegedUser('test@gmail.com', False))

  def testWhitelistedClientId(self):
    self.assertTrue(acl.IsWhitelistedClientId(endpoints.API_EXPLORER_CLIENT_ID))

  def testUnknownClientIdIsNotWhitelisted(self):
    self.assertFalse(acl.IsWhitelistedClientId('unknown_id'))

  def testAdminCanTriggerNewAnalysis(self):
    self.assertTrue(acl.CanTriggerNewAnalysis('test@chromium.org', True))

  def testGooglerCanTriggerNewAnalysis(self):
    self.assertTrue(acl.CanTriggerNewAnalysis('test@google.com', False))

  @mock.patch.object(acl.appengine_util, 'IsStaging', return_value=False)
  def testWhitelistedAppAccountCanTriggerNewAnalysis(self, _):
    for email in constants.WHITELISTED_APP_ACCOUNTS:
      self.assertTrue(acl.CanServiceAccountTriggerNewAnalysis(email))

  @mock.patch.object(acl.appengine_util, 'IsStaging', return_value=True)
  def testWhitelistedStagingAppAccountCanTriggerNewAnalysis(self, _):
    for email in constants.WHITELISTED_STAGING_APP_ACCOUNTS:
      self.assertTrue(acl.CanServiceAccountTriggerNewAnalysis(email))

  def testUnkownUserCanNotTriggerNewAnalysis(self):
    self.assertFalse(acl.CanTriggerNewAnalysis('test@gmail.com', False))

  @mock.patch.object(
      acl, 'CanServiceAccountTriggerNewAnalysis', return_value=True)
  @mock.patch.object(
      acl.auth_util, 'GetOauthUserEmail',
      return_value='email@appspot.gserviceaccount.com')
  def testValidateOauthUserForAuthorizedServiceAccount(self, *_):
    user_email, is_admin = acl.ValidateOauthUserForNewAnalysis()
    self.assertEqual('email@appspot.gserviceaccount.com', user_email)
    self.assertFalse(is_admin)

  @mock.patch.object(
      acl, 'CanServiceAccountTriggerNewAnalysis', return_value=False)
  @mock.patch.object(
      acl.auth_util, 'GetOauthUserEmail',
      return_value='email@appspot.gserviceaccount.com')
  def testValidateOauthUserForUnauthorizedServiceAccount(self, *_):
    with self.assertRaises(exceptions.UnauthorizedException):
      acl.ValidateOauthUserForNewAnalysis()

  @mock.patch.object(
      acl, 'CanTriggerNewAnalysis', return_value=True)
  @mock.patch.object(
      acl, 'IsWhitelistedClientId', return_value=False)
  @mock.patch.object(
      acl.auth_util, 'GetOauthClientId', return_value='id')
  @mock.patch.object(
      acl.auth_util, 'IsCurrentOauthUserAdmin', return_value=True)
  @mock.patch.object(
      acl.auth_util, 'GetOauthUserEmail', return_value='email')
  def testValidateOauthUserForUnauthorizedClientId(self, *_):
    with self.assertRaises(exceptions.UnauthorizedException):
      acl.ValidateOauthUserForNewAnalysis()

  @mock.patch.object(
      acl, 'CanTriggerNewAnalysis', return_value=True)
  @mock.patch.object(
      acl, 'IsWhitelistedClientId', return_value=True)
  @mock.patch.object(
      acl.auth_util, 'GetOauthClientId', return_value='id')
  @mock.patch.object(
      acl.auth_util, 'IsCurrentOauthUserAdmin', return_value=True)
  @mock.patch.object(
      acl.auth_util, 'GetOauthUserEmail', return_value='email')
  def testValidateOauthUserForAuthorizedUser(self, *_):
    user_email, is_admin = acl.ValidateOauthUserForNewAnalysis()
    self.assertEqual('email', user_email)
    self.assertTrue(is_admin)

  @mock.patch.object(
      acl, 'CanTriggerNewAnalysis', return_value=False)
  @mock.patch.object(
      acl, 'IsWhitelistedClientId', return_value=True)
  @mock.patch.object(
      acl.auth_util, 'GetOauthClientId', return_value='id')
  @mock.patch.object(
      acl.auth_util, 'IsCurrentOauthUserAdmin', return_value=False)
  @mock.patch.object(
      acl.auth_util, 'GetOauthUserEmail', return_value='email')
  def testValidateOauthUserForUnauthorizedUser(self, *_):
    with self.assertRaises(exceptions.UnauthorizedException):
      acl.ValidateOauthUserForNewAnalysis()

  @mock.patch.object(
      acl.auth_util, 'GetOauthUserEmail', return_value=None)
  def testValidateOauthUserForUnknownUserEmail(self, *_):
    with self.assertRaises(exceptions.UnauthorizedException):
      acl.ValidateOauthUserForNewAnalysis()
