# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Factilitates interacting with Bigquery through the REST API."""

import datetime
import httplib2
import json
import logging

from apiclient import discovery
from google.protobuf import json_format
from oauth2client import appengine as gae_oauth2client

# Bigquery authentication endpoint.
_AUTH_ENDPOINT = 'https://www.googleapis.com/auth/bigquery'

# Number of retries before giving up.
_REQUEST_RETRIES = 3

# Timeout for query requests, 60 seconds.
_TIMEOUT_MS = 60000


def _GetBigqueryClient():
  """Returns a Bigquery api client for the current project.

  This method caches the client for reusing.
  """
  if hasattr(_GetBigqueryClient, 'client'):
    return getattr(_GetBigqueryClient, 'client')

  credentials = gae_oauth2client.AppAssertionCredentials(scope=_AUTH_ENDPOINT)
  http_auth = credentials.authorize(http=httplib2.Http(timeout=60))
  bigquery_client = discovery.build('bigquery', 'v2', http=http_auth)

  setattr(_GetBigqueryClient, 'client', bigquery_client)
  return bigquery_client


def _SchemaResponseToDicts(schema):
  """Interprets a schema response into a usable python dictionary.

  Args:
      schema (dict): Type and name of the row fields. Example:
          [
            { 'type': 'INTEGER', 'name': 'field_name'},
            ...
          ]
  Returns:
    ([dict]) schema with fields and type conversion function attached. Example:
        {
          'name': 'example_field',
          'type_conversion_function': <function>,
          'nullable': True/False
        }
  """

  def _IntegerTypeConversion(val, nullable=False, repeated=False):
    if nullable and val is None:
      return None
    if repeated:
      return [int(x['v']) for x in val]
    return int(val)

  def _StringTypeConversion(val, nullable=False, repeated=False):
    if nullable and val is None:
      return None
    if repeated:
      return [str(x['v']) for x in val]
    return str(val)

  def _BooleanTypeConversion(val, nullable=False, repeated=False):
    if nullable and val is None:
      return None
    if repeated:
      return [x['v'].lower() == 'true' for x in val]
    return val.lower() == 'true'

  def _TimestampTypeConversion(val, nullable=False, repeated=False):
    if nullable and val is None:
      return None
    if repeated:
      return [datetime.datetime.utcfromtimestamp(float(x['v'])) for x in val]
    return datetime.datetime.utcfromtimestamp(float(val))

  known_types = {
      'INTEGER': _IntegerTypeConversion,
      'STRING': _StringTypeConversion,
      'BOOLEAN': _BooleanTypeConversion,
      'TIMESTAMP': _TimestampTypeConversion
  }

  schema_dicts = []
  for schema_field in schema:
    schema_dicts.append({
        'name':
            schema_field['name'],
        'type_conversion_function':
            known_types.get(schema_field['type'], lambda x, y, z: x),
        'nullable':
            schema_field['mode'] == 'NULLABLE',
        'repeated':
            schema_field['mode'] == 'REPEATED'
    })
  return schema_dicts


def _AssignTypeToRow(schema, row):
  """Uses a map to parse a given row's field, and assign it to obj.

  Args:
    schema (dict): Type and name of the row fields. Example:
        [
          { 'type': 'INTEGER', 'name': 'field_name'},
          ...
        ]
    row (dict): Raw row from bigquery response.
        {'f': [
            {'v': '8955294276910866544'},
            {'v': 'false'},
            {'v': 'tryserver.chromium.mac'}
        ]}
  Returns:
    (dict) Row in the form of a typed python dict.
  """
  row_dict = {}
  for idx, schema_field in enumerate(schema):
    type_func = schema_field['type_conversion_function']
    row_dict[schema_field['name']] = type_func(
        row['f'][idx]['v'], schema_field['nullable'], schema_field['repeated'])
  return row_dict


def _RowsResponseToDicts(schema, rows):
  """Parses the raw rows coming from bigquery to a list of dicts.

  Args:
    schema ([dict]): The schema interpereted by _SchemaResponseToDict.
        [{
          'name': 'example_field',
          'type_conversion_function': <function>,
          'nullable': True/False
        }, ...]
    rows ([dict]): Rows from the bigquery database.
        [{ 'f': [{'v': '8955294276910866544'},
                 {'v': 'false'},
                 {'v': 'tryserver.chromium.mac'}
                ], ...
        }]
  Returns:
    ([dict]) Parsed rows from input.
  """
  schema = _SchemaResponseToDicts(schema)

  parsed_rows = []
  for row in rows:
    parsed_rows.append(_AssignTypeToRow(schema, row))
  return parsed_rows


def InsertRequest(client, project_id, dataset_id, table_id, rows):
  """Inserts the given rows into a bigquery table.

  Args:
    client (apiclient.discovery): Bigquery client.
    project_id (str): Project Id in google cloud.
    dataset_id (str): Dataset Id in Bigquery.
    table_id (str): Table Id in Bigquery.
    rows ([dict]): Messages to send.
  Returns:
    (boolean) True if success, false otherwise.
  """
  body = {
      'kind': 'bigquery#tableDataInsertAllRequest',
      'rows': rows,
  }
  request = client.tabledata().insertAll(
      projectId=project_id, datasetId=dataset_id, tableId=table_id, body=body)
  response = request.execute(num_retries=_REQUEST_RETRIES)
  if response.get('insertErrors'):
    logging.error('InsertRequest reported errors: %r',
                  response.get('insertErrors'))
    return False

  return True


def _GenerateQueryParameters(parameters):
  """Generates query parameters using parameters.

  Reference: https://goo.gl/SyALkb.

  Currently this function only supports parameters of a single value. To support
  struct or array parameters, please refer to the link above.

  Args:
    parameters ([tuples]): A list of parameter tuples in the format:
      [(name, type, value)]
  """
  if not parameters:
    return None

  query_params = []
  for name, p_type, value in parameters:
    query_params.append({
        'name': name,
        'parameterType': {
            'type': p_type
        },
        'parameterValue': {
            'value': value
        }
    })
  return query_params


def ExecuteQuery(project_id,
                 query=None,
                 parameters=None,
                 paging=False,
                 job_id=None,
                 page_token=None,
                 max_results=None,
                 timeout=_TIMEOUT_MS):  # pragma: no cover

  if not paging:
    return QueryRequest(
        _GetBigqueryClient(),
        project_id,
        query,
        parameters=parameters,
        timeout=timeout)

  # Return first page when paging is True.
  if job_id is None:
    return QueryRequestPaging(
        _GetBigqueryClient(),
        project_id,
        query=query,
        parameters=parameters,
        max_results=max_results,
        timeout=timeout)

  # Return specified page of results when paging is True.
  return QueryRequestPaging(
      _GetBigqueryClient(),
      project_id,
      job_id=job_id,
      page_token=page_token,
      timeout=timeout)


def QueryRequest(client,
                 project_id,
                 query,
                 parameters=None,
                 timeout=_TIMEOUT_MS):
  """Runs a BigQuery SQL Query and returns all query result rows.

  Args:
    client (apiclient.discovery): Bigquery client.
    project_id (str): Project Id in google cloud.
    query (str): query to run.
    parameters ([tuple]): Parameters to be used in parameterized queries.
    timeout (int): How long to wait for the query to complete, in milliseconds,
      before the request times out and returns. Note that this is only a timeout
      for the request, not the query. If the query takes longer to run than the
      timeout value, the call returns without any results and with the
      'jobComplete' flag set to false.

  Returns:
    (boolean, [dict]) Boolean to indicate success/failure, and the rows that
        match the query.
  """
  job_id = _RunBigQuery(
      client, project_id, query, parameters=parameters, timeout=timeout)
  success, rows, page_token = _ReadQueryResultsPage(client, project_id, job_id)
  while page_token:
    success, next_page_rows, page_token = _ReadQueryResultsPage(
        client, project_id, job_id, page_token=page_token)
    if not success:
      return success, []

    rows += next_page_rows
  return success, rows


def QueryRequestPaging(client,
                       project_id,
                       query=None,
                       job_id=None,
                       page_token=None,
                       parameters=None,
                       max_results=None,
                       timeout=_TIMEOUT_MS):
  """Runs a BigQuery SQL Query and returns one page of the query results rows.

  Args:
    client (apiclient.discovery): Bigquery client.
    project_id (str): Project Id in google cloud.
    query (str): query to run.
    job_id (str): Job ID of the query job.
    page_token (str): Page token, returned by a previous call, to request the
      next page of results. Can only be used if a job_id is also given.
    parameters ([tuple]): Parameters to be used in parameterized queries.
    max_results (int): The maximum number of rows of data to return per page of
      results. In addition to this limit, responses are also limited to 10 MB.
      By default, there is no maximum row count, and only the byte limit
      applies.
    timeout (int): How long to wait for the query to complete, in milliseconds,
      before the request times out and returns. Note that this is only a timeout
      for the request, not the query. If the query takes longer to run than the
      timeout value, the call returns without any results and with the
      'jobComplete' flag set to false.

  Returns:
    success (boolean): Boolean to indicate success/failure of the request.
    rows ([dict]): Rows that match the query.
    job_id (str) : Job ID of the query job.
    page_token (str): Page token, returned by a previous call, to request the
      next page of results.
  """
  if job_id:
    assert query is None, 'Cannot specify the job id and give a query.'

  if job_id is None:
    assert page_token is None, 'Need to specify the job id to use a page token.'
    assert query, 'No query or job id given to read query results.'

    job_id = _RunBigQuery(
        client,
        project_id,
        query,
        parameters=parameters,
        max_results=max_results,
        timeout=timeout)

  success, rows, page_token = _ReadQueryResultsPage(
      client, project_id, job_id=job_id, page_token=page_token)
  return success, rows, job_id, page_token


def _RunBigQuery(client,
                 project_id,
                 query,
                 parameters=None,
                 max_results=None,
                 timeout=_TIMEOUT_MS):
  """Runs a BigQuery SQL query and returns the job id.

  Args:
    client (apiclient.discovery): Bigquery client.
    project_id (str): Project Id in google cloud.
    query (str): query to run.
    parameters ([tuple]): Parameters to be used in parameterized queries.
    max_results (int): The maximum number of rows of data to return per page of
      results. In addition to this limit, responses are also limited to 10 MB.
      By default, there is no maximum row count, and only the byte limit
      applies.
    timeout (int): How long to wait for the query to complete, in milliseconds,
      before the request times out and returns. Note that this is only a timeout
      for the request, not the query. If the query takes longer to run than the
      timeout value, the call returns without any results and with the
      'jobComplete' flag set to false.
  """
  body = {
      'kind': 'bigquery#queryRequest',
      'query': query,
      'timeoutMs': timeout,
      'useLegacySql': False,
      'parameterMode': 'NAMED',
      'queryParameters': _GenerateQueryParameters(parameters) or []
  }
  if max_results:
    body['maxResults'] = max_results
  request = client.jobs().query(projectId=project_id, body=body)
  response = request.execute(num_retries=_REQUEST_RETRIES)
  return response.get('jobReference').get('jobId')


def _ReadQueryResultsPage(client, project_id, job_id, page_token=None):
  """Gets the results of a query job by page.

  Args:
    client (apiclient.discovery): Bigquery client.
    project_id (str): Project Id in google cloud.
    job_id (str): Job ID of the query job.
    page_token (str): Page token, returned by a previous call, to request the
      next page of results.

  Returns:
    success (boolean): Boolean to indicate success/failure of the request.
    rows ([dict]): Rows that match the query.
    page_token (str): Page token, returned by a previous call, to request the
      next page of results.
  """
  response = client.jobs().getQueryResults(
      projectId=project_id, jobId=job_id, pageToken=page_token).execute()

  if response.get('errors'):
    logging.error('QueryRequest reported errors: %s', response.get('errors'))
    return False, [], None

  # First results page specific errors
  if not page_token:
    if not response.get('jobComplete'):
      logging.error('QueryRequest didn\'t finish, possibly due to timeout.')
      return False, [], None

    if response.get('totalRows') == 0:
      logging.info('QueryRequest succeeded, but there were no rows returned.')
      return True, [], None

    if (not response.get('schema') or not response.get('rows')):
      logging.error('QueryRequest succeeded, but there were missing fields.')
      return False, [], None

  rows = _RowsResponseToDicts(response['schema']['fields'], response['rows'])
  page_token = response.get('pageToken')

  return True, rows, page_token


def ReportEventsToBigquery(events_and_ids, project_id, dataset_id, table_id):
  """Reports the given events to the dataset/table.

  Args:
    events_and_ids ([(protobuf, str)]): List of tuples containing the events to
        be inserted and the insert ids associated with that insert.
    project_id (str): Project Id in google cloud.
    dataset_id (str): Dataset Id in Bigquery.
    table_id (str): Table Id in Bigquery.

  Returns:
    (boolean) True if success, false otherwise.
  """
  rows = [{
      'json':
          json.loads(
              json_format.MessageToJson(
                  event,
                  preserving_proto_field_name=True,
                  including_default_value_fields=True)),
      'insertId':
          insert_id
  } for event, insert_id in events_and_ids]

  return InsertRequest(_GetBigqueryClient(), project_id, dataset_id, table_id,
                       rows)
