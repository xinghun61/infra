# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from model.flake.flake import Flake
from model.flake.detection.flake_occurrence import (
    CQFalseRejectionFlakeOccurrence)
from waterfall.test.wf_testcase import WaterfallTestCase
from services import bigquery_helper
from services.flake_detection.detect_cq_false_rejection_flakes import (
    QueryAndStoreFlakes)
from services.flake_detection.detect_cq_false_rejection_flakes import (
    _UpdateLastFlakeHappenedTimeForFlakes)


class DetectCQFalseRejectionFlakesTest(WaterfallTestCase):

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
            }, {
                'type': 'STRING',
                'name': 'legacy_master_name',
                'mode': 'NULLABLE'
            }, {
                'type': 'INTEGER',
                'name': 'legacy_build_number',
                'mode': 'NULLABLE'
            }, {
                'type': 'INTEGER',
                'name': 'build_id',
                'mode': 'NULLABLE'
            }, {
                'type': 'STRING',
                'name': 'step_ui_name',
                'mode': 'NULLABLE'
            }, {
                'type': 'STRING',
                'name': 'test_name',
                'mode': 'NULLABLE'
            }, {
                'type': 'TIMESTAMP',
                'name': 'test_start_msec',
                'mode': 'NULLABLE'
            }, {
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
                             gerrit_cl_id='98765'):
    """Adds a row to the provided query response for testing.

    To obtain a query response for testing for the initial time, please call
    _GetEmptyQueryResponse. Note that the fields in the schema and the
    parameters of this method must match exactly (including orders), so if a new
    field is added to the schema, please update this method accordingly.
    """
    row = {
        'f': [
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
    super(DetectCQFalseRejectionFlakesTest, self).setUp()

    # NormalizeStepName performs network requests, needs to be mocked.
    patcher = mock.patch.object(
        Flake, 'NormalizeStepName', return_value='normalized_step_name')
    self.addCleanup(patcher.stop)
    patcher.start()

  @mock.patch.object(bigquery_helper, '_GetBigqueryClient')
  def testOneFlakeOccurrence(self, mocked_get_client):
    query_response = self._GetEmptyQueryResponse()
    self._AddRowToQueryResponse(query_response=query_response)

    mocked_client = mock.Mock()
    mocked_get_client.return_value = mocked_client
    mocked_client.jobs().query().execute.return_value = query_response

    QueryAndStoreFlakes()

    all_flakes = Flake.query().fetch()
    self.assertEqual(1, len(all_flakes))
    self.assertIsNotNone(all_flakes[0].last_occurred_time)

    all_flake_occurrences = CQFalseRejectionFlakeOccurrence.query().fetch()
    self.assertEqual(1, len(all_flake_occurrences))
    self.assertEqual(all_flakes[0], all_flake_occurrences[0].key.parent().get())

  @mock.patch.object(bigquery_helper, '_GetBigqueryClient')
  def testIdenticalFlakeOccurrences(self, mocked_get_client):
    query_response = self._GetEmptyQueryResponse()
    self._AddRowToQueryResponse(query_response=query_response)
    self._AddRowToQueryResponse(query_response=query_response)

    mocked_client = mock.Mock()
    mocked_get_client.return_value = mocked_client
    mocked_client.jobs().query().execute.return_value = query_response

    QueryAndStoreFlakes()

    all_flakes = Flake.query().fetch()
    self.assertEqual(1, len(all_flakes))

    all_flake_occurrences = CQFalseRejectionFlakeOccurrence.query().fetch()
    self.assertEqual(1, len(all_flake_occurrences))
    self.assertEqual(all_flakes[0], all_flake_occurrences[0].key.parent().get())

  @mock.patch.object(bigquery_helper, '_GetBigqueryClient')
  def testFlakeOccurrencesWithDifferentParent(self, mocked_get_client):
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

    QueryAndStoreFlakes()

    all_flakes = Flake.query().fetch()
    self.assertEqual(2, len(all_flakes))

    all_flake_occurrences = CQFalseRejectionFlakeOccurrence.query().fetch()
    self.assertEqual(2, len(all_flake_occurrences))
    parent1 = all_flake_occurrences[0].key.parent().get()
    parent2 = all_flake_occurrences[1].key.parent().get()
    self.assertTrue(parent1 in all_flakes)
    self.assertTrue(parent2 in all_flakes)
    self.assertNotEqual(parent1, parent2)

  @mock.patch.object(bigquery_helper, '_GetBigqueryClient')
  def testParameterizedGtestFlakeOccurrences(self, mocked_get_client):
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

    QueryAndStoreFlakes()

    all_flakes = Flake.query().fetch()
    self.assertEqual(1, len(all_flakes))

    all_flake_occurrences = CQFalseRejectionFlakeOccurrence.query().fetch()
    self.assertEqual(2, len(all_flake_occurrences))
    self.assertEqual(all_flakes[0], all_flake_occurrences[0].key.parent().get())
    self.assertEqual(all_flakes[0], all_flake_occurrences[1].key.parent().get())

  @mock.patch.object(bigquery_helper, '_GetBigqueryClient')
  def testGtestWithPrefixesFlakeOccurrences(self, mocked_get_client):
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

    QueryAndStoreFlakes()

    all_flakes = Flake.query().fetch()
    self.assertEqual(1, len(all_flakes))

    all_flake_occurrences = CQFalseRejectionFlakeOccurrence.query().fetch()
    self.assertEqual(2, len(all_flake_occurrences))
    self.assertEqual(all_flakes[0], all_flake_occurrences[0].key.parent().get())
    self.assertEqual(all_flakes[0], all_flake_occurrences[1].key.parent().get())

  def testUpdateLastFlakeHappenedTimeForFlakes(self):
    luci_project = 'chromium'
    normalized_step_name = 'normalized_step_name'
    normalized_test_name = 'normalized_test_name'
    flake = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name)
    flake.put()
    flake_key = flake.key

    step_ui_name = 'step'
    test_name = 'test'
    luci_bucket = 'try'
    luci_builder = 'luci builder'
    legacy_master_name = 'buildbot master'
    legacy_build_number = 999
    gerrit_cl_id = 98765

    # Flake's last_occurred_time is empty, updated.
    occurrence_1 = CQFalseRejectionFlakeOccurrence.Create(
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
        parent_flake_key=flake_key)
    occurrence_1.put()
    _UpdateLastFlakeHappenedTimeForFlakes([occurrence_1])
    flake = flake_key.get()
    self.assertEqual(flake.last_occurred_time, datetime(2018, 1, 1, 1))

    # Flake's last_occurred_time is earlier, updated.
    occurrence_2 = CQFalseRejectionFlakeOccurrence.Create(
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
        parent_flake_key=flake_key)
    occurrence_2.put()
    _UpdateLastFlakeHappenedTimeForFlakes([occurrence_2])
    flake = flake_key.get()
    self.assertEqual(flake.last_occurred_time, datetime(2018, 1, 1, 2))

    # Flake's last_occurred_time is later, not updated.
    occurrence_3 = CQFalseRejectionFlakeOccurrence.Create(
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
        parent_flake_key=flake_key)
    occurrence_3.put()
    _UpdateLastFlakeHappenedTimeForFlakes([occurrence_3])
    flake = flake_key.get()
    self.assertEqual(flake.last_occurred_time, datetime(2018, 1, 1, 2))
