# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import httplib
import json
import mock
import urllib2

from google.appengine.datastore import datastore_stub_util
from google.appengine.ext import ndb

from apiclient.errors import HttpError
import gae_ts_mon
from common import data_interface
import main
from model.flake import Flake, FlakyRun, FlakeOccurrence
from model.build_run import PatchsetBuilderRuns, BuildRun
from testing_utils import testing
from time_functions.testing import mock_datetime_utc


class DataInterfaceTestCase(testing.AppengineTestCase):
  app_module = main.app

  # This is needed to be able to test handlers using cross-group transactions.
  datastore_stub_consistency_policy = (
      datastore_stub_util.PseudoRandomHRConsistencyPolicy(probability=1))

  # Needed to read queues from queue.yaml in the root of the app.
  taskqueue_stub_root_path = '.'

  def setUp(self):
    super(DataInterfaceTestCase, self).setUp()
    gae_ts_mon.reset_for_unittest(disable=True)
    mock.patch('common.data_interface._build_bigquery_service',
               lambda: None).start()

  def tearDown(self):
    super(DataInterfaceTestCase, self).tearDown()
    mock.patch.stopall()

  def _desanitize_row(self, row):
    desanitized_row = {'f': []}
    for column in row:
      if isinstance(column, list):
        column = [
            {'v': self._desanitize_row(sub_column)}
            for sub_column in column
        ]
      desanitized_row['f'].append({'v': column})
    return desanitized_row

  def test_updates_cache(self):
    fake_flakes_data = {
        ('project', 'step_name', 'test_name', 'config'): [
            ['some', 'flaky', 'failure', 'details'],
            ['info', 'for', 'another', 'flake'],
            ['yet', 'another', 'flaky', 'failure'],
        ]
    }

    fake_bq_response = [
        self._desanitize_row(list(key) + [value])
        for key, value in fake_flakes_data.items()
    ]

    with mock.patch('common.data_interface._execute_query',
                    lambda *args, **kwargs: fake_bq_response):
      data_interface.update_cache()
      recovered_data = data_interface.get_flakes_data()

    self.assertEqual(recovered_data, fake_flakes_data)

  def test_ignores_flake_types_with_too_little_flakes(self):
    good_flake_type = ('project', 'step_name', 'test_name', 'config')
    bad_flake_type = ('project2', 'step_name', 'test_name', 'config')

    fake_flakes_data = {
        good_flake_type: [
            ['some', 'flaky', 'failure', 'details'],
            ['info', 'for', 'another', 'flake'],
            ['yet', 'another', 'flaky', 'failure'],
        ],
        bad_flake_type: [
            ['some', 'flaky', 'failure', 'details'],
            ['info', 'for', 'another', 'flake'],
        ]
    }

    fake_bq_response = [
        self._desanitize_row(list(key) + [value])
        for key, value in fake_flakes_data.items()
    ]

    with mock.patch('common.data_interface._execute_query',
                    lambda *args, **kwargs: fake_bq_response):
      data_interface.update_cache()
      recovered_data = data_interface.get_flakes_data()

    self.assertNotIn(bad_flake_type, recovered_data)

    self.assertIn(good_flake_type, recovered_data)
    self.assertEqual(fake_flakes_data[good_flake_type],
                     recovered_data[good_flake_type])
