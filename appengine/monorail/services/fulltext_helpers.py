# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A set of helpers functions for fulltext search."""

import logging

from google.appengine.api import search

import settings
from proto import ast_pb2
from proto import tracker_pb2
from search import query2ast

# GAE search API can only respond with 500 results per call.
_SEARCH_RESULT_CHUNK_SIZE = 500


def BuildFTSQuery(query_ast_conj, fulltext_fields):
  """Convert a Monorail query AST into a GAE search query string.

  Args:
    query_ast_conj: a Conjunction PB with a list of Comparison PBs that each
        have operator, field definitions, string values, and int values.
        All Conditions should be AND'd together.
    fulltext_fields: a list of string names of fields that may exist in the
        fulltext documents.  E.g., issue fulltext documents have a "summary"
        field.

  Returns:
    A string that can be passed to AppEngine's search API. Or, None if there
    were no fulltext conditions, so no fulltext search should be done.
  """
  fulltext_parts = [
      _BuildFTSCondition(cond, fulltext_fields)
      for cond in query_ast_conj.conds]
  if any(fulltext_parts):
    return ' '.join(fulltext_parts)
  else:
    return None


def _BuildFTSCondition(cond, fulltext_fields):
  """Convert one query AST condition into a GAE search query string."""
  if cond.op == ast_pb2.QueryOp.NOT_TEXT_HAS:
    neg = 'NOT '
  elif cond.op == ast_pb2.QueryOp.TEXT_HAS:
    neg = ''
  else:
    return ''  # FTS only looks at TEXT_HAS and NOT_TEXT_HAS

  parts = []

  for fd in cond.field_defs:
    if fd.field_name in fulltext_fields:
      pattern = fd.field_name + ':"%s"'
    elif fd.field_name == ast_pb2.ANY_FIELD:
      pattern = '"%s"'
    elif fd.field_id and fd.field_type == tracker_pb2.FieldTypes.STR_TYPE:
      pattern = 'custom_' + str(fd.field_id) + ':"%s"'
    else:
      pattern = 'pylint does not handle else-continue'
      continue  # This issue field is searched via SQL.

    for value in cond.str_values:
      # Strip out quotes around the value.
      value = value.strip('"')
      special_prefixes_match = any(
          value.startswith(p) for p in query2ast.NON_OP_PREFIXES)
      if not special_prefixes_match:
        value = value.replace(':', ' ')
        assert ('"' not in value), 'Value %r has a quote in it' % value
      parts.append(pattern % value)

  if parts:
    return neg + '(%s)' % ' OR '.join(parts)
  else:
    return ''  # None of the fields were fulltext fields.


def ComprehensiveSearch(fulltext_query, index_name):
  """Call the GAE search API, and keep calling it to get all results.

  Args:
    fulltext_query: string in the GAE search API query language.
    index_name: string name of the GAE fulltext index to hit.

  Returns:
    A list of integer issue IIDs or project IDs.
  """
  search_index = search.Index(name=index_name)

  try:
    response = search_index.search(search.Query(
        fulltext_query,
        options=search.QueryOptions(
            limit=_SEARCH_RESULT_CHUNK_SIZE, returned_fields=[], ids_only=True,
            cursor=search.Cursor())))
  except ValueError as e:
    raise query2ast.InvalidQueryError(e.message)

  logging.info('got %d initial results', len(response.results))
  ids = [int(result.doc_id) for result in response]

  remaining_iterations = int(
      settings.fulltext_limit_per_shard - 1 / _SEARCH_RESULT_CHUNK_SIZE)
  for _ in range(remaining_iterations):
    if not response.cursor:
      break
    response = search_index.search(search.Query(
        fulltext_query,
        options=search.QueryOptions(
            limit=_SEARCH_RESULT_CHUNK_SIZE, returned_fields=[], ids_only=True,
            cursor=response.cursor)))
    logging.info(
        'got %d more results: %r', len(response.results), response.results)
    ids.extend(int(result.doc_id) for result in response)

  logging.info('FTS result ids %d', len(ids))
  return ids
