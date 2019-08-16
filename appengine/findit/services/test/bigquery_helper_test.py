# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import datetime
import json
import mock
import unittest

from parameterized import parameterized

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

    schema = [{'type': 'INTEGER', 'name': 'field_name', 'mode': 'REPEATED'}]
    new_schema = bigquery_helper._SchemaResponseToDicts(schema)
    self.assertEqual(
        new_schema[0]['type_conversion_function']([{
            'v': '1'
        }, {
            'v': '2'
        }],
                                                  repeated=True), [1, 2])

    schema = [{'type': 'BOOLEAN', 'name': 'field_name', 'mode': 'NONNULLABLE'}]
    new_schema = bigquery_helper._SchemaResponseToDicts(schema)
    self.assertEqual(new_schema[0]['name'], 'field_name')
    self.assertEqual(new_schema[0]['nullable'], False)
    self.assertTrue('type_conversion_function' in new_schema[0])
    self.assertEqual(new_schema[0]['type_conversion_function']('true'), True)

    schema = [{'type': 'BOOLEAN', 'name': 'field_name', 'mode': 'REPEATED'}]
    new_schema = bigquery_helper._SchemaResponseToDicts(schema)
    self.assertEqual(
        new_schema[0]['type_conversion_function']([{
            'v': 'true'
        }, {
            'v': 'false'
        }],
                                                  repeated=True), [True, False])

    schema = [{'type': 'STRING', 'name': 'field_name', 'mode': 'NULLABLE'}]
    new_schema = bigquery_helper._SchemaResponseToDicts(schema)
    self.assertEqual(new_schema[0]['name'], 'field_name')
    self.assertEqual(new_schema[0]['nullable'], True)
    self.assertTrue('type_conversion_function' in new_schema[0])
    self.assertEqual(new_schema[0]['type_conversion_function']('str'), 'str')

    schema = [{'type': 'STRING', 'name': 'field_name', 'mode': 'REPEATED'}]
    new_schema = bigquery_helper._SchemaResponseToDicts(schema)
    self.assertEqual(
        new_schema[0]['type_conversion_function']([{
            'v': 'asdf1'
        }, {
            'v': 'asdf2'
        }],
                                                  repeated=True),
        ['asdf1', 'asdf2'])

    schema = [{'type': 'TIMESTAMP', 'name': 'field_name', 'mode': 'NULLABLE'}]
    new_schema = bigquery_helper._SchemaResponseToDicts(schema)
    self.assertEqual(new_schema[0]['name'], 'field_name')
    self.assertEqual(new_schema[0]['nullable'], True)
    self.assertTrue('type_conversion_function' in new_schema[0])
    self.assertEqual(
        new_schema[0]['type_conversion_function'](_UTC_TIMESTAMP_OF_START_TIME),
        _UTC_DATETIME_OF_START_TIME)

    schema = [{'type': 'TIMESTAMP', 'name': 'field_name', 'mode': 'REPEATED'}]
    new_schema = bigquery_helper._SchemaResponseToDicts(schema)
    self.assertEqual(
        new_schema[0]['type_conversion_function']([{
            'v': _UTC_TIMESTAMP_OF_START_TIME
        }, {
            'v': _UTC_TIMESTAMP_OF_START_TIME
        }],
                                                  repeated=True),
        [_UTC_DATETIME_OF_START_TIME, _UTC_DATETIME_OF_START_TIME])

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

  @parameterized.expand([
      (None, None),
      ([('name', 'type', 'value')], [{
          'name': 'name',
          'parameterType': {
              'type': 'type'
          },
          'parameterValue': {
              'value': 'value'
          }
      }]),
  ])
  def testGenerateQueryParameters(self, input_parameters,
                                  generated_query_parameters):
    self.assertEqual(generated_query_parameters,
                     bigquery_helper._GenerateQueryParameters(input_parameters))

  def testRunBigQuery(self):
    mock_client = mock.Mock()
    mock_client.jobs().query().execute.return_value = {
        "jobReference": {
            "jobId": 'job_id'
        },
    }
    self.assertEqual(
        'job_id', bigquery_helper._RunBigQuery(mock_client, 'project', 'query'))

  @parameterized.expand([
      # No page_token
      (  # Job did not complete
          {
              'response': {
                  "totalRows": 0,
                  "jobComplete": False,
              },
              'return_value': (False, [], None),
          },),
      (  # No results
          {
              'response': {
                  "totalRows": 0,
                  "jobComplete": True,
                  "schema": {
                      "fields": 'mock_fields'
                  },
                  "rows": ["rows"]
              },
              'return_value': (True, [], None),
          },),
      (  # Missing Fields in Response
          {
              'response': {
                  "totalRows": 1,
                  "jobComplete": True,
              },
              'return_value': (False, [], None),
          },),
      (  # Errors in Response
          {
              'response': {
                  "totalRows": 0,
                  "errors": ['error'],
                  "jobComplete": True,
                  "schema": {
                      "fields": 'mock_fields'
                  },
                  "rows": ["rows"]
              },
              'return_value': (False, [], None),
          },),
      (  # Success
          {
              'response': {
                  "totalRows": 1,
                  "jobComplete": True,
                  "schema": {
                      "fields": 'mock_fields'
                  },
                  "rows": ["rows"]
              },
              'return_value': (True, ["rows"], None),
          },),
      # Given page_token
      (  # Success
          {
              'page_token': 'mock_page',
              'response': {
                  "totalRows": 1,
                  "jobComplete": True,
                  "pageToken": 'mock_next_page',
                  "schema": {
                      "fields": 'mock_fields'
                  },
                  "rows": ["rows"]
              },
              'return_value': (True, ["rows"], 'mock_next_page'),
          },),
      (  # Errors in response, fails
          {
              'page_token': 'page',
              'response': {
                  "totalRows": 0,
                  "errors": ['error'],
                  "jobComplete": True,
                  "schema": {
                      "fields": 'mock_fields'
                  },
                  "rows": ["rows"]
              },
              'return_value': (False, [], None),
          },),
  ])
  @mock.patch.object(
      bigquery_helper, '_RowsResponseToDicts', return_value=["rows"])
  def testReadQueryResultsPage(self, cases, _):
    mock_client = mock.Mock()
    mock_client.jobs().getQueryResults(
    ).execute.return_value = cases['response']
    self.assertEqual(
        cases['return_value'],
        bigquery_helper._ReadQueryResultsPage(mock_client, 'project', 'job_id',
                                              cases.get('page_token')))

  @parameterized.expand([
      (  # Success, 1 page
          {
              'query_results': [(True, ['rows1'], None),],
              'expected_return': (True, ['rows1'])
          },),
      (  # Success, multiple pages
          {
              'query_results': [
                  (True, ['rows1'], 'page'),
                  (True, ['rows2'], None),
              ],
              'expected_return': (True, ['rows1', 'rows2'])
          },),
      (  # Fail, 1st page
          {
              'query_results': [(False, [], None),],
              'expected_return': (False, [])
          },),
      (  # Fail, nth page
          {
              'query_results': [
                  (True, ['rows1'], 'page'),
                  (False, [], None),
              ],
              'expected_return': (False, [])
          },),
  ])
  @mock.patch.object(bigquery_helper, '_RunBigQuery', return_value='job_id')
  @mock.patch.object(bigquery_helper, '_ReadQueryResultsPage')
  def testQueryRequest(self, cases, mock_get_results, *_):
    mock_client = mock.Mock()
    mock_get_results.side_effect = cases['query_results']
    self.assertEqual(
        cases['expected_return'],
        bigquery_helper.QueryRequest(mock_client, 'project', 'query'))

  @mock.patch.object(bigquery_helper, '_RunBigQuery', return_value='job_id')
  @mock.patch.object(
      bigquery_helper,
      '_ReadQueryResultsPage',
      side_effect=[(True, [], 'page'), (True, [], None)])
  def testQueryRequestOptionalArgs(self, mock_read_results, mock_run_query):
    mock_client = mock.Mock()
    bigquery_helper.QueryRequest(mock_client, 'project', 'query')
    mock_run_query.assert_called_with(
        mock_client,
        'project',
        'query',
        parameters=None,
        timeout=bigquery_helper._TIMEOUT_MS)
    mock_read_results.assert_has_calls([
        mock.call(mock_client, 'project', 'job_id'),
        mock.call(mock_client, 'project', 'job_id', page_token='page')
    ])

    mock_read_results.reset_mock()
    mock_read_results.side_effect = [(True, [], 'page'), (True, [], None)]
    bigquery_helper.QueryRequest(
        mock_client, 'project', 'query', parameters='params', timeout=1)
    mock_run_query.assert_called_with(
        mock_client, 'project', 'query', parameters='params', timeout=1)
    mock_read_results.assert_has_calls([
        mock.call(mock_client, 'project', 'job_id'),
        mock.call(mock_client, 'project', 'job_id', page_token='page')
    ])

  @parameterized.expand([
      (  # Run query, successfully return 1st page
          {
              'runbigquery_call_count': 1,
              'query': 'mock_query',
              'query_results': (True, ['rows1'], 'mock_next_page'),
              'expected_return': (True, ['rows1'], 'mock_job', 'mock_next_page')
          },),
      (  # Run query, fails.
          {
              'runbigquery_call_count': 1,
              'query': 'mock_query',
              'query_results': (False, [], None),
              'expected_return': (False, [], 'mock_job', None)
          },),
      (  # No query ran, success
          {
              'runbigquery_call_count': 0,
              'job_id': 'mock_job',
              'query_results': (False, [], None),
              'expected_return': (False, [], 'mock_job', None)
          },),
      (  # No query ran, fails
          {
              'runbigquery_call_count': 0,
              'job_id': 'mock_job',
              'query_results': (True, ['rows1'], 'mock_next_page'),
              'expected_return': (True, ['rows1'], 'mock_job', 'mock_next_page')
          },),
      (  # Page token given, valid parameters
          {
              'runbigquery_call_count': 0,
              'job_id': 'mock_job',
              'page_token': 'mock_page',
              'query_results': (True, ['rows1'], 'mock_next_page'),
              'expected_return': (True, ['rows1'], 'mock_job', 'mock_next_page')
          },),
  ])
  @mock.patch.object(bigquery_helper, '_RunBigQuery', return_value='mock_job')
  @mock.patch.object(bigquery_helper, '_ReadQueryResultsPage')
  def testQueryRequestPaging(self, cases, mock_read_results, mock_run_query):
    mock_client = mock.Mock()
    mock_read_results.return_value = cases['query_results']
    self.assertEqual(
        cases['expected_return'],
        bigquery_helper.QueryRequestPaging(
            mock_client,
            'project',
            query=cases.get('query'),
            job_id=cases.get('job_id'),
            page_token=cases.get('page_token')))
    self.assertEqual(cases['runbigquery_call_count'], mock_run_query.call_count)

  @parameterized.expand([
      (None, None, None),
      (None, None, 'page'),
      ('query', 'job_id', 'page'),
      ('query', 'job_id', None),
  ])
  def testQueryRequestPagingInvalidParameters(self, query, job_id, page_token):
    with self.assertRaises(AssertionError):
      bigquery_helper.QueryRequestPaging(
          'client',
          'project',
          query=query,
          job_id=job_id,
          page_token=page_token)

  @mock.patch.object(bigquery_helper, '_RunBigQuery', return_value='job_id')
  @mock.patch.object(
      bigquery_helper, '_ReadQueryResultsPage', return_value=(True, [], None))
  def testQueryRequestPagingOptionalArgsWithQuery(self, mock_read_results,
                                                  mock_run_query):
    mock_client = mock.Mock()
    bigquery_helper.QueryRequestPaging(mock_client, 'project', query='query')
    bigquery_helper.QueryRequestPaging(
        mock_client,
        'project',
        query='query',
        parameters='params',
        max_results=1,
        timeout=1)

    mock_run_query.assert_has_calls([
        mock.call(
            mock_client,
            'project',
            'query',
            parameters=None,
            max_results=None,
            timeout=bigquery_helper._TIMEOUT_MS),
        mock.call(
            mock_client,
            'project',
            'query',
            parameters='params',
            max_results=1,
            timeout=1)
    ])

    mock_read_results.assert_has_calls([
        mock.call(mock_client, 'project', job_id='job_id', page_token=None),
        mock.call(mock_client, 'project', job_id='job_id', page_token=None)
    ])

  @mock.patch.object(
      bigquery_helper, '_ReadQueryResultsPage', return_value=(True, [], None))
  def testQueryRequestPagingOptionalArgsWithJobId(self, mock_read_results):
    # Using default values.
    mock_client = mock.Mock()
    bigquery_helper.QueryRequestPaging(mock_client, 'project', job_id='job_id')
    mock_read_results.assert_called_once_with(
        mock_client, 'project', job_id='job_id', page_token=None)

    mock_read_results.reset_mock()
    bigquery_helper.QueryRequestPaging(
        mock_client, 'project', job_id='job_id', page_token='page')
    mock_read_results.assert_called_once_with(
        mock_client, 'project', job_id='job_id', page_token='page')

  @mock.patch.object(
      bigquery_helper, '_GetBigqueryClient', return_value='client')
  @mock.patch.object(bigquery_helper, 'QueryRequest')
  def testExecuteQueryNoPaging(self, mock_query_request, _):
    bigquery_helper.ExecuteQuery('project', 'query')
    bigquery_helper.ExecuteQuery(
        'project', query='query', parameters='params', max_results=1, timeout=1)

    mock_query_request.assert_has_calls([
        mock.call(
            'client',
            'project',
            'query',
            parameters=None,
            timeout=bigquery_helper._TIMEOUT_MS),
        mock.call('client', 'project', 'query', parameters='params', timeout=1)
    ])

  @parameterized.expand([
      ({
          'query':
              'query',
          'call_args':
              mock.call(
                  'client',
                  'project',
                  query='query',
                  parameters=None,
                  max_results=None,
                  timeout=bigquery_helper._TIMEOUT_MS)
      },),
      ({
          'job_id':
              'job_id',
          'call_args':
              mock.call(
                  'client',
                  'project',
                  job_id='job_id',
                  page_token=None,
                  timeout=bigquery_helper._TIMEOUT_MS)
      },),
      ({
          'job_id':
              'job_id',
          'page_token':
              'page_token',
          'call_args':
              mock.call(
                  'client',
                  'project',
                  job_id='job_id',
                  page_token='page_token',
                  timeout=bigquery_helper._TIMEOUT_MS)
      },),
      ({
          'job_id':
              'job_id',
          'query':
              'query',
          'call_args':
              mock.call(
                  'client',
                  'project',
                  job_id='job_id',
                  page_token=None,
                  timeout=bigquery_helper._TIMEOUT_MS)
      },),
  ])
  @mock.patch.object(
      bigquery_helper, '_GetBigqueryClient', return_value='client')
  @mock.patch.object(bigquery_helper, 'QueryRequestPaging')
  def testExecuteQueryPaging(self, cases, mock_query_request_paging, _):
    bigquery_helper.ExecuteQuery(
        'project',
        query=cases.get('query'),
        job_id=cases.get('job_id'),
        page_token=cases.get('page_token'),
        paging=True)
    self.assertEqual(cases['call_args'], mock_query_request_paging.call_args)

  @mock.patch.object(
      bigquery_helper, '_GetBigqueryClient', return_value='client')
  @mock.patch.object(bigquery_helper, 'QueryRequestPaging')
  def testExecuteQueryPagingOptionalArgsWithQuery(self,
                                                  mock_query_request_paging, _):
    bigquery_helper.ExecuteQuery(
        'project',
        query='query',
        paging=True,
        parameters='params',
        max_results=1,
        timeout=1)
    mock_query_request_paging.assert_called_once_with(
        'client',
        'project',
        query='query',
        parameters='params',
        max_results=1,
        timeout=1)

  @mock.patch.object(
      bigquery_helper, '_GetBigqueryClient', return_value='client')
  @mock.patch.object(bigquery_helper, 'QueryRequestPaging')
  def testExecuteQueryPagingOptionalArgsWithJobId(self,
                                                  mock_query_request_paging, _):
    bigquery_helper.ExecuteQuery(
        'project',
        job_id='job_id',
        page_token='page_token',
        paging=True,
        timeout=1)
    mock_query_request_paging.assert_called_once_with(
        'client',
        'project',
        job_id='job_id',
        page_token='page_token',
        timeout=1)

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
