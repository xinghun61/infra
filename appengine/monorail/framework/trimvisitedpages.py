# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes to handle cron requests to trim users' hotlists/issues visited."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from framework import jsonfeed

class TrimVisitedPages(jsonfeed.InternalTask):

  """Look for users with more than 10 visited hotlists and deletes extras."""

  def HandleRequest(self, mr):
    """Delete old RecentHotlist2User rows when there are too many"""
    self.services.user.TrimUserVisitedHotlists(mr.cnxn)
