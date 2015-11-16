# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import mock

from google.appengine.datastore import datastore_stub_util
from google.appengine.ext import ndb

import main
from model.flake import Flake, FlakyRun
from model.build_run import PatchsetBuilderRuns, BuildRun
from testing_utils import testing


class MockIssue(object):
  def __init__(self, issue_entry):
    self.summary = issue_entry.get('summary')
    self.description = issue_entry.get('description')
    self.status = issue_entry.get('status')
    self.labels = issue_entry.get('labels')
    self.open = True
    self.updated = datetime.datetime.utcnow()
    self.comments = []
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

  def update(self, issue, comment):
    self.issues[issue.id] = issue
    issue.comments.append(comment)


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
    ]
    for patcher in self.patchers:
      patcher.start()

  def tearDown(self):
    super(FlakeIssuesTestCase, self).tearDown()
    for patcher in self.patchers:
      patcher.stop()

  def _create_flake(self):
    tf = datetime.datetime.utcnow()
    p = PatchsetBuilderRuns(issue=123456, patchset=1, master='tryserver.test',
                            builder='test-builder').put()
    br_f1 = BuildRun(parent=p, buildnumber=1, result=2, time_finished=tf).put()
    br_s1 = BuildRun(parent=p, buildnumber=2, result=0, time_finished=tf).put()
    br_f2 = BuildRun(parent=p, buildnumber=3, result=4, time_finished=tf).put()
    br_s2 = BuildRun(parent=p, buildnumber=4, result=0, time_finished=tf).put()
    occ_key1 = FlakyRun(failure_run=br_f1, success_run=br_s1,
                        failure_run_time_finished=tf).put()
    occ_key2 = FlakyRun(failure_run=br_f2, success_run=br_s2,
                        failure_run_time_finished=tf).put()
    return Flake(name='foo.bar', count_day=10, occurrences=[occ_key1, occ_key2])


  def test_creates_issue_for_new_flake(self):
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
        'issue status to Untriaged.\n\n'
        'List of all flakes for this test/step can be found at '
        'https://chromium-try-flakes.appspot.com/all_flake_occurrences?key='
        'agx0ZXN0YmVkLXRlc3RyGQsSBUZsYWtlIg50ZXN0LWZsYWtlLWtleQw.')
    self.assertEqual(issue.status, 'Untriaged')
    self.assertEqual(issue.labels, ['Type-Bug', 'Pri-1', 'Cr-Tests-Flaky',
                                    'Via-TryFlakes', 'Sheriff-Chromium'])
    self.assertEqual(len(issue.comments), 0)

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

    response = self.test_app.post('/issues/process/%s' % flake_key.urlsafe())
    self.assertEqual(200, response.status_int)
    tasks = self.taskqueue_stub.get_filtered_tasks(queue_names='issue-updates')
    self.assertEqual(len(tasks), 0)

    flake.num_reported_flaky_runs = 0
    issue.updated = now - datetime.timedelta(days=4)
    flake_key = flake.put()
    response = self.test_app.post('/issues/process/%s' % flake_key.urlsafe())
    self.assertEqual(200, response.status_int)
    tasks = self.taskqueue_stub.get_filtered_tasks(queue_names='issue-updates')
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
        issue.comments[0],
        'Detected new flakes for test/step "foo.bar":\n\n'
        '  Failure: http://build.chromium.org/p/tryserver.test/builders/'
                   'test-builder/builds/1.\n'
        '  Success: http://build.chromium.org/p/tryserver.test/builders/'
                   'test-builder/builds/2.\n\n'
        '  Failure: http://build.chromium.org/p/tryserver.test/builders/'
                   'test-builder/builds/3.\n'
        '  Success: http://build.chromium.org/p/tryserver.test/builders/'
                   'test-builder/builds/4.\n\n'
        'This message was automatically generated by the chromium-try-flakes '
        'app.'
    )

  def test_updates_issue_only_if_there_are_new_flakes(self):
    issue = self.mock_api.create(MockIssue({}))

    now = datetime.datetime.utcnow()
    flake = self._create_flake()
    flake.issue_id = issue.id
    flake.issue_last_updated = now - datetime.timedelta(days=2)
    flake.num_reported_flaky_runs = 2
    flake_key = flake.put()

    self.assertEqual(len(issue.comments), 0)
    response = self.test_app.post('/issues/process/%s' % flake_key.urlsafe())
    self.assertEqual(200, response.status_int)
    self.assertEqual(len(issue.comments), 0)

    flake.num_reported_flaky_runs = 0
    flake_key = flake.put()
    response = self.test_app.post('/issues/process/%s' % flake_key.urlsafe())
    self.assertEqual(200, response.status_int)
    self.assertEqual(len(issue.comments), 1)

  def test_does_not_create_too_many_issues(self):
    with mock.patch('handlers.flake_issues.MAX_UPDATED_ISSUES_PER_DAY', 5):
      for _ in range(10):
        key = self._create_flake().put()
        response = self.test_app.post('/issues/process/%s' % key.urlsafe())
        self.assertEqual(200, response.status_int)

    issue_ids = [flake.issue_id for flake in Flake.query() if flake.issue_id]
    self.assertEqual(len(issue_ids), 5)
    self.assertEqual(len(self.mock_api.issues), 5)

  def test_does_not_post_too_many_flaky_runs_in_an_update(self):
    issue = self.mock_api.create(MockIssue({}))
    with mock.patch('handlers.flake_issues.MAX_FLAKY_RUNS_PER_UPDATE', 1):
      flake = self._create_flake()
      flake.issue_id = issue.id
      key = flake.put()
      response = self.test_app.post('/issues/process/%s' % key.urlsafe())
      self.assertEqual(200, response.status_int)

    self.assertEqual(len(self.mock_api.issues), 1)
    self.assertIn(100000, self.mock_api.issues)
    self.assertEqual(len(self.mock_api.issues[100000].comments), 1)
    self.assertEqual(
        self.mock_api.issues[100000].comments[0],
        'Detected new flakes for test/step "foo.bar":\n\n'
        '  Failure: http://build.chromium.org/p/tryserver.test/builders/'
                   'test-builder/builds/3.\n'
        '  Success: http://build.chromium.org/p/tryserver.test/builders/'
                   'test-builder/builds/4.\n\n'
        'This message was automatically generated by the chromium-try-flakes '
        'app.')

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

    self.assertEqual(len(self.mock_api.issues), 3)
    response = self.test_app.post('/issues/process/%s' % flake_key.urlsafe())
    self.assertEqual(200, response.status_int)
    tasks = self.taskqueue_stub.get_filtered_tasks(queue_names='issue-updates')
    self.assertEqual(len(tasks), 1)
    response = self.test_app.post('/issues/process/%s' % flake_key.urlsafe())
    self.assertEqual(200, response.status_int)
    self.assertEqual(len(self.mock_api.issues), 4)
