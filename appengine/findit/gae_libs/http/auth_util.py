# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re
import urlparse

from google.appengine.api import oauth
from google.appengine.api import users
from google.appengine.api.app_identity import app_identity

from libs.http.interceptor import LoggingInterceptor

_EMAIL_SCOPE = 'https://www.googleapis.com/auth/userinfo.email'
_HOST_REGEX_TO_SCOPES = [
    (
        re.compile(r'^.*\.googlesource\.com$'),  # Gerrit.
        'https://www.googleapis.com/auth/gerritcodereview'),
    (re.compile(r'^codereview\.chromium\.org$'), _EMAIL_SCOPE),  # Rietveld.
]


def GetAuthToken(scope=_EMAIL_SCOPE):
  """Gets auth token for requests to hosts that need authorizations."""
  auth_token, _ = app_identity.get_access_token(scope)
  return auth_token


class Authenticator(object):

  def GetHttpHeadersFor(self, url):
    """Returns a dict with http headers for authentication to the given url."""
    result = urlparse.urlparse(url)
    if result.scheme != 'https':
      return {}

    for host_regex, scope in _HOST_REGEX_TO_SCOPES:
      if host_regex.match(result.netloc):
        logging.debug('Authorization header of scope %s was created for %s',
                      scope, url)
        return {'Authorization': 'Bearer %s' % GetAuthToken(scope)}

    return {}


def GetUserEmail():
  """Returns the email of the logged-in user or None if not logged-in."""
  user = users.get_current_user()  # Cookie-based authentication.
  return user.email() if user else None


def IsCurrentUserAdmin():
  """Returns True if the logged-in user is an admin."""
  return users.is_current_user_admin()


def GetOauthClientId(scope=_EMAIL_SCOPE):
  """Returns the client id of the oauth user."""
  try:
    return oauth.get_client_id(scope)
  except oauth.OAuthRequestError:
    return None  # Invalid oauth token.


def GetOauthUserEmail(scope=_EMAIL_SCOPE):
  """Returns the email of the oauth client user."""
  try:
    user = oauth.get_current_user(scope)  # Oauth-based authentication.
  # TODO (crbug/766768): Retry when meets OAuthServiceFailureError.
  except (oauth.OAuthRequestError, oauth.OAuthServiceFailureError):
    user = None  # Invalid oauth token or experienced oauth service failure.
  return user.email() if user else None


def IsCurrentOauthUserAdmin(scope=_EMAIL_SCOPE):
  """Returns True if the oauth client user is an admin."""
  try:
    return oauth.is_current_user_admin(scope)
  except oauth.OAuthRequestError:
    return False  # Invalid oauth token.


def GetLoginUrl(url):
  return users.create_login_url(url)


def GetLogoutUrl(url='/'):
  return users.create_logout_url(url)


def GetUserInfo(url='/'):
  info = {
      'email': GetUserEmail(),
      'is_admin': IsCurrentUserAdmin(),
  }
  if info['email'] is not None:
    info['logout_url'] = GetLogoutUrl()
  else:
    info['login_url'] = GetLoginUrl(url)
  return info


class AuthenticatingInterceptor(LoggingInterceptor):
  """Interceptor that injects auth header to http requests."""

  def GetAuthenticationHeaders(self, request):
    return Authenticator().GetHttpHeadersFor(request.get('url'))
