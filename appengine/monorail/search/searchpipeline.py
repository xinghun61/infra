# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Helper functions and classes used in issue search and sorting."""

import logging
import re

from features import savedqueries_helpers
from search import query2ast
from services import tracker_fulltext
from services import fulltext_helpers
from tracker import tracker_helpers


# Users can use "is:starred" in queries to limit
# search results to issues starred by that user.
IS_STARRED_RE = re.compile(r'\b(?![-@.:])is:starred\b(?![-@.:])', re.I)

# Users can use "me" in other fields to refer to the logged in user name.
ME_RE = re.compile(r'(?<=[=:])me\b(?![-@.:=])', re.I)


def _AccumulateIssueProjectsAndConfigs(
    cnxn, project_dict, config_dict, services, issues):
  """Fetch any projects and configs that we need but haven't already loaded.

  Args:
    cnxn: connection to SQL database.
    project_dict: dict {project_id: project} of projects that we have
        already retrieved.
    config_dict: dict {project_id: project} of configs that we have
        already retrieved.
    services: connections to backends.
    issues: list of issues, which may be parts of different projects.

  Returns:
    Nothing, but projects_dict will be updated to include all the projects that
    contain the given issues, and config_dicts will be updated to incude all
    the corresponding configs.
  """
  new_ids = {issue.project_id for issue in issues}
  new_ids.difference_update(project_dict.iterkeys())
  new_projects_dict = services.project.GetProjects(cnxn, new_ids)
  project_dict.update(new_projects_dict)
  new_configs_dict = services.config.GetProjectConfigs(cnxn, new_ids)
  config_dict.update(new_configs_dict)


def ReplaceKeywordsWithUserID(me_user_id, query):
  """Substitutes User ID in terms such as is:starred and me.

  This is done on the query string before it is parsed because the query string
  is used as a key for cached search results in memcache.  A search for by one
  user for owner:me should not retrieve results stored for some other user.

  Args:
    me_user_id: Null when no user is logged in, or user ID of the logged in
        user when doing an interactive search, or the viewed user ID when
        viewing someone else's dashboard, or the subscribing user's ID when
        evaluating subscriptions.
    query: The query string.

  Returns:
    A string with "me" and "is:starred" removed or replaced by new terms that
    use the numeric user ID provided.
  """
  if me_user_id:
    star_term = 'starredby:%d' % me_user_id
    query = IS_STARRED_RE.sub(star_term, query)
    query = ME_RE.sub(str(me_user_id), query)
  else:
    query = IS_STARRED_RE.sub('', query)
    query = ME_RE.sub('', query)

  return query


def ParseQuery(mr, config, services):
  """Parse the user's query.

  Args:
    mr: commonly used info parsed from the request.
    config: The ProjectConfig PB for the project.
    services: connections to backends.

  Returns:
    A pair (ast, is_fulltext) with the parsed query abstract syntax tree
    and a boolean that is True if the query included any fulltext terms.
  """
  canned_query = savedqueries_helpers.SavedQueryIDToCond(
    mr.cnxn, services.features, mr.can)
  query_ast = query2ast.ParseUserQuery(
    mr.query, canned_query, query2ast.BUILTIN_ISSUE_FIELDS, config)

  is_fulltext_query = bool(
    query_ast.conjunctions and
    fulltext_helpers.BuildFTSQuery(
      query_ast.conjunctions[0], tracker_fulltext.ISSUE_FULLTEXT_FIELDS))

  return query_ast, is_fulltext_query

