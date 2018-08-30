# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

import logging

from api import monorail_servicer
from api.api_proto import sitewide_pb2
from api.api_proto import sitewide_prpc_pb2
from framework import xsrf


class SitewideServicer(monorail_servicer.MonorailServicer):
  """Handle API requests related to sitewide operations.

  Each API request is implemented with a method as defined in the .proto
  file that does any request-specific validation, uses work_env to
  safely operate on business objects, and returns a response proto.
  """

  DESCRIPTION = sitewide_prpc_pb2.SitewideServiceDescription

  def __init__(self, services, make_rate_limiter=True):
    # It might be that the token we're asked to refresh is the same one we are
    # using to authenticate. So we should use a longer timeout
    # (xsrf.REFRESH_TOKEN_TIMEOUT_SEC) when checking the XSRF
    super(SitewideServicer, self).__init__(
        services, make_rate_limiter, xsrf.REFRESH_TOKEN_TIMEOUT_SEC)

  @monorail_servicer.PRPCMethod
  def RefreshToken(self, mc, request):
    """Return a new token."""
    # Validate that the token we're asked to refresh would still be valid with a
    # longer timeout.
    xsrf.ValidateToken(
        request.token, mc.auth.user_id, request.token_path,
        timeout=xsrf.REFRESH_TOKEN_TIMEOUT_SEC)

    result = sitewide_pb2.RefreshTokenResponse(
        token=xsrf.GenerateToken(mc.auth.user_id, request.token_path),
        token_expires_sec=xsrf.TokenExpiresSec())
    return result
