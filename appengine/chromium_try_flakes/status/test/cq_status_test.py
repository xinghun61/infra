# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import mock
import urllib2

from google.appengine.datastore import datastore_stub_util
from google.appengine.ext import ndb
from google.appengine.runtime import DeadlineExceededError

import main
from model.fetch_status import FetchStatus
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

# Test results below capture various variants in which results may be processed.
# Special attention should be paid to the 'issue' and 'patchset' fields as code
# is expected to correctly process results from different issues and patchsets
# independently of each other.
TEST_CQ_STATUS_RESPONSE = json.dumps({
  'more': False,
  'cursor': '',
  'results': [
    # Ignored because action field is missing.
    {
      'fields': {
        'verifier': 'try job',
        'project': 'chromium',
      }
    },
    # Ignored because action field is not 'verifier_jobs_update'.
    {
      'fields': {
        'action': 'verifier_trigger',
        'verifier': 'try job',
        'project': 'chromium',
      }
    },
    # Ignored because verifier field is not 'try job'.
    {
      'fields': {
        'action': 'verifier_jobs_update',
        'verifier': 'experimental try job',
        'project': 'chromium',
      }
    },
    # Ignored because project field is not 'chromium'.
    {
      'fields': {
        'action': 'verifier_jobs_update',
        'verifier': 'try job',
        'project': 'blink',
      }
    },
    {
      'fields': {
        'action': 'verifier_jobs_update',
        'verifier': 'try job',
        'project': 'chromium',
        'jobs': {
          'JOB_PENDING': [
            # Ignored because the job is still pending.
            {
              'build_properties': {
                'buildnumber': 100,
                'issue': 987654321,
                'patchset': 1,
              },
              'master': 'tryserver.test',
              'builder': 'test-builder',
              'result': 6,  # TRY_PENDING
              'timestamp': '2015-10-30 17:08:12.123456',
            },
          ],
          'JOB_SUCCEEDED': [
            {
              'build_properties': {
                'buildnumber': 101,
                'issue': 123456789,
                'patchset': 20001,
              },
              'master': 'tryserver.test',
              'builder': 'test-builder',
              'result': 0,  # SUCCESS
              'timestamp': '2015-10-30 17:30:12.123456',
            },
            # This duplicate success should generate more flakes.
            {
              'build_properties': {
                'buildnumber': 102,
                'issue': 123456789,
                'patchset': 20001,
              },
              'master': 'tryserver.test',
              'builder': 'test-builder',
              'result': 0,  # SUCCESS
              'timestamp': '2015-10-30 17:30:12.123456',
            },
            # Two successes below should not result in a flaky run.
            {
              'build_properties': {
                'buildnumber': 103,
                'issue': 100200300,
                'patchset': 1,
              },
              'master': 'tryserver.test',
              'builder': 'test-builder',
              'result': 0,  # SUCCESS
              'timestamp': '2015-10-30 17:30:12.123456',
            },
            {
              'build_properties': {
                'buildnumber': 104,
                'issue': 100200300,
                'patchset': 1,
              },
              'master': 'tryserver.test',
              'builder': 'test-builder',
              'result': 0,  # SUCCESS
              'timestamp': '2015-10-30 17:30:12.123456',
            },
          ],
          'JOB_FAILED': [
            # Ignored because build_properties is empty.
            {
              'build_properties': {},
            },
            {
              'build_properties': {
                'buildnumber': 105,
                'issue': 987654321,
                'patchset': 20001,
              },
              'master': 'tryserver.test',
              'builder': 'test-builder',
              'result': 2,  # FAILURE
              'timestamp': '2015-10-30 16:58:12.123456',
            },
            {
              'build_properties': {
                'buildnumber': 106,
                'issue': 123456789,
                'patchset': 20001,
              },
              'master': 'tryserver.test',
              'builder': 'test-builder',
              'result': 2,  # FAILURE
              'timestamp': '2015-10-30 17:10:12.123456',
            },
            # Ignored as a duplicate of the previous one.
            {
              'build_properties': {
                'buildnumber': 106,
                'issue': 123456789,
                'patchset': 20001,
              },
              'master': 'tryserver.test',
              'builder': 'test-builder',
              'result': 2,  # FAILURE
              'timestamp': '2015-10-30 17:10:12.123456',
            },
            # Two failures below should not result in a flaky run.
            {
              'build_properties': {
                'buildnumber': 107,
                'issue': 100300200,
                'patchset': 20001,
              },
              'master': 'tryserver.test',
              'builder': 'test-builder',
              'result': 2,  # FAILURE
              'timestamp': '2015-10-30 17:10:12.123456',
            },
            {
              'build_properties': {
                # Build properties may be lists, but only first value is taken.
                'buildnumber': [108, 300, 500],
                'issue': [100300200, -1, -2],
                'patchset': [20001, 0],
              },
              'master': 'tryserver.test',
              'builder': 'test-builder',
              'result': 2,  # FAILURE
              'timestamp': '2015-10-30 17:10:12.123456',
            },
            # Ignored because buildnumber is missing.
            {
              'build_properties': {
                'issue': 100300200,
                'patchset': 20001,
              },
              'master': 'tryserver.test',
              'builder': 'test-builder',
              'result': 2,  # FAILURE
              'timestamp': '2015-10-30 17:10:12.123456',
            },
            # Ignored because buildnumber is not an integer.
            {
              'build_properties': {
                'buildnumber': 'abc',
                'issue': 100300200,
                'patchset': 20001,
              },
              'master': 'tryserver.test',
              'builder': 'test-builder',
              'result': 2,  # FAILURE
              'timestamp': '2015-10-30 17:10:12.123456',
            },
          ],
        },
      },
    },
    # Second result is here to force results processed in certain order. This
    # allows to test both cases when failure is before and after success.
    {
      'fields': {
        'action': 'verifier_jobs_update',
        'verifier': 'try job',
        'project': 'chromium',
        'jobs': {
          'JOB_FAILED': [
            {
              'build_properties': {
                'buildnumber': 109,
                'issue': 123456789,
                'patchset': 20001,
              },
              'master': 'tryserver.test',
              'builder': 'test-builder',
              'result': 2,  # FAILURE
              'timestamp': '2015-10-30 16:58:12.123456',
            },
          ],
          'JOB_SUCCEEDED': [
            {
              'build_properties': {
                'buildnumber': 110,
                'issue': 987654321,
                'patchset': 20001,
              },
              'master': 'tryserver.test',
              'builder': 'test-builder',
              'result': 0,  # SUCCESS
              'timestamp': '2015-10-30 17:30:12.123456',
            },
          ],
        },
      },
    },
  ],
})


class DateTimeMock(datetime.datetime):
  test_utcnow = datetime.datetime(2015, 10, 30, 14, 17, 42)

  @classmethod
  def utcnow(cls):
    return cls.test_utcnow


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
    self.assertEqual(200, response.status_int)

    tasks = self.taskqueue_stub.get_filtered_tasks(queue_names='issue-updates')
    self.assertEqual(len(tasks), 3)
    self.assertEqual(tasks[0].url, '/issues/process/%s' % key2.urlsafe())
    self.assertEqual(tasks[1].url, '/issues/process/%s' % key3.urlsafe())
    self.assertEqual(tasks[2].url, '/issues/process/%s' % key5.urlsafe())

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
    fr_key = self._create_flaky_run(datetime.datetime.utcnow())

    urlfetch_mock = mock.Mock()
    urlfetch_mock.return_value.content = 'invalid-json'

    with mock.patch('google.appengine.api.urlfetch.fetch', urlfetch_mock):
      cq_status.get_flaky_run_reason(fr_key)

  def test_get_flaky_run_reason(self):
    now = datetime.datetime.utcnow()
    fr_key = self._create_flaky_run(now)

    urlfetch_mock = mock.Mock()
    urlfetch_mock.return_value.content = TEST_BUILDBOT_JSON_REPLY

    # We also create one Flake to test that it is correctly updated. Other Flake
    # entities will be created automatically.
    Flake(id='bar5', name='bar5', occurrences=[],
          last_time_seen=datetime.datetime.min).put()

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

  def _mock_response(self, content):
    m = mock.Mock()
    if isinstance(content, basestring):
      m.content = content
    else:
      m.content = json.dumps(content)
    return m

  def test_fetch_cq_status_handles_and_retries_non_json_replies(self):
    urlfetch_mock = mock.Mock()
    urlfetch_mock.side_effect = [
        self._mock_response('DeadlineExceededError'),
        self._mock_response('DeadlineExceededError'),
        self._mock_response('invalid-json'),
        self._mock_response('invalid-json'),
        self._mock_response('invalid-json'),
        self._mock_response('invalid-json'),  # should give up on this one
    ]

    with mock.patch('google.appengine.api.urlfetch.fetch', urlfetch_mock):
      with mock.patch('time.sleep'):
        # No exceptions should be raised - we should just silently fail.
        cq_status.fetch_cq_status()

    # Make sure we actually give up after last call.
    self.assertEqual(urlfetch_mock.call_count, 6)

  @mock.patch('datetime.datetime', DateTimeMock)
  def test_cq_status_fetch_fetches_one_week_if_no_previous_status(self):
    urlfetch_mock = mock.Mock()
    urlfetch_mock.return_value.content = json.dumps({
        'more': False, 'cursor': None, 'results': []})

    with mock.patch('google.appengine.api.urlfetch.fetch', urlfetch_mock):
      cq_status.fetch_cq_status()

    urlfetch_mock.assert_called_once_with(
      'https://chromium-cq-status.appspot.com/query?'
      'tags=action=verifier_jobs_update&begin=1445609862.0&end=1446214662.0&'
      'count=10')

  @mock.patch('datetime.datetime', DateTimeMock)
  def test_cq_status_fetch_continues_previous_fetch(self):
    urlfetch_mock = mock.Mock()
    urlfetch_mock.return_value.content = json.dumps({
        'more': False, 'cursor': None, 'results': []})

    FetchStatus(cursor='abcd', begin='1445604262.0', end='1446212662.0',
                done=False).put()
    with mock.patch('google.appengine.api.urlfetch.fetch', urlfetch_mock):
      cq_status.fetch_cq_status()

    urlfetch_mock.assert_called_once_with(
      'https://chromium-cq-status.appspot.com/query?'
      'tags=action=verifier_jobs_update&cursor=abcd&begin=1445604262.0&'
      'end=1446212662.0&count=10')

  @mock.patch('datetime.datetime', DateTimeMock)
  def test_cq_status_fetch_without_begin_end(self):
    urlfetch_mock = mock.Mock()
    urlfetch_mock.return_value.content = json.dumps({
        'more': False, 'cursor': None, 'results': []})

    FetchStatus(cursor='abcd', done=False).put()
    with mock.patch('google.appengine.api.urlfetch.fetch', urlfetch_mock):
      cq_status.fetch_cq_status()

    urlfetch_mock.assert_called_once_with(
      'https://chromium-cq-status.appspot.com/query?'
      'tags=action=verifier_jobs_update&cursor=abcd&count=10')

  @mock.patch('datetime.datetime', DateTimeMock)
  def test_cq_status_fetch_stats_new_fetch_from_last_build_run(self):
    urlfetch_mock = mock.Mock()
    urlfetch_mock.return_value.content = json.dumps({
        'more': False, 'cursor': None, 'results': []})

    FetchStatus(cursor='xxx', begin='1', end='2', done=True).put()
    BuildRun(time_finished=datetime.datetime(2015, 10, 30, 13, 17, 42),
             buildnumber=0, result=0).put()
    BuildRun(time_finished=datetime.datetime(2015, 10, 30, 12, 17, 42),
             buildnumber=0, result=0).put()
    with mock.patch('google.appengine.api.urlfetch.fetch', urlfetch_mock):
      cq_status.fetch_cq_status()

    urlfetch_mock.assert_called_once_with(
      'https://chromium-cq-status.appspot.com/query?'
      'tags=action=verifier_jobs_update&begin=1446211062.0&end=1446214662.0&'
      'count=10')

  def test_cq_status_fetch_captures_deadline_exceeded_errors(self):
    urlfetch_mock = mock.Mock()
    urlfetch_mock.return_value.content = json.dumps({
        'more': False, 'cursor': None, 'results': []})

    with mock.patch('google.appengine.api.urlfetch.fetch', urlfetch_mock):
      with mock.patch('status.cq_status.parse_cq_data') as parse_cq_data_mock:
        parse_cq_data_mock.side_effect = [DeadlineExceededError()]
        cq_status.fetch_cq_status()

  def test_cq_status_fetch_captures_urllib2_error(self):
    urlfetch_mock = mock.Mock()
    urlfetch_mock.side_effect = [
        urllib2.URLError('reason'),
        self._mock_response({'more': False, 'cursor': None, 'results': []}),
    ]

    with mock.patch('google.appengine.api.urlfetch.fetch', urlfetch_mock):
      cq_status.fetch_cq_status()

  @mock.patch('datetime.datetime', DateTimeMock)
  def test_cq_status_fetch_stores_intermediate_status(self):
    urlfetch_mock = mock.Mock()
    urlfetch_mock.side_effect = [
        self._mock_response({'more': True, 'cursor': 'abcd', 'results': []}),
        self._mock_response({'more': False, 'cursor': None, 'results': []}),
    ]

    with mock.patch('google.appengine.api.urlfetch.fetch', urlfetch_mock):
      with mock.patch('status.cq_status.parse_cq_data') as parse_cq_data_mock:
        parse_cq_data_mock.side_effect = [None, DeadlineExceededError()]
        cq_status.fetch_cq_status()

    fetch_status = FetchStatus.query().get()
    self.assertEqual(fetch_status.cursor, 'abcd')
    self.assertEqual(fetch_status.begin, '1445609862.0')
    self.assertEqual(fetch_status.end, '1446214662.0')
    self.assertEqual(fetch_status.done, False)

  def test_cq_status_fetch_processes_all_flakes(self):
    urlfetch_mock = mock.Mock()
    urlfetch_mock.side_effect = [
        self._mock_response({'more': True, 'cursor': 'abcd', 'results': []}),
        self._mock_response({'more': True, 'cursor': 'efgh', 'results': []}),
        self._mock_response({'more': False, 'cursor': '', 'results': []}),
    ]

    with mock.patch('google.appengine.api.urlfetch.fetch', urlfetch_mock):
      cq_status.fetch_cq_status()

    self.assertEqual(urlfetch_mock.call_count, 3)

  def test_cq_status_fetch_detects_flaky_runs_correctly(self):
    urlfetch_mock = mock.Mock()
    urlfetch_mock.return_value.content = TEST_CQ_STATUS_RESPONSE

    with mock.patch('google.appengine.api.urlfetch.fetch', urlfetch_mock):
      cq_status.fetch_cq_status()

    flaky_runs = FlakyRun.query().fetch(100)
    self.assertEqual(len(flaky_runs), 3)

    # We only compare select few properties of the created FlakyRun entities.
    flaky_run_tuples = set()
    for flaky_run in flaky_runs:
      failure_run = flaky_run.failure_run.get()
      success_run = flaky_run.success_run.get()
      self.assertEqual(failure_run.key.parent(), success_run.key.parent())
      pbr = failure_run.key.parent().get()
      flaky_run_tuple = (pbr.master, pbr.builder, pbr.issue, pbr.patchset,
                         failure_run.buildnumber, success_run.buildnumber)
      flaky_run_tuples.add(flaky_run_tuple)

    expected_flaky_runs = set([
      ('tryserver.test', 'test-builder', 987654321, 20001, 105, 110),
      ('tryserver.test', 'test-builder', 123456789, 20001, 109, 101),
      ('tryserver.test', 'test-builder', 123456789, 20001, 106, 101),
    ])
    self.assertEqual(flaky_run_tuples, expected_flaky_runs)

  def test_cq_status_fetch_creates_deferred_tasks_correctly(self):
    urlfetch_mock = mock.Mock()
    urlfetch_mock.return_value.content = TEST_CQ_STATUS_RESPONSE

    with mock.patch('google.appengine.api.urlfetch.fetch', urlfetch_mock):
      cq_status.fetch_cq_status()

    tasks = self.taskqueue_stub.get_filtered_tasks()
    self.assertEqual(len(tasks), 3)

  def test_cq_status_processes_timestamp_in_raw_json(self):
    urlfetch_mock = mock.Mock()
    urlfetch_mock.return_value.content = (
        '{"more":false,"cursor":"","results":[],"timestamp":"foo"}')

    with mock.patch('google.appengine.api.urlfetch.fetch', urlfetch_mock):
      with mock.patch('logging.info') as logging_info_mock:
        cq_status.fetch_cq_status()
        logging_info_mock.assert_any_call(' current fetch has time of foo')
