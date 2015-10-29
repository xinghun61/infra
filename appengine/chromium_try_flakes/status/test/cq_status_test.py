# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import mock

from google.appengine.datastore import datastore_stub_util
from google.appengine.ext import ndb

import main
from model.flake import Flake, FlakyRun
from model.build_run import BuildRun, PatchsetBuilderRuns
from status import cq_status
from testing_utils import testing


TEST_BUILDBOT_JSON_REPLY = json.dumps({
  'steps': [
    # Simple case.
    {'results': [2], 'name': 'foo1', 'text': ['bar1']},

    # Invalid test results.
    {'results': [2], 'name': 'foo2', 'text': ['TEST RESULTS WERE INVALID']},

    # GTest tests.
    {
      'results': [2],
      'name': 'foo3',
      'text': ['failures:<br/>bar2<br/>bar3<br/><br/>ignored:<br/>bar4']
    },

    # GPU tests.
    {
      'results': [2],
      'name': 'foo4',
      'text': ['<"http://url/path?query&tests=bar5,bar6,,bar7">']
    },

    # Ignore non-success non-failure results (7 is TRY_PENDING).
    {'results': [7], 'name': 'foo5', 'text': ['bar8']},

    # Ignore steps that are failing without patch too (ToT is broken).
    {'results': [2], 'name': 'foo6 (with patch)', 'text': ['bar9']},
    {'results': [2], 'name': 'foo6 (without patch)', 'text': ['bar9']},

    # Ignore steps that are duplicating error in another step.
    {'results': [2], 'name': 'steps', 'text': ['bar10']},
    {'results': [2], 'name': '[swarming] foo7', 'text': ['bar11']},
    {'results': [2], 'name': 'presubmit', 'text': ['bar12']},

    # Only count first step (with patch) and ignore summary step.
    {'results': [2], 'name': 'foo8 (with patch)', 'text': ['bar13']},
    {'results': [0], 'name': 'foo8 (without patch)', 'text': ['bar14']},
    {'results': [2], 'name': 'foo8', 'text': ['bar15']},

    # GTest without flakes.
    {
      'results': [2],
      'name': 'foo9',
      'text': ['failures:<br/><br/><br/>']
    },

  ]
})


class CQStatusTestCase(testing.AppengineTestCase):
  app_module = main.app

  # This is needed to be able to test handlers using cross-group transactions.
  datastore_stub_consistency_policy = (
      datastore_stub_util.PseudoRandomHRConsistencyPolicy(probability=1))

  # Needed to read queues from queue.yaml in the root of the app.
  taskqueue_stub_root_path = ''

  def test_create_tasks_to_update_issue_tracker(self):
    Flake(name='foo1', count_day=1).put()
    key2 = Flake(name='foo2', count_day=10).put()
    key3 = Flake(name='foo3', count_day=15).put()
    Flake(name='foo4', count_day=5).put()
    key5 = Flake(name='foo5', count_day=200).put()

    path = '/cron/update_issue_tracker'
    response = self.test_app.get(path, headers={'X-AppEngine-Cron': 'true'})
    self.assertEquals(200, response.status_int)

    tasks = self.taskqueue_stub.get_filtered_tasks(queue_names='issue-updates')
    self.assertEquals(len(tasks), 3)
    self.assertEquals(tasks[0].url, '/issues/process/%s' % key2.urlsafe())
    self.assertEquals(tasks[1].url, '/issues/process/%s' % key3.urlsafe())
    self.assertEquals(tasks[2].url, '/issues/process/%s' % key5.urlsafe())

  def _create_flaky_run(self, tf):
    pbr = PatchsetBuilderRuns(
        issue=123456789, patchset=20001, master='test.master',
        builder='test-builder').put()
    br_f = BuildRun(
        parent=pbr, buildnumber=100, result=2, time_finished=tf).put()
    br_s = BuildRun(
        parent=pbr, buildnumber=101, result=0, time_finished=tf).put()
    return FlakyRun(
        failure_run=br_f, success_run=br_s, failure_run_time_finished=tf).put()

  def test_get_flaky_run_reason_ignores_invalid_json(self):
    fr_key = self._create_flaky_run(datetime.datetime.now())

    urlfetch_mock = mock.Mock()
    urlfetch_mock.return_value.content = 'invalid-json'

    with mock.patch('google.appengine.api.urlfetch.fetch', urlfetch_mock):
      cq_status.get_flaky_run_reason(fr_key)

  def test_get_flaky_run_reason(self):
    now = datetime.datetime.now()
    fr_key = self._create_flaky_run(now)

    urlfetch_mock = mock.Mock()
    urlfetch_mock.return_value.content = TEST_BUILDBOT_JSON_REPLY

    with mock.patch('google.appengine.api.urlfetch.fetch', urlfetch_mock):
      cq_status.get_flaky_run_reason(fr_key)

    # Verify that we've used correct URL to access buildbot JSON endpoint.
    urlfetch_mock.assert_called_once_with(
        'http://build.chromium.org/p/test.master/json/builders/test-builder/'
        'builds/100')

    # Expected flakes to be found: list of (step_name, test_name).
    expected_flakes = [
        ('foo1', 'bar1'), ('foo2', 'TEST RESULTS WERE INVALID'),
        ('foo3', 'bar2'), ('foo3', 'bar3'), ('foo4', 'bar5'), ('foo4', 'bar6'),
        ('foo4', 'bar7'), ('foo8 (with patch)', 'bar13'),
    ]

    flake_occurrences = fr_key.get().flakes
    self.assertEqual(len(flake_occurrences), len(expected_flakes))
    actual_flake_occurrences = [
        (fo.name, fo.failure) for fo in flake_occurrences]
    self.assertEqual(expected_flakes, actual_flake_occurrences)

    # We compare sets below, because order of flakes returned by datastore
    # doesn't have to be same as steps above.
    flakes = Flake.query().fetch()
    self.assertEqual(len(flakes), len(expected_flakes))
    expected_flake_names = set([ef[1] for ef in expected_flakes])
    actual_flake_names = set([f.name for f in flakes])
    self.assertEqual(expected_flake_names, actual_flake_names)

    for flake in flakes:
      self.assertEqual(flake.occurrences, [fr_key])
      self.assertEqual(flake.last_time_seen, now)
      self.assertEqual(flake.count_hour, 1)
      self.assertEqual(flake.count_day, 1)
      self.assertEqual(flake.count_week, 1)
      self.assertEqual(flake.count_month, 1)
      self.assertEqual(flake.last_hour, True)
      self.assertEqual(flake.last_day, True)
      self.assertEqual(flake.last_week, True)
      self.assertEqual(flake.last_month, True)
