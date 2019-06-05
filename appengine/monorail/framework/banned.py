# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A class to display the a message explaining that the user has been banned.

We can ban a user for anti-social behavior.  We indicate that the user is
banned by adding a 'banned' field to his/her User PB in the DB.  Whenever
a user with a banned indicator visits any page, AssertBasePermission()
checks has_banned and redirects to this page.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging

from third_party import ezt

from framework import permissions
from framework import servlet


class Banned(servlet.Servlet):
  """The Banned page shows a message explaining that the user is banned."""

  _PAGE_TEMPLATE = 'framework/banned-page.ezt'

  def AssertBasePermission(self, mr):
    """Allow banned users to see this page, and prevent non-banned users."""
    # Note, we do not call Servlet.AssertBasePermission because
    # that would redirect banned users here again in an endless loop.

    # We only show this page to users who are banned.  If a non-banned user
    # follows a link to this URL, don't show the banned message, because that
    # would lead to a big misunderstanding.
    if not permissions.IsBanned(mr.auth.user_pb, mr.auth.user_view):
      logging.info('non-banned user: %s', mr.auth.user_pb)
      self.abort(404)

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page."""
    # Aside from plus-addresses, we do not display the specific
    # reason for banning.
    is_plus_address = '+' in (mr.auth.user_pb.email or '')

    return {
        'is_plus_address': ezt.boolean(is_plus_address),

        # Make the "Sign Out" link just sign out, don't try to bring the
        # user back to this page after they sign out.
        'currentPageURLEncoded': None,
        }
