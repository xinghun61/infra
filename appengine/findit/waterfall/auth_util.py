# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.api.app_identity import app_identity

def GetAuthToken():  # pragma: no cover
  """Gets auth token for requests to swarming server and isolated server."""
  auth_token, _ = app_identity.get_access_token(
      'https://www.googleapis.com/auth/userinfo.email')
  return auth_token
