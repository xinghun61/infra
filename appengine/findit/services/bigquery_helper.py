# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Factilitates interacting with Bigquery through the REST API."""

import httplib2
import json

from apiclient import discovery
from google.protobuf import json_format
from oauth2client import appengine as gae_oauth2client

_BIGQUERY_AUTH_ENDPOINT = 'https://www.googleapis.com/auth/bigquery'
_CREDENTIALS = gae_oauth2client.AppAssertionCredentials(
    scope=_BIGQUERY_AUTH_ENDPOINT)
_HTTP_AUTH = _CREDENTIALS.authorize(http=httplib2.Http(timeout=60))
_REQUEST_RETRIES = 3


# TODO (crbug.com/807501): Cache the client.
def _CreateBigqueryClient():
  """Returns a Bigquery api client for the current project.

  Logic is encapsulated for testing purposes.
  """
  client = discovery.build('bigquery', 'v2', http=_HTTP_AUTH)
  return client


def _InsertRequest(client, project_id, dataset_id, table_id, rows):
  """Inserts the given rows into a bigquery table.

  Args:
    (apiclient.dicovery) client: Bigquery client.
    (str) project_id: Project Id in google cloud.
    (str) dataset_id: Dataset Id in Bigquery.
    (str) table_id: Table Id in Bigquery.
    ([dict]) rows: Messages to send.
  Returns:
    (dict) Server response with possible errors {'insertErrors': <errors>}
  """
  body = {
      'kind': 'bigquery#tableDataInsertAllRequest',
      'rows': rows,
  }
  request = client.tabledata().insertAll(
      projectId=project_id, datasetId=dataset_id, tableId=table_id, body=body)
  return request.execute(num_retries=_REQUEST_RETRIES)


def ReportEventsToBigquery(events_and_ids, project_id, dataset_id, table_id):
  """Reports the given events to the dataset/table.

  Args:
    ([(protobuf, str)]) events_and_ids: List of tuples containing the events to
        be inserted and the insert ids associated with that insert.
    (str) project_id: Project Id in google cloud.
    (str) dataset_id: Dataset Id in Bigquery.
    (str) table_id: Table Id in Bigquery.

  Returns:
    ([str]): List of errors or None.
  """
  rows = [{
      'json':
          json.loads(
              json_format.MessageToJson(
                  event, preserving_proto_field_name=True)),
      'insertId':
          insert_id
  } for event, insert_id in events_and_ids]

  response = _InsertRequest(_CreateBigqueryClient(), project_id, dataset_id,
                            table_id, rows)
  return response.get('insertErrors')
