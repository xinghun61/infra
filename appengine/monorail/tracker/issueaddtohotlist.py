# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes that implement adding issues to hotlists from /issues/ pages."""

import logging

from framework import jsonfeed
from framework import permissions

class AddToHotlist(jsonfeed.JsonFeed):
  """AddToHotlist is a servlet which adds issues to hotlists."""

  def AssertBasePermission(self, mr):
    super(AddToHotlist, self).AssertBasePermission(mr)
    hotlist_ids_dict = self.services.features.GetHotlists(
        mr.cnxn, mr.hotlist_ids)
    for _id, hotlist in hotlist_ids_dict.iteritems():
      if not permissions.CanEditHotlist(mr.auth.effective_ids, hotlist):
        raise permissions.PermissionException(
            'You are not allowed to edit hotlist %s' % hotlist.name)

  def HandleRequest(self, mr):
    return {'issues': ', '.join(mr.issue_refs),
            'hotlists': ', '.join(str(h_id) for h_id in mr.hotlist_ids)}
