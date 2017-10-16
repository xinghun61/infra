# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes that implement adding issues to hotlists from /issues/ pages."""

import logging
import time

from features import hotlist_helpers
from framework import jsonfeed
from framework import permissions

class UpdateHotlists(jsonfeed.JsonFeed):
  """AddToHotlist is a servlet which adds issues to hotlists."""

  def AssertBasePermission(self, mr):
    super(UpdateHotlists, self).AssertBasePermission(mr)
    hotlist_ids = (mr.hotlist_ids_add or []) + (mr.hotlist_ids_remove or [])
    if hotlist_ids:
      hotlist_ids_dict = self.services.features.GetHotlists(
          mr.cnxn, hotlist_ids)
      for _id, hotlist in hotlist_ids_dict.iteritems():
        if not permissions.CanEditHotlist(mr.auth.effective_ids, hotlist):
          raise permissions.PermissionException(
              'You are not allowed to edit hotlist %s' % hotlist.name)
    else:
      if not permissions.CanCreateHotlist(mr.perms):
        raise permissions.PermissionException(
            'User is not allowed to create a hotlist.')

  def createNewHotlist(self, mr):
    hotlist_name = 'Hotlist-1'
    count = 1
    taken_names = [h.name for h in self.services.features.GetHotlistsByUserID(
        mr.cnxn, mr.auth.user_id)]
    while hotlist_name in taken_names:
      count += 1
      hotlist_name = 'Hotlist-%d' % count
    return self.services.features.CreateHotlist(
        mr.cnxn, hotlist_name, 'Hotlist of bulk added issues', '',
        [mr.auth.user_id], [])

  def HandleRequest(self, mr):
    project_names = []
    refs = []
    for issue_ref in mr.issue_refs:
      issue_split = issue_ref.split(':')
      project_names.append(issue_split[0])
      refs.append((issue_split[0], int(issue_split[1])))
    ref_projects = self.services.project.GetProjectsByName(
        mr.cnxn, project_names)
    default_project_name = ''
    selected_iids, misses = self.services.issue.ResolveIssueRefs(
        mr.cnxn, ref_projects, default_project_name, refs)


    # Start updating hotlists.
    hotlist_ids_add = mr.hotlist_ids_add or []
    hotlist_ids_remove = mr.hotlist_ids_remove or []
    if (not hotlist_ids_add and not hotlist_ids_remove):
      hotlist_ids_add = [self.createNewHotlist(mr).hotlist_id]

    # Add issues to hotlists.
    added_tuples = [(issue_id, mr.auth.user_id,
                          int(time.time()), '') for issue_id in
                         selected_iids]
    self.services.features.AddIssuesToHotlists(
          mr.cnxn, hotlist_ids_add, added_tuples)

    # Remove issues from hotlists.
    for hotlist_id in hotlist_ids_remove:
      self.services.features.RemoveIssuesFromHotlist(
          mr.cnxn, hotlist_id, selected_iids)

    # Organize response data.
    missed = []
    for miss in misses:
      project_name = self.services.project.GetProject(
          mr.cnxn, miss[0]).project_name
      missed.append(('%s:%d' % (project_name, miss[1])))

    updated_hotlist_pbs = [self.services.features.GetHotlist(
        mr.cnxn, hotlist_id) for hotlist_id in
                           hotlist_ids_add + hotlist_ids_remove]

    user_issue_hotlists = []
    user_remaining_hotlists = []
    if selected_iids:
      # For updating user's hotlist when adding issues via the issue
      # details page. selected_iids should only contain one issue in this case.
      user_hotlists = self.services.features.GetHotlistsByUserID(
          mr.cnxn, mr.auth.user_id)

      user_issue_hotlists = list(set(user_hotlists) & set(
          self.services.features.GetHotlistsByIssueID(
              mr.cnxn, selected_iids[0])))

      user_remaining_hotlists = list(
          set(user_hotlists).difference(set(user_issue_hotlists)))

    return {'missed': missed,  # missed issues
            # names of hotlists that issues were added to or a new hotlist
            'updatedHotlistNames': [h.name for h in updated_hotlist_pbs],
            'issueHotlistIds': [h.hotlist_id for h in user_issue_hotlists],
            'issueHotlistNames': [h.name for h in user_issue_hotlists],
            'issueHotlistUrls': [hotlist_helpers.GetURLOfHotlist(
                mr.cnxn, hotlist, self.services.user) for
                                 hotlist in user_issue_hotlists],
            'remainingHotlistNames': [h.name for h in user_remaining_hotlists],
            'remainingHotlistIds': [h.hotlist_id for h in
                                    user_remaining_hotlists]
    }
