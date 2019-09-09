# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from parameterized import parameterized

from google.appengine.ext import ndb

from waterfall.test.wf_testcase import WaterfallTestCase

from common.swarmbucket import swarmbucket
from libs import time_util
from model.flake.flake import Flake
from model.flake.flake import FlakeIssue
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
                'mode': 'REPEATED'
            }]
        }
    }

  def _AddRowToDisabledTestQueryResponse(self,
                                         query_response,
                                         test_name='test_name',
                                         step_name='step_name',
                                         builder_name='builder',
                                         build_id=999,
                                         bugs=None):
    """Adds a row to the provided query response for testing.

    To obtain a query response for testing for the initial time, please call
    _GetEmptyDisabledTestQueryResponse. Note that the fields in the schema and
    the parameters of this method must match exactly (including orders), so if
    a new field is added to the schema, please update this method accordingly.
    """
    if not bugs:
      bugs = []
    bugs = [{'v': bug} for bug in bugs]
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

  @parameterized.expand([
      ('os', 'builder_name_msan', ('MSan:True', 'os:os')),
      (None, 'builder_name_msan', ('MSan:True',)),
      (None, 'builder_name', (detect_disabled_tests._DEFAULT_CONFIG,)),
  ])
  @mock.patch.object(step_util, 'GetOS')
  def testCreateDisabledVariant(self, os, builder_name, expected_variant,
                                mock_get_os):
    mock_get_os.return_value = os
    disabled_test_variant = detect_disabled_tests._CreateDisabledVariant(
        123, builder_name, 'step_name')
    self.assertEqual(True, mock_get_os.call_args[1].get('partial_match'))
    self.assertEqual(expected_variant, disabled_test_variant)

  @parameterized.expand([
      ([
          'https://bugs.chromium.org/p/chromium/issues/detail?id=123',
          'http://bugs.chromium.org/p/chromium/issues/detail?id=1234512345'
      ], {
          ndb.Key('FlakeIssue', 'chromium@123'),
          ndb.Key('FlakeIssue', 'chromium@1234512345')
      }),
      ([
          'https://http://bugs.chromium.org/p/chromium/issues/detail?id=123',
          'http://https://bugs.chromium.org/p/chromium/issues/detail?id=12345'
      ], set()),
      ([
          'bugs.chromium.org/p/chromium/issues/detail?id=123',
          'bugs.chromium.org/p/chromium/issues/detail?id=12345'
      ], {
          ndb.Key('FlakeIssue', 'chromium@123'),
          ndb.Key('FlakeIssue', 'chromium@12345')
      }),
      ([
          'bugs.chromium.org/p/chromium/issues/detail?id=123invalid',
          'bugs.chromium.org/p/chromium/issues/detail?id=1234512345/invalid'
      ], set()),
      (['https://crbug.com/123', 'http://crbug.com/1234512345'], {
          ndb.Key('FlakeIssue', 'chromium@123'),
          ndb.Key('FlakeIssue', 'chromium@1234512345')
      }),
      ([
          'https://https://crbug.com/123',
          'https://https://crbug.com/1234512345'
      ], set()),
      (['crbug.com/123', 'crbug.com/1234512345'], {
          ndb.Key('FlakeIssue', 'chromium@123'),
          ndb.Key('FlakeIssue', 'chromium@1234512345')
      }),
      ([
          'crbug.com/123invalid', 'invalidcrbug.com/1234',
          'invalidcrbug.com/123invalid'
      ], set()),
      ([None, None], set()),
      ([], set()),
  ])
  def testCreateIssueKeys(self, bugs, expected_issues_keys):
    self.assertEqual(expected_issues_keys,
                     detect_disabled_tests._CreateIssueKeys(bugs))

  def testCreateIssueExisting(self):
    existing_flake_issue = FlakeIssue.Create(_DEFAULT_LUCI_PROJECT, 123)
    existing_flake_issue.status = 'existing_flake_issue'
    existing_flake_issue.put()
    future = detect_disabled_tests._CreateIssue(
        ndb.Key('FlakeIssue', 'chromium@123'))
    future.get_result()
    flake_issues = FlakeIssue.query().fetch()
    self.assertEqual(1, len(flake_issues))
    self.assertIn(existing_flake_issue, flake_issues)

  def testCreateIssueNew(self):
    future = detect_disabled_tests._CreateIssue(
        ndb.Key('FlakeIssue', 'chromium@123'))
    future.get_result()
    flake_issues = FlakeIssue.query().fetch()
    expected_flake_issue = FlakeIssue.Create('chromium', 123)
    self.assertEqual(1, len(flake_issues))
    self.assertIn(expected_flake_issue, flake_issues)

  @parameterized.expand([
      (  # Tests have different keys, create two entries.
          {
              'local_tests': {
                  ndb.Key('LuciTest', 'a@b@test_key_2'): {
                      'disabled_test_variants': {('config1',)},
                      'issue_keys': {ndb.Key('FlakeIssue', 'chromium@123')},
                      'tags': set()
                  },
              },
              'new_disabled_variant': ('config1',),
              'expected_local_tests': {
                  ndb.Key('LuciTest', 'a@b@test_key_1'): {
                      'disabled_test_variants': {('config1',)},
                      'issue_keys': {ndb.Key('FlakeIssue', 'chromium@123')},
                      'tags': set()
                  },
                  ndb.Key('LuciTest', 'a@b@test_key_2'): {
                      'disabled_test_variants': {('config1',)},
                      'issue_keys': {ndb.Key('FlakeIssue', 'chromium@123')},
                      'tags': set()
                  },
              }
          },),
      (  # Tests have same key, update variants and issue_keys
          {
              'local_tests': {
                  ndb.Key('LuciTest', 'a@b@test_key_1'): {
                      'disabled_test_variants': {('config1',),},
                      'issue_keys': {ndb.Key('FlakeIssue', 'chromium@124')},
                      'tags': set()
                  },
              },
              'new_disabled_variant': ('config2',),
              'expected_local_tests': {
                  ndb.Key('LuciTest', 'a@b@test_key_1'): {
                      'disabled_test_variants': {
                          ('config1',),
                          ('config2',),
                      },
                      'issue_keys': {
                          ndb.Key('FlakeIssue', 'chromium@123'),
                          ndb.Key('FlakeIssue', 'chromium@124')
                      },
                      'tags': set()
                  },
              }
          },),
      (  # Cannot retrieve disabled variants. Adds Default config.
          {
              'local_tests': {
                  ndb.Key('LuciTest', 'a@b@test_key_1'): {
                      'disabled_test_variants': {('config2',)},
                      'issue_keys': {ndb.Key('FlakeIssue', 'chromium@123')},
                      'tags': set()
                  },
              },
              'new_disabled_variant': ('Unknown',),
              'expected_local_tests': {
                  ndb.Key('LuciTest', 'a@b@test_key_1'): {
                      'disabled_test_variants': {('config2',), ('Unknown',)},
                      'issue_keys': {ndb.Key('FlakeIssue', 'chromium@123')},
                      'tags': set()
                  },
              },
          },),
  ])
  @mock.patch.object(
      LuciTest, 'CreateKey', return_value=ndb.Key('LuciTest', 'a@b@test_key_1'))
  @mock.patch.object(detect_disabled_tests, '_CreateDisabledVariant')
  def testCreateLocalTests(self, cases, mocked_disabled_variant, *_):
    rows = [{
        'builder_name': 'builder1',
        'build_id': 123,
        'bugs': ['crbug.com/123'],
        'step_name': 'step_name',
        'test_name': 'test_name1'
    }]
    mocked_disabled_variant.return_value = cases['new_disabled_variant']

    # Updating local_tests
    local_tests = cases['local_tests']
    for row in rows:
      detect_disabled_tests._CreateLocalTests(row, local_tests)
    self.assertEqual(local_tests, cases['expected_local_tests'])

  # To filter out tests results with invalid build_id.
  # TODO (crbug.com/999215): Remove this check after test-results is fixed.
  def testCreateLocalTestsInvalidBuildID(self):
    local_tests = {}
    rows = [{
        'builder_name': 'builder1',
        'build_id': 1,
        'bugs': ['crbug.com/123'],
        'step_name': 'step_name',
        'test_name': 'test_name1'
    }]
    for row in rows:
      detect_disabled_tests._CreateLocalTests(row, local_tests)
    self.assertEqual({}, local_tests)

  @parameterized.expand([
      # Update an existing LuciTest.
      (  # Only variants
          {
              'remote_test':
                  LuciTest(
                      key=LuciTest.CreateKey('a', 'b', 'c'),
                      disabled_test_variants=set(),
                      issue_keys=[ndb.Key('FlakeIssue', 'bug1')],
                      tags=set(),
                      last_updated_time=datetime(2019, 6, 27, 0, 0, 0)),
              'test_key':
                  LuciTest.CreateKey('a', 'b', 'c'),
              'disabled_test_variants': {('config1', 'config2'),},
              'issue_keys':
                  set(),
              'expected_issue_keys': [ndb.Key('FlakeIssue', 'bug1')],
              'query_time':
                  datetime(2019, 6, 29, 0, 0, 0),
          },),  # Update an existing LuciTest.
      (  # Only issue_keys.
          {
              'remote_test':
                  LuciTest(
                      key=LuciTest.CreateKey('a', 'b', 'c'),
                      disabled_test_variants={
                          ('config1', 'config2'),
                      },
                      issue_keys=[ndb.Key('FlakeIssue', 'bug1')],
                      tags=set(),
                      last_updated_time=datetime(2019, 6, 27, 0, 0, 0)),
              'test_key':
                  LuciTest.CreateKey('a', 'b', 'c'),
              'disabled_test_variants': {('config1', 'config2'),},
              'issue_keys': {
                  ndb.Key('FlakeIssue', 'bug1'),
                  ndb.Key('FlakeIssue', 'bug2')
              },
              'expected_issue_keys': [
                  ndb.Key('FlakeIssue', 'bug1'),
                  ndb.Key('FlakeIssue', 'bug2')
              ],
              'query_time':
                  datetime(2019, 6, 29, 0, 0, 0),
          },),  # Update an existing LuciTest.
      (  # Variants and issue_keys.
          {
              'remote_test':
                  LuciTest(
                      key=LuciTest.CreateKey('a', 'b', 'c'),
                      disabled_test_variants=set(),
                      issue_keys=[ndb.Key('FlakeIssue', 'bug1')],
                      tags=set(),
                      last_updated_time=datetime(2019, 6, 27, 0, 0, 0)),
              'test_key':
                  LuciTest.CreateKey('a', 'b', 'c'),
              'disabled_test_variants': {('config1', 'config2'),},
              'issue_keys': {
                  ndb.Key('FlakeIssue', 'bug1'),
                  ndb.Key('FlakeIssue', 'bug2')
              },
              'expected_issue_keys': [
                  ndb.Key('FlakeIssue', 'bug1'),
                  ndb.Key('FlakeIssue', 'bug2')
              ],
              'query_time':
                  datetime(2019, 6, 29, 0, 0, 0),
          },),
      # Create a new LuciTest.
      (  # Only variants.
          {
              'remote_test': None,
              'test_key': LuciTest.CreateKey('a', 'b', 'c'),
              'disabled_test_variants': {('config1', 'config2'),},
              'expected_issue_keys': [],
              'query_time': datetime(2019, 6, 29, 0, 0, 0),
          },),
      (  # Only issue_keys.
          #TODO: Default config if empty tuple
          {
              'remote_test': None,
              'test_key': LuciTest.CreateKey('a', 'b', 'c'),
              'disabled_test_variants': {('Unknown',)},
              'issue_keys': {ndb.Key('FlakeIssue', 'bug1')},
              'expected_issue_keys': [ndb.Key('FlakeIssue', 'bug1')],
              'query_time': datetime(2019, 6, 29, 0, 0, 0),
          },),
      (  # Variants and issue_keys.
          {
              'remote_test': None,
              'test_key': LuciTest.CreateKey('a', 'b', 'c'),
              'disabled_test_variants': {('config1', 'config2'),},
              'issue_keys': {ndb.Key('FlakeIssue', 'bug1')},
              'expected_issue_keys': [ndb.Key('FlakeIssue', 'bug1')],
              'query_time': datetime(2019, 6, 29, 0, 0, 0),
          },),
  ])
  def testUpdateDatastore(self, cases):
    if cases['remote_test']:
      cases['remote_test'].put()
    test_attributes = {
        'disabled_test_variants': cases.get('disabled_test_variants', set()),
        'issue_keys': cases.get('issue_keys', set()),
        'tags': cases.get('tags', set())
    }
    future = detect_disabled_tests._UpdateDatastore(
        cases['test_key'], test_attributes, cases['query_time'])
    future.get_result()
    updated_test = cases['test_key'].get()
    self.assertEqual(cases['disabled_test_variants'],
                     updated_test.disabled_test_variants)
    self.assertEqual(cases['query_time'], updated_test.last_updated_time)
    self.assertEqual(cases['expected_issue_keys'], updated_test.issue_keys)

  @parameterized.expand([
      (  # New test, should be updated.
          {
              'local_tests': {
                  ndb.Key('LuciTest', 'a@b@test_key'): {
                      'disabled_test_variants': {('config1',)},
                      'issue_keys': {ndb.Key('FlakeIssue', 'chromium@123')},
                      'tags': set()
                  },
              },
              'expected_remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'a@b@test_key'),
                      disabled_test_variants={('config1',)},
                      last_updated_time=datetime(2019, 6, 29, 0, 0, 0),
                      tags=set(),
                      issue_keys=[ndb.Key('FlakeIssue', 'chromium@123')]),
          },),
      (  # No change, should not be updated.
          {
              'remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'a@b@test_key'),
                      disabled_test_variants={('config1',)},
                      tags=set(),
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0),
                      issue_keys=[ndb.Key('FlakeIssue', 'chromium@123')]),
              'local_tests': {
                  ndb.Key('LuciTest', 'a@b@test_key'): {
                      'disabled_test_variants': {('config1',)},
                      'issue_keys': {ndb.Key('FlakeIssue', 'chromium@123')},
                      'tags': set()
                  },
              },
              'expected_remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'a@b@test_key'),
                      disabled_test_variants={('config1',)},
                      tags=set(),
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0),
                      issue_keys=[ndb.Key('FlakeIssue', 'chromium@123')]),
          },),
      (  # Change in variants, should be updated.
          {
              'remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'a@b@test_key'),
                      disabled_test_variants={('config1',)},
                      tags=set(),
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0),
                      issue_keys=[]),
              'local_tests': {
                  ndb.Key('LuciTest', 'a@b@test_key'): {
                      'disabled_test_variants': {('config2',)},
                      'issue_keys': set(),
                      'tags': set()
                  },
              },
              'expected_remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'a@b@test_key'),
                      disabled_test_variants={('config2',)},
                      tags=set(),
                      last_updated_time=datetime(2019, 6, 29, 0, 0, 0),
                      issue_keys=[]),
          },),
      (  # Change in variants, no new bugs, issue_keys should not be updated.
          {
              'remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'a@b@test_key'),
                      disabled_test_variants={('config1',)},
                      tags=set(),
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0),
                      issue_keys=[ndb.Key('FlakeIssue', 'chromium@123')]),
              'local_tests': {
                  ndb.Key('LuciTest', 'a@b@test_key'): {
                      'disabled_test_variants': {('config2',)},
                      'issue_keys': set(),
                      'tags': set()
                  },
              },
              'expected_remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'a@b@test_key'),
                      disabled_test_variants={('config2',)},
                      tags=set(),
                      last_updated_time=datetime(2019, 6, 29, 0, 0, 0),
                      issue_keys=[ndb.Key('FlakeIssue', 'chromium@123')]),
          },),
      (  # New bugs, should be updated.
          {
              'remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'a@b@test_key'),
                      disabled_test_variants={('config1',)},
                      tags=set(),
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0),
                      issue_keys=[ndb.Key('FlakeIssue', 'chromium@124')]),
              'local_tests': {
                  ndb.Key('LuciTest', 'a@b@test_key'): {
                      'disabled_test_variants': {('config1',)},
                      'issue_keys': {ndb.Key('FlakeIssue', 'chromium@123')},
                      'tags': set()
                  },
              },
              'expected_remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'a@b@test_key'),
                      disabled_test_variants={('config1',)},
                      tags=set(),
                      last_updated_time=datetime(2019, 6, 29, 0, 0, 0),
                      issue_keys=[
                          ndb.Key('FlakeIssue', 'chromium@123'),
                          ndb.Key('FlakeIssue', 'chromium@124')
                      ]),
          },),
      (  # Change in variants and new bugs, should be updated.
          {
              'remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'a@b@test_key'),
                      disabled_test_variants={('config1',)},
                      tags=set(),
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0),
                      issue_keys=[ndb.Key('FlakeIssue', 'chromium@124')]),
              'local_tests': {
                  ndb.Key('LuciTest', 'a@b@test_key'): {
                      'disabled_test_variants': {('config2',)},
                      'issue_keys': {
                          ndb.Key('FlakeIssue', 'chromium@123'),
                          ndb.Key('FlakeIssue', 'chromium@124')
                      },
                      'tags': set()
                  },
              },
              'expected_remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'a@b@test_key'),
                      disabled_test_variants={('config2',)},
                      tags=set(),
                      last_updated_time=datetime(2019, 6, 29, 0, 0, 0),
                      issue_keys=[
                          ndb.Key('FlakeIssue', 'chromium@123'),
                          ndb.Key('FlakeIssue', 'chromium@124')
                      ]),
          },),
      (  # Test does not appear in local_tests, should not be updated.
          {
              'remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'a@b@test_key'),
                      disabled_test_variants={('config1',)},
                      tags=set(),
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0)),
              'local_tests': {},
              'expected_remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'a@b@test_key'),
                      disabled_test_variants={('config1',)},
                      tags=set(),
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
                      key=ndb.Key('LuciTest', 'a@b@test_key'),
                      disabled_test_variants={('config1',)},
                      tags=set(),
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0)),
              'local_tests': {
                  ndb.Key('LuciTest', 'a@b@test_key'): {
                      'disabled_test_variants': {('config1',), ('config2',)},
                      'issue_keys': set()
                  }
              },
              'expected_remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'a@b@test_key'),
                      disabled_test_variants={('config1',)},
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0)),
          },),
      (  # No longer disabled test, should be updated.
          {
              'remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'a@b@test_key'),
                      disabled_test_variants={('config1',)},
                      tags=set(),
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0),
                      issue_keys=[ndb.Key('FlakeIssue', 'chromium@123')]),
              'local_tests': {},
              'expected_remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'a@b@test_key'),
                      disabled_test_variants=set(),
                      tags=set(),
                      last_updated_time=datetime(2019, 6, 29, 0, 0, 0),
                      issue_keys=[ndb.Key('FlakeIssue', 'chromium@123')]),
          },),
      (  # Not disabled test, should not be updated.
          {
              'remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'a@b@test_key'),
                      disabled_test_variants=set(),
                      tags=set(),
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0)),
              'local_tests': {},
              'expected_remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest', 'a@b@test_key'),
                      disabled_test_variants=set(),
                      tags=set(),
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
      (  # Currently disabled, no changes, should not be updated.
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
                      tags=set(),
                      issue_keys=[ndb.Key('FlakeIssue', 'chromium@123')],
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
                      issue_keys=[ndb.Key('FlakeIssue', 'chromium@123')],
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0))
          },),
      (  # Currently disabled, change in variants, should be updated.
          {
              'remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest',
                                  'chromium@normal_step_name@test_name1'),
                      disabled_test_variants={('os:os2',)},
                      tags=set(),
                      issue_keys=[ndb.Key('FlakeIssue', 'chromium@123')],
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
                      tags=set(),
                      issue_keys=[ndb.Key('FlakeIssue', 'chromium@123')],
                      last_updated_time=datetime(2019, 6, 29, 0, 0, 0))
          },),
      (  # Currently disabled, change in bugs, should be updated.
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
                      tags=set(),
                      issue_keys=[],
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
                      tags=set(),
                      issue_keys=[ndb.Key('FlakeIssue', 'chromium@123')],
                      last_updated_time=datetime(2019, 6, 29, 0, 0, 0))
          },),
      (  # No longer disabled, should be updated.
          {
              'remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest',
                                  'chromium@normal_step_name@test_name2'),
                      disabled_test_variants={('os:os2',)},
                      tags=set(),
                      issue_keys=[ndb.Key('FlakeIssue', 'chromium@123')],
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0)),
              'expected_remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest',
                                  'chromium@normal_step_name@test_name2'),
                      issue_keys=[ndb.Key('FlakeIssue', 'chromium@123')],
                      tags=set(),
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
                      tags=set(),
                      issue_keys=[ndb.Key('FlakeIssue', 'chromium@123')],
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0)),
              'expected_remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest',
                                  'chromium@normal_step_name@test_name2'),
                      disabled_test_variants=set(),
                      tags=set(),
                      issue_keys=[ndb.Key('FlakeIssue', 'chromium@123')],
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0))
          },),
  ])
  @mock.patch.object(swarmbucket, 'GetMasters', return_value=['chromium.linux'])
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
        bugs=['crbug.com/123'])

    mocked_client = mock.Mock()
    mocked_get_client.return_value = mocked_client
    mocked_client.jobs().query().execute.return_value = query_response
    mocked_client.jobs().getQueryResults().execute.return_value = query_response

    detect_disabled_tests.ProcessQueryForDisabledTests()
    self.assertEqual(cases['expected_remote_test'],
                     cases['remote_test'].key.get())

  @parameterized.expand([
      ({}, 2, [
          (True, ['row1', 'row2'], None),
      ]),
      ({}, 6, [
          (True, ['row1', 'row2'], 'page'),
          (True, ['row1', 'row2'], 'next_page'),
          (True, ['row1', 'row2'], None),
      ]),
  ])
  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2019, 6, 29, 0, 0, 0))
  @mock.patch.object(bigquery_helper, '_GetBigqueryClient')
  @mock.patch.object(bigquery_helper, '_RunBigQuery', return_value='job')
  @mock.patch.object(detect_disabled_tests, '_CreateLocalTests')
  @mock.patch.object(bigquery_helper, '_ReadQueryResultsPage')
  def testExecuteQuery(self, local_tests, mock_local_call_count, paged_rows,
                       mock_execute_query, mock_create_local, *_):
    mock_execute_query.side_effect = paged_rows
    actual_local_tests = detect_disabled_tests._ExecuteQuery()
    self.assertEqual(local_tests, actual_local_tests)
    self.assertEqual(mock_local_call_count, mock_create_local.call_count)

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2019, 6, 29, 0, 0, 0))
  @mock.patch.object(bigquery_helper, '_GetBigqueryClient')
  @mock.patch.object(bigquery_helper, '_RunBigQuery', return_value='job')
  @mock.patch.object(detect_disabled_tests, '_CreateLocalTests')
  @mock.patch.object(bigquery_helper, '_ReadQueryResultsPage')
  def testExecuteQueryNoRows(self, mock_execute_query, mock_create_local, *_):
    mock_execute_query.side_effect = [
        (True, [], None),
    ]
    with self.assertRaises(AssertionError):
      detect_disabled_tests._ExecuteQuery()

    self.assertFalse(mock_create_local.called)
