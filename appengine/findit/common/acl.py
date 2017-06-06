# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common import constants


def CanTriggerNewAnalysis(user_email, is_admin):
  """Returns True if the given email account is authorized for access."""
  return is_admin or (user_email and (
      user_email in constants.WHITELISTED_APP_ACCOUNTS or
      user_email.endswith('@google.com')))
