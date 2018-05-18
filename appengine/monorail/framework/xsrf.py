# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Utility routines for avoiding cross-site-request-forgery."""

import base64
import hmac
import logging
import time

# This is a file in the top-level directory that you must edit before deploying
import settings
from framework import framework_constants
from services import secrets_svc

# This is how long tokens are valid.
TOKEN_TIMEOUT_SEC = 2 * framework_constants.SECS_PER_HOUR

# The token refresh servlet accepts old tokens to generate new ones, but
# we still impose a limit on how old they can be.
REFRESH_TOKEN_TIMEOUT_SEC = 10 * framework_constants.SECS_PER_DAY

# When the JS on a page decides whether or not it needs to refresh the
# XSRF token before submitting a form, there could be some clock skew,
# so we subtract a little time to avoid having the JS use an existing
# token that the server might consider expired already.
TOKEN_TIMEOUT_MARGIN_SEC = 5 * framework_constants.SECS_PER_MINUTE

# Form tokens and issue stars are limited to only work with the specific
# servlet path for the servlet that processes them.  There are several
# XHR handlers that mainly read data without making changes, so we just
# use 'xhr' with all of them.
XHR_SERVLET_PATH = 'xhr'

# Return the same XSRF token within a 10 minute period to allow the same
# token to be used in multiple requests by the same user. Quickly changing the
# XSRF token defeats URL-based caching. More context in crbug.com/monorail/3814.
TOKEN_GRANULARITY_MINUTES = 10 * framework_constants.SECS_PER_MINUTE

DELIMITER = ':'


def GenerateToken(user_id, servlet_path, token_time=None):
  """Return a security token specifically for the given user.

  Args:
    user_id: int user ID of the user viewing an HTML form.
    servlet_path: string URI path to limit the use of the token.
    token_time: Time at which the token is generated in seconds since the
        epoch.  This is used in validation and testing. Defaults to the
        current time.

  Returns:
    A url-safe security token.  The token is a string with the digest
    the user_id and time, followed by plain-text copy of the time that is
    used in validation.

  Raises:
    ValueError: if the XSRF secret was not configured.
  """
  if not user_id:
    return ''  # Don't give tokens out to anonymous visitors.

  token_time = token_time or GetRoundedTime()
  digester = hmac.new(secrets_svc.GetXSRFKey())
  digester.update(str(user_id))
  digester.update(DELIMITER)
  digester.update(servlet_path)
  digester.update(DELIMITER)
  digester.update(str(token_time))
  digest = digester.digest()

  token = base64.urlsafe_b64encode('%s%s%d' % (digest, DELIMITER, token_time))
  return token


def ValidateToken(
  token, user_id, servlet_path, now=None, timeout=TOKEN_TIMEOUT_SEC):
  """Return True if the given token is valid for the given scope.

  Args:
    token: String token that was presented by the user.
    user_id: int user ID.
    servlet_path: string URI path to limit the use of the token.
    now: Time in seconds since th epoch.  Defaults to the current time.
        It is explicitly specified only in tests.

  Raises:
    TokenIncorrect: if the token is missing or invalid.
  """
  if not token:
    raise TokenIncorrect('missing token')

  try:
    decoded = base64.urlsafe_b64decode(str(token))
    token_time = long(decoded.split(DELIMITER)[-1])
  except (TypeError, ValueError):
    raise TokenIncorrect('could not decode token')
  now = now or GetRoundedTime()

  # The given token should match the generated one with the same time.
  expected_token = GenerateToken(user_id, servlet_path, token_time=token_time)
  if len(token) != len(expected_token):
    raise TokenIncorrect('presented token is wrong size')

  # Perform constant time comparison to avoid timing attacks
  different = 0
  for x, y in zip(token, expected_token):
    different |= ord(x) ^ ord(y)
  if different:
    raise TokenIncorrect(
        'presented token does not match expected token: %r != %r' % (
            token, expected_token))

  # We check expiration last so that we only raise the expriration error
  # if the token would have otherwise been valid.
  if now - token_time > timeout:
    raise TokenIncorrect('token has expired')


def TokenExpiresSec(now=None):
  """Return timestamp when current tokens will expire, minus a safety margin."""
  now = now or GetRoundedTime()
  return now + TOKEN_TIMEOUT_SEC - TOKEN_TIMEOUT_MARGIN_SEC


def GetRoundedTime():
  now = int(time.time())
  rounded = now - (now % TOKEN_GRANULARITY_MINUTES)
  return rounded

class Error(Exception):
  """Base class for errors from this module."""
  pass


# Caught separately in servlet.py
class TokenIncorrect(Error):
  """The POST body has an incorrect URL Command Attack token."""
  pass
