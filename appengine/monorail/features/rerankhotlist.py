# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Class that implements the reranking on the hotlistissues table page."""

from framework import jsonfeed
from framework import permissions
from services import features_svc


class RerankHotlistIssue(jsonfeed.JsonFeed):
  """Rerank an issue in a hotlist."""

  def AssertBasePermission(self, mr):
    super(RerankHotlistIssue, self).AssertBasePermission(mr)
    if mr.target_id and mr.moved_ids and mr.split_above:
      try:
        hotlist = self._GetHotlist(mr)
      except features_svc.NoSuchHotlistException:
        return
      edit_perm = permissions.CanEditHotlist(mr.auth.effective_ids, hotlist)
      if not edit_perm:
        raise permissions.PermissionException(
            'User is not allowed to re-rank this hotlist')

  def HandleRequest(self, _mr):
    # TODO(jojwang): HandleRequest will create and return a new JSON
    # representation of table_data to be used for table rendering.
    return {'table_data': ''}

  def _GetHotlist(self, mr):
    """Retrieve the current hotlist."""
    if mr.hotlist_id is None:
      return None
    try:
      hotlist = self.services.features.GetHotlist( mr.cnxn, mr.hotlist_id)
    except features_svc.NoSuchHotlistException:
      self.abort(404, 'hotlist not found')
    return hotlist
