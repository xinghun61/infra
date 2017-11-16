# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module contains customized exceptions."""


class UnauthorizedException(Exception):
  """Indicates that the user is not authorized to access."""


class RetryException(Exception):
  """Custom exception for transient errors in underlying services.

  The service layer may raise this exception to indicate to the calling layer
  that the operation may succeed if retried, as the failure may be temporary
  (network blip, timeout, etc.)
  """

  def __init__(self, reason, message):
    """
    Args:
        reason (str): Error reason.
        message (str): Human-readable explanation of the reason.
    """
    self.error_reason = reason
    self.error_message = message
