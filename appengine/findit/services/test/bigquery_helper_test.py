# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import mock
import unittest

from apiclient import discovery
from oauth2client import appengine as gae_oauth2client
from google.protobuf import json_format

from services import bigquery_helper


class BigqueryHelperTest(unittest.TestCase):

  @mock.patch.object(discovery, 'build')
  def testCreateBigqueryClient(self, mock_client):
    bigquery_helper._CreateBigqueryClient()

    self.assertTrue(mock_client.called)

  def testBigqueryInsertRequest(self):
    mock_client = mock.Mock()
    mock_client.tabledata().insertAll().execute.return_value = {}
    bigquery_helper._InsertRequest(mock_client, 'project', 'dataset', 'table',
                                   [])
    self.assertTrue(mock_client.tabledata().insertAll().execute.called)

  @mock.patch.object(bigquery_helper, '_CreateBigqueryClient')
  @mock.patch.object(json_format, 'MessageToJson')
  @mock.patch.object(bigquery_helper, '_InsertRequest', return_value={})
  def testReportEventsToBigQuery(self, insert_fn, json_func, *_):
    request_dict = {"hello": "world"}
    json_func.return_value = json.dumps(request_dict)

    events_and_ids = [(None, 'insertid')]
    self.assertEqual(None,
                     bigquery_helper.ReportEventsToBigquery(
                         events_and_ids, 'projectid', 'datasetid', 'tableid'))
    args, _ = insert_fn.call_args
    self.assertEqual(args[-1], [{'json': request_dict, 'insertId': 'insertid'}])


  @mock.patch.object(bigquery_helper, '_CreateBigqueryClient')
  @mock.patch.object(json_format, 'MessageToJson')
  @mock.patch.object(
      bigquery_helper,
      '_InsertRequest',
      return_value={'insertErrors': ['error']})
  def testReportEventsToBigQueryWithError(self, insert_fn, json_func, *_):
    request_dict = {"hello": "world"}
    json_func.return_value = json.dumps(request_dict)

    events_and_ids = [(None, 'insertid')]
    self.assertEqual(['error'],
                     bigquery_helper.ReportEventsToBigquery(
                         events_and_ids, 'projectid', 'datasetid', 'tableid'))
    args, _ = insert_fn.call_args
    self.assertEqual(args[-1], [{'json': request_dict, 'insertId': 'insertid'}])
