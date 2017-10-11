# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes that implement removing an issue from a hotlist on /issues/ pages."""

import logging
import time

from features import hotlist_helpers
from framework import jsonfeed
from framework import permissions

class RemoveFromHotlist(jsonfeed.JsonFeed):
  """RemoveFromHotlist is a servlet which removes an issue from a hotlist."""

  def AssertBasePermission(self, mr):
    super(RemoveFromHotlist, self).AssertBasePermission(mr)
    if mr.hotlist_ids:
      hotlist_ids_dict = self.services.features.GetHotlists(
          mr.cnxn, mr.hotlist_ids)
      for _id, hotlist in hotlist_ids_dict.iteritems():
        if not permissions.CanEditHotlist(mr.auth.effective_ids, hotlist):
          raise permissions.PermissionException(
              'You are not allowed to edit hotlist %s' % hotlist.name)

  def HandleRequest(self, mr):
    if len(mr.issue_refs) != 1 or len(mr.hotlist_ids) != 1:
      logging.error(
          'Wrong number of issues/hotlists: issues: %s, hotlists: %s.' % (
              mr.issue_refs, mr.hotlist_ids))
      self.abort(400, 'only one issue and one hotlist can be given.')

    hotlist_id = mr.hotlist_ids[0]
    issue_ref = mr.issue_refs[0]
    issue_split = issue_ref.split(':')
    issue_tuple_ref = (issue_split[0], int(issue_split[1]))
    ref_projects = self.services.project.GetProjectsByName(
        mr.cnxn, [issue_split[0]])
    issue_ids, misses = self.services.issue.ResolveIssueRefs(
        mr.cnxn, ref_projects, '', [issue_tuple_ref])

    # The returned values must all be arrays.
    missed = []
    all_hotlist_names = []
    all_hotlist_urls = []
    removed_hotlist_names = []
    if issue_ids:
      issue_id = issue_ids[0]
      self.services.features.RemoveIssueFromHotlist(
          mr.cnxn, hotlist_id, issue_id)

      removed_hotlist_pb = self.services.features.GetHotlist(
          mr.cnxn, hotlist_id)
      removed_hotlist_names = [removed_hotlist_pb.name]

      user_issue_hotlists = list(
          set(self.services.features.GetHotlistsByUserID(
              mr.cnxn, mr.auth.user_id)) &
          set(self.services.features.GetHotlistsByIssueID(
              mr.cnxn, issue_id)))

      all_hotlist_names = [hotlist.name for hotlist in user_issue_hotlists]
      all_hotlist_urls = [hotlist_helpers.GetURLOfHotlist(
          mr.cnxn, hotlist, self.services.user) for
                          hotlist in user_issue_hotlists]
    if misses:
      missed = issue_ref

    return {
        'missed': missed,
        'updatedHotlistNames': removed_hotlist_names,
        'allHotlistNames': all_hotlist_names,
        'allHotlistUrls': all_hotlist_urls}
