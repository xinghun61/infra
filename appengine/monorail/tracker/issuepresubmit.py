# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""JSON feed for issue presubmit warningins."""

import logging

from framework import framework_views
from framework import jsonfeed
from framework import permissions
from tracker import tracker_bizobj
from tracker import tracker_helpers


class IssuePresubmitJSON(jsonfeed.JsonFeed):
  """JSON data for any warnings as the user edits an issue."""

  def HandleRequest(self, mr):
    """Provide the UI with warning info as the user edits an issue.

    Args:
      mr: common information parsed from the HTTP request.

    Returns:
      Results dictionary in JSON format.
    """
    # TODO(jrobbins): Get the issue and do a dry run of updating it, if
    # the user has permission to even view it.

    with self.profiler.Phase('parsing request'):
      post_data = mr.request.POST
      parsed = tracker_helpers.ParseIssueRequest(
          mr.cnxn, post_data, self.services, mr.errors, mr.project_name)

    logging.info('parsed.users %r', parsed.users)

    if not parsed.users.owner_id:
      logging.info('No owner')
      return {
          'owner_availabilty': '',
          'owner_avail_state': '',
          }

    with self.profiler.Phase('making user proxies'):
      involved_user_ids = [parsed.users.owner_id]
      users_by_id = framework_views.MakeAllUserViews(
          mr.cnxn, self.services.user, involved_user_ids)
      proposed_owner_view = users_by_id[parsed.users.owner_id]

    # TODO(jrobbins): also check for process warnings.

    return {
        'owner_availability': proposed_owner_view.avail_message_short,
        'owner_avail_state': proposed_owner_view.avail_state,
        }
