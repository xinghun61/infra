# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Class that implements the reranking on the hotlistissues table page."""

import logging

from features import features_bizobj
from features import hotlist_helpers
from framework import jsonfeed
from framework import permissions
from framework import sorting
from services import features_svc
from tracker import rerank_helpers


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

  def HandleRequest(self, mr):
    changed_ranks = self._GetNewRankings(mr)

    if changed_ranks:
      relations_to_change = dict(
          (issue_id, rank) for issue_id, rank in changed_ranks)

      self.services.features.UpdateHotlistItemsFields(
          mr.cnxn, mr.hotlist_id, new_ranks=relations_to_change)

      hotlist_items = self.services.features.GetHotlist(
          mr.cnxn, mr.hotlist_id).items

      # Note: Cannot use mr.hotlist because hotlist_issues
      # of mr.hotlist is not updated

      sorting.InvalidateArtValuesKeys(
          mr.cnxn, [hotlist_item.issue_id for hotlist_item in hotlist_items])
      (table_data, _) = hotlist_helpers.CreateHotlistTableData(
          mr, hotlist_items, self.services)

      json_table_data = [{
          'cells': [{
              'type': cell.type,
              'values': [{
                  'item': value.item,
                  'isDerived': value.is_derived,
              } for value in cell.values],
              'colIndex': cell.col_index,
              'align': cell.align,
              'noWrap': cell.NOWRAP,
              'nonColLabels': [{
                  'value': label.value,
                  'isDerived': label.is_derived,
              } for label in cell.non_column_labels],
          } for cell in table_row.cells],
          'issueRef': table_row.issue_ref,
          'idx': table_row.idx,
          'projectName': table_row.project_name,
          'projectURL': table_row.project_url,
          'localID': table_row.local_id,
          'issueID': table_row.issue_id,
          'isStarred': table_row.starred,
          'issueCleanURL': table_row.issue_clean_url,
          'issueContextURL': table_row.issue_ctx_url,
      } for table_row in table_data]

      for row, json_row in zip(
          [table_row for table_row in table_data], json_table_data):
        if (row.group and row.group.cells):
          json_row.update({'group': {
              'rowsInGroup': row.group.rows_in_group,
              'cells': [{'groupName': cell.group_name,
                         'values': [{
                          # TODO(jojwang): check if this gives error when there
                          # is no value.item
                             'item': value.item if value.item else 'None',
                         } for value in cell.values],
              } for cell in row.group.cells],
          }})
        else:
          json_row['group'] = 'no'

      return {'table_data': json_table_data}
    else:
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

  def _GetNewRankings(self, mr):
    """Compute new issue reference rankings."""
    missing = False
    if not (mr.target_id):
      logging.info('No target_id.')
      missing = True
    if not (mr.moved_ids):
      logging.info('No moved_ids.')
      missing = True
    if mr.split_above is None:
      logging.info('No split_above.')
      missing = True
    if missing:
      return

    untouched_items = [
        (item.issue_id, item.rank) for item in
        mr.hotlist.items if item.issue_id not in mr.moved_ids]

    # Note: The original reranking methods were written for reranking lists
    # sorted High to Low. Hotlist issues are reranked when they are sorted
    # Low to High so the mr.split_above must be flipped.
    lower, higher = features_bizobj.SplitHotlistIssueRanks(
        mr.target_id, not mr.split_above, untouched_items)
    return rerank_helpers.GetInsertRankings(lower, higher, mr.moved_ids)
