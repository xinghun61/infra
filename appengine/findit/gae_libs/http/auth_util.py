# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.api import oauth
from google.appengine.api import users
from google.appengine.api.app_identity import app_identity


_EMAIL_SCOPE = 'https://www.googleapis.com/auth/userinfo.email'


def GetAuthToken(scope=_EMAIL_SCOPE):  # pragma: no cover
  """Gets auth token for requests to hosts that need authorizations."""
  auth_token, _ = app_identity.get_access_token(scope)
  return auth_token


def GetUserEmail(scope=_EMAIL_SCOPE):  # pragma: no cover
  """Returns the email of the logged-in user or None if not logged-in."""
  user = users.get_current_user()  # Cookie-based authentication.
  if not user:
    try:
      user = oauth.get_current_user(scope)  # Oauth-based authentication.
    except oauth.OAuthRequestError:
      pass  # Not logged-in or invalid oauth token.
  return user.email() if user else None


def IsCurrentUserAdmin(scope=_EMAIL_SCOPE):  # pragma: no cover
  """Returns True if the logged-in user is an admin."""
  is_admin = users.is_current_user_admin()
  try:
    is_admin = is_admin or oauth.is_current_user_admin(scope)
  except oauth.OAuthRequestError:
    pass  # Not logged-in or invalid oauth token.
  return is_admin


def GetLoginUrl(url):  # pragma: no cover
  return users.create_login_url(url)


def GetLogoutUrl(url='/'):  # pragma: no cover
  return users.create_logout_url(url)


def GetUserInfo(url='/'):  # pragma: no cover
  info = {
      'email': GetUserEmail(),
      'is_admin': IsCurrentUserAdmin(),
  }
  if info['email'] is not None:
    info['logout_url'] = GetLogoutUrl()
  else:
    info['login_url'] = GetLoginUrl(url)
  return info
