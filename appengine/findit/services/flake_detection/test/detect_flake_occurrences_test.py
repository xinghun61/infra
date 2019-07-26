# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import json
import mock
import textwrap

from buildbucket_proto.build_pb2 import Build
from buildbucket_proto.build_pb2 import BuilderID
from buildbucket_proto.step_pb2 import Step
from google.appengine.api import taskqueue

from common.waterfall import buildbucket_client
from dto.test_location import TestLocation as DTOTestLocation
from libs import time_util
from model.flake.detection.flake_occurrence import BuildConfiguration
from model.flake.detection.flake_occurrence import FlakeOccurrence
from model.flake.flake import Flake
from model.flake.flake import TAG_DELIMITER
from model.flake.flake import TestLocation as NDBTestLocation
from model.flake.flake_type import FlakeType
from model.flake.flake_type import FLAKE_TYPE_DESCRIPTIONS
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

  def _GetEmptyBuildQueryResponse(self):
    """Returns an empty query response for testing.

    The returned response is empty, please call _AddRowToBuildQueryResponse
    to add rows for testing. Note that the fields in the schema and the
    parameters of the _AddRowToFlakeQueryResponse method must match exactly
    (including orders), so if a new field is added to the schema, please
    update _AddRowToFlakeQueryResponse accordingly.
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
                           'type': 'INTEGER',
                           'name': 'gerrit_cl_id',
                           'mode': 'NULLABLE'
                       }]
        }
    }

  def _AddRowToBuildQueryResponse(self,
                                  query_response,
                                  luci_project='chromium',
                                  luci_bucket='try',
                                  luci_builder='linux_chromium_rel_ng',
                                  legacy_master_name='tryserver.chromium.linux',
                                  legacy_build_number='999',
                                  build_id='123',
                                  gerrit_cl_id='98765',
                                  gerrit_project='chromium/src'):
    """Adds a row to the provided query response for testing.

    To obtain a query response for testing for the initial time, please call
    _GetEmptyBuildQueryResponse. Note that the fields in the schema and the
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
                'v': gerrit_cl_id
            },
        ]
    }
    query_response['rows'].append(row)
    query_response['totalRows'] = str(int(query_response['totalRows']) + 1)

  def _GetEmptyFlakeQueryResponse(self):
    """Returns an empty query response for testing.

    The returned response is empty, please call _AddRowToFlakeQueryResponse
    to add rows for testing. Note that the fields in the schema and the
    parameters of the _AddRowToFlakeQueryResponse method must match exactly
    (including orders), so if a new field is added to the schema, please
    update _AddRowToFlakeQueryResponse accordingly.
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

  def _AddRowToFlakeQueryResponse(self,
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
    _GetEmptyFlakeQueryResponse. Note that the fields in the schema and the
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
        build_id=123,
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
      time_util, 'GetDateDaysBeforeNow', return_value=datetime(2019, 1, 1))
  def testUpdateTestLocationAndTagsRecentlyUpdated(self, _):
    flake = Flake(
        normalized_test_name='suite.test',
        tags=['gerrit_project::chromium/src'],
    )
    flake.last_test_location_based_tag_update_time = datetime(2019, 6, 1)
    self.assertFalse(
        detect_flake_occurrences._UpdateTestLocationAndTags(flake, [], {}, {}))

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
      step_util, 'GetCanonicalStepName', return_value='context_lost_tests')
  @mock.patch.object(
      detect_flake_occurrences, '_GetTestLocation', return_value=None)
  def testUpdateTestLocationAndTagsNoLocationWithComponent(self, *_):
    flake = Flake(
        normalized_test_name='suite.test',
        normalized_step_name='telemetry_gpu_integration_test',
        tags=['gerrit_project::chromium/src'],
    )
    occurrences = [
        FlakeOccurrence(
            step_ui_name='context_lost_tests',
            build_configuration=BuildConfiguration(
                legacy_master_name='master',
                luci_builder='builder',
                legacy_build_number=123,
            )),
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
        'component::Internals>GPU>Testing',
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
    flake.archived = True
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
    self.assertFalse(flake.archived)

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

    detect_flake_occurrences.QueryAndStoreHiddenFlakes()
    self.assertIsNone(detect_flake_occurrences._GetLastCQHiddenFlakeQueryTime())
    detect_flake_occurrences.QueryAndStoreHiddenFlakes()
    self.assertEqual(
        datetime(2018, 12, 20),
        detect_flake_occurrences._GetLastCQHiddenFlakeQueryTime())
    detect_flake_occurrences.QueryAndStoreHiddenFlakes()

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
    query_response = self._GetEmptyFlakeQueryResponse()
    test_name1 = 'suite.test'
    test_name2 = 'suite.test_1'

    self._AddRowToFlakeQueryResponse(
        query_response=query_response,
        step_ui_name='step_ui_name',
        test_name=test_name1,
        gerrit_cl_id='10000')

    self._AddRowToFlakeQueryResponse(
        query_response=query_response,
        step_ui_name='step_ui_name',
        test_name=test_name1,
        gerrit_cl_id='10001',
        build_id='124',
        test_start_msec='1')

    self._AddRowToFlakeQueryResponse(
        query_response=query_response,
        luci_builder='another_builder',
        step_ui_name='step_ui_name',
        test_name=test_name1,
        gerrit_cl_id='10001',
        build_id='125')

    self._AddRowToFlakeQueryResponse(
        query_response=query_response,
        step_ui_name='step_ui_name',
        test_name=test_name2,
        gerrit_cl_id='10000')
    mocked_client = mock.Mock()
    mocked_get_client.return_value = mocked_client
    mocked_client.jobs().query().execute.return_value = query_response

    detect_flake_occurrences.QueryAndStoreHiddenFlakes()

    all_flake_occurrences = FlakeOccurrence.query().fetch()
    self.assertEqual(4, len(all_flake_occurrences))

  def testStoreDetectedCIFlakesNoBuild(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    flaky_tests = {'s': ['t1', 't2']}

    detect_flake_occurrences.StoreDetectedCIFlakes(master_name, builder_name,
                                                   build_number, flaky_tests)

    flake = Flake.Get('chromium', 'normalized_step_name', 't1')
    self.assertIsNone(flake)

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

  @mock.patch.object(detect_flake_occurrences, '_UpdateFlakeMetadata')
  @mock.patch.object(Flake, 'NormalizeStepName', return_value='step1')
  @mock.patch.object(Flake, 'NormalizeTestName')
  @mock.patch.object(Flake, 'GetTestLabelName')
  @mock.patch.object(buildbucket_client, 'GetV2Build')
  @mock.patch.object(step_util, 'GetStepLogFromBuildObject')
  def testProcessBuildForFlakes(self, mock_metadata, mock_build,
                                mock_normalized_test_name, mock_lable_name, *_):
    flake_type_enum = FlakeType.CQ_FALSE_REJECTION
    build_id = 123
    luci_project = 'luci_project'
    luci_bucket = 'luci_bucket'
    luci_builder = 'luci_builder'
    legacy_master_name = 'legacy_master_name'
    start_time = datetime(2019, 3, 6)
    end_time = datetime(2019, 3, 6, 0, 0, 10)

    findit_step = Step()
    findit_step.name = 'FindIt Flakiness'
    step1 = Step()
    step1.name = 'step1 (with patch)'
    step1.start_time.FromDatetime(start_time)
    step1.end_time.FromDatetime(end_time)
    builder = BuilderID(
        project=luci_project,
        bucket=luci_bucket,
        builder=luci_builder,
    )
    build = Build(id=build_id, builder=builder, number=build_id)
    build.steps.extend([findit_step, step1])
    build.input.properties['mastername'] = legacy_master_name
    build.input.properties['patch_project'] = 'chromium/src'
    mock_change = build.input.gerrit_changes.add()
    mock_change.host = 'mock.gerrit.host'
    mock_change.change = 12345
    mock_change.patchset = 1
    mock_build.return_value = build

    def _MockTestName(test_name, _step_ui_name):  # pylint: disable=unused-argument
      return test_name

    mock_normalized_test_name.side_effect = _MockTestName
    mock_lable_name.side_effect = _MockTestName

    flakiness_metadata = {
        'Failing With Patch Tests That Caused Build Failure': {
            'step1 (with patch)': ['s1_t1', 's1_t2']
        },
        'Step Layer Flakiness': {}
    }
    mock_metadata.return_value = flakiness_metadata

    # Flake object for s2_t1 exists.
    flake1 = Flake.Create(
        luci_project=luci_project,
        normalized_step_name='step1',
        normalized_test_name='s1_t1',
        test_label_name='s1_t1')
    flake1.put()

    detect_flake_occurrences.ProcessBuildForFlakes(
        detect_flake_occurrences.DetectFlakesFromFlakyCQBuildParam(
            build_id=build_id,
            flake_type_desc=FLAKE_TYPE_DESCRIPTIONS[flake_type_enum]))

    flake1_occurrence_num = FlakeOccurrence.query(ancestor=flake1.key).count()
    self.assertEqual(1, flake1_occurrence_num)

    flake2 = Flake.Get(luci_project, 'step1', 's1_t2')
    self.assertIsNotNone(flake2)

  @mock.patch.object(taskqueue, 'add')
  @mock.patch.object(bigquery_helper, '_GetBigqueryClient')
  def testDetectFlakeBuilds(self, mocked_get_client, mock_add_task):
    flake_type = FlakeType.CQ_FALSE_REJECTION

    query_response = self._GetEmptyBuildQueryResponse()
    self._AddRowToBuildQueryResponse(
        query_response=query_response, build_id='123', gerrit_cl_id='10000')
    mocked_client = mock.Mock()
    mocked_get_client.return_value = mocked_client
    mocked_client.jobs().query().execute.return_value = query_response

    taskqueue_task_names = []

    def _MockAddTask(name, **kwargs):  # pylint: disable=unused-argument
      taskqueue_task_names.append(name)

    mock_add_task.side_effect = _MockAddTask

    # First time query for build 123.
    QueryAndStoreFlakes(flake_type)
    self.assertEqual(['detect-flake-123-cq_false_rejection'],
                     taskqueue_task_names)

    self._AddRowToBuildQueryResponse(
        query_response=query_response, gerrit_cl_id='10001', build_id='124')

    self._AddRowToBuildQueryResponse(
        query_response=query_response,
        luci_builder='another_builder',
        gerrit_cl_id='10001',
        build_id='125')

    mocked_client.jobs().query().execute.return_value = query_response
    taskqueue_task_names = []
    # Queries for build 123 - 125.
    QueryAndStoreFlakes(flake_type)

    self.assertItemsEqual([
        'detect-flake-124-cq_false_rejection',
        'detect-flake-125-cq_false_rejection'
    ], taskqueue_task_names)
