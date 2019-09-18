# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from parameterized import parameterized

from google.appengine.ext import ndb

from waterfall.test.wf_testcase import WaterfallTestCase

from common.swarmbucket import swarmbucket
from libs import test_name_util
from libs import time_util
from model.flake.flake import Flake
from model.flake.flake import FlakeIssue
from model.flake.flake import TestLocation as TestLocation
from model.test_inventory import LuciTest
from services import bigquery_helper
from services import step_util
from services import test_tag_util
from services.disabled_tests import detect_disabled_tests

_DEFAULT_LUCI_PROJECT = 'chromium'


class DetectTestDisablementTest(WaterfallTestCase):

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
    super(DetectTestDisablementTest, self).setUp()

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

  @mock.patch.object(
      detect_disabled_tests,
      '_GetNewTestTags',
      return_value={'mock_tag::mock_tag'})
  @mock.patch.object(
      detect_disabled_tests,
      '_CreateDisabledVariant',
      return_value=('config1',))
  @mock.patch.object(
      Flake, 'NormalizeTestName', return_value='normal_test_name')
  def testCreateLocalTestsNewTest(self, *_):
    row = {
        'builder_name': 'builder1',
        'build_id': 123,
        'bugs': ['crbug.com/123'],
        'step_name': 'step_name',
        'test_name': 'test_name1'
    }
    local_tests = {}
    detect_disabled_tests._CreateLocalTests(row, local_tests, {}, {})
    expected_local_test = {
        ndb.Key('LuciTest', 'chromium@normal_step_name@normal_test_name'): {
            'disabled_test_variants': {('config1',)},
            'issue_keys': {ndb.Key('FlakeIssue', 'chromium@123')},
            'tags': {'mock_tag::mock_tag'}
        }
    }
    self.assertEqual(expected_local_test, local_tests)

  @mock.patch.object(
      detect_disabled_tests,
      '_GetNewTestTags',
      return_value={'mock_tag::mock_tag1'})
  @mock.patch.object(
      detect_disabled_tests,
      '_CreateDisabledVariant',
      return_value=('config1',))
  @mock.patch.object(
      Flake, 'NormalizeTestName', return_value='normal_test_name')
  def testCreateLocalTestsExistingTest(self, *_):
    row = {
        'builder_name': 'builder1',
        'build_id': 123,
        'bugs': ['crbug.com/123'],
        'step_name': 'step_name',
        'test_name': 'test_name1'
    }
    local_tests = {
        ndb.Key('LuciTest', 'chromium@normal_step_name@normal_test_name'): {
            'disabled_test_variants': {('config2',)},
            'issue_keys': {ndb.Key('FlakeIssue', 'chromium@124')},
            'tags': {'mock_tag::mock_tag2'}
        }
    }
    detect_disabled_tests._CreateLocalTests(row, local_tests, {}, {})
    expected_local_tests = {
        ndb.Key('LuciTest', 'chromium@normal_step_name@normal_test_name'): {
            'disabled_test_variants': {('config2',), ('config1',)},
            'issue_keys': {
                ndb.Key('FlakeIssue', 'chromium@124'),
                ndb.Key('FlakeIssue', 'chromium@123')
            },
            'tags': {'mock_tag::mock_tag2', 'mock_tag::mock_tag1'}
        }
    }
    self.assertEqual(expected_local_tests, local_tests)

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
      detect_disabled_tests._CreateLocalTests(row, local_tests, {}, {})
    self.assertEqual({}, local_tests)

  @mock.patch.object(test_tag_util, 'GetTestLocation')
  @mock.patch.object(test_name_util, 'GTEST_REGEX')
  def testCreateLocationBasedTagsGTest(self, mock_regex, mock_get_location):
    mock_regex.match.return_value = True
    self.assertEqual(0, mock_get_location.call_count)

  @parameterized.expand([
      ({
          'tags': {'component::tag', 'step::tag'},
          'normalized_step_name': 'step',
          'has_flake': True,
          'mocked_for_gpu_test_calls': 0,
          'mocked_get_from_flake_calls': 0,
          'mocked_create_calls': 0
      },),
      ({
          'tags': {'step::tag'},
          'normalized_step_name': 'telemetry_gpu_integration_test',
          'has_flake': True,
          'mocked_for_gpu_test_calls': 1,
          'mocked_get_from_flake_calls': 0,
          'mocked_create_calls': 0
      },),
      ({
          'tags': {'step::tag'},
          'normalized_step_name': 'step',
          'has_flake': True,
          'mocked_for_gpu_test_calls': 0,
          'mocked_get_from_flake_calls': 1,
          'mocked_create_calls': 0
      },),
      ({
          'tags': {'step::tag'},
          'normalized_step_name': 'step',
          'has_flake': False,
          'mocked_for_gpu_test_calls': 0,
          'mocked_get_from_flake_calls': 1,
          'mocked_create_calls': 1
      },),
  ])
  @mock.patch.object(detect_disabled_tests, '_CreateLocationBasedTags')
  @mock.patch.object(detect_disabled_tests, '_GetLocationBasedTagsFromFlake')
  @mock.patch.object(detect_disabled_tests, '_GetLocationBasedTagsForGPUTest')
  def testGetLocationBasedTags(self, cases, mocked_for_gpu_test,
                               mocked_get_from_flake, mocked_create):
    mocked_get_from_flake.return_value = {'tag'
                                         } if cases['has_flake'] else set()
    detect_disabled_tests._GetLocationBasedTags(cases['tags'], 'step', 'test',
                                                cases['normalized_step_name'],
                                                'normal_test', 123, {}, {})
    self.assertEqual(cases['mocked_for_gpu_test_calls'],
                     mocked_for_gpu_test.call_count)
    self.assertEqual(cases['mocked_get_from_flake_calls'],
                     mocked_get_from_flake.call_count)
    self.assertEqual(cases['mocked_create_calls'], mocked_create.call_count)

  def testGetNewTestTagsExistingLocationTags(self):
    existing_tags = {'component::tag'}
    expected_tags = sorted({
        'step::step (with patch)',
        'test_type::step',
    })
    self.assertEqual(
        expected_tags,
        sorted(
            detect_disabled_tests._GetNewTestTags(
                existing_tags, 'step (with patch)', 'test', 'normal_step',
                'normal_test', 123, {}, {})))

  def testGetTestLocationWithFlake(self):
    luci_project = detect_disabled_tests._DEFAULT_LUCI_PROJECT
    normalized_step_name = 'normal_step'
    normalized_test_name = 'normal_test'
    flake = Flake.Create(luci_project, normalized_step_name,
                         normalized_test_name, 'label')
    flake.tags = sorted({
        'watchlist::feature',
        'watchlist::url',
        'directory::base/feature/',
        'directory::base/',
        'source::base/feature/url_test.cc',
        'component::root>a>b',
        'parent_component::root>a>b',
        'parent_component::root>a',
        'parent_component::root',
        'step::from/flake',
        'test_type::from/flake',
        'other_tag::from/flake',
    })
    flake.put()

    expected_tags = sorted({
        'test_type::step',
        'step::step (with patch)',
        'watchlist::feature',
        'watchlist::url',
        'directory::base/feature/',
        'directory::base/',
        'source::base/feature/url_test.cc',
        'component::root>a>b',
        'parent_component::root>a>b',
        'parent_component::root>a',
        'parent_component::root',
    })
    self.assertEqual(
        expected_tags,
        sorted(
            detect_disabled_tests._GetNewTestTags(
                {}, 'step (with patch)', 'test', normalized_step_name,
                normalized_test_name, 123, {}, {})))

  @parameterized.expand([
      (
          TestLocation(file_path='base/feature/url_test.cc'),
          {
              'test_type::step',
              'step::step (with patch)',
              'watchlist::feature',
              'watchlist::url',
              'directory::base/feature/',
              'directory::base/',
              'source::base/feature/url_test.cc',
              'component::root>a>b',
              'parent_component::root>a>b',
              'parent_component::root>a',
              'parent_component::root',
          },
      ),
      (
          None,
          {
              'test_type::step',
              'step::step (with patch)',
              'component::%s' % test_tag_util.DEFAULT_COMPONENT,
              'parent_component::%s' % test_tag_util.DEFAULT_COMPONENT,
          },
      ),
  ])
  @mock.patch.object(test_tag_util, 'GetTestLocation')
  def testGetNewTestTagsNoFlake(self, location, expected_tags,
                                mock_get_location):
    watchlists = {
        'feature': 'base/feature',
        'url': r'base/feature/url_test\.cc',
        'other': 'a/b/c',
    }
    component_mapping = {
        'base/feature/': 'root>a>b',
        'base/feature/url': 'root>a>b>c',
    }
    mock_get_location.return_value = location
    self.assertEqual(
        expected_tags,
        detect_disabled_tests._GetNewTestTags({}, 'step (with patch)', 'test',
                                              'normal_step', 'normal_test', 123,
                                              component_mapping, watchlists))

  @mock.patch.object(
      step_util, 'GetCanonicalStepName', return_value='depth_capture_tests')
  def testGetNewTestTagsGPU(self, *_):
    existing_tags = {
        'test_type::context_lost_tests', 'step::context_lost_tests',
        'component::Internals>GPU>Testing'
    }
    expected_tags = sorted([
        'test_type::context_lost_tests', 'step::context_lost_tests',
        'test_type::depth_capture_tests', 'step::depth_capture_tests',
        'component::Internals>GPU>Testing'
    ])
    actual_tags = sorted(
        existing_tags.union(
            detect_disabled_tests._GetNewTestTags(
                existing_tags, 'depth_capture_tests', 'test_name',
                'telemetry_gpu_integration_test', 'normal_test', 123, {}, {})))
    self.assertEqual(expected_tags, actual_tags)

  @parameterized.expand([
      (  # Create a new LuciTest.
          {
              'remote_test': None,
              'test_key': LuciTest.CreateKey('a', 'b', 'c'),
              'test_attributes': {
                  'disabled_test_variants': {('config1', 'config2'),},
                  'issue_keys': {ndb.Key('FlakeIssue', 'bug1')},
                  'tags': {
                      'watchlist::new',
                      'directory::new',
                      'source::new',
                      'parent_component::new',
                      'component::new',
                      'step::new',
                      'test_type::new',
                  }
              },
              'expected_disabled_test_variants': {('config1', 'config2'),},
              'expected_issue_keys': [ndb.Key('FlakeIssue', 'bug1')],
              'expected_tags': {
                  'watchlist::new',
                  'directory::new',
                  'source::new',
                  'parent_component::new',
                  'component::new',
                  'step::new',
                  'test_type::new',
              },
              'query_time': datetime(2019, 6, 29, 0, 0, 0),
          },),
      (  # Update existing LuciTest
          {
              'remote_test':
                  LuciTest(
                      key=LuciTest.CreateKey('a', 'b', 'c'),
                      disabled_test_variants=set(),
                      issue_keys=[ndb.Key('FlakeIssue', 'bug1')],
                      tags={
                          'watchlist::existing',
                          'directory::existing',
                          'source::existing',
                          'parent_component::existing',
                          'component::existing',
                          'step::existing',
                          'test_type::existing',
                      },
                      last_updated_time=datetime(2019, 6, 27, 0, 0, 0)),
              'test_key':
                  LuciTest.CreateKey('a', 'b', 'c'),
              'test_attributes': {
                  'disabled_test_variants': {('config1', 'config2'),},
                  'issue_keys': {ndb.Key('FlakeIssue', 'bug2')},
                  'tags': {
                      'watchlist::new',
                      'directory::new',
                      'source::new',
                      'parent_component::new',
                      'component::new',
                      'step::new',
                      'test_type::new',
                  },
              },
              'expected_disabled_test_variants': {('config1', 'config2'),},
              'expected_issue_keys': [
                  ndb.Key('FlakeIssue', 'bug1'),
                  ndb.Key('FlakeIssue', 'bug2')
              ],
              'expected_tags': {
                  'watchlist::new',
                  'directory::new',
                  'source::new',
                  'parent_component::new',
                  'component::new',
                  'step::new',
                  'test_type::new',
              },
              'query_time':
                  datetime(2019, 6, 29, 0, 0, 0),
          },),
  ])
  def testUpdateDatastore(self, cases):
    if cases['remote_test']:
      cases['remote_test'].put()

    future = detect_disabled_tests._UpdateDatastore(
        cases['test_key'], cases['test_attributes'], cases['query_time'])
    future.get_result()

    updated_test = cases['test_key'].get()
    self.assertEqual(cases['query_time'], updated_test.last_updated_time)
    self.assertEqual(cases['expected_disabled_test_variants'],
                     updated_test.disabled_test_variants)
    self.assertEqual(
        sorted(cases['expected_issue_keys']), updated_test.issue_keys)
    self.assertEqual(sorted(cases['expected_tags']), updated_test.tags)

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
                      issue_keys=[ndb.Key('FlakeIssue', 'chromium@123')],
                      tags=sorted({
                          'component::%s' % test_tag_util.DEFAULT_COMPONENT,
                          'parent_component::%s' %
                          test_tag_util.DEFAULT_COMPONENT,
                          'step::step_name (full)',
                          'test_type::step_name',
                      }),
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
                      tags=sorted({
                          'component::%s' % test_tag_util.DEFAULT_COMPONENT,
                          'parent_component::%s' %
                          test_tag_util.DEFAULT_COMPONENT,
                          'step::step_name (full)',
                          'test_type::step_name',
                      }),
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0))
          },),
      (  # Currently disabled, change in variants, should be updated.
          {
              'remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest',
                                  'chromium@normal_step_name@test_name1'),
                      disabled_test_variants={('os:os2',)},
                      issue_keys=[ndb.Key('FlakeIssue', 'chromium@123')],
                      tags=sorted({
                          'component::%s' % test_tag_util.DEFAULT_COMPONENT,
                          'parent_component::%s' %
                          test_tag_util.DEFAULT_COMPONENT,
                          'step::step_name (full)',
                          'test_type::step_name',
                      }),
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
                      tags=sorted({
                          'component::%s' % test_tag_util.DEFAULT_COMPONENT,
                          'parent_component::%s' %
                          test_tag_util.DEFAULT_COMPONENT,
                          'step::step_name (full)',
                          'test_type::step_name',
                      }),
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
                      issue_keys=[],
                      tags=sorted({
                          'component::%s' % test_tag_util.DEFAULT_COMPONENT,
                          'parent_component::%s' %
                          test_tag_util.DEFAULT_COMPONENT,
                          'step::step_name (full)',
                          'test_type::step_name',
                      }),
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
                      tags=sorted({
                          'component::%s' % test_tag_util.DEFAULT_COMPONENT,
                          'parent_component::%s' %
                          test_tag_util.DEFAULT_COMPONENT,
                          'step::step_name (full)',
                          'test_type::step_name',
                      }),
                      last_updated_time=datetime(2019, 6, 29, 0, 0, 0))
          },),
      (  # Currently disabled, change in tags, should be updated.
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
                      issue_keys=[ndb.Key('FlakeIssue', 'chromium@123')],
                      tags=sorted({
                          'watchlist::tag',
                          'directory::tag',
                          'source::tag',
                          'parent_component::tag',
                          'component::tag',
                          'step::tag',
                          'test_type::tag',
                      }),
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
                      tags=sorted({
                          'component::%s' % test_tag_util.DEFAULT_COMPONENT,
                          'parent_component::%s' %
                          test_tag_util.DEFAULT_COMPONENT,
                          'step::step_name (full)',
                          'test_type::step_name',
                      }),
                      issue_keys=[ndb.Key('FlakeIssue', 'chromium@123')],
                      last_updated_time=datetime(2019, 6, 29, 0, 0, 0))
          },),
      (  # Currently disabled, change in all, should be updated.
          {
              'remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest',
                                  'chromium@normal_step_name@test_name1'),
                      disabled_test_variants={('os:os2',)},
                      tags=sorted({
                          'watchlist::tag',
                          'directory::tag',
                          'source::tag',
                          'parent_component::tag',
                          'component::tag',
                          'step::tag',
                          'test_type::tag',
                      }),
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
                      tags=sorted({
                          'component::%s' % test_tag_util.DEFAULT_COMPONENT,
                          'parent_component::%s' %
                          test_tag_util.DEFAULT_COMPONENT,
                          'step::step_name (full)',
                          'test_type::step_name',
                      }),
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
                      tags=sorted({
                          'watchlist::tag',
                          'directory::tag',
                          'source::tag',
                          'parent_component::tag',
                          'component::tag',
                          'step::tag',
                          'test_type::tag',
                      }),
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
                      issue_keys=[ndb.Key('FlakeIssue', 'chromium@123')],
                      tags=set(),
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0)),
              'expected_remote_test':
                  LuciTest(
                      key=ndb.Key('LuciTest',
                                  'chromium@normal_step_name@test_name2'),
                      disabled_test_variants=set(),
                      issue_keys=[ndb.Key('FlakeIssue', 'chromium@123')],
                      tags=set(),
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0))
          },),
  ])
  @mock.patch.object(
      test_tag_util, '_GetChromiumDirectoryToComponentMapping', return_value={})
  @mock.patch.object(test_tag_util, '_GetChromiumWATCHLISTS', return_value={})
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
        step_name='step_name (full)',
        test_name='test_name1',
        builder_name='msan_asan_builder1',
        build_id=123,
        bugs=['crbug.com/123'])

    mocked_client = mock.Mock()
    mocked_get_client.return_value = mocked_client
    mocked_client.jobs().query().execute.return_value = query_response
    mocked_client.jobs().getQueryResults().execute.return_value = query_response

    detect_disabled_tests.ProcessQueryForDisabledTests()
    actual_remote_test = cases['remote_test'].key.get()
    self.assertEqual(cases['expected_remote_test'], actual_remote_test)

  @parameterized.expand([
      (  # Currently disabled, changes, should be updated.
          {
              'remote_test':
                  LuciTest(
                      key=ndb.Key(
                          'LuciTest',
                          'chromium@telemetry_gpu_integration_test@test_name1'),
                      disabled_test_variants={(
                          'ASan:True',
                          'MSan:True',
                          'os:os1',
                      )},
                      issue_keys=[ndb.Key('FlakeIssue', 'chromium@123')],
                      tags=sorted({
                          'step::existing',
                          'test_type::existing',
                          'component::existing',
                      }),
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0)),
              'expected_remote_test':
                  LuciTest(
                      key=ndb.Key(
                          'LuciTest',
                          'chromium@telemetry_gpu_integration_test@test_name1'),
                      disabled_test_variants={(
                          'ASan:True',
                          'MSan:True',
                          'os:os1',
                      )},
                      issue_keys=[ndb.Key('FlakeIssue', 'chromium@123')],
                      tags=sorted({
                          'step::step_name (full)',
                          'test_type::step_name',
                          'component::Internals>GPU>Testing',
                      }),
                      last_updated_time=datetime(2019, 6, 29, 0, 0, 0))
          },),
      (  # No longer disabled, should be updated.
          {
              'remote_test':
                  LuciTest(
                      key=ndb.Key(
                          'LuciTest',
                          'chromium@telemetry_gpu_integration_test@test_name2'),
                      disabled_test_variants={(
                          'ASan:True',
                          'MSan:True',
                          'os:os1',
                      )},
                      issue_keys=[ndb.Key('FlakeIssue', 'chromium@123')],
                      tags=sorted({
                          'step::existing',
                          'test_type::existing',
                          'component::existing',
                      }),
                      last_updated_time=datetime(2019, 6, 28, 0, 0, 0)),
              'expected_remote_test':
                  LuciTest(
                      key=ndb.Key(
                          'LuciTest',
                          'chromium@telemetry_gpu_integration_test@test_name2'),
                      disabled_test_variants=set(),
                      issue_keys=[ndb.Key('FlakeIssue', 'chromium@123')],
                      tags=[],
                      last_updated_time=datetime(2019, 6, 29, 0, 0, 0))
          },),
  ])
  @mock.patch.object(
      test_tag_util, '_GetChromiumDirectoryToComponentMapping', return_value={})
  @mock.patch.object(test_tag_util, '_GetChromiumWATCHLISTS', return_value={})
  @mock.patch.object(swarmbucket, 'GetMasters', return_value=['chromium.linux'])
  @mock.patch.object(step_util, 'GetOS', return_value='os1')
  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2019, 6, 29, 0, 0, 0))
  @mock.patch.object(
      step_util, 'GetCanonicalStepName', return_value='depth_capture_tests')
  @mock.patch.object(
      Flake, 'NormalizeStepName', return_value='telemetry_gpu_integration_test')
  @mock.patch.object(bigquery_helper, '_GetBigqueryClient')
  def testProcessQueryForDisabledTestsGPUTest(self, cases, mocked_get_client,
                                              *_):
    cases['remote_test'].put()
    query_response = self._GetEmptyDisabledTestQueryResponse()
    self._AddRowToDisabledTestQueryResponse(
        query_response=query_response,
        step_name='step_name (full)',
        test_name='test_name1',
        builder_name='msan_asan_builder1',
        build_id=123,
        bugs=['crbug.com/123'])

    mocked_client = mock.Mock()
    mocked_get_client.return_value = mocked_client
    mocked_client.jobs().query().execute.return_value = query_response
    mocked_client.jobs().getQueryResults().execute.return_value = query_response

    detect_disabled_tests.ProcessQueryForDisabledTests()
    actual_remote_test = cases['remote_test'].key.get()
    self.assertEqual(cases['expected_remote_test'], actual_remote_test)

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
  @mock.patch.object(
      test_tag_util, '_GetChromiumDirectoryToComponentMapping', return_value={})
  @mock.patch.object(test_tag_util, '_GetChromiumWATCHLISTS', return_value={})
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
  @mock.patch.object(
      test_tag_util, '_GetChromiumDirectoryToComponentMapping', return_value={})
  @mock.patch.object(test_tag_util, '_GetChromiumWATCHLISTS', return_value={})
  @mock.patch.object(detect_disabled_tests, '_CreateLocalTests')
  @mock.patch.object(bigquery_helper, '_ReadQueryResultsPage')
  def testExecuteQueryNoRows(self, mock_execute_query, mock_create_local, *_):
    mock_execute_query.side_effect = [
        (True, [], None),
    ]
    with self.assertRaises(AssertionError):
      detect_disabled_tests._ExecuteQuery()

    self.assertFalse(mock_create_local.called)
