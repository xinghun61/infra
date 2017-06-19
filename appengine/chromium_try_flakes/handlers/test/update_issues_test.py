# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
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
from common.test.mocks import MockIssue, MockIssueTrackerAPI
import main
from model.flake import Issue, FlakeType
import handlers.update_issues
from testing_utils import testing
from time_functions.testing import mock_datetime_utc


class UpdateIssuesTestCase(testing.AppengineTestCase):
  app_module = main.app

  # This is needed to be able to test handlers using cross-group transactions.
  datastore_stub_consistency_policy = (
      datastore_stub_util.PseudoRandomHRConsistencyPolicy(probability=1))

  def setUp(self):
    super(UpdateIssuesTestCase, self).setUp()
    self.mock_api = MockIssueTrackerAPI()
    mock.patch('common.monorail_interface.IssueTrackerAPI',
               lambda *args, **kwargs: self.mock_api).start()
    mock.patch('common.monorail_interface.MonorailIssue',
               MockIssue).start()

    self.flake_type_keys = [
        FlakeType(project='webrtc',
                  step_name='some_step',
                  test_name='some_test',
                  config='some_config',
                  last_updated=datetime.datetime.utcnow()).put(),
        FlakeType(project='webrtc',
                  step_name='some_step',
                  test_name='some_test',
                  last_updated=datetime.datetime.utcnow()).put(),
        FlakeType(project='webrtc',
                  step_name='compile',
                  last_updated=datetime.datetime.utcnow()).put(),
        FlakeType(project='webrtc',
                  step_name='some_other_step',
                  config='fake_config',
                  last_updated=datetime.datetime.utcnow()).put(),
    ]

  def tearDown(self):
    super(UpdateIssuesTestCase, self).tearDown()
    mock.patch.stopall()

  def test_duplicated_issue(self):
    monorail_issue1 = self.mock_api.create(MockIssue({}))
    monorail_issue2 = self.mock_api.create(MockIssue({}))

    monorail_issue1.open = False
    monorail_issue1.status = 'Duplicate'
    monorail_issue1.merged_into = monorail_issue2.id
    monorail_issue1.merged_into_project = monorail_issue2.project_id

    flakes = range(10)
    issue_key = Issue(issue_id=monorail_issue1.id,
                      project=monorail_issue1.project_id,
                      flake_type_keys=self.flake_type_keys).put()

    flakes_by_issue = handlers.update_issues.update_issue_ids({
        issue_key: flakes,
    })

    self.assertEqual(len(flakes_by_issue), 1)
    new_issue = flakes_by_issue.keys()[0].get()

    self.assertEqual(new_issue.issue_id, monorail_issue2.id)
    self.assertEqual(new_issue.project, monorail_issue2.project_id)
    self.assertEqual(new_issue.flake_type_keys, self.flake_type_keys)
    self.assertEqual(flakes_by_issue.values()[0], flakes)

  def test_duplicated_issue_closed_loop(self):
    monorail_issue1 = self.mock_api.create(MockIssue({}))
    monorail_issue2 = self.mock_api.create(MockIssue({}))

    monorail_issue1.open = False
    monorail_issue1.status = 'Duplicate'
    monorail_issue1.merged_into = monorail_issue2.id
    monorail_issue1.merged_into_project = monorail_issue2.project_id

    monorail_issue2.open = False
    monorail_issue2.status = 'Duplicate'
    monorail_issue2.merged_into = monorail_issue1.id
    monorail_issue2.merged_into_project = monorail_issue1.project_id

    flakes = range(10)
    issue_key = Issue(issue_id=monorail_issue1.id,
                      project=monorail_issue1.project_id,
                      flake_type_keys=self.flake_type_keys).put()

    flakes_by_issue = handlers.update_issues.update_issue_ids({
        issue_key: flakes,
    })

    self.assertEqual(len(flakes_by_issue), 1)
    new_issue = flakes_by_issue.keys()[0].get()

    self.assertIn(new_issue.issue_id, self.mock_api.issues)
    self.assertEqual(new_issue.flake_type_keys, self.flake_type_keys)
    self.assertEqual(flakes_by_issue.values()[0], flakes)
    self.assertIsNone(issue_key.get())

  def test_duplicated_issue_both_used(self):
    monorail_issue1 = self.mock_api.create(MockIssue({}))
    monorail_issue2 = self.mock_api.create(MockIssue({}))
    monorail_issue1.open = False
    monorail_issue1.status = 'Duplicate'
    monorail_issue1.merged_into = monorail_issue2.id
    monorail_issue1.merged_into_project = monorail_issue2.project_id

    new_flakes_1 = range(10)
    issue_key1 = Issue(issue_id=monorail_issue1.id,
                       project=monorail_issue1.project_id,
                       flake_type_keys=self.flake_type_keys[:2]).put()

    Issue(issue_id=monorail_issue2.id, project=monorail_issue2.project_id,
          flake_type_keys=self.flake_type_keys[1:]).put()

    flakes_by_issue = handlers.update_issues.update_issue_ids({
        issue_key1: new_flakes_1,
    })

    self.assertEqual(len(flakes_by_issue), 1)
    new_issue = flakes_by_issue.keys()[0].get()

    self.assertEqual(new_issue.issue_id, monorail_issue2.id)
    self.assertEqual(new_issue.project, monorail_issue2.project_id)
    self.assertListEqual(sorted(new_issue.flake_type_keys),
                         sorted(self.flake_type_keys))
    self.assertIsNone(issue_key1.get())

  def test_duplicated_issue_both_updated(self):
    monorail_issue1 = self.mock_api.create(MockIssue({}))
    monorail_issue2 = self.mock_api.create(MockIssue({}))
    monorail_issue1.open = False
    monorail_issue1.status = 'Duplicate'
    monorail_issue1.merged_into = monorail_issue2.id
    monorail_issue1.merged_into_project = monorail_issue2.project_id

    new_flakes_1 = range(10)
    issue_key1 = Issue(issue_id=monorail_issue1.id,
                       project=monorail_issue1.project_id,
                       flake_type_keys=self.flake_type_keys[:2]).put()

    new_flakes_2 = range(10, 20)
    issue_key2 = Issue(issue_id=monorail_issue2.id,
                       project=monorail_issue2.project_id,
                       flake_type_keys=self.flake_type_keys[1:]).put()

    flakes_by_issue = handlers.update_issues.update_issue_ids({
        issue_key1: new_flakes_1,
        # issue_key_2 is included so we can test that when we merge issue1 into
        # issue2, issue2 get's the new flakes updates from issue1 as well.
        issue_key2: new_flakes_2,
    })

    self.assertEqual(len(flakes_by_issue), 1)
    new_issue = flakes_by_issue.keys()[0].get()

    self.assertEqual(new_issue.issue_id, monorail_issue2.id)
    self.assertEqual(new_issue.project, monorail_issue2.project_id)
    self.assertListEqual(sorted(new_issue.flake_type_keys),
                         sorted(self.flake_type_keys))
    self.assertListEqual(sorted(flakes_by_issue.values()[0]),
                         sorted(new_flakes_1 + new_flakes_2))
    self.assertIsNone(issue_key1.get())

  def test_closed_issue_1h_ago(self):
    monorail_issue1 = self.mock_api.create(MockIssue({}))
    monorail_issue1.open = False
    monorail_issue1.closed = (
        datetime.datetime.utcnow() - datetime.timedelta(hours=1))

    flakes = range(10)
    issue_key = Issue(issue_id=monorail_issue1.id,
                      project=monorail_issue1.project_id,
                      flake_type_keys=self.flake_type_keys).put()

    flakes_by_issue = handlers.update_issues.update_issue_ids({
        issue_key: flakes,
    })

    self.assertEqual(len(flakes_by_issue), 0)
    self.assertIsNotNone(issue_key.get())

  def test_closed_issue_4d_ago(self):
    monorail_issue1 = self.mock_api.create(MockIssue({}))
    monorail_issue1.open = False
    monorail_issue1.closed = (
        datetime.datetime.utcnow() - datetime.timedelta(days=4))

    flakes = range(10)
    issue_key = Issue(issue_id=monorail_issue1.id,
                      project=monorail_issue1.project_id,
                      flake_type_keys=self.flake_type_keys).put()

    flakes_by_issue = handlers.update_issues.update_issue_ids({
        issue_key: flakes,
    })

    self.assertEqual(len(flakes_by_issue), 1)
    new_issue = flakes_by_issue.keys()[0].get()

    self.assertIsNotNone(new_issue)
    self.assertIn(new_issue.issue_id, self.mock_api.issues)
    self.assertEqual(new_issue.flake_type_keys, self.flake_type_keys)
    self.assertEqual(flakes_by_issue.values()[0], flakes)
    self.assertIsNone(issue_key.get())
