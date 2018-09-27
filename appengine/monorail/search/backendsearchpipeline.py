# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Backend issue issue search and sorting.

Each of several "besearch" backend jobs manages one shard of the overall set
of issues in the system. The backend search pipeline retrieves the issues
that match the user query, puts them into memcache, and returns them to
the frontend search pipeline.
"""

import logging
import re
import time

from google.appengine.api import memcache

import settings
from features import savedqueries_helpers
from framework import authdata
from framework import framework_constants
from framework import framework_helpers
from framework import sorting
from framework import sql
from proto import ast_pb2
from proto import tracker_pb2
from search import ast2ast
from search import ast2select
from search import ast2sort
from search import query2ast
from search import searchpipeline
from services import tracker_fulltext
from services import fulltext_helpers
from tracker import tracker_bizobj


# Used in constructing the at-risk query.
AT_RISK_LABEL_RE = re.compile(r'^(restrict-view-.+)$', re.IGNORECASE)

# Limit on the number of list items to show in debug log statements
MAX_LOG = 200


class BackendSearchPipeline(object):
  """Manage the process of issue search, including Promises and caching.

  Even though the code is divided into several methods, the public
  methods should be called in sequence, so the execution of the code
  is pretty much in the order of the source code lines here.
  """

  def __init__(
      self, mr, services, default_results_per_page,
      query_project_names, logged_in_user_id, me_user_id):

    self.mr = mr
    self.services = services
    self.default_results_per_page = default_results_per_page

    self.query_project_list = services.project.GetProjectsByName(
        mr.cnxn, query_project_names).values()
    self.query_project_ids = [
        p.project_id for p in self.query_project_list]

    self.me_user_id = me_user_id
    self.mr.auth = authdata.AuthData.FromUserID(
        mr.cnxn, logged_in_user_id, services)

    # The following fields are filled in as the pipeline progresses.
    # The value None means that we still need to compute that value.
    self.result_iids = None  # Sorted issue IDs that match the query
    self.search_limit_reached = False  # True if search results limit is hit.
    self.error = None

    self._MakePromises()

  def _MakePromises(self):
    config_dict = self.services.config.GetProjectConfigs(
        self.mr.cnxn, self.query_project_ids)
    self.harmonized_config = tracker_bizobj.HarmonizeConfigs(
        config_dict.values())

    self.canned_query = savedqueries_helpers.SavedQueryIDToCond(
        self.mr.cnxn, self.services.features, self.mr.can)

    self.canned_query, warnings = searchpipeline.ReplaceKeywordsWithUserID(
        self.me_user_id, self.canned_query)
    self.mr.warnings.extend(warnings)
    self.user_query, warnings = searchpipeline.ReplaceKeywordsWithUserID(
        self.me_user_id, self.mr.query)
    self.mr.warnings.extend(warnings)
    logging.debug('Searching query: %s %s', self.canned_query, self.user_query)

    slice_term = ('Issue.shard = %s', [self.mr.shard_id])

    sd = sorting.ComputeSortDirectives(
        self.harmonized_config, self.mr.group_by_spec, self.mr.sort_spec)

    self.result_iids_promise = framework_helpers.Promise(
        _GetQueryResultIIDs, self.mr.cnxn,
        self.services, self.canned_query, self.user_query,
        self.query_project_ids, self.harmonized_config, sd,
        slice_term, self.mr.shard_id, self.mr.invalidation_timestep)

  def SearchForIIDs(self):
    """Wait for the search Promises and store their results."""
    with self.mr.profiler.Phase('WaitOnPromises'):
      self.result_iids, self.search_limit_reached, self.error = (
          self.result_iids_promise.WaitAndGetValue())


def SearchProjectCan(
    cnxn, services, project_ids, query_ast, shard_id, harmonized_config,
    left_joins=None, where=None, sort_directives=None, query_desc=''):
  """Return a list of issue global IDs in the projects that satisfy the query.

  Args:
    cnxn: Regular database connection to the master DB.
    services: interface to issue storage backends.
    project_ids: list of int IDs of the project to search
    query_ast: A QueryAST PB with conjunctions and conditions.
    shard_id: limit search to the specified shard ID int.
    harmonized_config: harmonized config for all projects being searched.
    left_joins: SQL LEFT JOIN clauses that are needed in addition to
        anything generated from the query_ast.
    where: SQL WHERE clauses that are needed in addition to
        anything generated from the query_ast.
    sort_directives: list of strings specifying the columns to sort on.
    query_desc: descriptive string for debugging.

  Returns:
    (issue_ids, capped, error) where issue_ids is a list of issue issue_ids
    that satisfy the query, capped is True if the number of results were
    capped due to an implementation limit, and error is any well-known error
    (probably a query parsing error) encountered during search.
  """
  logging.info('searching projects %r for AST %r', project_ids, query_ast)
  start_time = time.time()
  left_joins = left_joins or []
  where = where or []
  if project_ids:
    cond_str = 'Issue.project_id IN (%s)' % sql.PlaceHolders(project_ids)
    where.append((cond_str, project_ids))

  try:
    query_ast = ast2ast.PreprocessAST(
        cnxn, query_ast, project_ids, services, harmonized_config)
    logging.info('simplified AST is %r', query_ast)
    query_left_joins, query_where, _ = ast2select.BuildSQLQuery(query_ast)
    left_joins.extend(query_left_joins)
    where.extend(query_where)
  except ast2ast.MalformedQuery as e:
    # TODO(jrobbins): inform the user that their query had invalid tokens.
    logging.info('Invalid query tokens %s.\n %r\n\n', e.message, query_ast)
    return [], False, e
  except ast2select.NoPossibleResults as e:
    # TODO(jrobbins): inform the user that their query was impossible.
    logging.info('Impossible query %s.\n %r\n\n', e.message, query_ast)
    return [], False, e
  logging.info('translated to left_joins %r', left_joins)
  logging.info('translated to where %r', where)

  fts_capped = False
  if query_ast.conjunctions:
    # TODO(jrobbins): Handle "OR" in queries.  For now, we just process the
    # first conjunction.
    assert len(query_ast.conjunctions) == 1
    conj = query_ast.conjunctions[0]
    full_text_iids, fts_capped = tracker_fulltext.SearchIssueFullText(
        project_ids, conj, shard_id)
    if full_text_iids is not None:
      if not full_text_iids:
        return [], False, None  # No match on fulltext, so don't bother DB.
      cond_str = 'Issue.id IN (%s)' % sql.PlaceHolders(full_text_iids)
      where.append((cond_str, full_text_iids))

  label_def_rows = []
  status_def_rows = []
  if sort_directives:
    if project_ids:
      for pid in project_ids:
        label_def_rows.extend(services.config.GetLabelDefRows(cnxn, pid))
        status_def_rows.extend(services.config.GetStatusDefRows(cnxn, pid))
    else:
      label_def_rows = services.config.GetLabelDefRowsAnyProject(cnxn)
      status_def_rows = services.config.GetStatusDefRowsAnyProject(cnxn)

  harmonized_labels = tracker_bizobj.HarmonizeLabelOrStatusRows(
      label_def_rows)
  harmonized_statuses = tracker_bizobj.HarmonizeLabelOrStatusRows(
      status_def_rows)
  harmonized_fields = harmonized_config.field_defs
  sort_left_joins, order_by = ast2sort.BuildSortClauses(
      sort_directives, harmonized_labels, harmonized_statuses,
      harmonized_fields)
  logging.info('translated to sort left_joins %r', sort_left_joins)
  logging.info('translated to order_by %r', order_by)

  issue_ids, db_capped = services.issue.RunIssueQuery(
      cnxn, left_joins + sort_left_joins, where, order_by, shard_id=shard_id)
  logging.warn('executed "%s" query %r for %d issues in %dms',
               query_desc, query_ast, len(issue_ids),
               int((time.time() - start_time) * 1000))
  capped = fts_capped or db_capped
  return issue_ids, capped, None

def _FilterSpam(query_ast):
  uses_spam = False
  # TODO(jrobbins): Handle "OR" in queries.  For now, we just modify the
  # first conjunction.
  conjunction = query_ast.conjunctions[0]
  for condition in conjunction.conds:
    for field in condition.field_defs:
      if field.field_name == 'spam':
        uses_spam = True

  if not uses_spam:
    query_ast.conjunctions[0].conds.append(
        ast_pb2.MakeCond(
            ast_pb2.QueryOp.NE,
            [tracker_pb2.FieldDef(
                field_name='spam',
                field_type=tracker_pb2.FieldTypes.BOOL_TYPE)
             ],
        [], []))

  return query_ast

def _GetQueryResultIIDs(
    cnxn, services, canned_query, user_query,
    query_project_ids, harmonized_config, sd, slice_term,
    shard_id, invalidation_timestep):
  """Do a search and return a list of matching issue IDs.

  Args:
    cnxn: connection to the database.
    services: interface to issue storage backends.
    canned_query: string part of the query from the drop-down menu.
    user_query: string part of the query that the user typed in.
    query_project_ids: list of project IDs to search.
    harmonized_config: combined configs for all the queried projects.
    sd: list of sort directives.
    slice_term: additional query term to narrow results to a logical shard
        within a physical shard.
    shard_id: int number of the database shard to search.
    invalidation_timestep: int timestep to use keep memcached items fresh.

  Returns:
    Tuple consisting of:
      A list of issue issue_ids that match the user's query.  An empty list, [],
      is returned if no issues match the query.
      Boolean that is set to True if the search results limit of this shard is
      hit.
      An error (subclass of Exception) encountered during query processing. None
      means that no error was encountered.
  """
  query_ast = _FilterSpam(query2ast.ParseUserQuery(
      user_query, canned_query, query2ast.BUILTIN_ISSUE_FIELDS,
      harmonized_config))

  logging.info('query_project_ids is %r', query_project_ids)

  is_fulltext_query = bool(
    query_ast.conjunctions and
    fulltext_helpers.BuildFTSQuery(
      query_ast.conjunctions[0], tracker_fulltext.ISSUE_FULLTEXT_FIELDS))
  expiration = framework_constants.MEMCACHE_EXPIRATION
  if is_fulltext_query:
    expiration = framework_constants.FULLTEXT_MEMCACHE_EXPIRATION

  # Might raise ast2ast.MalformedQuery or ast2select.NoPossibleResults.
  result_iids, search_limit_reached, error = SearchProjectCan(
      cnxn, services, query_project_ids, query_ast, shard_id,
      harmonized_config, sort_directives=sd, where=[slice_term],
      query_desc='getting query issue IDs')
  logging.info('Found %d result_iids', len(result_iids))
  if error:
    logging.warn('Got error %r', error)

  projects_str = ','.join(str(pid) for pid in sorted(query_project_ids))
  projects_str = projects_str or 'all'
  memcache_key = ';'.join([
      projects_str, canned_query, user_query, ' '.join(sd), str(shard_id)])
  memcache.set(memcache_key, (result_iids, invalidation_timestep),
               time=expiration, namespace=settings.memcache_namespace)
  logging.info('set memcache key %r', memcache_key)

  search_limit_memcache_key = ';'.join([
      projects_str, canned_query, user_query, ' '.join(sd),
      'search_limit_reached', str(shard_id)])
  memcache.set(search_limit_memcache_key,
               (search_limit_reached, invalidation_timestep),
               time=expiration, namespace=settings.memcache_namespace)
  logging.info('set search limit memcache key %r',
               search_limit_memcache_key)

  timestamps_for_projects = memcache.get_multi(
      keys=(['%d;%d' % (pid, shard_id) for pid in query_project_ids] +
            ['all:%d' % shard_id]),
      namespace=settings.memcache_namespace)

  if query_project_ids:
    for pid in query_project_ids:
      key = '%d;%d' % (pid, shard_id)
      if key not in timestamps_for_projects:
        memcache.set(
            key, invalidation_timestep,
            time=framework_constants.MEMCACHE_EXPIRATION,
            namespace=settings.memcache_namespace)
  else:
    key = 'all;%d' % shard_id
    if key not in timestamps_for_projects:
      memcache.set(
          key, invalidation_timestep,
          time=framework_constants.MEMCACHE_EXPIRATION,
          namespace=settings.memcache_namespace)

  return result_iids, search_limit_reached, error
