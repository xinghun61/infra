# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Protocol buffers for Monorail site-wide features."""

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from protorpc import messages


class UserTypeRestriction(messages.Enum):
  """An enum for site-wide settings about who can take an action."""
  # Anyone may do it.
  ANYONE = 1

  # Only domain admins may do it.
  ADMIN_ONLY = 2

  # No one may do it, the feature is basically disabled.
  NO_ONE = 3

  # TODO(jrobbins): implement same-domain users
