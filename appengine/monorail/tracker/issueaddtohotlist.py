# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes that implement adding issues to hotlists from /issues/ pages."""

import logging
import time

from features import hotlist_helpers
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
    project_names = []
    refs = []
    for issue_ref in mr.issue_refs:
      issue_split = issue_ref.split(':')
      project_names.append(issue_split[0])
      refs.append((issue_split[0], int(issue_split[1])))
    ref_projects = self.services.project.GetProjectsByName(
        mr.cnxn, project_names)
    # TODO(jojwang): a default_project_name can be passed in for adding an issue
    # via the issuedetail page
    default_project_name = ''
    selected_iids, misses = self.services.issue.ResolveIssueRefs(
        mr.cnxn, ref_projects, default_project_name, refs)
    added_tuples = [(issue_id, mr.auth.user_id,
                          int(time.time())) for issue_id in
                         selected_iids]
    self.services.features.AddIssuesToHotlists(
        mr.cnxn, mr.hotlist_ids, added_tuples)

    missed = []
    for miss in misses:
      project_name = self.services.project.GetProject(
          mr.cnxn, miss[0]).project_name
      missed.append(('%s:%d' % (project_name, miss[1])))

    added_hotlist_pbs = [self.services.features.GetHotlist(
        mr.cnxn, hotlist_id) for hotlist_id in mr.hotlist_ids]

    user_issue_hotlists = list(set(self.services.features.GetHotlistsByUserID(
        mr.cnxn, mr.auth.user_id)) &
                               set(self.services.features.GetHotlistsByIssueID(
                                   mr.cnxn, selected_iids[0])))
    all_hotlist_urls = [hotlist_helpers.GetURLOfHotlist(
        mr.cnxn, hotlist, self.services.user) for
                        hotlist in user_issue_hotlists]
    all_hotlist_names = [hotlist.name for hotlist in user_issue_hotlists]
    return {'addedHotlistIDs': mr.hotlist_ids,
            'missed': missed,
            'addedHotlistNames': [h.name for h in added_hotlist_pbs],
            'allHotlistNames': all_hotlist_names,
            'allHotlistUrls': all_hotlist_urls}
