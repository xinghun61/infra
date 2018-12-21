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

  def _IntegerTypeConversion(val, nullable=False):
    if nullable and val is None:
      return None
    return int(val)

  def _StringTypeConversion(val, nullable=False):
    if nullable and val is None:
      return None
    return str(val)

  def _BooleanTypeConversion(val, nullable=False):
    if nullable and val is None:
      return None
    return val.lower() == 'true'

  def _TimestampTypeConversion(val, nullable=False):
    if nullable and val is None:
      return None
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
            known_types.get(schema_field['type'], lambda x, y: x),
        'nullable':
            schema_field['mode'] == 'NULLABLE'
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
    row_dict[schema_field['name']] = type_func(row['f'][idx]['v'],
                                               schema_field['nullable'])
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
    client (apiclient.dicovery): Bigquery client.
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


def ExecuteQuery(project_id, query, parameters=None):  # pragma: no cover
  return QueryRequest(_GetBigqueryClient(), project_id, query, parameters)


def QueryRequest(client,
                 project_id,
                 query,
                 parameters=None,
                 timeout=_TIMEOUT_MS):
  """Inserts the given rows into a bigquery table.

  Args:
    client (apiclient.dicovery): Bigquery client.
    project_id (str): Project Id in google cloud.
    query (str): query to run.
    parameters ([tuple]): parameters to be used in parameterized queries.
  Returns:
    (boolean, [dict]) Boolean to indicate success/failure, and the rows that
        match the query.
  """
  body = {
      'kind': 'bigquery#queryRequest',
      'query': query,
      'timeoutMs': timeout,
      'useLegacySql': False,
      'parameterMode': 'NAMED',
      'queryParameters': _GenerateQueryParameters(parameters) or []
  }
  request = client.jobs().query(projectId=project_id, body=body)
  response = request.execute(num_retries=_REQUEST_RETRIES)

  if response.get('errors'):
    logging.error('QueryRequest reported errors: %s', response.get('errors'))
    return False, []

  if not response.get('jobComplete'):
    logging.error('QueryRequest didn\'t finish, possibly due to timeout.')
    return False, []

  if response.get('totalRows') == '0':
    logging.info('QueryRequest succeeded, but there were no rows returned.')
    return True, []

  if (not response.get('schema') or not response.get('rows')):
    logging.error('QueryRequest succeeded, but there were missing fields.')
    return False, []

  return True, _RowsResponseToDicts(response['schema']['fields'],
                                    response['rows'])


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
