# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common import constants
from gae_libs import appengine_util


def IsPrivilegedUser(user_email, is_admin):
  """Returns True if the given email account is authorized for access."""
  return is_admin or (user_email and user_email.endswith('@google.com'))


def CanTriggerNewAnalysis(user_email, is_admin):
  """Returns True if the given email account could trigger a new analysis."""
  if not appengine_util.IsStaging():
    whitelisted_app_accounts = constants.WHITELISTED_APP_ACCOUNTS
  else:
    whitelisted_app_accounts = constants.WHITELISTED_STAGING_APP_ACCOUNTS
  return (IsPrivilegedUser(user_email, is_admin) or
          user_email in whitelisted_app_accounts)
