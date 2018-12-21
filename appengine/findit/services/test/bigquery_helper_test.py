# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import datetime
import json
import mock
import unittest

from apiclient import discovery
from oauth2client import appengine as gae_oauth2client
from google.protobuf import json_format

from services import bigquery_helper

# Used to test the timestamp conversion function.
_UTC_TIMESTAMP_OF_START_TIME = '0'
_UTC_DATETIME_OF_START_TIME = datetime.datetime(
    year=1970, month=1, day=1, hour=0, minute=0, second=0)

_UTC_TIMESTAMP_OF_YEAR_TWO_THOUSAND = '0.946684800E9'
_UTC_DATETIME_OF_YEAR_TWO_THOUSAND = datetime.datetime(
    year=2000, month=1, day=1, hour=0, minute=0, second=0)


class BigqueryHelperTest(unittest.TestCase):

  @mock.patch.object(discovery, 'build')
  def testGetBigqueryClient(self, mock_client):
    bigquery_helper._GetBigqueryClient()
    self.assertTrue(mock_client.called)

  @mock.patch.object(discovery, 'build')
  def testGetBigqueryClientIsCached(self, _):
    client = bigquery_helper._GetBigqueryClient()
    self.assertEqual(client, bigquery_helper._GetBigqueryClient())

  def testSchemaResponseToDicts(self):
    schema = [{'type': 'INTEGER', 'name': 'field_name', 'mode': 'NULLABLE'}]
    new_schema = bigquery_helper._SchemaResponseToDicts(schema)
    self.assertEqual(new_schema[0]['name'], 'field_name')
    self.assertEqual(new_schema[0]['nullable'], True)
    self.assertTrue('type_conversion_function' in new_schema[0])
    self.assertEqual(new_schema[0]['type_conversion_function']('1'), 1)

    schema = [{'type': 'BOOLEAN', 'name': 'field_name', 'mode': 'NONNULLABLE'}]
    new_schema = bigquery_helper._SchemaResponseToDicts(schema)
    self.assertEqual(new_schema[0]['name'], 'field_name')
    self.assertEqual(new_schema[0]['nullable'], False)
    self.assertTrue('type_conversion_function' in new_schema[0])
    self.assertEqual(new_schema[0]['type_conversion_function']('true'), True)

    schema = [{'type': 'STRING', 'name': 'field_name', 'mode': 'NULLABLE'}]
    new_schema = bigquery_helper._SchemaResponseToDicts(schema)
    self.assertEqual(new_schema[0]['name'], 'field_name')
    self.assertEqual(new_schema[0]['nullable'], True)
    self.assertTrue('type_conversion_function' in new_schema[0])
    self.assertEqual(new_schema[0]['type_conversion_function']('str'), 'str')

    schema = [{'type': 'TIMESTAMP', 'name': 'field_name', 'mode': 'NULLABLE'}]
    new_schema = bigquery_helper._SchemaResponseToDicts(schema)
    self.assertEqual(new_schema[0]['name'], 'field_name')
    self.assertEqual(new_schema[0]['nullable'], True)
    self.assertTrue('type_conversion_function' in new_schema[0])
    self.assertEqual(
        new_schema[0]['type_conversion_function'](_UTC_TIMESTAMP_OF_START_TIME),
        _UTC_DATETIME_OF_START_TIME)

  def testAssignTypeToRow(self):
    schema = bigquery_helper._SchemaResponseToDicts([{
        'type': 'INTEGER',
        'name': 'int_field_name',
        'mode': 'NULLABLE'
    }, {
        'type': 'BOOLEAN',
        'name': 'boolean_field_name',
        'mode': 'NULLABLE'
    }, {
        'type': 'STRING',
        'name': 'string_field_name',
        'mode': 'NULLABLE'
    }, {
        'type': 'TIMESTAMP',
        'name': 'timestamp_field_name',
        'mode': 'NULLABLE'
    }])
    row = {
        'f': [{
            'v': '123'
        }, {
            'v': 'false'
        }, {
            'v': 'tryserver.chromium.mac'
        }, {
            'v': _UTC_TIMESTAMP_OF_START_TIME
        }]
    }

    obj = bigquery_helper._AssignTypeToRow(schema, row)
    self.assertEqual(obj['int_field_name'], 123)
    self.assertEqual(obj['boolean_field_name'], False)
    self.assertEqual(obj['string_field_name'], 'tryserver.chromium.mac')
    self.assertEqual(obj['timestamp_field_name'], _UTC_DATETIME_OF_START_TIME)

  def testAssignTypeToRowWithNullable(self):
    schema = bigquery_helper._SchemaResponseToDicts([{
        'type': 'INTEGER',
        'name': 'int_field_name',
        'mode': 'NULLABLE'
    }, {
        'type': 'BOOLEAN',
        'name': 'boolean_field_name',
        'mode': 'NULLABLE'
    }, {
        'type': 'STRING',
        'name': 'string_field_name',
        'mode': 'NULLABLE'
    }, {
        'type': 'TIMESTAMP',
        'name': 'timestamp_field_name',
        'mode': 'NULLABLE'
    }])
    row = {'f': [{'v': None}, {'v': None}, {'v': None}, {'v': None}]}

    obj = bigquery_helper._AssignTypeToRow(schema, row)
    self.assertEqual(obj['int_field_name'], None)
    self.assertEqual(obj['boolean_field_name'], None)
    self.assertEqual(obj['string_field_name'], None)
    self.assertEqual(obj['timestamp_field_name'], None)

  def testAssignTypeToRowWithUnknownSchema(self):
    schema = bigquery_helper._SchemaResponseToDicts([{
        'type': 'FOOBAR',
        'name': 'field_name',
        'mode': 'NULLABLE'
    }])
    row = {'f': [{'v': '123'}]}

    obj = bigquery_helper._AssignTypeToRow(schema, row)
    self.assertEqual(obj, {'field_name': '123'})

  def testRowsResponseToDicts(self):
    schema = [{
        'type': 'FOOBAR',
        'name': 'f1',
        'mode': 'NULLABLE'
    }, {
        'type': 'INTEGER',
        'name': 'f2',
        'mode': 'NULLABLE'
    }, {
        'type': 'STRING',
        'name': 'f3',
        'mode': 'NULLABLE'
    }, {
        'type': 'BOOLEAN',
        'name': 'f4',
        'mode': 'NULLABLE'
    }, {
        'type': 'TIMESTAMP',
        'name': 'f5',
        'mode': 'NULLABLE'
    }]

    rows = [
        {
            'f': [{
                'v': '123'
            }, {
                'v': '100'
            }, {
                'v': 'tryserver.chromium.mac'
            }, {
                'v': 'false'
            }, {
                'v': _UTC_TIMESTAMP_OF_START_TIME
            }]
        },
        {
            'f': [{
                'v': '321'
            }, {
                'v': '200'
            }, {
                'v': 'fryserver.chromium.mac'
            }, {
                'v': 'true'
            }, {
                'v': _UTC_TIMESTAMP_OF_YEAR_TWO_THOUSAND
            }]
        },
    ]

    result_rows = bigquery_helper._RowsResponseToDicts(schema, rows)
    self.assertEqual(result_rows, [{
        'f1': '123',
        'f2': 100,
        'f3': 'tryserver.chromium.mac',
        'f4': False,
        'f5': _UTC_DATETIME_OF_START_TIME
    },
                                   {
                                       'f1': '321',
                                       'f2': 200,
                                       'f3': 'fryserver.chromium.mac',
                                       'f4': True,
                                       'f5': _UTC_DATETIME_OF_YEAR_TWO_THOUSAND
                                   }])

  def testBigqueryInsertRequest(self):
    mock_client = mock.Mock()
    mock_client.tabledata().insertAll().execute.return_value = {}
    success = bigquery_helper.InsertRequest(mock_client, 'project', 'dataset',
                                            'table', [])
    self.assertTrue(success)
    self.assertTrue(mock_client.tabledata().insertAll().execute.called)

  def testBigqueryInsertRequestWithErrors(self):
    mock_client = mock.Mock()
    mock_client.tabledata().insertAll().execute.return_value = {
        'insertErrors': ['error']
    }
    success = bigquery_helper.InsertRequest(mock_client, 'project', 'dataset',
                                            'table', [])
    self.assertFalse(success)
    self.assertTrue(mock_client.tabledata().insertAll().execute.called)

  @mock.patch.object(
      bigquery_helper, '_RowsResponseToDicts', return_value=[{
          'foo': 1
      }])
  def testBigqueryQueryRequest(self, _):
    mock_client = mock.Mock()
    mock_client.jobs().query().execute.return_value = {
        "totalRows": 1,
        "jobComplete": True,
        "schema": {
            "fields": 'mock_fields'
        },
        "rows": ["rows"]
    }
    success, rows = bigquery_helper.QueryRequest(mock_client, 'project',
                                                 'query')
    self.assertTrue(mock_client.jobs().query().execute.called)
    self.assertTrue(success)
    self.assertEqual(len(rows), 1)

  def testBigqueryQueryRequestIncomplete(self):
    mock_client = mock.Mock()
    mock_client.jobs().query().execute.return_value = {}
    success, rows = bigquery_helper.QueryRequest(mock_client, 'project',
                                                 'query')
    self.assertTrue(mock_client.jobs().query().execute.called)
    self.assertFalse(success)
    self.assertEqual(rows, [])

  def testBigqueryQueryRequestNoRows(self):
    mock_client = mock.Mock()
    mock_client.jobs().query().execute.return_value = {
        'jobComplete': True,
        'totalRows': '0'
    }
    success, rows = bigquery_helper.QueryRequest(mock_client, 'project',
                                                 'query')
    self.assertTrue(mock_client.jobs().query().execute.called)
    self.assertTrue(success)
    self.assertEqual(rows, [])

  def testBigqueryQueryRequestWithErrors(self):
    mock_client = mock.Mock()
    mock_client.jobs().query().execute.return_value = {'errors': ['error']}
    success, rows = bigquery_helper.QueryRequest(mock_client, 'project',
                                                 'query')
    self.assertTrue(mock_client.jobs().query().execute.called)
    self.assertFalse(success)
    self.assertEqual(rows, [])

  def testBigqueryQueryRequestWithMissingFields(self):
    mock_client = mock.Mock()
    mock_client.jobs().query().execute.return_value = {}
    success, rows = bigquery_helper.QueryRequest(mock_client, 'project',
                                                 'query')
    self.assertTrue(mock_client.jobs().query().execute.called)
    self.assertFalse(success)
    self.assertEqual(rows, [])

  def testBigqueryQueryRequestWithParameters(self):
    parameters = [('name', 'type', 'value')]
    expected_query_params = [{
        'name': 'name',
        'parameterType': {
            'type': 'type'
        },
        'parameterValue': {
            'value': 'value'
        }
    }]
    self.assertEqual(expected_query_params,
                     bigquery_helper._GenerateQueryParameters(parameters))
    self.assertIsNone(bigquery_helper._GenerateQueryParameters(None))

  @mock.patch.object(bigquery_helper, '_GetBigqueryClient')
  @mock.patch.object(json_format, 'MessageToJson')
  @mock.patch.object(bigquery_helper, 'InsertRequest', return_value=True)
  def testReportEventsToBigQuery(self, insert_fn, json_func, *_):
    request_dict = {"hello": "world"}
    json_func.return_value = json.dumps(request_dict)

    events_and_ids = [(None, 'insertid')]
    self.assertTrue(
        bigquery_helper.ReportEventsToBigquery(events_and_ids, 'projectid',
                                               'datasetid', 'tableid'))
    args, _ = insert_fn.call_args
    self.assertEqual(args[-1], [{'json': request_dict, 'insertId': 'insertid'}])

  @mock.patch.object(bigquery_helper, '_GetBigqueryClient')
  @mock.patch.object(json_format, 'MessageToJson')
  @mock.patch.object(bigquery_helper, 'InsertRequest', return_value=False)
  def testReportEventsToBigQueryWithError(self, insert_fn, json_func, *_):
    request_dict = {"hello": "world"}
    json_func.return_value = json.dumps(request_dict)

    events_and_ids = [(None, 'insertid')]
    self.assertFalse(
        bigquery_helper.ReportEventsToBigquery(events_and_ids, 'projectid',
                                               'datasetid', 'tableid'))
    args, _ = insert_fn.call_args
    self.assertEqual(args[-1], [{'json': request_dict, 'insertId': 'insertid'}])
