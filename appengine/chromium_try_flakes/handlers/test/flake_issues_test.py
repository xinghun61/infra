# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import mock
import urllib2

from google.appengine.datastore import datastore_stub_util
from google.appengine.ext import ndb

from handlers.flake_issues import ProcessIssue, CreateFlakyRun
import main
from model.flake import Flake, FlakyRun, FlakeOccurrence
from model.build_run import PatchsetBuilderRuns, BuildRun
from testing_utils import testing
from time_functions.testing import mock_datetime_utc


TEST_TEST_RESULTS_REPLY = json.dumps({
  'tests': {
    'test1': {
      'expected': 'PASS',
      'actual': 'FAIL FAIL PASS',
    },
    'test2': {
      'a': {
        'expected': 'PASS',
        'actual': 'FAIL',
      },
      'b': {
        'expected': 'SKIP',
        'actual': 'SKIP',
      },
      'c': {
        'expected': 'PASS FAIL',
        'actual': 'PASS',
      },
      'd': {
        'expected': 'PASS',
        'actual': 'TIMEOUT FAIL TIMEOUT',
      },
      'e': {
        'expected': 'TIMEOUT',
        'actual': 'TIMEOUT',
      },
      'f': {
        'expected': 'PASS',
        'actual': 'SKIP',
      },
    },
  },
  'path_delimiter': '.',
})


TEST_BUILDBOT_JSON_REPLY = json.dumps({
  'steps': [
    # Simple case.
    {'results': [2], 'name': 'foo1', 'text': ['bar1']},

    # Invalid test results.
    {'results': [2], 'name': 'foo2', 'text': ['TEST RESULTS WERE INVALID']},

    # Ignore non-success non-failure results (7 is TRY_PENDING).
    {'results': [7], 'name': 'foo5', 'text': ['bar8']},

    # Ignore steps that are failing without patch too (ToT is broken).
    {'results': [2], 'name': 'foo6 (with patch)', 'text': ['bar9']},
    {'results': [2], 'name': 'foo6 (without patch)', 'text': ['bar9']},

    # Ignore steps that are duplicating error in another step.
    {'results': [2], 'name': 'steps', 'text': ['bar10']},
    {'results': [2], 'name': '[swarming] foo7', 'text': ['bar11']},
    {'results': [2], 'name': 'presubmit', 'text': ['bar12']},
    {'results': [2], 'name': 'recipe failure reason', 'text': ['bar12a']},
    {'results': [2], 'name': 'test results', 'text': ['bar12b']},
    {'results': [2], 'name': 'Uncaught Exception', 'text': ['bar12c']},
    {'results': [2], 'name': 'bot_update', 'text': ['bot_update PATCH FAILED']},

    # Only count first step (with patch) and ignore summary step.
    {'results': [2], 'name': 'foo8 xx (with patch)', 'text': ['bar13']},
    {'results': [0], 'name': 'foo8 xx (without patch)', 'text': ['bar14']},
    {'results': [2], 'name': 'foo8 xx (retry summary)', 'text': ['bar15']},
  ]
})


class MockComment(object):
  def __init__(self, created, author, comment=None):
    self.created = created
    self.author = author
    self.comment = comment

class MockIssue(object):
  def __init__(self, issue_entry):
    self.created = issue_entry.get('created')
    self.summary = issue_entry.get('summary')
    self.description = issue_entry.get('description')
    self.status = issue_entry.get('status')
    self.labels = issue_entry.get('labels', [])
    self.open = True
    self.updated = datetime.datetime.utcnow()
    self.comments = []
    self.cc = []
    self.merged_into = None


class MockIssueTrackerAPI(object):
  def __init__(self):
    self.issues = {}
    self.next_issue_id = 100000

  def create(self, issue):
    issue.id = self.next_issue_id
    self.next_issue_id += 1
    self.issues[issue.id] = issue
    return issue

  def getIssue(self, issue_id):
    return self.issues[issue_id]

  def getComments(self, issue_id):
    return self.issues[issue_id].comments

  def update(self, issue, comment):
    self.issues[issue.id] = issue
    issue.comments.append(
        MockComment(datetime.datetime.utcnow(), 'app@ae.org', comment))


class FlakeIssuesTestCase(testing.AppengineTestCase):
  app_module = main.app

  # This is needed to be able to test handlers using cross-group transactions.
  datastore_stub_consistency_policy = (
      datastore_stub_util.PseudoRandomHRConsistencyPolicy(probability=1))

  # Needed to read queues from queue.yaml in the root of the app.
  taskqueue_stub_root_path = '.'

  def setUp(self):
    super(FlakeIssuesTestCase, self).setUp()
    self.mock_api = MockIssueTrackerAPI()
    self.patchers = [
        mock.patch('issue_tracker.issue_tracker_api.IssueTrackerAPI',
                   lambda *args, **kwargs: self.mock_api),
        mock.patch('issue_tracker.issue.Issue', MockIssue),
        mock.patch('google.appengine.api.app_identity.get_service_account_name',
                   lambda *args, **kwargs: 'app@ae.org')
    ]
    for patcher in self.patchers:
      patcher.start()


  def tearDown(self):
    super(FlakeIssuesTestCase, self).tearDown()
    for patcher in self.patchers:
      patcher.stop()

  def _create_flake(self):
    tf = datetime.datetime.utcnow()
    ts = tf - datetime.timedelta(hours=1)
    tf2 = tf - datetime.timedelta(days=1)
    ts2 = tf2 - datetime.timedelta(hours=1)
    p = PatchsetBuilderRuns(issue=123456, patchset=1, master='tryserver.test',
                            builder='test-builder').put()
    br_f0 = BuildRun(parent=p, buildnumber=0, result=2, time_started=ts2,
                     time_finished=tf2).put()
    br_f1 = BuildRun(parent=p, buildnumber=1, result=2, time_started=ts,
                     time_finished=tf).put()
    br_s1 = BuildRun(parent=p, buildnumber=2, result=0, time_started=ts,
                     time_finished=tf).put()
    br_f2 = BuildRun(parent=p, buildnumber=3, result=4, time_started=ts,
                     time_finished=tf).put()
    br_s2 = BuildRun(parent=p, buildnumber=4, result=0, time_started=ts,
                     time_finished=tf).put()
    occ_key1 = FlakyRun(failure_run=br_f0, success_run=br_s2,
                        failure_run_time_started=ts2,
                        failure_run_time_finished=tf2).put()
    occ_key2 = FlakyRun(failure_run=br_f1, success_run=br_s1,
                        failure_run_time_started=ts,
                        failure_run_time_finished=tf).put()
    occ_key3 = FlakyRun(failure_run=br_f2, success_run=br_s2,
                        failure_run_time_started=ts,
                        failure_run_time_finished=tf).put()
    return Flake(name='foo.bar', count_day=10,
                 occurrences=[occ_key1, occ_key2, occ_key3])


  @mock_datetime_utc(2015, 11, 10, 10, 11, 0)
  def test_creates_issue_for_new_flake(self):
    with mock.patch('handlers.flake_issues.MIN_REQUIRED_FLAKY_RUNS', 2):
      flake = self._create_flake()
      flake.key = ndb.Key('Flake', 'test-flake-key')
      flake.put()

      response = self.test_app.post('/issues/process/%s' % flake.key.urlsafe())
      self.assertEqual(200, response.status_int)

    self.assertEqual(len(self.mock_api.issues), 1)
    self.assertIn(100000, self.mock_api.issues)
    issue = self.mock_api.issues[100000]
    self.assertEqual(issue.summary, '"foo.bar" is flaky')
    self.assertEqual(
        issue.description,
        '"foo.bar" is flaky.\n\nThis issue was created automatically by the '
        'chromium-try-flakes app. Please find the right owner to fix the '
        'respective test/step and assign this issue to them. If the step/test '
        'is infrastructure-related, please add Infra-Troopers label and change '
        'issue status to Untriaged. When done, please remove the issue from '
        'Sheriff Bug Queue by removing the Sheriff-Chromium label.\n\n'
        'We have detected 2 recent flakes. List of all flakes can be found at '
        'https://chromium-try-flakes.appspot.com/all_flake_occurrences?key='
        'agx0ZXN0YmVkLXRlc3RyGQsSBUZsYWtlIg50ZXN0LWZsYWtlLWtleQw.\n\n'
        'Flaky tests should be disabled within 30 minutes unless culprit CL is '
        'found and reverted. Please see more details here: '
        'https://sites.google.com/a/chromium.org/dev/developers/tree-sheriffs/'
        'sheriffing-bug-queues#triaging-auto-filed-flakiness-bugs')
    self.assertEqual(issue.status, 'Untriaged')
    self.assertEqual(issue.labels, ['Type-Bug', 'Pri-1', 'Cr-Tests-Flaky',
                                    'Via-TryFlakes', 'Sheriff-Chromium'])
    self.assertEqual(len(issue.comments), 0)

    # Check that flake in datastore was properly updated.
    updated_flake = flake.key.get()
    self.assertEqual(updated_flake.issue_id, 100000)
    self.assertEqual(updated_flake.num_reported_flaky_runs, 3)
    self.assertEqual(updated_flake.issue_last_updated,
                     datetime.datetime(2015, 11, 10, 10, 11, 0))

  @mock_datetime_utc(2015, 11, 10, 10, 11, 0)
  def test_creates_issue_for_troopers(self):
    flake = self._create_flake()
    flake.name = 'compile (with patch)'
    flake.put()

    with mock.patch('handlers.flake_issues.MIN_REQUIRED_FLAKY_RUNS', 2):
      response = self.test_app.post('/issues/process/%s' % flake.key.urlsafe())

    self.assertEqual(200, response.status_int)

    # Only check what differentiates a trooper issue from a sheriff issue. The
    # rest of the properties are checked in test_creates_issue_for_new_flake.
    self.assertIn(100000, self.mock_api.issues)
    issue = self.mock_api.issues[100000]
    self.assertIn(
        'If the step/test is not infrastructure-related (e.g. flaky test), '
        'please add Sheriff-Chromium label and change issue status to '
        'Untriaged. When done, please remove the issue from Trooper Bug Queue '
        'by removing the Infra-Troopers label.', issue.description)
    self.assertEqual(issue.labels, ['Type-Bug', 'Pri-1', 'Cr-Tests-Flaky',
                                    'Via-TryFlakes', 'Infra-Troopers'])

  def test_updates_new_occurrences_with_issue_id(self):
    flake = self._create_flake()
    flake.num_reported_flaky_runs = 1
    flake.put()

    # Already reported occurrences should not be updated.
    fr1 = flake.occurrences[0].get()
    fr1.flakes = [FlakeOccurrence(name='', failure='foo.bar')]
    fr1.put()

    fr2 = flake.occurrences[1].get()
    fr2.flakes = [
        # Occurrences for other flakes should not be updated.
        FlakeOccurrence(name='', failure='bar.foo'),
        # This occurrence should be updated.
        FlakeOccurrence(name='', failure='foo.bar'),
    ]
    fr2.put()

    # Only flakes that are reported should be updated. This flake has too large
    # distance between failure and success runs.
    fr3 = flake.occurrences[2].get()
    fr3.flakes = [FlakeOccurrence(name='', failure='foo.bar')]
    fr3.failure_run_time_finished = (
        fr3.success_run.get().time_finished - datetime.timedelta(hours=13))
    fr3.put()

    with mock.patch('handlers.flake_issues.MIN_REQUIRED_FLAKY_RUNS', 1):
      response = self.test_app.post('/issues/process/%s' % flake.key.urlsafe())
      self.assertEqual(200, response.status_int)

    self.assertEqual(flake.occurrences[0].get().flakes[0].issue_id, 0)
    self.assertEqual(flake.occurrences[1].get().flakes[0].issue_id, 0)
    self.assertEqual(flake.occurrences[1].get().flakes[1].issue_id, 100000)
    self.assertEqual(flake.occurrences[2].get().flakes[0].issue_id, 0)

  def test_recreates_issue_after_a_week(self):
    issue = self.mock_api.create(MockIssue({}))
    issue.open = False

    now = datetime.datetime.utcnow()
    flake = self._create_flake()
    flake.issue_id = issue.id
    flake.issue_last_updated = now - datetime.timedelta(days=2)
    flake.num_reported_flaky_runs = 0
    flake_key = flake.put()
    issue.updated = now - datetime.timedelta(days=2)

    with mock.patch('handlers.flake_issues.MIN_REQUIRED_FLAKY_RUNS', 2):
      response = self.test_app.post('/issues/process/%s' % flake_key.urlsafe())
      self.assertEqual(200, response.status_int)
      tasks = self.taskqueue_stub.get_filtered_tasks(
          queue_names='issue-updates')
      self.assertEqual(len(tasks), 0)

      flake.num_reported_flaky_runs = 0
      issue.updated = now - datetime.timedelta(days=4)
      flake_key = flake.put()
      response = self.test_app.post('/issues/process/%s' % flake_key.urlsafe())
      self.assertEqual(200, response.status_int)
      tasks = self.taskqueue_stub.get_filtered_tasks(
          queue_names='issue-updates')
      self.assertEqual(len(tasks), 1)
      response = self.test_app.post('/issues/process/%s' % flake_key.urlsafe())
      self.assertEqual(200, response.status_int)

    self.assertEqual(len(self.mock_api.issues), 2)
    self.assertEqual(self.mock_api.issues.keys(), [100000, 100001])
    self.assertTrue(self.mock_api.issues[100001].description.endswith(
        'This flaky test/step was previously tracked in issue 100000.'))

  def test_updates_issue_only_once_a_day(self):
    issue = self.mock_api.create(MockIssue({}))
    issue.labels = ['Sheriff-Chromium']

    now = datetime.datetime.utcnow()
    flake = self._create_flake()
    flake.issue_id = issue.id
    flake.issue_last_updated = now - datetime.timedelta(hours=23)
    flake.num_reported_flaky_runs = 0
    flake_key = flake.put()

    with mock.patch('handlers.flake_issues.MIN_REQUIRED_FLAKY_RUNS', 2):
      self.assertEqual(len(issue.comments), 0)
      response = self.test_app.post('/issues/process/%s' % flake_key.urlsafe())
      self.assertEqual(200, response.status_int)
      self.assertEqual(len(issue.comments), 0)

      flake.issue_last_updated = now - datetime.timedelta(hours=25)
      flake_key = flake.put()
      response = self.test_app.post('/issues/process/%s' % flake_key.urlsafe())
      self.assertEqual(200, response.status_int)
    self.assertEqual(len(issue.comments), 1)
    self.assertEqual(
        issue.comments[0].comment,
        'Detected 2 new flakes for test/step "foo.bar". To see the actual '
        'flakes, please visit https://chromium-try-flakes.appspot.com/'
        'all_flake_occurrences?key=agx0ZXN0YmVkLXRlc3RyCwsSBUZsYWtlGAoM. This '
        'message was posted automatically by the chromium-try-flakes app. '
        'Since flakiness is ongoing, the issue was moved back into Sheriff Bug '
        'Queue (unless already there).'
    )

  def test_adds_sheriff_label_when_updating_issue(self):
    issue = self.mock_api.create(MockIssue({}))

    now = datetime.datetime.utcnow()
    flake = self._create_flake()
    flake.issue_id = issue.id
    flake.num_reported_flaky_runs = 0
    flake.issue_last_updated = now - datetime.timedelta(hours=25)
    flake_key = flake.put()

    with mock.patch('handlers.flake_issues.MIN_REQUIRED_FLAKY_RUNS', 2):
      self.test_app.post('/issues/process/%s' % flake_key.urlsafe())

    self.assertIn('Sheriff-Chromium', issue.labels)

  def test_updates_issue_only_if_there_are_new_flakes(self):
    issue = self.mock_api.create(MockIssue({}))

    now = datetime.datetime.utcnow()
    flake = self._create_flake()
    flake.issue_id = issue.id
    flake.issue_last_updated = now - datetime.timedelta(days=2)
    flake.num_reported_flaky_runs = 3
    flake_key = flake.put()

    with mock.patch('handlers.flake_issues.MIN_REQUIRED_FLAKY_RUNS', 2):
      self.assertEqual(len(issue.comments), 0)
      response = self.test_app.post('/issues/process/%s' % flake_key.urlsafe())
      self.assertEqual(200, response.status_int)
      self.assertEqual(len(issue.comments), 0)

      flake.num_reported_flaky_runs = 0
      flake_key = flake.put()
      response = self.test_app.post('/issues/process/%s' % flake_key.urlsafe())
      self.assertEqual(200, response.status_int)
      self.assertEqual(len(issue.comments), 1)

  @mock_datetime_utc(2015, 11, 10, 12, 13, 14)
  def test_updates_flake_in_datastore_after_updating_issue(self):
    issue = self.mock_api.create(MockIssue({}))

    flake = self._create_flake()
    flake.issue_id = issue.id
    flake.issue_last_updated = datetime.datetime(2015, 11, 8, 12, 13, 14)
    flake.num_reported_flaky_runs = 0
    flake_key = flake.put()

    with mock.patch('handlers.flake_issues.MIN_REQUIRED_FLAKY_RUNS', 2):
      response = self.test_app.post('/issues/process/%s' % flake_key.urlsafe())
      self.assertEqual(200, response.status_int)

    updated_flake = flake.key.get()
    self.assertEqual(updated_flake.issue_id, 100000)
    self.assertEqual(updated_flake.num_reported_flaky_runs, 3)
    self.assertEqual(updated_flake.issue_last_updated,
                     datetime.datetime(2015, 11, 10, 12, 13, 14))

  def test_does_not_create_too_many_issues(self):
    with mock.patch('handlers.flake_issues.MAX_UPDATED_ISSUES_PER_DAY', 5):
      with mock.patch('handlers.flake_issues.MIN_REQUIRED_FLAKY_RUNS', 2):
        for _ in range(10):
          key = self._create_flake().put()
          response = self.test_app.post('/issues/process/%s' % key.urlsafe())
          self.assertEqual(200, response.status_int)

    issue_ids = [flake.issue_id for flake in Flake.query() if flake.issue_id]
    self.assertEqual(len(issue_ids), 5)
    self.assertEqual(len(self.mock_api.issues), 5)

  def test_does_require_minimum_flaky_runs(self):
    with mock.patch('handlers.flake_issues.MIN_REQUIRED_FLAKY_RUNS', 3):
      flake = self._create_flake()
      key = flake.put()
      response = self.test_app.post('/issues/process/%s' % key.urlsafe())
      self.assertEqual(200, response.status_int)
    self.assertEqual(len(self.mock_api.issues), 0)

  def test_handles_issues_marked_as_duplicates_correctly(self):
    issue1 = self.mock_api.create(MockIssue({}))
    issue2 = self.mock_api.create(MockIssue({}))
    issue3 = self.mock_api.create(MockIssue({}))
    issue1.open = False
    issue1.status = 'Duplicate'
    issue1.merged_into = issue2.id
    issue2.open = False
    issue2.status = 'Duplicate'
    issue2.merged_into = issue3.id

    now = datetime.datetime.utcnow()
    flake = self._create_flake()
    flake.issue_id = issue1.id
    flake.issue_last_updated = now - datetime.timedelta(days=2)
    flake.num_reported_flaky_runs = 0
    flake_key = flake.put()

    with mock.patch('handlers.flake_issues.MIN_REQUIRED_FLAKY_RUNS', 2):
      response = self.test_app.post('/issues/process/%s' % flake_key.urlsafe())
      self.assertEqual(200, response.status_int)

    self.assertEqual(flake_key.get().issue_id, issue3.id)

  def test_detects_duplication_loop_and_recreates_issue(self):
    issue1 = self.mock_api.create(MockIssue({}))
    issue2 = self.mock_api.create(MockIssue({}))
    issue3 = self.mock_api.create(MockIssue({}))
    issue1.open = False
    issue1.status = 'Duplicate'
    issue1.merged_into = issue2.id
    issue2.open = False
    issue2.status = 'Duplicate'
    issue2.merged_into = issue3.id
    issue3.open = False
    issue3.status = 'Duplicate'
    issue3.merged_into = issue1.id

    now = datetime.datetime.utcnow()
    flake = self._create_flake()
    flake.issue_id = issue1.id
    flake.issue_last_updated = now - datetime.timedelta(days=2)
    flake.num_reported_flaky_runs = 0
    flake_key = flake.put()

    with mock.patch('handlers.flake_issues.MIN_REQUIRED_FLAKY_RUNS', 2):
      self.assertEqual(len(self.mock_api.issues), 3)
      response = self.test_app.post('/issues/process/%s' % flake_key.urlsafe())
      self.assertEqual(200, response.status_int)
      tasks = self.taskqueue_stub.get_filtered_tasks(
          queue_names='issue-updates')
      self.assertEqual(len(tasks), 1)
      response = self.test_app.post('/issues/process/%s' % flake_key.urlsafe())
      self.assertEqual(200, response.status_int)
      self.assertEqual(len(self.mock_api.issues), 4)

  @mock_datetime_utc(2015, 12, 4, 15, 0, 0)
  def test_correctly_computes_stale_deadline_based_on_created_time(self):
    issue = self.mock_api.create(MockIssue({}))
    issue.created = datetime.datetime(2015, 11, 1, 11, 0, 0)
    self.test_app.post('/issues/update-if-stale/%s' % issue.id)
    self.assertIn('Sheriff-Chromium', issue.labels)

    issue = self.mock_api.create(MockIssue({}))
    issue.created = datetime.datetime(2015, 11, 1, 11, 0, 0)
    issue.comments = [
        MockComment(datetime.datetime(2015, 12, 3, 11, 0, 0), 'app@ae.org'),
        MockComment(datetime.datetime(2015, 12, 4, 11, 0, 0), 'app@ae.org'),
    ]
    self.test_app.post('/issues/update-if-stale/%s' % issue.id)
    self.assertIn('Sheriff-Chromium', issue.labels)

    issue = self.mock_api.create(MockIssue({}))
    issue.created = datetime.datetime(2015, 11, 13, 11, 0, 0)
    self.test_app.post('/issues/update-if-stale/%s' % issue.id)
    self.assertNotIn('Sheriff-Chromium', issue.labels)

  @mock_datetime_utc(2015, 12, 4, 15, 0, 0)
  def test_correctly_computes_stale_deadline(self):
    # Creation date here is set to a later datetime than some comments for
    # testing purposes. This allows to make sure it's not used and instead an
    # earlier datetime from comment is used ot determine if an issue is stale.
    issue = self.mock_api.create(MockIssue({}))
    issue.created = datetime.datetime(2015, 12, 3, 11, 0, 0)
    issue.comments = [
        MockComment(datetime.datetime(2015, 11, 1, 11, 0, 0), 'test@a.org'),
        MockComment(datetime.datetime(2015, 12, 3, 11, 0, 0), 'app@ae.org'),
    ]
    self.test_app.post('/issues/update-if-stale/%s' % issue.id)
    self.assertIn('Sheriff-Chromium', issue.labels)

    issue = self.mock_api.create(MockIssue({}))
    issue.created = datetime.datetime(2015, 12, 1, 11, 0, 0)
    issue.comments = [
        MockComment(datetime.datetime(2015, 11, 1, 11, 0, 0), 'test@a.org'),
        MockComment(datetime.datetime(2015, 11, 13, 11, 0, 0), 'test@b.org'),
    ]
    self.test_app.post('/issues/update-if-stale/%s' % issue.id)
    self.assertNotIn('Sheriff-Chromium', issue.labels)

  @mock_datetime_utc(2015, 12, 1, 15, 0, 0)
  def test_does_not_count_weekends_towards_staleness(self):
    issue = self.mock_api.create(MockIssue({}))
    issue.created = datetime.datetime(2015, 11, 27, 11, 0, 0)
    self.test_app.post('/issues/update-if-stale/%s' % issue.id)
    self.assertNotIn('Sheriff-Chromium', issue.labels)

  @mock_datetime_utc(2015, 12, 4, 15, 0, 0)
  def test_posts_comment_when_moving_to_bug_queue(self):
    issue = self.mock_api.create(MockIssue({}))
    issue.created = datetime.datetime(2015, 11, 1, 11, 0, 0)
    self.test_app.post('/issues/update-if-stale/%s' % issue.id)
    self.assertIn('Sheriff-Chromium', issue.labels)
    self.assertEqual(len(issue.comments), 1)
    self.assertEqual(
        issue.comments[0].comment,
        'There has been no update on this issue for over 30 days, therefore it '
        'has been moved back into the Sheriff Bug Queue (unless already '
        'there). Sheriffs, please make sure that owner is aware of the issue '
        'and assign to another owner if necessary. If the flaky test/step has '
        'already been fixed, please close this issue.')

  @mock_datetime_utc(2015, 12, 4, 15, 0, 0)
  def test_ignores_closed_issues_when_checking_staleness(self):
    issue = self.mock_api.create(MockIssue({}))
    issue.created = datetime.datetime(2015, 12, 1, 11, 0, 0)
    issue.open = False
    self.test_app.post('/issues/update-if-stale/%s' % issue.id)
    self.assertNotIn('Sheriff-Chromium', issue.labels)

  @mock_datetime_utc(2015, 12, 8, 15, 0, 0)
  def test_cc_stale_flakes_reports_when_stale_for_7_days(self):
    issue = self.mock_api.create(MockIssue({}))
    issue.created = datetime.datetime(2015, 12, 1, 11, 0, 0)
    issue.labels = ['Sheriff-Chromium']
    self.test_app.post('/issues/update-if-stale/%s' % issue.id)
    self.assertIn('stale-flakes-reports@google.com', issue.cc)
    self.assertEqual(len(issue.comments), 1)
    self.assertEqual(
        issue.comments[0].comment,
        'Reporting to stale-flakes-reports@google.com to investigate why this '
        'issue is not being processed by Sheriffs.')

  @mock_datetime_utc(2015, 12, 8, 15, 0, 0)
  def test_removes_closed_issue_id_from_old_flakes(self):
    issue = self.mock_api.create(MockIssue({}))
    issue.updated = datetime.datetime(2015, 12, 3, 15, 0, 0)
    issue.open = False

    flake = self._create_flake()
    flake.issue_id = issue.id
    flake_key = flake.put()

    self.test_app.post('/issues/update-if-stale/%s' % issue.id)

    updated_flake = flake_key.get()
    self.assertEqual(updated_flake.issue_id, 0)
    self.assertEqual(updated_flake.old_issue_id, issue.id)

  @mock_datetime_utc(2015, 12, 8, 15, 0, 0)
  def test_does_not_remove_closed_issue_id_for_recently_updated_issues(self):
    issue = self.mock_api.create(MockIssue({}))
    issue.updated = datetime.datetime(2015, 12, 7, 15, 0, 0)
    issue.open = False

    flake = self._create_flake()
    flake.issue_id = issue.id
    flake_key = flake.put()

    self.test_app.post('/issues/update-if-stale/%s' % issue.id)

    updated_flake = flake_key.get()
    self.assertEqual(updated_flake.issue_id, issue.id)
    self.assertEqual(updated_flake.old_issue_id, 0)

  def test_correctly_finds_first_flake(self):
    fake_run = ndb.Key('BuildRun', 'fake')
    def flaky_run(dt):
      return FlakyRun(failure_run=fake_run, success_run=fake_run,
                      failure_run_time_finished=dt).put()

    fr1 = flaky_run(datetime.datetime(2015, 10, 12, 8, 0, 0))
    fr2 = flaky_run(datetime.datetime(2015, 10, 12, 12, 0, 0))
    fr3 = flaky_run(datetime.datetime(2015, 10, 18, 8, 0, 0))
    fr4 = flaky_run(datetime.datetime(2015, 10, 19, 8, 0, 0))
    fr5 = flaky_run(datetime.datetime(2015, 10, 19, 11, 0, 0))

    self.assertEqual(
        ProcessIssue._get_first_flake_occurrence_time(
          Flake(name='foo', occurrences=[fr1, fr2, fr3, fr4, fr5])),
        datetime.datetime(2015, 10, 18, 8, 0, 0))
    self.assertEqual(
        ProcessIssue._get_first_flake_occurrence_time(
          Flake(name='foo', occurrences=[fr1, fr2])),
        datetime.datetime(2015, 10, 12, 8, 0, 0))
    self.assertEqual(
        ProcessIssue._get_first_flake_occurrence_time(
          Flake(name='foo', occurrences=[fr5])),
        datetime.datetime(2015, 10, 19, 11, 0, 0))

class CreateFlakyRunTestCase(testing.AppengineTestCase):
  app_module = main.app

  # This is needed to be able to test handlers using cross-group transactions.
  datastore_stub_consistency_policy = (
      datastore_stub_util.PseudoRandomHRConsistencyPolicy(probability=1))

  def _create_build_runs(self, ts, tf):
    pbr = PatchsetBuilderRuns(
        issue=123456789, patchset=20001, master='test.master',
        builder='test-builder').put()
    br_f = BuildRun(parent=pbr, buildnumber=100, result=2, time_started=ts,
                    time_finished=tf).put()
    br_s = BuildRun(parent=pbr, buildnumber=101, result=0, time_started=ts,
                    time_finished=tf).put()
    return br_f, br_s

  def test_get_flaky_run_reason_ignores_invalid_json(self):
    now = datetime.datetime.utcnow()
    br_f, br_s = self._create_build_runs(now - datetime.timedelta(hours=1), now)

    urlfetch_mock = mock.Mock()
    urlfetch_mock.return_value.content = 'invalid-json'

    with mock.patch('google.appengine.api.urlfetch.fetch', urlfetch_mock):
      self.test_app.post('/issues/create_flaky_run',
                         {'failure_run_key': br_f.urlsafe(),
                          'success_run_key': br_s.urlsafe()})

  def test_handles_incorrect_parameters(self):
    self.test_app.post('/issues/create_flaky_run', {}, status=400)


  def test_logs_info_for_http_404_errors(self):
    urlfetch_mock = mock.Mock()
    urlfetch_mock.return_value.status_code = 404
    with mock.patch('google.appengine.api.urlfetch.fetch', urlfetch_mock):
      with mock.patch('logging.info') as info_mock:
        CreateFlakyRun.get_flakes(
            'master.test', 'builder-test', 123,
            {'name': 'step', 'text': 'step'})
        self.assertEqual(info_mock.call_count, 1)

  def test_logs_exception_for_other_http_errors(self):
    urlfetch_mock = mock.Mock()
    urlfetch_mock.return_value.status_code = 403
    with mock.patch('google.appengine.api.urlfetch.fetch', urlfetch_mock):
      with mock.patch('logging.exception') as exception_mock:
        CreateFlakyRun.get_flakes(
            'master.test', 'builder-test', 123,
            {'name': 'step', 'text': 'step'})
        self.assertEqual(exception_mock.call_count, 1)

  def test_get_flaky_run_reason(self):
    now = datetime.datetime.utcnow()
    br_f, br_s = self._create_build_runs(now - datetime.timedelta(hours=1), now)

    urlfetch_mock = mock.Mock(side_effect = [
        # JSON results for the build.
        mock.Mock(status_code=200, content=TEST_BUILDBOT_JSON_REPLY),
        # JSON results for step "foo1".
        mock.Mock(status_code=200, content=TEST_TEST_RESULTS_REPLY),
        # For step "foo8 xx (with patch)", something failed while parsing JSON,
        # step text ("bar13") should be reported as flake.
        Exception(),
    ])

    # We also create one Flake to test that it is correctly updated. Other Flake
    # entities will be created automatically.
    Flake(id='bar13', name='bar13', occurrences=[],
          last_time_seen=datetime.datetime.min).put()

    with mock.patch('google.appengine.api.urlfetch.fetch', urlfetch_mock):
      self.test_app.post('/issues/create_flaky_run',
                         {'failure_run_key': br_f.urlsafe(),
                          'success_run_key': br_s.urlsafe()})

    flaky_runs = FlakyRun.query().fetch(100)
    self.assertEqual(len(flaky_runs), 1)
    flaky_run = flaky_runs[0]
    self.assertEqual(flaky_run.failure_run, br_f)
    self.assertEqual(flaky_run.success_run, br_s)
    self.assertEqual(flaky_run.failure_run_time_finished, now)
    self.assertEqual(flaky_run.failure_run_time_started,
                     now - datetime.timedelta(hours=1))

    urlfetch_mock.assert_has_calls([
      # Verify that we've used correct URL to access buildbot JSON endpoint.
      mock.call(
        'http://build.chromium.org/p/test.master/json/builders/test-builder/'
        'builds/100'),
      # Verify that we've used correct URLs to retrieve test-results GTest JSON.
      mock.call(
        'http://test-results.appspot.com/testfile?builder=test-builder&'
        'name=full_results.json&master=test.master&testtype=foo1&'
        'buildnumber=100'),
      mock.call(
        'http://test-results.appspot.com/testfile?builder=test-builder&'
        'name=full_results.json&master=test.master&'
        'testtype=foo8%20%28with%20patch%29&buildnumber=100')])

    # Expected flakes to be found: list of (step_name, test_name).
    expected_flakes = [
        ('foo1', 'test2.a'),
        ('foo1', 'test2.d'),
        ('foo2', 'TEST RESULTS WERE INVALID'),
        ('foo8 xx (with patch)', 'bar13'),
    ]

    flake_occurrences = flaky_run.flakes
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
      self.assertEqual(flake.occurrences, [flaky_run.key])

  def test_flattens_tests_correctly(self):
    passed, failed, skipped = CreateFlakyRun._flatten_tests(
        json.loads(TEST_TEST_RESULTS_REPLY)['tests'], '/')
    self.assertEqual(set(passed), set(['test1']))
    self.assertEqual(set(failed), set(['test2/a', 'test2/d']))
    self.assertEqual(set(skipped), set(['test2/b']))
