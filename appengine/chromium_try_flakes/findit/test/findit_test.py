# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import mock

from google.appengine.datastore import datastore_stub_util

import main  # Fiddles sys.path so must come first.

import gae_ts_mon
from findit import findit
from model.build_run import BuildRun, PatchsetBuilderRuns
from model.flake import Flake, FlakyRun, FlakeOccurrence
from testing_utils import testing


class FindItAPITestCase(testing.AppengineTestCase):
  app_module = main.app

  # This is needed to be able to test handlers using cross-group transactions.
  datastore_stub_consistency_policy = (
      datastore_stub_util.PseudoRandomHRConsistencyPolicy(probability=1))

  def setUp(self):
    super(FindItAPITestCase, self).setUp()
    gae_ts_mon.reset_for_unittest(disable=True)
    self.maxDiff = None
    self.client = mock.Mock()
    self.patchers = [
        mock.patch('endpoints.endpoints.build_client',
                   lambda *_, **__: self.client),
        mock.patch('endpoints.endpoints.retry_request', mock.Mock()),
    ]
    for patcher in self.patchers:
      patcher.start()

  def tearDown(self):
    super(FindItAPITestCase, self).tearDown()
    for patcher in self.patchers:
      patcher.stop()

  @staticmethod
  def _create_flake():
    tf = datetime.datetime.utcnow()
    ts = tf - datetime.timedelta(hours=1)
    p = PatchsetBuilderRuns(issue=1, patchset=1, master='tryserver.bar',
                            builder='baz').put()
    br_f0 = BuildRun(parent=p, buildnumber=10, result=2, time_started=ts,
                     time_finished=tf).put()
    br_f1 = BuildRun(parent=p, buildnumber=20, result=2, time_started=ts,
                     time_finished=tf).put()
    br_s0 = BuildRun(parent=p, buildnumber=30, result=0, time_started=ts,
                     time_finished=tf).put()
    occ1 = FlakyRun(
        failure_run=br_f0, success_run=br_s0, failure_run_time_started=ts,
        failure_run_time_finished=tf, flakes=[
          FlakeOccurrence(name='step1', failure='step1'),
        ])
    occ2 = FlakyRun(
        failure_run=br_f1, success_run=br_s0, failure_run_time_started=ts,
        failure_run_time_finished=tf, flakes=[
          FlakeOccurrence(name='step2', failure='testX'),
          FlakeOccurrence(name='step3', failure='testY'),
        ])
    f = Flake(
        name='foo', count_day=10, occurrences=[occ1.put(), occ2.put()],
        is_step=True, issue_id=123456)
    return f, [occ1, occ2]

  def test_creates_flake_request_correctly(self):
    flake, occurrences = self._create_flake()
    api = findit.FindItAPI()
    api.flake(flake, occurrences)
    self.assertEquals(self.client.flake.call_count, 1)
    self.assertDictEqual(self.client.flake.call_args[1]['body'], {
      'name': 'foo',
      'is_step': True,
      'bug_id': 123456,
      'build_steps': [
        {
          'master_name': 'tryserver.bar',
          'builder_name': 'baz',
          'build_number': 10,
          'step_name': 'step1'
        },
        {
          'master_name': 'tryserver.bar',
          'builder_name': 'baz',
          'build_number': 20,
          'step_name': 'step2'
        },
        {
          'master_name': 'tryserver.bar',
          'builder_name': 'baz',
          'build_number': 20,
          'step_name': 'step3'
        }
      ]
    })
