# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A class that provides persistence for Monorail's additional features.

Business objects are described in tracker_pb2.py, features_pb2.py, and
tracker_bizobj.py.
"""

import collections
import logging

from features import features_constants
from features import filterrules_helpers
from framework import framework_bizobj
from framework import sql
from proto import features_pb2
from services import caches
from tracker import tracker_bizobj
from tracker import tracker_constants

QUICKEDITHISTORY_TABLE_NAME = 'QuickEditHistory'
QUICKEDITMOSTRECENT_TABLE_NAME = 'QuickEditMostRecent'
SAVEDQUERY_TABLE_NAME = 'SavedQuery'
PROJECT2SAVEDQUERY_TABLE_NAME = 'Project2SavedQuery'
SAVEDQUERYEXECUTESINPROJECT_TABLE_NAME = 'SavedQueryExecutesInProject'
USER2SAVEDQUERY_TABLE_NAME = 'User2SavedQuery'
FILTERRULE_TABLE_NAME = 'FilterRule'
HOTLIST_TABLE_NAME = 'Hotlist'
HOTLIST2ISSUE_TABLE_NAME = 'Hotlist2Issue'
HOTLIST2USER_TABLE_NAME = 'Hotlist2User'


QUICKEDITHISTORY_COLS = [
    'user_id', 'project_id', 'slot_num', 'command', 'comment']
QUICKEDITMOSTRECENT_COLS = ['user_id', 'project_id', 'slot_num']
SAVEDQUERY_COLS = ['id', 'name', 'base_query_id', 'query']
PROJECT2SAVEDQUERY_COLS = ['project_id', 'rank', 'query_id']
SAVEDQUERYEXECUTESINPROJECT_COLS = ['query_id', 'project_id']
USER2SAVEDQUERY_COLS = ['user_id', 'rank', 'query_id', 'subscription_mode']
FILTERRULE_COLS = ['project_id', 'rank', 'predicate', 'consequence']
HOTLIST_COLS = [
    'id', 'name', 'summary', 'description', 'is_private', 'default_col_spec']
HOTLIST_ABBR_COLS = ['id', 'name', 'summary', 'is_private']
HOTLIST2ISSUE_COLS = ['hotlist_id', 'issue_id', 'rank']
HOTLIST2USER_COLS = ['hotlist_id', 'user_id', 'role_name']


class HotlistTwoLevelCache(caches.AbstractTwoLevelCache):
  """Class to manage both RAM and memcache for Project PBs."""

  def __init__(self, cachemanager, features_service):
    super(HotlistTwoLevelCache, self).__init__(
        cachemanager, 'hotlist', 'hotlist:', features_pb2.Hotlist)
    self.features_service = features_service

  def _DeserializeHotlists(
      self, hotlist_rows, issue_rows, role_rows):
    """Convert database rows into a dictionary of Hotlist PB keyed by ID.

    Args:
      hotlist_rows: a list of hotlist rows from HOTLIST_TABLE_NAME.
      issue_rows: a list of issue rows from HOTLIST2ISSUE_TABLE_NAME,
        ordered by rank DESC, issue_id.
      role_rows: a list of role rows from HOTLIST2USER_TABLE_NAME

    Returns:
      a dict mapping hotlist_id to hotlist PB"""
    hotlist_dict = {}

    for hotlist_row in hotlist_rows:
      (hotlist_id, hotlist_name, summary, description, is_private,
       default_col_spec) = hotlist_row
      hotlist = features_pb2.MakeHotlist(
          hotlist_name, hotlist_id=hotlist_id, summary=summary,
          description=description, is_private=bool(is_private),
          default_col_spec=default_col_spec)
      hotlist_dict[hotlist_id] = hotlist

    for (hotlist_id, issue_id, rank) in issue_rows:
      hotlist = hotlist_dict.get(hotlist_id)
      if hotlist:
        hotlist.iid_rank_pairs.append(
            features_pb2.MakeHotlistIssue(issue_id=issue_id, rank=rank))
      else:
        logging.warn('hotlist %d not found', hotlist_id)

    for (hotlist_id, user_id, role_name) in role_rows:
      hotlist = hotlist_dict.get(hotlist_id)
      if not hotlist:
        logging.warn('hotlist %d not found', hotlist_id)
      elif role_name == 'owner':
        hotlist.owner_ids.append(user_id)
      elif role_name == 'editor':
        hotlist.editor_ids.append(user_id)
      elif role_name == 'follower':
        hotlist.follower_ids.append(user_id)
      else:
        logging.info('unknown role name %s', role_name)

    return hotlist_dict

  def FetchItems(self, cnxn, keys):
    """On RAM and memcache miss, hit the database to get missing hotlists."""
    hotlist_rows = self.features_service.hotlist_tbl.Select(
        cnxn, cols=HOTLIST_COLS, id=keys)
    issue_rows = self.features_service.hotlist2issue_tbl.Select(
        cnxn, cols=HOTLIST2ISSUE_COLS, hotlist_id=keys,
        order_by=[('rank DESC', ''), ('issue_id', '')])
    role_rows = self.features_service.hotlist2user_tbl.Select(
        cnxn, cols=HOTLIST2USER_COLS, hotlist_id=keys)
    retrieved_dict = self._DeserializeHotlists(
        hotlist_rows, issue_rows, role_rows)
    return retrieved_dict


class FeaturesService(object):
  """The persistence layer for servlets in the features directory."""

  def __init__(self, cache_manager):
    """Initialize this object so that it is ready to use.

    Args:
      cache_manager: local cache with distributed invalidation.
    """
    self.quickedithistory_tbl = sql.SQLTableManager(QUICKEDITHISTORY_TABLE_NAME)
    self.quickeditmostrecent_tbl = sql.SQLTableManager(
        QUICKEDITMOSTRECENT_TABLE_NAME)

    self.savedquery_tbl = sql.SQLTableManager(SAVEDQUERY_TABLE_NAME)
    self.project2savedquery_tbl = sql.SQLTableManager(
        PROJECT2SAVEDQUERY_TABLE_NAME)
    self.savedqueryexecutesinproject_tbl = sql.SQLTableManager(
        SAVEDQUERYEXECUTESINPROJECT_TABLE_NAME)
    self.user2savedquery_tbl = sql.SQLTableManager(USER2SAVEDQUERY_TABLE_NAME)

    self.filterrule_tbl = sql.SQLTableManager(FILTERRULE_TABLE_NAME)

    self.hotlist_tbl = sql.SQLTableManager(HOTLIST_TABLE_NAME)
    self.hotlist2issue_tbl = sql.SQLTableManager(HOTLIST2ISSUE_TABLE_NAME)
    self.hotlist2user_tbl = sql.SQLTableManager(HOTLIST2USER_TABLE_NAME)

    self.saved_query_cache = cache_manager.MakeCache('user', max_size=1000)

    self.hotlist_2lc = HotlistTwoLevelCache(cache_manager, self)
    self.hotlist_names_owner_to_ids = cache_manager.MakeCache('hotlist')
    self.hotlist_user_to_ids = cache_manager.MakeCache('hotlist')

  ### QuickEdit command history

  def GetRecentCommands(self, cnxn, user_id, project_id):
    """Return recent command items for the "Redo" menu.

    Args:
      cnxn: Connection to SQL database.
      user_id: int ID of the current user.
      project_id: int ID of the current project.

    Returns:
      A pair (cmd_slots, recent_slot_num).  cmd_slots is a list of
      3-tuples that can be used to populate the "Redo" menu of the
      quick-edit dialog.  recent_slot_num indicates which of those
      slots should initially populate the command and comment fields.
    """
    # Always start with the standard 5 commands.
    history = tracker_constants.DEFAULT_RECENT_COMMANDS[:]
    # If the user has modified any, then overwrite some standard ones.
    history_rows = self.quickedithistory_tbl.Select(
        cnxn, cols=['slot_num', 'command', 'comment'],
        user_id=user_id, project_id=project_id)
    for slot_num, command, comment in history_rows:
      if slot_num < len(history):
        history[slot_num - 1] = (command, comment)

    slots = []
    for idx, (command, comment) in enumerate(history):
      slots.append((idx + 1, command, comment))

    recent_slot_num = self.quickeditmostrecent_tbl.SelectValue(
        cnxn, 'slot_num', default=1, user_id=user_id, project_id=project_id)

    return slots, recent_slot_num

  def StoreRecentCommand(
      self, cnxn, user_id, project_id, slot_num, command, comment):
    """Store the given command and comment in the user's command history."""
    self.quickedithistory_tbl.InsertRow(
        cnxn, replace=True, user_id=user_id, project_id=project_id,
        slot_num=slot_num, command=command, comment=comment)
    self.quickeditmostrecent_tbl.InsertRow(
        cnxn, replace=True, user_id=user_id, project_id=project_id,
        slot_num=slot_num)

  def ExpungeQuickEditHistory(self, cnxn, project_id):
    """Completely delete every users' quick edit history for this project."""
    self.quickeditmostrecent_tbl.Delete(cnxn, project_id=project_id)
    self.quickedithistory_tbl.Delete(cnxn, project_id=project_id)

  ### Saved User and Project Queries

  def GetSavedQueries(self, cnxn, query_ids):
    """Retrieve the specified SaveQuery PBs."""
    # TODO(jrobbins): RAM cache
    saved_queries = {}
    savedquery_rows = self.savedquery_tbl.Select(
        cnxn, cols=SAVEDQUERY_COLS, id=query_ids)
    for saved_query_tuple in savedquery_rows:
      qid, name, base_id, query = saved_query_tuple
      saved_queries[qid] = tracker_bizobj.MakeSavedQuery(
          qid, name, base_id, query)

    sqeip_rows = self.savedqueryexecutesinproject_tbl.Select(
        cnxn, cols=SAVEDQUERYEXECUTESINPROJECT_COLS,
        query_id=query_ids)
    for query_id, project_id in sqeip_rows:
      saved_queries[query_id].executes_in_project_ids.append(project_id)

    return saved_queries

  def GetSavedQuery(self, cnxn, query_id):
    """Retrieve the specified SaveQuery PB."""
    saved_queries = self.GetSavedQueries(cnxn, [query_id])
    return saved_queries.get(query_id)

  def _GetUsersSavedQueriesDict(self, cnxn, user_ids):
    """Return a dict of all SavedQuery PBs for the specified users."""
    results_dict, missed_uids = self.saved_query_cache.GetAll(user_ids)

    if missed_uids:
      savedquery_rows = self.user2savedquery_tbl.Select(
          cnxn, cols=SAVEDQUERY_COLS + ['user_id', 'subscription_mode'],
          left_joins=[('SavedQuery ON query_id = id', [])],
          order_by=[('rank', [])], user_id=missed_uids)
      sqeip_rows = self.savedqueryexecutesinproject_tbl.Select(
          cnxn, cols=SAVEDQUERYEXECUTESINPROJECT_COLS,
          query_id={row[0] for row in savedquery_rows})
      sqeip_dict = {}
      for qid, pid in sqeip_rows:
        sqeip_dict.setdefault(qid, []).append(pid)

      for saved_query_tuple in savedquery_rows:
        query_id, name, base_id, query, uid, sub_mode = saved_query_tuple
        sq = tracker_bizobj.MakeSavedQuery(
            query_id, name, base_id, query, subscription_mode=sub_mode,
            executes_in_project_ids=sqeip_dict.get(query_id, []))
        results_dict.setdefault(uid, []).append(sq)

    self.saved_query_cache.CacheAll(results_dict)
    return results_dict

  # TODO(jrobbins): change this termonology to "canned query" rather than
  # "saved" throughout the application.
  def GetSavedQueriesByUserID(self, cnxn, user_id):
    """Return a list of SavedQuery PBs for the specified user."""
    saved_queries_dict = self._GetUsersSavedQueriesDict(cnxn, [user_id])
    saved_queries = saved_queries_dict.get(user_id, [])
    return saved_queries[:]

  def GetCannedQueriesForProjects(self, cnxn, project_ids):
    """Return a dict {project_id: [saved_query]} for the specified projects."""
    # TODO(jrobbins): caching
    cannedquery_rows = self.project2savedquery_tbl.Select(
        cnxn, cols=['project_id'] + SAVEDQUERY_COLS,
        left_joins=[('SavedQuery ON query_id = id', [])],
        order_by=[('rank', [])], project_id=project_ids)

    result_dict = collections.defaultdict(list)
    for cq_row in cannedquery_rows:
      project_id = cq_row[0]
      canned_query_tuple = cq_row[1:]
      result_dict[project_id].append(
          tracker_bizobj.MakeSavedQuery(*canned_query_tuple))

    return result_dict

  def GetCannedQueriesByProjectID(self, cnxn, project_id):
    """Return the list of SavedQueries for the specified project."""
    project_ids_to_canned_queries = self.GetCannedQueriesForProjects(
        cnxn, [project_id])
    return project_ids_to_canned_queries.get(project_id, [])

  def _UpdateSavedQueries(self, cnxn, saved_queries, commit=True):
    """Store the given SavedQueries to the DB."""
    savedquery_rows = [
        (sq.query_id or None, sq.name, sq.base_query_id, sq.query)
        for sq in saved_queries]
    existing_query_ids = [sq.query_id for sq in saved_queries if sq.query_id]
    if existing_query_ids:
      self.savedquery_tbl.Delete(cnxn, id=existing_query_ids, commit=commit)

    generated_ids = self.savedquery_tbl.InsertRows(
        cnxn, SAVEDQUERY_COLS, savedquery_rows, commit=commit,
        return_generated_ids=True)
    if generated_ids:
      logging.info('generated_ids are %r', generated_ids)
      for sq in saved_queries:
        generated_id = generated_ids.pop(0)
        if not sq.query_id:
          sq.query_id = generated_id

  def UpdateCannedQueries(self, cnxn, project_id, canned_queries):
    """Update the canned queries for a project.

    Args:
      cnxn: connection to SQL database.
      project_id: int project ID of the project that contains these queries.
      canned_queries: list of SavedQuery PBs to update.
    """
    self.project2savedquery_tbl.Delete(
        cnxn, project_id=project_id, commit=False)
    self._UpdateSavedQueries(cnxn, canned_queries, commit=False)
    project2savedquery_rows = [
        (project_id, rank, sq.query_id)
        for rank, sq in enumerate(canned_queries)]
    self.project2savedquery_tbl.InsertRows(
        cnxn, PROJECT2SAVEDQUERY_COLS, project2savedquery_rows,
        commit=False)
    cnxn.Commit()

  def UpdateUserSavedQueries(self, cnxn, user_id, saved_queries):
    """Store the given saved_queries for the given user."""
    saved_query_ids = [sq.query_id for sq in saved_queries if sq.query_id]
    self.savedqueryexecutesinproject_tbl.Delete(
        cnxn, query_id=saved_query_ids, commit=False)
    self.user2savedquery_tbl.Delete(cnxn, user_id=user_id, commit=False)

    self._UpdateSavedQueries(cnxn, saved_queries, commit=False)
    user2savedquery_rows = []
    for rank, sq in enumerate(saved_queries):
      user2savedquery_rows.append(
          (user_id, rank, sq.query_id, sq.subscription_mode or 'noemail'))

    self.user2savedquery_tbl.InsertRows(
        cnxn, USER2SAVEDQUERY_COLS, user2savedquery_rows, commit=False)

    sqeip_rows = []
    for sq in saved_queries:
      for pid in sq.executes_in_project_ids:
        sqeip_rows.append((sq.query_id, pid))

    self.savedqueryexecutesinproject_tbl.InsertRows(
        cnxn, SAVEDQUERYEXECUTESINPROJECT_COLS, sqeip_rows, commit=False)
    cnxn.Commit()

    self.saved_query_cache.Invalidate(cnxn, user_id)

  ### Subscriptions

  def GetSubscriptionsInProjects(self, cnxn, project_ids):
    """Return all saved queries for users that have any subscription there.

    Args:
      cnxn: Connection to SQL database.
      project_ids: list of int project IDs that contain the modified issues.

    Returns:
      A dict {user_id: all_saved_queries, ...} for all users that have any
      subscription in any of the specified projects.
    """
    join_str = (
        'SavedQueryExecutesInProject ON '
        'SavedQueryExecutesInProject.query_id = User2SavedQuery.query_id')
    # TODO(jrobbins): cache this since it rarely changes.
    subscriber_rows = self.user2savedquery_tbl.Select(
        cnxn, cols=['user_id'], distinct=True,
        joins=[(join_str, [])],
        subscription_mode='immediate', project_id=project_ids)
    subscriber_ids = [row[0] for row in subscriber_rows]
    logging.info('subscribers relevant to projects %r are %r',
                 project_ids, subscriber_ids)
    user_ids_to_saved_queries = self._GetUsersSavedQueriesDict(
        cnxn, subscriber_ids)
    return user_ids_to_saved_queries

  def ExpungeSavedQueriesExecuteInProject(self, cnxn, project_id):
    """Remove any references from saved queries to projects in the database."""
    self.savedqueryexecutesinproject_tbl.Delete(cnxn, project_id=project_id)

    savedquery_rows = self.project2savedquery_tbl.Select(
        cnxn, cols=['query_id'], project_id=project_id)
    savedquery_ids = [row[0] for row in savedquery_rows]
    self.project2savedquery_tbl.Delete(cnxn, project_id=project_id)
    self.savedquery_tbl.Delete(cnxn, id=savedquery_ids)

  ### Filter rules

  def _DeserializeFilterRules(self, filterrule_rows):
    """Convert the given DB row tuples into PBs."""
    result_dict = collections.defaultdict(list)

    for filterrule_row in sorted(filterrule_rows):
      project_id, _rank, predicate, consequence = filterrule_row
      (default_status, default_owner_id, add_cc_ids, add_labels,
       add_notify) = self._DeserializeRuleConsequence(consequence)
      rule = filterrules_helpers.MakeRule(
          predicate, default_status=default_status,
          default_owner_id=default_owner_id, add_cc_ids=add_cc_ids,
          add_labels=add_labels, add_notify=add_notify)
      result_dict[project_id].append(rule)

    return result_dict

  def _DeserializeRuleConsequence(self, consequence):
    """Decode the THEN-part of a filter rule."""
    (default_status, default_owner_id, add_cc_ids, add_labels,
     add_notify) = None, None, [], [], []
    for action in consequence.split():
      verb, noun = action.split(':')
      if verb == 'default_status':
        default_status = noun
      elif verb == 'default_owner_id':
        default_owner_id = int(noun)
      elif verb == 'add_cc_id':
        add_cc_ids.append(int(noun))
      elif verb == 'add_label':
        add_labels.append(noun)
      elif verb == 'add_notify':
        add_notify.append(noun)

    return (default_status, default_owner_id, add_cc_ids, add_labels,
            add_notify)

  def _GetFilterRulesByProjectIDs(self, cnxn, project_ids):
    """Return {project_id: [FilterRule, ...]} for the specified projects."""
    # TODO(jrobbins): caching
    filterrule_rows = self.filterrule_tbl.Select(
        cnxn, cols=FILTERRULE_COLS, project_id=project_ids)
    return self._DeserializeFilterRules(filterrule_rows)

  def GetFilterRules(self, cnxn, project_id):
    """Return a list of FilterRule PBs for the specified project."""
    rules_by_project_id = self._GetFilterRulesByProjectIDs(cnxn, [project_id])
    return rules_by_project_id[project_id]

  def _SerializeRuleConsequence(self, rule):
    """Put all actions of a filter rule into one string."""
    assignments = []
    for add_lab in rule.add_labels:
      assignments.append('add_label:%s' % add_lab)
    if rule.default_status:
      assignments.append('default_status:%s' % rule.default_status)
    if rule.default_owner_id:
      assignments.append('default_owner_id:%d' % rule.default_owner_id)
    for add_cc_id in rule.add_cc_ids:
      assignments.append('add_cc_id:%d' % add_cc_id)
    for add_notify in rule.add_notify_addrs:
      assignments.append('add_notify:%s' % add_notify)

    return ' '.join(assignments)

  def UpdateFilterRules(self, cnxn, project_id, rules):
    """Update the filter rules part of a project's issue configuration.

    Args:
      cnxn: connection to SQL database.
      project_id: int ID of the current project.
      rules: a list of FilterRule PBs.
    """
    rows = []
    for rank, rule in enumerate(rules):
      predicate = rule.predicate
      consequence = self._SerializeRuleConsequence(rule)
      if predicate and consequence:
        rows.append((project_id, rank, predicate, consequence))

    self.filterrule_tbl.Delete(cnxn, project_id=project_id)
    self.filterrule_tbl.InsertRows(cnxn, FILTERRULE_COLS, rows)

  def ExpungeFilterRules(self, cnxn, project_id):
    """Completely destroy filter rule info for the specified project."""
    self.filterrule_tbl.Delete(cnxn, project_id=project_id)

  ### Creating hotlists

  def CreateHotlist(
      self, cnxn, name, summary, description, owner_ids, editor_ids,
      issue_ids=None, is_private=None, default_col_spec=None):
    """Create and store a Hotlist with the given attributes.

    Args:
      cnxn: connection to SQL database.
      name: a valid hotlist name.
      summary: one-line explanation of the hotlist.
      description: one-page explanation of the hotlist.
      owner_ids: a list of user IDs for the hotlist owners.
      editor_ids: a list of user IDs for the hotlist editors.
      issue_ids: a list of issue IDs for the hotlist issues.
      is_private: True if the hotlist can only be viewed by owners and editors.
      default_col_spec: the default columns that show in list view.

    Returns:
      The int id of the new hotlist.

    Raises:
      HotlistAlreadyExists: if any of the owners already own a hotlist with
        the same name.
    """
    assert framework_bizobj.IsValidHotlistName(name)
    if self.LookupHotlistIDs(cnxn, [name], owner_ids):
      raise HotlistAlreadyExists()

    iid_rank_pairs = [
        (issue_id, rank*100) for rank, issue_id in enumerate(issue_ids or [])]
    if default_col_spec is None:
      default_col_spec = features_constants.DEFAULT_COL_SPEC
    hotlist = features_pb2.MakeHotlist(
        name, iid_rank_pairs=iid_rank_pairs, summary=summary,
        description=description, is_private=is_private, owner_ids=owner_ids,
        editor_ids=editor_ids, default_col_spec=default_col_spec)
    hotlist.hotlist_id = self._InsertHotlist(cnxn, hotlist)
    return hotlist.hotlist_id

  def UpdateHotlist(
      self, cnxn, hotlist_id, name=None, summary=None, description=None,
      is_private=None, default_col_spec=None):
    """Update the DB with the given hotlist information."""
    # Note: If something is None, it does not get changed to None,
    # it just does not get updated.
    hotlist = self.GetHotlist(cnxn, hotlist_id, use_cache=False)
    if not hotlist:
      raise NoSuchHotlistException()

    delta = {}
    if name is not None:
      delta['name'] = name
    if summary is not None:
      delta['summary'] = summary
    if description is not None:
      delta['description'] = description
    if is_private is not None:
      delta['is_private'] = is_private
    if default_col_spec is not None:
      delta['default_col_spec'] = default_col_spec

    self.hotlist_tbl.Update(cnxn, delta, id=hotlist_id)

    self.hotlist_2lc.InvalidateKeys(cnxn, [hotlist_id])

    # Update the hotlist PB in RAM
    if name is not None:
      hotlist.name = name
    if summary is not None:
      hotlist.summary = summary
    if description is not None:
      hotlist.description = description
    if is_private is not None:
      hotlist.is_private = is_private
    if default_col_spec is not None:
      hotlist.default_col_spec = default_col_spec

  def UpdateHotlistIssues(
      self, cnxn, hotlist_id, remove, added_pairs, commit=True):
    """Updates a hotlist's list of hotlistissues.

    Args:
      cnxn: connection to SQL database.
      hotlist_id: the ID of the hotlist to update
      remove: a list of issue_ids for be removed
      added_pairs: a list of (issue_id, pairs) for issues to be added
    """
    hotlist = self.GetHotlist(cnxn, hotlist_id, use_cache=False)
    if not hotlist:
      raise NoSuchHotlistException()

    # adding new Hotlistissues, ignoring pairs where issue_id is already in
    # hotlist's iid_rank_pairs
    current_issues_ids = {
        iid_rank_pair.issue_id for iid_rank_pair in hotlist.iid_rank_pairs}

    self.hotlist2issue_tbl.Delete(
        cnxn, hotlist_id=hotlist_id,
        issue_id=[remove_id for remove_id in remove
                  if remove_id in current_issues_ids],
        commit=False)

    insert_rows = [
        (hotlist_id, issue_id, rank)
        for (issue_id, rank) in added_pairs
        if issue_id not in current_issues_ids]
    self.hotlist2issue_tbl.InsertRows(
        cnxn, cols=HOTLIST2ISSUE_COLS, row_values=insert_rows, commit=commit)
    self.hotlist_2lc.InvalidateKeys(cnxn, [hotlist_id])

    # removing an issue that was never in the hotlist would not cause any
    # problems.
    iid_rank_pairs = [
        iid_rank_pair for iid_rank_pair in hotlist.iid_rank_pairs if
        iid_rank_pair.issue_id not in remove]

    new_hotlist_issues = [
        features_pb2.MakeHotlistIssue(issue_id, rank)
        for (issue_id, rank) in added_pairs
        if issue_id not in current_issues_ids]
    iid_rank_pairs.extend(new_hotlist_issues)
    hotlist.iid_rank_pairs = iid_rank_pairs

  def UpdateHotlistIssuesRankings(
      self, cnxn, hotlist_id, relations_to_change, commit=True):
    """Updates rankings of hotlistissues.

    Args:
      cnxn: connection to SQL database.
      hotlist_id: the ID of the hotlist to update
      relations_to_change: This should be a dictionary of {issue_id: rank,...}
        of relations that need to be changed.
      commit: set to False to skip the DB commit and do it in the caller.
    """
    hotlist = self.GetHotlist(cnxn, hotlist_id, use_cache=False)
    if not hotlist:
      raise NoSuchHotlistException()

    issue_ids = relations_to_change.keys()
    self.hotlist2issue_tbl.Delete(
        cnxn, hotlist_id=hotlist_id, issue_id=issue_ids, commit=False)
    insert_rows = [
        (hotlist_id, issue_id, relations_to_change[
            issue_id]) for issue_id in issue_ids]
    self.hotlist2issue_tbl.InsertRows(
        cnxn, cols=HOTLIST2ISSUE_COLS , row_values=insert_rows, commit=commit)

    self.hotlist_2lc.InvalidateKeys(cnxn, [hotlist_id])

    # Update the hotlist PB in RAM
    rank_pairs = hotlist.iid_rank_pairs
    for hotlist_issue in rank_pairs:
      if hotlist_issue.issue_id in relations_to_change:
        hotlist_issue.rank = relations_to_change[hotlist_issue.issue_id]

  def _InsertHotlist(self, cnxn, hotlist):
    """Insert the given hotlist into the database."""
    hotlist_id = self.hotlist_tbl.InsertRow(
        cnxn, name=hotlist.name, summary=hotlist.summary,
        description=hotlist.description, is_private=hotlist.is_private,
        default_col_spec=hotlist.default_col_spec)
    logging.info('stored hotlist was given id %d', hotlist_id)

    self.hotlist2issue_tbl.InsertRows(
        cnxn, HOTLIST2ISSUE_COLS,
        [(hotlist_id, issue.issue_id, issue.rank)
         for issue in hotlist.iid_rank_pairs],
        commit=False)
    self.hotlist2user_tbl.InsertRows(
        cnxn, HOTLIST2USER_COLS,
        [(hotlist_id, user_id, 'owner')
         for user_id in hotlist.owner_ids] +
        [(hotlist_id, user_id, 'editor')
         for user_id in hotlist.editor_ids] +
        [(hotlist_id, user_id, 'follower')
         for user_id in hotlist.follower_ids])

    self.hotlist_user_to_ids.InvalidateKeys(cnxn, hotlist.owner_ids)

    return hotlist_id

  ### Lookup hotlist IDs

  def LookupHotlistIDs(self, cnxn, hotlist_names, owner_ids):
    """Return a dict of (name, owner_id) mapped to hotlist_id for all hotlists
    with one of the given names and any of the given owners. Hotlists that
    match multiple owners will be in the dict multiple times."""
    id_dict, missed_keys = self.hotlist_names_owner_to_ids.GetAll(
        [(name.lower(), owner_id)
         for name in hotlist_names for owner_id in owner_ids])
    if missed_keys:
      missed_names, missed_owners = map(list, zip(*missed_keys))
      hotlist_rows = self.hotlist_tbl.Select(
          cnxn, cols=['id', 'name'], name=missed_names)
      if hotlist_rows:
        id_to_name = dict(hotlist_rows)
        hotlist_ids = [row[0] for row in hotlist_rows]
        role_rows = self.hotlist2user_tbl.Select(
            cnxn, cols=['hotlist_id', 'user_id'], hotlist_id=hotlist_ids,
            user_id=missed_owners, role_name='owner')
        retrieved_dict = {
            (id_to_name[hotlist_id], owner_id) : hotlist_id
            for (hotlist_id, owner_id) in role_rows}
        to_cache = {
            (name.lower(), owner_id) : hotlist_id
            for ((name, owner_id), hotlist_id) in retrieved_dict.items()}
        self.hotlist_names_owner_to_ids.CacheAll(to_cache)
        id_dict.update(retrieved_dict)

    return id_dict

  def LookupUserHotlists(self, cnxn, user_ids):
    """Return a dict of {user_id: [hotlist_id,...]} for all user_ids."""
    id_dict, missed_ids = self.hotlist_user_to_ids.GetAll(user_ids)
    if missed_ids:
      retrieved_dict = {user_id: [] for user_id in missed_ids}
      id_rows = self.hotlist2user_tbl.Select(
          cnxn, cols=['user_id', 'hotlist_id'], user_id=user_ids)
      for (user_id, hotlist_id) in id_rows:
        retrieved_dict[user_id].append(hotlist_id)
      self.hotlist_user_to_ids.CacheAll(retrieved_dict)
      id_dict.update(retrieved_dict)

    return id_dict

  ### Get hotlists

  def GetHotlists(self, cnxn, hotlist_ids, use_cache=True):
    """Returns dict of {hotlist_id: hotlist PB}."""
    hotlists_dict, missed_ids = self.hotlist_2lc.GetAll(
        cnxn, hotlist_ids, use_cache=use_cache)

    if missed_ids:
      raise NoSuchHotlistException()

    return hotlists_dict

  def GetHotlistsByUserID(self, cnxn, user_id, use_cache=True):
    """Get a list of hotlist PBs for a given user."""
    hotlist_id_dict = self.LookupUserHotlists(cnxn, [user_id])
    hotlists = self.GetHotlists(
        cnxn, hotlist_id_dict.get(user_id, []), use_cache=use_cache)
    return hotlists.values()

  def GetHotlist(self, cnxn, hotlist_id, use_cache=True):
    """Returns hotlist PB."""
    hotlist_dict = self.GetHotlists(cnxn, [hotlist_id], use_cache=use_cache)
    return hotlist_dict[hotlist_id]

  def GetHotlistsByID(self, cnxn, hotlist_ids, use_cache=True):
    """Load all the Hotlist PBs for the given hotlists.

    Args:
      cnxn: connection to SQL database.
      hotlist_ids: list of hotlist ids.
      use_cache: specifiy False to force database query.

    Returns:
      A dict mapping ids to the corresponding Hotlist protocol buffers and
      a list of any hotlist_ids that were not found.
    """
    hotlists_dict, missed_ids = self.hotlist_2lc.GetAll(
        cnxn, hotlist_ids, use_cache=use_cache)
    return hotlists_dict, missed_ids

  def GetHotlistByID(self, cnxn, hotlist_id, use_cache=True):
    """Load the specified hotlist from the database, None if does not exist."""
    hotlist_dict, _ = self.GetHotlistsByID(
        cnxn, [hotlist_id], use_cache=use_cache)
    return hotlist_dict.get(hotlist_id)

  def UpdateHotlistRoles(
      self, cnxn, hotlist_id, owner_ids, editor_ids, follower_ids):
    """"Store the hotlist's roles in the DB."""
    # This will be a newly contructed object, not from the cache and not
    # shared with any other thread.
    hotlist = self.GetHotlist(cnxn, hotlist_id, use_cache=False)
    if not hotlist:
      raise NoSuchHotlistException()

    self.hotlist2user_tbl.Delete(
        cnxn, hotlist_id=hotlist_id, role_name='owner', commit=False)
    self.hotlist2user_tbl.Delete(
        cnxn, hotlist_id=hotlist_id, role_name='editor', commit=False)
    self.hotlist2user_tbl.Delete(
        cnxn, hotlist_id=hotlist_id, role_name='follower', commit=False)

    self.hotlist2user_tbl.InsertRows(
        cnxn, ['hotlist_id', 'user_id', 'role_name'],
        [(hotlist_id, user_id, 'owner') for user_id in owner_ids],
        commit=False)
    self.hotlist2user_tbl.InsertRows(
        cnxn, ['hotlist_id', 'user_id', 'role_name'],
        [(hotlist_id, user_id, 'editor') for user_id in editor_ids],
        commit=False)
    self.hotlist2user_tbl.InsertRows(
        cnxn, ['hotlist_id', 'user_id', 'role_name'],
        [(hotlist_id, user_id, 'follower') for user_id in follower_ids],
        commit=False)

    cnxn.Commit()
    self.hotlist_2lc.InvalidateKeys(cnxn, [hotlist_id])
    hotlist.owner_ids = owner_ids
    hotlist.editor_ids = editor_ids
    hotlist.follower_ids = follower_ids


class HotlistAlreadyExists(Exception):
  """Tried to create a hotlist with the same name as another hotlist
  with the same owner."""
  pass

class NoSuchHotlistException(Exception):
  """The requested hotlist was not found."""
  pass
