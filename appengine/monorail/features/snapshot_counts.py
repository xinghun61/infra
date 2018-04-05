# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""An endpoint for performing IssueSnapshot queries for charts."""

from businesslogic import work_env
from features import savedqueries_helpers
from framework import jsonfeed
from search import searchpipeline


# TODO(jeffcarp): Transition this handler to APIv2.
class SnapshotCounts(jsonfeed.InternalTask):
  """Handles IssueSnapshot queries.

  URL params:
    timestamp (int): The point in time at which snapshots will be counted.
    group_by (str, optional): One of (label, component). Defines the second
      dimension for bucketing IssueSnapshot counts. Defaults to None, returning
      one key 'total'.
    label_prefix (str): Required if group_by=label. Returns only labels
      with this prefix, e.g. 'Pri'.
    q (str, optional): Query string.
    can (str, optional): Canned query parameter.

  Output:
    A JSON response with the following structure:
    {
      results: { name: count } for item in 2nd dimension.
      unsupported_fields: a list of strings for each unsupported field in query.
    }
  """

  def HandleRequest(self, mr):
    group_by = mr.GetParam('group_by', None)
    label_prefix = mr.GetParam('label_prefix', None)
    timestamp = mr.GetParam('timestamp')
    if timestamp:
      timestamp = int(timestamp)
    else:
      return { 'error': 'Param `timestamp` required.' }
    if group_by == 'label' and not label_prefix:
      return { 'error': 'Param `label_prefix` required.' }
    if mr.query and mr.can:
      canned_query = savedqueries_helpers.SavedQueryIDToCond(
          mr.cnxn, self.services.features, mr.can)
      canned_query, warnings = searchpipeline.ReplaceKeywordsWithUserID(
          mr.me_user_id, canned_query)
      # TODO(jeffcarp): Expose warnings & combine with unsupported fields.
      mr.warnings.extend(warnings)
    else:
      canned_query = None

    with work_env.WorkEnv(mr, self.services) as we:
      results, unsupported_fields = we.SnapshotCountsQuery(timestamp, group_by,
          label_prefix, mr.query, canned_query)

    return {
      'results': results,
      'unsupported_fields': unsupported_fields,
    }
