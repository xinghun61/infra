# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A set of functions that provide persistence for stars.

Stars can be on users, projects, or issues.
"""

import logging

import settings
from features import filterrules_helpers
from framework import sql


USERSTAR_TABLE_NAME = 'UserStar'
PROJECTSTAR_TABLE_NAME = 'ProjectStar'
ISSUESTAR_TABLE_NAME = 'IssueStar'
HOTLISTSTAR_TABLE_NAME = 'HotlistStar'

# TODO(jrobbins): Consider adding memcache here if performance testing shows
# that stars are a bottleneck.  Keep in mind that issue star counts are
# already denormalized and stored in the Issue, which is cached in memcache.


class AbstractStarService(object):
  """The persistence layer for any kind of star data."""

  def __init__(self, cache_manager, tbl, item_col, user_col, cache_kind):
    """Constructor.

    Args:
      cache_manager: local cache with distributed invalidation.
      tbl: SQL table that stores star data.
      item_col: string SQL column name that holds int item IDs.
      user_col: string SQL column name that holds int user IDs
          of the user who starred the item.
      cache_kind: string saying the kind of RAM cache.
    """
    self.tbl = tbl
    self.item_col = item_col
    self.user_col = user_col

    # Items starred by users, keyed by user who did the starring.
    self.star_cache = cache_manager.MakeCache('user')
    # Users that starred an item, keyed by item ID.
    self.starrer_cache = cache_manager.MakeCache(cache_kind)
    # Counts of the users that starred an item, keyed by item ID.
    self.star_count_cache = cache_manager.MakeCache(cache_kind)

  def ExpungeStars(self, cnxn, item_id):
    """Wipes an item's stars from the system."""
    self.tbl.Delete(cnxn, **{self.item_col: item_id})

  def LookupItemStarrers(self, cnxn, item_id):
    """Returns list of users having stars on the specified item."""
    starrer_list_dict = self.LookupItemsStarrers(cnxn, [item_id])
    return starrer_list_dict[item_id]

  def LookupItemsStarrers(self, cnxn, items_ids):
    """Returns {item_id: [uid, ...]} of users who starred these items."""
    starrer_list_dict, missed_ids = self.starrer_cache.GetAll(items_ids)

    if missed_ids:
      rows = self.tbl.Select(
          cnxn, cols=[self.item_col, self.user_col],
          **{self.item_col: missed_ids})
      # Ensure that every requested item_id has an entry so that even
      # zero-star items get cached.
      retrieved_starrers = {item_id: [] for item_id in missed_ids}
      for item_id, starrer_id in rows:
        retrieved_starrers[item_id].append(starrer_id)
      starrer_list_dict.update(retrieved_starrers)
      self.starrer_cache.CacheAll(retrieved_starrers)

    return starrer_list_dict

  def LookupStarredItemIDs(self, cnxn, starrer_user_id):
    """Returns list of item IDs that were starred by the specified user."""
    if not starrer_user_id:
      return []  # Anon user cannot star anything.

    cached_item_ids = self.star_cache.GetItem(starrer_user_id)
    if cached_item_ids is not None:
      return cached_item_ids

    rows = self.tbl.Select(cnxn, cols=[self.item_col], user_id=starrer_user_id)
    starred_ids = [row[0] for row in rows]
    self.star_cache.CacheItem(starrer_user_id, starred_ids)
    return starred_ids

  def IsItemStarredBy(self, cnxn, item_id, starrer_user_id):
    """Return True if the given issue is starred by the given user."""
    starred_ids = self.LookupStarredItemIDs(cnxn, starrer_user_id)
    return item_id in starred_ids

  def CountItemStars(self, cnxn, item_id):
    """Returns the number of stars on the specified item."""
    count_dict = self.CountItemsStars(cnxn, [item_id])
    return count_dict.get(item_id, 0)

  def CountItemsStars(self, cnxn, item_ids):
    """Get a dict {item_id: count} for the given items."""
    item_count_dict, missed_ids = self.star_count_cache.GetAll(item_ids)

    if missed_ids:
      rows = self.tbl.Select(
          cnxn, cols=[self.item_col, 'COUNT(%s)' % self.user_col],
          group_by=[self.item_col],
          **{self.item_col: missed_ids})
      # Ensure that every requested item_id has an entry so that even
      # zero-star items get cached.
      retrieved_counts = {item_id: 0 for item_id in missed_ids}
      retrieved_counts.update(rows)
      item_count_dict.update(retrieved_counts)
      self.star_count_cache.CacheAll(retrieved_counts)

    return item_count_dict

  def _SetStarsBatch(self, cnxn, item_id, starrer_user_ids, starred):
    """Sets or unsets stars for the specified item and users."""
    if starred:
      rows = [(item_id, user_id) for user_id in starrer_user_ids]
      self.tbl.InsertRows(
          cnxn, [self.item_col, self.user_col], rows, ignore=True)
    else:
      self.tbl.Delete(
          cnxn, **{self.item_col: item_id, self.user_col: starrer_user_ids})

    self.star_cache.InvalidateKeys(cnxn, starrer_user_ids)
    self.starrer_cache.Invalidate(cnxn, item_id)
    self.star_count_cache.Invalidate(cnxn, item_id)

  def SetStarsBatch(self, cnxn, item_id, starrer_user_ids, starred):
    """Sets or unsets stars for the specified item and users."""
    self._SetStarsBatch(cnxn, item_id, starrer_user_ids, starred)

  def SetStar(self, cnxn, item_id, starrer_user_id, starred):
    """Sets or unsets a star for the specified item and user."""
    self._SetStarsBatch(cnxn, item_id, [starrer_user_id], starred)



class UserStarService(AbstractStarService):
  """Star service for stars on users."""

  def __init__(self, cache_manager):
    tbl = sql.SQLTableManager(USERSTAR_TABLE_NAME)
    super(UserStarService, self).__init__(
        cache_manager, tbl, 'starred_user_id', 'user_id', 'user')


class ProjectStarService(AbstractStarService):
  """Star service for stars on projects."""

  def __init__(self, cache_manager):
    tbl = sql.SQLTableManager(PROJECTSTAR_TABLE_NAME)
    super(ProjectStarService, self).__init__(
        cache_manager, tbl, 'project_id', 'user_id', 'project')


class HotlistStarService(AbstractStarService):
  """Star service for stars on hotlists."""

  def __init__(self, cache_manager):
    tbl = sql.SQLTableManager(HOTLISTSTAR_TABLE_NAME)
    super(HotlistStarService, self).__init__(
        cache_manager, tbl, 'hotlist_id', 'user_id', 'hotlist')


class IssueStarService(AbstractStarService):
  """Star service for stars on issues."""

  def __init__(self, cache_manager):
    tbl = sql.SQLTableManager(ISSUESTAR_TABLE_NAME)
    super(IssueStarService, self).__init__(
        cache_manager, tbl, 'issue_id', 'user_id', 'issue')

  # pylint: disable=arguments-differ
  def SetStar(
      self, cnxn, services, config, issue_id, starrer_user_id, starred):
    # TODO(agable): The number of arguments required by this function is
    # crazy. Find a way to simplify it so that it only needs the same
    # arguments as AbstractSetStar above.
    """Add or remove a star on the given issue for the given user.

    Args:
      cnxn: connection to SQL database.
      services: connections to persistence layer.
      config: ProjectIssueConfig PB for the project containing the issue.
      issue_id: integer global ID of an issue.
      starrer_user_id: user ID of the user who starred the issue.
      starred: boolean True for adding a star, False when removing one.
    """
    self.SetStarsBatch(
        cnxn, services, config, issue_id, [starrer_user_id], starred)

  # pylint: disable=arguments-differ
  def SetStarsBatch(
      self, cnxn, services, config, issue_id, starrer_user_ids, starred):
    """Add or remove a star on the given issue for the given user.

    Args:
      cnxn: connection to SQL database.
      services: connections to persistence layer.
      config: ProjectIssueConfig PB for the project containing the issue.
      issue_id: integer global ID of an issue.
      starrer_user_id: user ID of the user who starred the issue.
      starred: boolean True for adding a star, False when removing one.
    """
    logging.info(
        'SetStarsBatch:%r, %r, %r', issue_id, starrer_user_ids, starred)
    super(IssueStarService, self).SetStarsBatch(
        cnxn, issue_id, starrer_user_ids, starred)

    # Because we will modify issues, load from DB rather than cache.
    issue = services.issue.GetIssue(cnxn, issue_id, use_cache=False)
    issue.star_count = self.CountItemStars(cnxn, issue_id)
    filterrules_helpers.ApplyFilterRules(cnxn, services, issue, config)
    # Note: only star_count could change due to the starring, but any
    # field could have changed as a result of filter rules.
    services.issue.UpdateIssue(cnxn, issue)

    self.star_cache.InvalidateKeys(cnxn, starrer_user_ids)
    self.starrer_cache.Invalidate(cnxn, issue_id)
