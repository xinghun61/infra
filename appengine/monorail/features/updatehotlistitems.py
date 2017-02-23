# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes for  updating  hotlistitems of a hotlistissues table page."""

import logging


from framework import jsonfeed
from framework import permissions
from services import features_svc


class UpdateHotlistIssueNote(jsonfeed.JsonFeed):
  """Update a hotlist item's note."""

  def AssertBasePermission(self, mr):
    super(UpdateHotlistIssueNote, self).AssertBasePermission(mr)
    edit_perm = permissions.CanEditHotlist(mr.auth.effective_ids, mr.hotlist)
    if not edit_perm:
      raise permissions.PermissionException(
          'User is not allowed to edit this hotlist')

  def HandleRequest(self, mr):
    new_note = mr.GetParam('new_note')
    iid = mr.GetIntParam('iid')
    new_notes = {iid: new_note}

    self.services.features.UpdateHotlistItemsFields(
        mr.cnxn, mr.hotlist_id, new_notes=new_notes)

    return {'new_note': new_note,
            'iid': iid}
