# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A class that provides persistence for Monorail's additional features.

Business objects are described in tracker_pb2.py and tracker_bizobj.py.
"""

import collections
import logging

from features import filterrules_helpers
from framework import sql
from tracker import tracker_bizobj
from tracker import tracker_constants

QUICKEDITHISTORY_TABLE_NAME = 'QuickEditHistory'
QUICKEDITMOSTRECENT_TABLE_NAME = 'QuickEditMostRecent'
SAVEDQUERY_TABLE_NAME = 'SavedQuery'
PROJECT2SAVEDQUERY_TABLE_NAME = 'Project2SavedQuery'
SAVEDQUERYEXECUTESINPROJECT_TABLE_NAME = 'SavedQueryExecutesInProject'
USER2SAVEDQUERY_TABLE_NAME = 'User2SavedQuery'
FILTERRULE_TABLE_NAME = 'FilterRule'
FILTERRULE_COLS = ['project_id', 'rank', 'predicate', 'consequence']


QUICKEDITHISTORY_COLS = [
    'user_id', 'project_id', 'slot_num', 'command', 'comment']
QUICKEDITMOSTRECENT_COLS = ['user_id', 'project_id', 'slot_num']
SAVEDQUERY_COLS = ['id', 'name', 'base_query_id', 'query']
PROJECT2SAVEDQUERY_COLS = ['project_id', 'rank', 'query_id']
SAVEDQUERYEXECUTESINPROJECT_COLS = ['query_id', 'project_id']
USER2SAVEDQUERY_COLS = ['user_id', 'rank', 'query_id', 'subscription_mode']


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

    self.saved_query_cache = cache_manager.MakeCache('user', max_size=1000)

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
    return saved_queries[query_id]

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
