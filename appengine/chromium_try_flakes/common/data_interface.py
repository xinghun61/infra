# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple
import datetime
import httplib2
import json
import math
import zlib

from google.appengine.api import app_identity
from google.appengine.ext import ndb

import apiclient.discovery
import oauth2client.appengine
from model.flake import Cache, CacheAncestor


NEW_FLAKES_QUERY = (
    'SELECT'
    '  project,'
    '  step_name,'
    '  test_name,'
    '  config,'
    '  ARRAY_AGG('
    '    STRUCT('
    '      failure_utc_msec,'
    '      master_name,'
    '      builder_name,'
    '      fail_build_id,'
    '      pass_build_id,'
    '      patch_url '
    '    )'
    '  ) '
    'FROM'
    '  plx.google.chrome_infra.cq_flaky_failures.all '
    'GROUP BY'
    '  project,'
    '  step_name,'
    '  test_name,'
    '  config;'
)

N_SLICES = 100


def _build_bigquery_service():  # pragma: no cover
  credentials = oauth2client.appengine.AppAssertionCredentials(
      scope='https://www.googleapis.com/auth/bigquery')
  http = credentials.authorize(http=httplib2.Http(timeout=60))
  return apiclient.discovery.build('bigquery', 'v2', http=http)


# TODO(ehmaldonado): Add tests for this.
def _execute_query(bq_service, query, params=None):  # pragma: no cover
  bq_project_id = app_identity.get_application_id()
  # Set 50 second timeout for the query, which leaves 10 seconds for overhead
  # before HTTP timeout. The query will actually continue to run after the
  # timeout and we wait for results in a loop.
  bq_timeout = 50 * 1000

  body = {
    'timeoutMs': bq_timeout,
    'query': query,
    'useLegacySql': False,
  }
  if params:
    body['queryParameters'] = params
  response = bq_service.jobs().query(
      projectId=bq_project_id, body=body).execute(num_retries=5)
  job_id = response['jobReference']['jobId']
  if response.get('jobComplete'):
    # Query returned results immediately.
    rows = response.get('rows', [])
    page_token = response.get('pageToken')
  else:
    # Query is still running. Wait for results. We do not put a timeout this
    # loop since AppEngine will terminate ourselves automatically after
    # overall request timeout is reached.
    while True:
      results_response = bq_service.jobs().getQueryResults(
          projectId=bq_project_id, jobId=job_id,
          timeoutMs=bq_timeout).execute(num_retries=5)
      if results_response.get('jobComplete'):
        rows = results_response.get('rows', [])
        page_token = results_response.get('pageToken')
        break
  # Get additional results if any.
  while page_token:
    results_request = bq_service.jobs().getQueryResults(
        projectId=bq_project_id, jobId=job_id, pageToken=page_token)
    results_response = results_request.execute(num_retries=5)
    rows.extend(results_response.get('rows', []))
    page_token = results_response.get('pageToken')
  return rows


def _sanitize_row(row):
  """Sanitize a row returned by BigQuery.

  In the format BigQuery returns, a row is a dict with a single entry 'f'
  which contains a list of values. A value is a dict with a single entry 'v'.

    row_1 = {'f': [{'v': 'value 1'},
                   {'v': 'value_2'}]}

  When we use ARRAY_AGG(STRUCT(...)) the value is a list of values, each value
  storing a list of rows.

    row_2 = {'f': [{'v': 'some_project'},
                   {'v': 'some_step_name'},
                   {'v': 'some_test_name'},
                   {'v': 'some_config'},
                   # When we aggregate the value stores a list of values
                   {'v': [
                       # Each value contains a row as described above.
                       {'v': {'f': ['v': 'some_master',
                                    'v': 'some_builder']}},
                       {'v': {'f': ['v': 'some_other_master',
                                    'v': 'some_other_builder']}}
                   ]}]}

  This function essentialy gets rid of the 'v's and 'f's. For the examples
  above we'd get:

    sanitized_row_1 = ['value_1',
                       'value_2']

    sanitized_row_2 = ['some_project',
                       'some_step_name',
                       'some_test_name',
                       'some_config',
                       [
                           ['some_master',
                            'some_builder'],
                           ['some_other_master',
                            'some_other_builder'],
                       ]]
  """
  sanitized_row = []
  for column in row['f']:
    column = column['v']
    if isinstance(column, list):
      column = [_sanitize_row(sub_column['v']) for sub_column in column]
    sanitized_row.append(column)
  return sanitized_row


def _split_list(row, position):
  return tuple(row[:position]), row[position]


def _get_cache_ancestor_key():
  ancestor_key = ndb.Key('CacheAncestor', 'singleton')
  if ancestor_key.get():
    return ancestor_key
  return CacheAncestor(key=ancestor_key).put()


@ndb.transactional
def _update_cache(data, slice_size):
  ancestor_key = _get_cache_ancestor_key()
  ndb.delete_multi(Cache.query(ancestor=ancestor_key).fetch(keys_only=True))
  slices = [
      Cache(idx=slice_index, data=data[i:i+slice_size],
            parent=ancestor_key)
      for slice_index, i in enumerate(range(0, len(data), slice_size))
  ]
  ndb.put_multi(slices)


def update_cache():
  bq_service = _build_bigquery_service()
  data = _execute_query(bq_service, NEW_FLAKES_QUERY)
  flakes_cache = zlib.compress(json.dumps([_sanitize_row(row) for row in data]))
  slice_size = int(math.ceil(len(flakes_cache) / float(N_SLICES)))
  _update_cache(flakes_cache, slice_size)


@ndb.transactional
def get_flakes_data():
  ancestor_key = _get_cache_ancestor_key()
  slices = Cache.query(ancestor=ancestor_key).fetch()
  flakes_cache = json.loads(zlib.decompress(''.join(
      s.data for s in sorted(slices, key=lambda s: s.idx))))
  # We create a dict where we index by the 4 first elements of the table, i.e.
  # the flake type.
  return dict(_split_list(row, position=4) for row in flakes_cache)
