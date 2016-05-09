# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.api.app_identity import app_identity


_EMAIL_SCOPE = 'https://www.googleapis.com/auth/userinfo.email'


def GetAuthToken(scope=_EMAIL_SCOPE):  # pragma: no cover
  """Gets auth token for requests to hosts that need authorizations."""
  auth_token, _ = app_identity.get_access_token(scope)
  return auth_token
