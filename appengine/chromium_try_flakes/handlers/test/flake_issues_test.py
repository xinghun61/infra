# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import mock

from google.appengine.datastore import datastore_stub_util
from google.appengine.ext import ndb

from handlers.flake_issues import ProcessIssue
import main
from model.flake import Flake, FlakyRun
from model.build_run import PatchsetBuilderRuns, BuildRun
from testing_utils import testing
from time_functions.testing import mock_datetime_utc


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
        'agx0ZXN0YmVkLXRlc3RyGQsSBUZsYWtlIg50ZXN0LWZsYWtlLWtleQw.')
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
        'message was posted automatically by the chromium-try-flakes app.'
    )

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
    issue.created = datetime.datetime(2015, 12, 1, 11, 0, 0)
    self.test_app.post('/issues/update-if-stale/%s' % issue.id)
    self.assertIn('Sheriff-Chromium', issue.labels)

    issue = self.mock_api.create(MockIssue({}))
    issue.created = datetime.datetime(2015, 12, 1, 11, 0, 0)
    issue.comments = [
        MockComment(datetime.datetime(2015, 12, 3, 11, 0, 0), 'app@ae.org'),
        MockComment(datetime.datetime(2015, 12, 4, 11, 0, 0), 'app@ae.org'),
    ]
    self.test_app.post('/issues/update-if-stale/%s' % issue.id)
    self.assertIn('Sheriff-Chromium', issue.labels)

    issue = self.mock_api.create(MockIssue({}))
    issue.created = datetime.datetime(2015, 12, 3, 11, 0, 0)
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
        MockComment(datetime.datetime(2015, 12, 1, 11, 0, 0), 'test@a.org'),
        MockComment(datetime.datetime(2015, 12, 3, 11, 0, 0), 'app@ae.org'),
    ]
    self.test_app.post('/issues/update-if-stale/%s' % issue.id)
    self.assertIn('Sheriff-Chromium', issue.labels)

    issue = self.mock_api.create(MockIssue({}))
    issue.created = datetime.datetime(2015, 12, 1, 11, 0, 0)
    issue.comments = [
        MockComment(datetime.datetime(2015, 12, 1, 11, 0, 0), 'test@a.org'),
        MockComment(datetime.datetime(2015, 12, 3, 11, 0, 0), 'test@b.org'),
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
    issue.created = datetime.datetime(2015, 12, 1, 11, 0, 0)
    self.test_app.post('/issues/update-if-stale/%s' % issue.id)
    self.assertIn('Sheriff-Chromium', issue.labels)
    self.assertEqual(len(issue.comments), 1)
    self.assertEqual(
        issue.comments[0].comment,
        'There has been no update on this issue for over 3 days, therefore it '
        'has been moved back into the Sheriff queue (unless it was already '
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
