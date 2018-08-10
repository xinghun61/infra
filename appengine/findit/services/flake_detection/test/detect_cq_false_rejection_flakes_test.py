# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import mock

from model.flake.detection.flake import Flake
from model.flake.detection.flake_occurrence import (
    CQFalseRejectionFlakeOccurrence)
from waterfall.test.wf_testcase import WaterfallTestCase
from services import bigquery_helper
from services.flake_detection.detect_cq_false_rejection_flakes import (
    QueryAndStoreFlakes)


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
                'type': 'INTEGER',
                'name': 'reference_succeeded_build_id',
                'mode': 'NULLABLE'
            }, {
                'type': 'STRING',
                'name': 'step_name',
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
                             reference_succeeded_build_id='456',
                             step_name='fake_step',
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
                'v': reference_succeeded_build_id
            },
            {
                'v': step_name
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
        step_name='step_name1',
        test_name='suite1.test1')
    self._AddRowToQueryResponse(
        query_response=query_response,
        build_id='678',
        step_name='step_name2',
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
        step_name='step_name',
        test_name='instance1/suite.test/0')
    self._AddRowToQueryResponse(
        query_response=query_response,
        step_name='step_name',
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
        step_name='step_name',
        test_name='suite.test')
    self._AddRowToQueryResponse(
        query_response=query_response,
        step_name='step_name',
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
