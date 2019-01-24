# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import json
import mock
import textwrap

from dto.test_location import TestLocation as DTOTestLocation
from libs import time_util
from model.flake.detection.flake_occurrence import BuildConfiguration
from model.flake.detection.flake_occurrence import FlakeOccurrence
from model.flake.flake import Flake
from model.flake.flake import TAG_DELIMITER
from model.flake.flake import TestLocation as NDBTestLocation
from model.flake.flake_type import FlakeType
from model.wf_build import WfBuild
from services import bigquery_helper
from services import step_util
from services.flake_detection import detect_flake_occurrences
from services.flake_detection.detect_flake_occurrences import (
    QueryAndStoreFlakes)
from services.flake_detection.detect_flake_occurrences import (
    _UpdateFlakeMetadata)
from waterfall import build_util
from waterfall.test.wf_testcase import WaterfallTestCase


class DetectFlakesOccurrencesTest(WaterfallTestCase):

  def _GetEmptyQueryResponse(self):
    """Returns an empty query response for testing.

    The returned response is empty, please call _AddRowToQueryResponse method
    to add rows for testing. Note that the fields in the schema and the
    parameters of the _AddRowToQueryResponse method must match exactly
    (including orders), so if a new field is added to the schema, please
    update _AddRowToQueryResponse accordingly.
    """
    return {
        'rows': [],
        'jobComplete': True,
        'totalRows': '0',
        'schema': {
            'fields': [{
                'type': 'STRING',
                'name': 'gerrit_project',
                'mode': 'NULLABLE'
            }, {
                'type': 'STRING',
                'name': 'luci_project',
                'mode': 'NULLABLE'
            }, {
                'type': 'STRING',
                'name': 'luci_bucket',
                'mode': 'NULLABLE'
            }, {
                'type': 'STRING',
                'name': 'luci_builder',
                'mode': 'NULLABLE'
            },
                       {
                           'type': 'STRING',
                           'name': 'legacy_master_name',
                           'mode': 'NULLABLE'
                       },
                       {
                           'type': 'INTEGER',
                           'name': 'legacy_build_number',
                           'mode': 'NULLABLE'
                       },
                       {
                           'type': 'INTEGER',
                           'name': 'build_id',
                           'mode': 'NULLABLE'
                       },
                       {
                           'type': 'STRING',
                           'name': 'step_ui_name',
                           'mode': 'NULLABLE'
                       },
                       {
                           'type': 'STRING',
                           'name': 'test_name',
                           'mode': 'NULLABLE'
                       },
                       {
                           'type': 'TIMESTAMP',
                           'name': 'test_start_msec',
                           'mode': 'NULLABLE'
                       },
                       {
                           'type': 'INTEGER',
                           'name': 'gerrit_cl_id',
                           'mode': 'NULLABLE'
                       }]
        }
    }

  def _AddRowToQueryResponse(self,
                             query_response,
                             luci_project='chromium',
                             luci_bucket='try',
                             luci_builder='linux_chromium_rel_ng',
                             legacy_master_name='tryserver.chromium.linux',
                             legacy_build_number='999',
                             build_id='123',
                             step_ui_name='fake_step',
                             test_name='fake_test',
                             test_start_msec='0',
                             gerrit_cl_id='98765',
                             gerrit_project='chromium/src'):
    """Adds a row to the provided query response for testing.

    To obtain a query response for testing for the initial time, please call
    _GetEmptyQueryResponse. Note that the fields in the schema and the
    parameters of this method must match exactly (including orders), so if a new
    field is added to the schema, please update this method accordingly.
    """
    row = {
        'f': [
            {
                'v': gerrit_project
            },
            {
                'v': luci_project
            },
            {
                'v': luci_bucket
            },
            {
                'v': luci_builder
            },
            {
                'v': legacy_master_name
            },
            {
                'v': legacy_build_number
            },
            {
                'v': build_id
            },
            {
                'v': step_ui_name
            },
            {
                'v': test_name
            },
            {
                'v': test_start_msec
            },
            {
                'v': gerrit_cl_id
            },
        ]
    }
    query_response['rows'].append(row)
    query_response['totalRows'] = str(int(query_response['totalRows']) + 1)

  def setUp(self):
    super(DetectFlakesOccurrencesTest, self).setUp()

    # NormalizeStepName performs network requests, needs to be mocked.
    patcher = mock.patch.object(
        Flake, 'NormalizeStepName', return_value='normalized_step_name')
    self.addCleanup(patcher.stop)
    patcher.start()

  def testNormalizePath(self):
    self.assertEqual('a/b/c', detect_flake_occurrences._NormalizePath('a/b/c'))
    self.assertEqual('a/b/c',
                     detect_flake_occurrences._NormalizePath('../../a/b/c'))
    self.assertEqual('a/b/c',
                     detect_flake_occurrences._NormalizePath('../../a/b/./c'))
    self.assertEqual('b/c',
                     detect_flake_occurrences._NormalizePath('../a/../b/c'))

  @mock.patch.object(
      detect_flake_occurrences.step_util,
      'GetStepMetadata',
      return_value={'swarm_task_ids': ['t1', 't2']})
  @mock.patch.object(
      detect_flake_occurrences.swarmed_test_util,
      'GetTestLocation',
      side_effect=[None, DTOTestLocation(file='../../path/a.cc', line=2)])
  def testGetTestLocation(self, *_):
    occurrence = FlakeOccurrence(
        build_configuration=BuildConfiguration(
            legacy_master_name='master',
            luci_builder='builder',
            legacy_build_number=123,
        ),
        step_ui_name='test on Mac',
    )
    self.assertEqual(
        'path/a.cc',
        detect_flake_occurrences._GetTestLocation(occurrence).file_path)

  @mock.patch.object(
      detect_flake_occurrences.FinditHttpClient,
      'Get',
      return_value=(200,
                    json.dumps({
                        'dir-to-component': {
                            'p/dir1': 'a>b',
                            'p/dir2': 'd>e>f',
                        }
                    }), None))
  def testGetChromiumDirectoryToComponentMapping(self, *_):
    self.assertEqual({
        'p/dir1/': 'a>b',
        'p/dir2/': 'd>e>f'
    }, detect_flake_occurrences._GetChromiumDirectoryToComponentMapping())

  @mock.patch.object(
      detect_flake_occurrences.CachedGitilesRepository,
      'GetSource',
      return_value=textwrap.dedent(r"""
                         {
                           'WATCHLIST_DEFINITIONS': {
                             'watchlist1': {
                               'filepath': 'path/to/source\.cc'
                             },
                             'watchlist2': {
                               'filepath': 'a/to/file1\.cc'\
                                           '|b/to/file2\.cc'
                             }
                           }
                         }"""))
  def testGetChromiumWATCHLISTS(self, *_):
    self.assertEqual({
        'watchlist1': r'path/to/source\.cc',
        'watchlist2': r'a/to/file1\.cc|b/to/file2\.cc',
    }, detect_flake_occurrences._GetChromiumWATCHLISTS())

  @mock.patch.object(
      detect_flake_occurrences, '_GetTestLocation', return_value=None)
  @mock.patch.object(
      detect_flake_occurrences,
      '_GetChromiumDirectoryToComponentMapping',
      return_value={})
  @mock.patch.object(
      detect_flake_occurrences, '_GetChromiumWATCHLISTS', return_value={})
  @mock.patch.object(bigquery_helper, '_GetBigqueryClient')
  def testOneFlakeOccurrence(self, mocked_get_client, *_):
    query_response = self._GetEmptyQueryResponse()
    self._AddRowToQueryResponse(query_response=query_response)

    mocked_client = mock.Mock()
    mocked_get_client.return_value = mocked_client
    mocked_client.jobs().query().execute.return_value = query_response

    QueryAndStoreFlakes(FlakeType.CQ_FALSE_REJECTION)

    all_flakes = Flake.query().fetch()
    self.assertEqual(1, len(all_flakes))
    self.assertIsNotNone(all_flakes[0].last_occurred_time)

    all_false_rejection_occurrences = FlakeOccurrence.query(
        FlakeOccurrence.flake_type == FlakeType.CQ_FALSE_REJECTION).fetch()
    self.assertEqual(1, len(all_false_rejection_occurrences))
    self.assertEqual(all_flakes[0],
                     all_false_rejection_occurrences[0].key.parent().get())

    QueryAndStoreFlakes(FlakeType.RETRY_WITH_PATCH)
    all_retry_with_patch_occurrences = FlakeOccurrence.query(
        FlakeOccurrence.flake_type == FlakeType.RETRY_WITH_PATCH).fetch()
    self.assertEqual(1, len(all_retry_with_patch_occurrences))
    self.assertEqual(all_flakes[0],
                     all_retry_with_patch_occurrences[0].key.parent().get())

    all_flake_occurrences = FlakeOccurrence.query(
        ancestor=all_flakes[0].key).fetch()
    self.assertEqual(2, len(all_flake_occurrences))

  @mock.patch.object(
      detect_flake_occurrences, '_GetTestLocation', return_value=None)
  @mock.patch.object(
      detect_flake_occurrences,
      '_GetChromiumDirectoryToComponentMapping',
      return_value={})
  @mock.patch.object(
      detect_flake_occurrences, '_GetChromiumWATCHLISTS', return_value={})
  @mock.patch.object(bigquery_helper, '_GetBigqueryClient')
  def testIdenticalFlakeOccurrences(self, mocked_get_client, *_):
    query_response = self._GetEmptyQueryResponse()
    self._AddRowToQueryResponse(query_response=query_response)
    self._AddRowToQueryResponse(query_response=query_response)

    mocked_client = mock.Mock()
    mocked_get_client.return_value = mocked_client
    mocked_client.jobs().query().execute.return_value = query_response

    QueryAndStoreFlakes(FlakeType.CQ_FALSE_REJECTION)

    all_flakes = Flake.query().fetch()
    self.assertEqual(1, len(all_flakes))

    all_flake_occurrences = FlakeOccurrence.query(
        FlakeOccurrence.flake_type == FlakeType.CQ_FALSE_REJECTION).fetch()
    self.assertEqual(1, len(all_flake_occurrences))
    self.assertEqual(all_flakes[0], all_flake_occurrences[0].key.parent().get())

  @mock.patch.object(
      detect_flake_occurrences, '_GetTestLocation', return_value=None)
  @mock.patch.object(
      detect_flake_occurrences,
      '_GetChromiumDirectoryToComponentMapping',
      return_value={})
  @mock.patch.object(
      detect_flake_occurrences, '_GetChromiumWATCHLISTS', return_value={})
  @mock.patch.object(bigquery_helper, '_GetBigqueryClient')
  def testFlakeOccurrencesWithDifferentParent(self, mocked_get_client, *_):
    query_response = self._GetEmptyQueryResponse()
    self._AddRowToQueryResponse(
        query_response=query_response,
        build_id='123',
        step_ui_name='step_ui_name1',
        test_name='suite1.test1')
    self._AddRowToQueryResponse(
        query_response=query_response,
        build_id='678',
        step_ui_name='step_ui_name2',
        test_name='suite2.test2')

    mocked_client = mock.Mock()
    mocked_get_client.return_value = mocked_client
    mocked_client.jobs().query().execute.return_value = query_response

    QueryAndStoreFlakes(FlakeType.CQ_FALSE_REJECTION)

    all_flakes = Flake.query().fetch()
    self.assertEqual(2, len(all_flakes))

    all_flake_occurrences = FlakeOccurrence.query(
        FlakeOccurrence.flake_type == FlakeType.CQ_FALSE_REJECTION).fetch()
    self.assertEqual(2, len(all_flake_occurrences))
    parent1 = all_flake_occurrences[0].key.parent().get()
    parent2 = all_flake_occurrences[1].key.parent().get()
    self.assertTrue(parent1 in all_flakes)
    self.assertTrue(parent2 in all_flakes)
    self.assertNotEqual(parent1, parent2)

  @mock.patch.object(
      detect_flake_occurrences, '_GetTestLocation', return_value=None)
  @mock.patch.object(
      detect_flake_occurrences,
      '_GetChromiumDirectoryToComponentMapping',
      return_value={})
  @mock.patch.object(
      detect_flake_occurrences, '_GetChromiumWATCHLISTS', return_value={})
  @mock.patch.object(bigquery_helper, '_GetBigqueryClient')
  def testParameterizedGtestFlakeOccurrences(self, mocked_get_client, *_):
    query_response = self._GetEmptyQueryResponse()
    self._AddRowToQueryResponse(
        query_response=query_response,
        step_ui_name='step_ui_name',
        test_name='instance1/suite.test/0')
    self._AddRowToQueryResponse(
        query_response=query_response,
        step_ui_name='step_ui_name',
        test_name='instance2/suite.test/1')

    mocked_client = mock.Mock()
    mocked_get_client.return_value = mocked_client
    mocked_client.jobs().query().execute.return_value = query_response

    QueryAndStoreFlakes(FlakeType.CQ_FALSE_REJECTION)

    all_flakes = Flake.query().fetch()
    self.assertEqual(1, len(all_flakes))

    all_flake_occurrences = FlakeOccurrence.query(
        FlakeOccurrence.flake_type == FlakeType.CQ_FALSE_REJECTION).fetch()
    self.assertEqual(2, len(all_flake_occurrences))
    self.assertEqual(all_flakes[0], all_flake_occurrences[0].key.parent().get())
    self.assertEqual(all_flakes[0], all_flake_occurrences[1].key.parent().get())

  @mock.patch.object(
      detect_flake_occurrences, '_GetTestLocation', return_value=None)
  @mock.patch.object(
      detect_flake_occurrences,
      '_GetChromiumDirectoryToComponentMapping',
      return_value={})
  @mock.patch.object(
      detect_flake_occurrences, '_GetChromiumWATCHLISTS', return_value={})
  @mock.patch.object(bigquery_helper, '_GetBigqueryClient')
  def testGtestWithPrefixesFlakeOccurrences(self, mocked_get_client, *_):
    query_response = self._GetEmptyQueryResponse()
    self._AddRowToQueryResponse(
        query_response=query_response,
        step_ui_name='step_ui_name',
        test_name='suite.test')
    self._AddRowToQueryResponse(
        query_response=query_response,
        step_ui_name='step_ui_name',
        test_name='suite.PRE_PRE_test')

    mocked_client = mock.Mock()
    mocked_get_client.return_value = mocked_client
    mocked_client.jobs().query().execute.return_value = query_response

    QueryAndStoreFlakes(FlakeType.CQ_FALSE_REJECTION)

    all_flakes = Flake.query().fetch()
    self.assertEqual(1, len(all_flakes))

    all_flake_occurrences = FlakeOccurrence.query(
        FlakeOccurrence.flake_type == FlakeType.CQ_FALSE_REJECTION).fetch()
    self.assertEqual(2, len(all_flake_occurrences))
    self.assertEqual(all_flakes[0], all_flake_occurrences[0].key.parent().get())
    self.assertEqual(all_flakes[0], all_flake_occurrences[1].key.parent().get())

  @mock.patch.object(
      detect_flake_occurrences,
      '_GetTestLocation',
      return_value=NDBTestLocation(file_path='unknown/path.cc',))
  def testUpdateTestLocationAndTagsNoComponent(self, *_):
    flake = Flake(
        normalized_test_name='suite.test',
        tags=['gerrit_project::chromium/src'],
    )
    occurrences = [
        FlakeOccurrence(step_ui_name='browser_tests'),
    ]
    component_mapping = {
        'base/feature/': 'root>a>b',
        'base/feature/url': 'root>a>b>c',
    }
    watchlist = {
        'feature': 'base/feature',
        'url': r'base/feature/url_test\.cc',
        'other': 'a/b/c',
    }

    expected_tags = sorted([
        'gerrit_project::chromium/src',
        'directory::unknown/',
        'source::unknown/path.cc',
        'component::Unknown',
        'parent_component::Unknown',
    ])

    for tag in flake.tags:
      name = tag.split(TAG_DELIMITER)[0]
      self.assertTrue(name in detect_flake_occurrences.SUPPORTED_TAGS)

    self.assertTrue(
        detect_flake_occurrences._UpdateTestLocationAndTags(
            flake, occurrences, component_mapping, watchlist))
    self.assertEqual(expected_tags, flake.tags)

  @mock.patch.object(
      detect_flake_occurrences,
      '_GetTestLocation',
      return_value=NDBTestLocation(file_path='base/feature/url_test.cc',))
  def testUpdateTestLocationAndTags(self, *_):
    flake = Flake(
        normalized_test_name='suite.test',
        tags=[
            'gerrit_project::chromium/src', 'watchlist::old', 'directory::old',
            'component::old', 'parent_component::old', 'source::old'
        ],
    )
    occurrences = [
        FlakeOccurrence(step_ui_name='browser_tests'),
    ]
    component_mapping = {
        'base/feature/': 'root>a>b',
        'base/feature/url': 'root>a>b>c',
    }
    watchlist = {
        'feature': 'base/feature',
        'url': r'base/feature/url_test\.cc',
        'other': 'a/b/c',
    }

    expected_tags = sorted([
        'gerrit_project::chromium/src',
        'watchlist::feature',
        'watchlist::url',
        'directory::base/feature/',
        'directory::base/',
        'source::base/feature/url_test.cc',
        'component::root>a>b',
        'parent_component::root>a>b',
        'parent_component::root>a',
        'parent_component::root',
    ])

    for tag in flake.tags:
      name = tag.split(TAG_DELIMITER)[0]
      self.assertTrue(name in detect_flake_occurrences.SUPPORTED_TAGS)

    self.assertTrue(
        detect_flake_occurrences._UpdateTestLocationAndTags(
            flake, occurrences, component_mapping, watchlist))
    self.assertEqual(expected_tags, flake.tags)

  @mock.patch.object(
      detect_flake_occurrences, '_GetTestLocation', return_value=None)
  @mock.patch.object(
      detect_flake_occurrences,
      '_GetChromiumDirectoryToComponentMapping',
      return_value={})
  @mock.patch.object(
      detect_flake_occurrences, '_GetChromiumWATCHLISTS', return_value={})
  def testUpdateMetadataForFlakes(self, *_):
    luci_project = 'chromium'
    normalized_step_name = 'normalized_step_name'
    normalized_test_name = 'normalized_test_name'
    test_label_name = 'test_label'
    flake = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name,
        test_label_name=test_label_name)
    flake.put()
    flake_key = flake.key

    step_ui_name = 'step'
    test_name = 'test'
    luci_bucket = 'try'
    luci_builder = 'luci builder'
    legacy_master_name = 'buildbot master'
    legacy_build_number = 999
    gerrit_cl_id = 98765

    # Flake's last_occurred_time and tags are empty, updated.
    occurrence_1 = FlakeOccurrence.Create(
        flake_type=FlakeType.CQ_FALSE_REJECTION,
        build_id=123,
        step_ui_name=step_ui_name,
        test_name=test_name,
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder=luci_builder,
        legacy_master_name=legacy_master_name,
        legacy_build_number=legacy_build_number,
        time_happened=datetime(2018, 1, 1, 1),
        gerrit_cl_id=gerrit_cl_id,
        parent_flake_key=flake_key,
        tags=['tag1::v1'])
    occurrence_1.put()
    _UpdateFlakeMetadata([occurrence_1])
    flake = flake_key.get()
    self.assertEqual(flake.last_occurred_time, datetime(2018, 1, 1, 1))
    self.assertEqual(flake.tags, ['tag1::v1'])

    # Flake's last_occurred_time is earlier and tags are different, updated.
    occurrence_2 = FlakeOccurrence.Create(
        flake_type=FlakeType.CQ_FALSE_REJECTION,
        build_id=124,
        step_ui_name=step_ui_name,
        test_name=test_name,
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder=luci_builder,
        legacy_master_name=legacy_master_name,
        legacy_build_number=legacy_build_number,
        time_happened=datetime(2018, 1, 1, 2),
        gerrit_cl_id=gerrit_cl_id,
        parent_flake_key=flake_key,
        tags=['tag2::v2'])
    occurrence_2.put()
    _UpdateFlakeMetadata([occurrence_2])
    flake = flake_key.get()
    self.assertEqual(flake.last_occurred_time, datetime(2018, 1, 1, 2))
    self.assertEqual(flake.tags, ['tag1::v1', 'tag2::v2'])

    # Flake's last_occurred_time is later and tags are the same, not updated.
    occurrence_3 = FlakeOccurrence.Create(
        flake_type=FlakeType.CQ_FALSE_REJECTION,
        build_id=125,
        step_ui_name=step_ui_name,
        test_name=test_name,
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder=luci_builder,
        legacy_master_name=legacy_master_name,
        legacy_build_number=legacy_build_number,
        time_happened=datetime(2018, 1, 1),
        gerrit_cl_id=gerrit_cl_id,
        parent_flake_key=flake_key,
        tags=['tag2::v2'])
    occurrence_3.put()
    _UpdateFlakeMetadata([occurrence_3])
    flake = flake_key.get()
    self.assertEqual(flake.last_occurred_time, datetime(2018, 1, 1, 2))
    self.assertEqual(flake.tags, ['tag1::v1', 'tag2::v2'])

  @mock.patch.object(detect_flake_occurrences, '_UpdateFlakeMetadata')
  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2018, 12, 20))
  @mock.patch.object(bigquery_helper, 'ExecuteQuery')
  def testDetectCQHiddenFlakesShouldSkip(self, mock_query, *_):
    flake = Flake.Create(
        luci_project='luci_project',
        normalized_step_name='s',
        normalized_test_name='t',
        test_label_name='t')
    flake.put()
    existing_occurrence = FlakeOccurrence.Create(
        flake_type=FlakeType.CQ_HIDDEN_FLAKE,
        build_id=123,
        step_ui_name='s',
        test_name='t',
        luci_project='luci_project',
        luci_bucket='luci_bucket',
        luci_builder='luci_builder',
        legacy_master_name='legacy_master_name',
        legacy_build_number=123,
        time_happened=datetime(2018, 12, 19, 23),
        gerrit_cl_id=654321,
        parent_flake_key=flake.key,
        tags=[])
    existing_occurrence.time_detected = datetime(2018, 12, 19, 23, 30)
    existing_occurrence.put()

    mock_query.side_effect = [(False, []), (True, [])]

    QueryAndStoreFlakes(FlakeType.CQ_HIDDEN_FLAKE)
    self.assertIsNone(detect_flake_occurrences._GetLastCQHiddenFlakeQueryTime())
    QueryAndStoreFlakes(FlakeType.CQ_HIDDEN_FLAKE)
    self.assertEqual(
        datetime(2018, 12, 20),
        detect_flake_occurrences._GetLastCQHiddenFlakeQueryTime())
    QueryAndStoreFlakes(FlakeType.CQ_HIDDEN_FLAKE)

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2018, 12, 20))
  def testDetectCQHiddenFlakesShouldRun(self, _):
    flake = Flake.Create(
        luci_project='luci_project',
        normalized_step_name='s',
        normalized_test_name='t',
        test_label_name='t')
    flake.put()
    existing_occurrence = FlakeOccurrence.Create(
        flake_type=FlakeType.CQ_HIDDEN_FLAKE,
        build_id=123,
        step_ui_name='s',
        test_name='t',
        luci_project='luci_project',
        luci_bucket='luci_bucket',
        luci_builder='luci_builder',
        legacy_master_name='legacy_master_name',
        legacy_build_number=123,
        time_happened=datetime(2018, 12, 19, 20),
        gerrit_cl_id=654321,
        parent_flake_key=flake.key,
        tags=[])
    existing_occurrence.time_detected = datetime(2018, 12, 19, 20)
    existing_occurrence.put()

    self.assertEqual(('2018-12-19 19:40:00 UTC', '2018-12-19 22:00:00 UTC'),
                     detect_flake_occurrences._GetCQHiddenFlakeQueryStartTime())

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2018, 12, 20))
  @mock.patch.object(
      detect_flake_occurrences, '_GetTestLocation', return_value=None)
  @mock.patch.object(
      detect_flake_occurrences,
      '_GetChromiumDirectoryToComponentMapping',
      return_value={})
  @mock.patch.object(
      detect_flake_occurrences, '_GetChromiumWATCHLISTS', return_value={})
  @mock.patch.object(bigquery_helper, '_GetBigqueryClient')
  def testDetectCQHiddenFlakes(self, mocked_get_client, *_):
    query_response = self._GetEmptyQueryResponse()
    test_name1 = 'suite.test'
    test_name2 = 'suite.test_1'

    self._AddRowToQueryResponse(
        query_response=query_response,
        step_ui_name='step_ui_name',
        test_name=test_name1,
        gerrit_cl_id='10000')

    self._AddRowToQueryResponse(
        query_response=query_response,
        step_ui_name='step_ui_name',
        test_name=test_name1,
        gerrit_cl_id='10001',
        build_id='124',
        test_start_msec='1')

    self._AddRowToQueryResponse(
        query_response=query_response,
        luci_builder='another_builder',
        step_ui_name='step_ui_name',
        test_name=test_name1,
        gerrit_cl_id='10001',
        build_id='125')

    self._AddRowToQueryResponse(
        query_response=query_response,
        step_ui_name='step_ui_name',
        test_name=test_name2,
        gerrit_cl_id='10000')
    mocked_client = mock.Mock()
    mocked_get_client.return_value = mocked_client
    mocked_client.jobs().query().execute.return_value = query_response

    QueryAndStoreFlakes(FlakeType.CQ_HIDDEN_FLAKE)

    all_flake_occurrences = FlakeOccurrence.query().fetch()
    self.assertEqual(4, len(all_flake_occurrences))

  @mock.patch.object(
      detect_flake_occurrences, '_GetChromiumWATCHLISTS', return_value={})
  @mock.patch.object(
      detect_flake_occurrences,
      '_GetChromiumDirectoryToComponentMapping',
      return_value={})
  @mock.patch.object(
      build_util,
      'GetBuilderInfoForLUCIBuild',
      return_value=('chromium', 'try'))
  def testStoreDetectedCIFlakes(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    build = WfBuild.Create(master_name, builder_name, build_number)
    build.build_id = '87654321'
    build.put()

    flaky_tests = {'s': ['t1', 't2']}

    detect_flake_occurrences.StoreDetectedCIFlakes(master_name, builder_name,
                                                   build_number, flaky_tests)

    flake = Flake.Get('chromium', 'normalized_step_name', 't1')
    self.assertIsNotNone(flake)

    occurrences = FlakeOccurrence.query(ancestor=flake.key).fetch()
    self.assertEqual(1, len(occurrences))
    self.assertEqual(FlakeType.CI_FAILED_STEP, occurrences[0].flake_type)

  @mock.patch.object(
      step_util, 'GetCanonicalStepName', return_value='webgl_conformance_tests')
  def testGetTestSuiteForOccurrence(self, _):
    row = {
        'build_id': 123,
        'step_ui_name': 'webgl_conformance_tests on platform',
        'luci_builder': 'linux_chromium_rel_ng',
        'test_start_msec': datetime(1970, 1, 1, 0, 0),
        'gerrit_project': 'chromium/src',
        'luci_bucket': 'try',
        'gerrit_cl_id': 10000,
        'legacy_master_name': 'tryserver.chromium.linux',
        'test_name': 'suite.test',
        'luci_project': 'chromium',
        'legacy_build_number': 999
    }
    self.assertEqual(
        'webgl_conformance_tests',
        detect_flake_occurrences._GetTestSuiteForOccurrence(
            row, 'normalized_test_name', 'telemetry_gpu_integration_test'))
