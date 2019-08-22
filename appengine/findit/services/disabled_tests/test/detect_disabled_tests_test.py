# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from parameterized import parameterized

from google.appengine.ext import ndb

from waterfall.test.wf_testcase import WaterfallTestCase

from libs import time_util
from model.flake.flake import Flake
from model.test_inventory import LuciTest
from services import bigquery_helper
from services import step_util
from services.disabled_tests import detect_disabled_tests

_DEFAULT_LUCI_PROJECT = 'chromium'


class DetectDisabledTestsTest(WaterfallTestCase):

  def _GetEmptyDisabledTestQueryResponse(self):
    """Returns an empty query response for testing.

    The returned response is empty, please call
    _AddRowToDisabledTestQueryResponse to add rows for testing. Note that the
    fields in the schema and the parameters of the
    _AddRowToDisabledTestQueryResponse method must match exactly (including
    orders), so if a new field is added to the schema, please update
    _AddRowToDisabledTestQueryResponse accordingly.
    """
    return {
        'rows': [],
        'jobReference': {
            'jobId': 123
        },
        'jobComplete': True,
        'totalRows': '0',
        'schema': {
            'fields': [{
                'type': 'STRING',
                'name': 'test_name',
                'mode': 'NULLABLE'
            }, {
                'type': 'STRING',
                'name': 'step_name',
                'mode': 'NULLABLE'
            }, {
                'type': 'STRING',
                'name': 'builder_name',
                'mode': 'NULLABLE'
            }, {
                'type': 'INTEGER',
                'name': 'build_id',
                'mode': 'NULLABLE'
            }, {
                'type': 'STRING',
                'name': 'bugs',
                'mode': 'NULLABLE'
            }]
        }
    }

  def _AddRowToDisabledTestQueryResponse(self,
                                         query_response,
                                         test_name='test_name',
                                         step_name='step_name',
                                         builder_name='builder',
                                         build_id=999,
                                         bugs='crbug.com/123'):
    """Adds a row to the provided query response for testing.

    To obtain a query response for testing for the initial time, please call
    _GetEmptyDisabledTestQueryResponse. Note that the fields in the schema and
    the parameters of this method must match exactly (including orders), so if
    a new field is added to the schema, please update this method accordingly.
    """
    row = {
        'f': [
            {
                'v': test_name
            },
            {
                'v': step_name
            },
            {
                'v': builder_name
            },
            {
                'v': build_id
            },
            {
                'v': bugs
            },
        ]
    }
    query_response['rows'].append(row)
    query_response['totalRows'] = str(int(query_response['totalRows']) + 1)

  def setUp(self):
    super(DetectDisabledTestsTest, self).setUp()

    # NormalizeStepName performs network requests, needs to be mocked.
    patcher = mock.patch.object(
        Flake, 'NormalizeStepName', return_value='normal_step_name')
    self.addCleanup(patcher.stop)
    patcher.start()

  @parameterized.expand([
      ('builder_name', []),
      ('builder_name_asan_', [
          'ASan:True',
      ]),
      ('builder_name_lsan_', [
          'LSan:True',
      ]),
      ('builder_name_msan_', [
          'MSan:True',
      ]),
      ('builder_name_tsan_', [
          'TSan:True',
      ]),
      ('builder_name_ubsan_', [
          'UBSan:True',
      ]),
      ('builder_name_ASAN_LSAN_MSAN_TSAN_UBSAN', [
          'ASan:True',
          'LSan:True',
          'MSan:True',
          'TSan:True',
          'UBSan:True',
      ]),
      ('builder_msanasanlsantsanubsan_name', [
          'ASan:True',
          'LSan:True',
          'MSan:True',
          'TSan:True',
          'UBSan:True',
      ]),
      ('builder_aSaN_name_L_S_A_N_MsAn_', [
          'ASan:True',
          'MSan:True',
      ]),
  ])
  def testGetMemoryFlags(self, builder_name, expected_memory_flags):
    actual_memory_flags = detect_disabled_tests._GetMemoryFlags(builder_name)
    self.assertEqual(len(expected_memory_flags), len(actual_memory_flags))
    for flag in expected_memory_flags:
      self.assertIn(flag, actual_memory_flags)

  @parameterized.expand([('os', ('MSan:True', 'os:os')), (None,
                                                          ('MSan:True',))])
  @mock.patch.object(step_util, 'GetOS')
  def testCreateDisabledVariant(self, os, expected_variant, mock_get_os):
    mock_get_os.return_value = os
    disabled_test_variant = detect_disabled_tests._CreateDisabledVariant(
        123, 'builder_name_msan', 'step_name')
    self.assertEqual(True, mock_get_os.call_args[1].get('partial_match'))
    self.assertEqual(expected_variant, disabled_test_variant)

  @parameterized.expand([
      (  # Tests have different keys, create two entries.
          {
              'local_tests': {
                  ndb.Key('LuciTest', 'test_key_2'): {('config1',)},
              },
              'new_disabled_variant': ('config1',),
              'expected_local_tests': {
                  ndb.Key('LuciTest', 'test_key_1'): {('config1',)},
                  ndb.Key('LuciTest', 'test_key_2'): {('config1',)},
              }
          },),
      (  # Tests have same key, create one entry with two variants.
          {
              'local_tests': {
                  ndb.Key('LuciTest', 'test_key_1'): {('config2',)},
              },
              'new_disabled_variant': ('config1',),
              'expected_local_tests': {
                  ndb.Key('LuciTest', 'test_key_1'): {('config1',),
                                                      ('config2',)},
              }
          },),
      (  # Cannot retrieve disabled variants. Does not add to local_tests.
          {
              'local_tests': {
                  ndb.Key('LuciTest', 'test_key_1'): {('config2',)},
              },
              'new_disabled_variant': None,
              'expected_local_tests': {
                  ndb.Key('LuciTest', 'test_key_1'): {('config2',)},
              },
          },),
  ])
  @mock.patch.object(
      LuciTest, 'CreateKey', return_value=ndb.Key('LuciTest', 'test_key_1'))
  @mock.patch.object(detect_disabled_tests, '_CreateDisabledVariant')
  def testCreateLocalTests(self, cases, mocked_disabled_variant, *_):
    rows = [{
        'builder_name': 'builder1',
        'build_id': 123,
        'bugs': None,
        'step_name': 'step_name',
        'test_name': 'test_name1'
    }]
    mocked_disabled_variant.return_value = cases['new_disabled_variant']

    # Updating local_tests
    local_tests = cases['local_tests']
    for row in rows:
      detect_disabled_tests._CreateLocalTests(row, local_tests)
    self.assertEqual(local_tests, cases['expected_local_tests'])

  @parameterized.expand([
      (  # Update an existing LuciTest.
          {
              'remote_test':
                  LuciTest(
                      key=LuciTest.CreateKey('a', 'b', 'c'),
                      disabled_test_variants=set(),
                      last_updated_time=datetime(2019, 6, 27, 0, 0, 0)),
              'test_key':
                  LuciTest.CreateKey('a', 'b', 'c'),
              'disabled_test_variants': {('config1', 'config2'),},
              'query_time':
                  datetime(2019, 6, 29, 0, 0, 0),
          },),
      (  # Create a new LuciTest.
          {
              'remote_test': None,
              'test_key': LuciTest.CreateKey('a', 'b', 'c'),
              'disabled_test_variants': {('config1', 'config2'),},
              'query_time': datetime(2019, 6, 29, 0, 0, 0),
          },),
  ])
  def testUpdateDatastore(self, cases):
    if cases['remote_test']:
      cases['remote_test'].put()
    future = detect_disabled_tests._UpdateDatastore(
        cases['test_key'], cases['disabled_test_variants'], cases['query_time'])
    future.get_result()
    updated_test = cases['test_key'].get()
    self.assertEqual(cases['disabled_test_variants'],
                     updated_test.disabled_test_variants)
    self.assertEqual(cases['query_time'], updated_test.last_updated_time)

  @parameterized.expand([
      (  # New test, should be updated.
          {
              'local_tests': {
                  ndb.Key('LuciTest', 'test_key'): {('config1',)},
              },
              'expected_remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'test_key'),
                      disabled_test_variants={('config1',)},
                      last_updated_time=datetime(2019, 6, 29, 0, 0, 0)),
          },),
      (  # No change in variants, should not be updated.
          {
              'remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'test_key'),
                      disabled_test_variants={('config1',)},
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0)),
              'local_tests': {
                  ndb.Key('LuciTest', 'test_key'): {('config1',)},
              },
              'expected_remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'test_key'),
                      disabled_test_variants={('config1',)},
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0)),
          },),
      (  # Change in variants, should be updated.
          {
              'remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'test_key'),
                      disabled_test_variants={('config1',)},
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0)),
              'local_tests': {
                  ndb.Key('LuciTest', 'test_key'): {('config2',)},
              },
              'expected_remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'test_key'),
                      disabled_test_variants={('config2',)},
                      last_updated_time=datetime(2019, 6, 29, 0, 0, 0)),
          },),
      (  # Test does not appear in local_tests, should not be updated.
          {
              'remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'test_key'),
                      disabled_test_variants={('config1',)},
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0)),
              'local_tests': {},
              'expected_remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'test_key'),
                      disabled_test_variants={('config1',)},
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0)),
          },),
  ])
  def testUpdateCurrentlyDisabledTests(self, cases):
    remote_test = cases.get('remote_test')
    if remote_test:
      remote_test.put()
    detect_disabled_tests._UpdateCurrentlyDisabledTests(
        cases['local_tests'], datetime(2019, 6, 29, 0, 0, 0))
    remote_tests = LuciTest.query().fetch()

    self.assertEqual(1, len(remote_tests))
    self.assertIn(cases['expected_remote_test'], remote_tests)

  @parameterized.expand([
      (  # Currently disabled test, should not be updated.
          {
              'remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'test_key'),
                      disabled_test_variants={('config1',)},
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0)),
              'local_tests': {
                  ndb.Key('LuciTest', 'test_key'): {('config1',), ('config2',)},
              },
              'expected_remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'test_key'),
                      disabled_test_variants={('config1',)},
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0)),
          },),
      (  # No longer disabled test, should be updated.
          {
              'remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'test_key'),
                      disabled_test_variants={('config1',)},
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0)),
              'local_tests': {},
              'expected_remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'test_key'),
                      disabled_test_variants=set(),
                      last_updated_time=datetime(2019, 6, 29, 0, 0, 0)),
          },),
      (  # Not disabled test, should not be updated.
          {
              'remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'test_key'),
                      disabled_test_variants=set(),
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0)),
              'local_tests': {},
              'expected_remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'test_key'),
                      disabled_test_variants=set(),
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0)),
          },),
  ])
  def testUpdateNoLongerDisabledTests(self, cases):
    cases['remote_test'].put()
    detect_disabled_tests._UpdateNoLongerDisabledTests(
        cases['local_tests'], datetime(2019, 6, 29, 0, 0, 0))
    remote_tests = LuciTest.query().fetch()

    self.assertEqual(1, len(remote_tests))
    self.assertIn(cases['expected_remote_test'], remote_tests)

  @parameterized.expand([
      (  # Currently disabled, no change in variants, should not be updated.
          {
              'remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest',
                                  'chromium@normal_step_name@test_name1'),
                      disabled_test_variants={(
                          'ASan:True',
                          'MSan:True',
                          'os:os1',
                      )},
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0)),
              'expected_remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest',
                                  'chromium@normal_step_name@test_name1'),
                      disabled_test_variants={(
                          'ASan:True',
                          'MSan:True',
                          'os:os1',
                      )},
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0))
          },),
      (  # Currently disabled, change in variants, should be updated.
          {
              'remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest',
                                  'chromium@normal_step_name@test_name1'),
                      disabled_test_variants={('os:os2',)},
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0)),
              'expected_remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest',
                                  'chromium@normal_step_name@test_name1'),
                      disabled_test_variants={(
                          'ASan:True',
                          'MSan:True',
                          'os:os1',
                      )},
                      last_updated_time=datetime(2019, 6, 29, 0, 0, 0))
          },),
      (  # No longer disabled, should be updated.
          {
              'remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest',
                                  'chromium@normal_step_name@test_name2'),
                      disabled_test_variants={('os:os2',)},
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0)),
              'expected_remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest',
                                  'chromium@normal_step_name@test_name2'),
                      disabled_test_variants=set(),
                      last_updated_time=datetime(2019, 6, 29, 0, 0, 0))
          },),
      (  # Not disabled, should not be updated.
          {
              'remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest',
                                  'chromium@normal_step_name@test_name2'),
                      disabled_test_variants=set(),
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0)),
              'expected_remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest',
                                  'chromium@normal_step_name@test_name2'),
                      disabled_test_variants=set(),
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0))
          },),
  ])
  @mock.patch.object(step_util, 'GetOS', return_value='os1')
  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2019, 6, 29, 0, 0, 0))
  @mock.patch.object(bigquery_helper, '_GetBigqueryClient')
  def testProcessQueryForDisabledTests(self, cases, mocked_get_client, *_):
    cases['remote_test'].put()
    query_response = self._GetEmptyDisabledTestQueryResponse()
    self._AddRowToDisabledTestQueryResponse(
        query_response=query_response,
        step_name='step_name',
        test_name='test_name1',
        builder_name='msan_asan_builder1',
        build_id=123,
        bugs=None)

    mocked_client = mock.Mock()
    mocked_get_client.return_value = mocked_client
    mocked_client.jobs().query().execute.return_value = query_response
    mocked_client.jobs().getQueryResults().execute.return_value = query_response

    detect_disabled_tests.ProcessQueryForDisabledTests()
    self.assertEqual(cases['expected_remote_test'],
                     cases['remote_test'].key.get())

  @parameterized.expand([
      ({}, 2, [
          (True, ['row1', 'row2'], 'job', None),
      ]),
      ({}, 0, [
          (True, [], 'job', None),
      ]),
      ({}, 6, [
          (True, ['row1', 'row2'], 'job', 'page'),
          (True, ['row1', 'row2'], 'job', 'next_page'),
          (True, ['row1', 'row2'], 'job', None),
      ]),
  ])
  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2019, 6, 29, 0, 0, 0))
  @mock.patch.object(bigquery_helper, '_GetBigqueryClient')
  @mock.patch.object(detect_disabled_tests, '_CreateLocalTests')
  @mock.patch.object(bigquery_helper, 'ExecuteQuery')
  def testExecuteQuery(self, local_tests, mock_local_call_count, paged_rows,
                       mock_execute_query, mock_create_local, *_):
    mock_execute_query.side_effect = paged_rows
    actual_local_tests = detect_disabled_tests._ExecuteQuery()
    self.assertEqual(local_tests, actual_local_tests)
    self.assertEqual(mock_local_call_count, mock_create_local.call_count)

  @parameterized.expand([
      (0, [
          (False, [], 'job', None),
      ]),
      (4, [
          (True, ['row1', 'row2'], 'job', 'page'),
          (True, ['row1', 'row2'], 'job', 'next_page'),
          (False, [], 'job', None),
      ]),
  ])
  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2019, 6, 29, 0, 0, 0))
  @mock.patch.object(bigquery_helper, '_GetBigqueryClient')
  @mock.patch.object(detect_disabled_tests, '_CreateLocalTests')
  @mock.patch.object(bigquery_helper, 'ExecuteQuery')
  def testExecuteQueryFails(self, mock_local_call_count, paged_rows,
                            mock_execute_query, mock_create_local, *_):
    mock_execute_query.side_effect = paged_rows
    with self.assertRaises(Exception):
      detect_disabled_tests._ExecuteQuery()
    self.assertEqual(mock_local_call_count, mock_create_local.call_count)
