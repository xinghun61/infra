# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Servlet for XSRF token refresh.

Our XSRF tokens expire in 2 hours (as defined in xsrf.py), which would
mean that users who open an issue page and take a long lunch would see
an error if they try to submit a comment when they get back.
"""

import logging

from framework import framework_constants
from framework import jsonfeed
from framework import xsrf


# TODO(jrobbins): Make this also work with xhr tokens by checking expiration
# time in CS_doPost().


class TokenRefresh(jsonfeed.JsonFeed):
  """JSON feed to give the user a new XSRF token."""

  # Setting this class variable tells servlet.py to not check the XHR
  # token for the token refresh request itself.  It will always be
  # expired, otherwise we would not need a new one.  Instead, we check
  # the form_token with a longer expiration.
  CHECK_SECURITY_TOKEN = False

  def HandleRequest(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """
    if not mr.auth.user_id:
      return {}

    post_data = mr.request.POST
    form_token_path = post_data.get('form_token_path')
    xsrf.ValidateToken(
        post_data.get('form_token'),
        mr.auth.user_id,
        form_token_path,
        timeout=xsrf.REFRESH_TOKEN_TIMEOUT_SEC)

    return {
      'form_token': xsrf.GenerateToken(mr.auth.user_id, form_token_path),
      'token_expires_sec': xsrf.TokenExpiresSec(),
      }


