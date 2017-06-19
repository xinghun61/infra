# Copyright 2015 The Chromium Authors. All rights reserved.
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
from common import monorail_interface
from common.test.mocks import MockIssue, MockIssueTrackerAPI
import main
from model.flake import FlakeType
from handlers.lemur_test import FlakeInfo
from testing_utils import testing
from time_functions.testing import mock_datetime_utc


class MonorailInterfaceTestCase(testing.AppengineTestCase):
  app_module = main.app

  # This is needed to be able to test handlers using cross-group transactions.
  datastore_stub_consistency_policy = (
      datastore_stub_util.PseudoRandomHRConsistencyPolicy(probability=1))

  # Needed to read queues from queue.yaml in the root of the app.
  taskqueue_stub_root_path = '.'

  def setUp(self):
    super(MonorailInterfaceTestCase, self).setUp()
    gae_ts_mon.reset_for_unittest(disable=True)
    self.mock_api = MockIssueTrackerAPI()
    mock.patch('common.monorail_interface.IssueTrackerAPI',
               lambda *args, **kwargs: self.mock_api).start()
    mock.patch('common.monorail_interface.MonorailIssue',
               MockIssue).start()

    now = datetime.datetime(2015, 10, 10, 1, 1, 1)
    self.fake_flake_types = [
        FlakeType(project='webrtc',
                  step_name='some_step',
                  test_name='some_test',
                  config='some_config',
                  last_updated=now),
        FlakeType(project='webrtc',
                  step_name='some_step',
                  test_name='some_test',
                  last_updated=now),
        FlakeType(project='webrtc',
                  step_name='compile',
                  last_updated=now),
        FlakeType(project='webrtc',
                  step_name='some_other_step',
                  config='fake_config',
                  last_updated=now),
    ]
    self.fake_flake_infos = [
        FlakeInfo(flake_type=flake_type, flakes_count=i+1)
        for i, flake_type in enumerate(self.fake_flake_types)
    ]

  def tearDown(self):
    super(MonorailInterfaceTestCase, self).tearDown()
    mock.patch.stopall()

  def test_follow_duplication_chain(self):
    issue1 = self.mock_api.create(MockIssue({}))
    issue2 = self.mock_api.create(MockIssue({}))
    issue3 = self.mock_api.create(MockIssue({}))
    issue1.open = False
    issue1.status = 'Duplicate'
    issue1.merged_into = issue2.id
    issue1.merged_into_project = issue2.project_id
    issue2.open = False
    issue2.status = 'Duplicate'
    issue2.merged_into = issue3.id
    issue2.merged_into_project = issue3.project_id

    issue = monorail_interface.follow_duplication_chain(issue1.project_id,
                                                        issue1.id)
    self.assertEqual(issue.id, issue3.id)

  def test_follow_duplication_chain_loop(self):
    issue1 = self.mock_api.create(MockIssue({}))
    issue2 = self.mock_api.create(MockIssue({}))
    issue3 = self.mock_api.create(MockIssue({}))
    issue1.open = False
    issue1.status = 'Duplicate'
    issue1.merged_into = issue2.id
    issue1.merged_into_project = issue2.project_id
    issue2.open = False
    issue2.status = 'Duplicate'
    issue2.merged_into = issue3.id
    issue2.merged_into_project = issue3.project_id
    issue3.open = False
    issue3.status = 'Duplicate'
    issue3.merged_into = issue1.id
    issue3.merged_into_project = issue1.project_id

    issue = monorail_interface.follow_duplication_chain(issue1.project_id,
                                                        issue1.id)
    self.assertEqual(None, issue)

  def test_recreate_issue(self):
    monorail_interface.recreate_issue('chromium', 12345, self.fake_flake_types)
    self.assertEqual(len(self.mock_api.issues), 1)
    self.assertIn(100000, self.mock_api.issues)
    issue = self.mock_api.issues[100000]
    self.assertEqual(
        issue.summary,
        'New flaky failures have been detected for 4 flake types.')
    self.assertEqual(
        issue.description,
        'New flaky failures have been detected for 4 flake types.\n\n'
        'This issue was created automatically by the chromium-try-flakes app. '
        'Please find the right owner to fix the respective test/step and assign'
        ' this issue to them.\n\n'
        '  Step Name:      some_step\n'
        '  Test Name:      some_test\n'
        '  Config:         some_config\n\n'
        '  Step Name:      some_step\n'
        '  Test Name:      some_test\n'
        '  Config:         None\n\n'
        '  Step Name:      compile\n'
        '  Test Name:      None\n'
        '  Config:         None\n\n'
        '  Step Name:      some_other_step\n'
        '  Test Name:      None\n'
        '  Config:         fake_config\n\n'
        'The mapping of issues to flake types can be edited at [Generic URL '
        'where the user can look for the issue, since we dont know issue number'
        ' yet].\n\n'
        'This issue was re-created after issue 12345 was closed.\n\n')
    self.assertEqual(issue.status, 'Untriaged')
    self.assertEqual(issue.labels, ['Type-Bug', 'Pri-1', 'Via-TryFlakes',
                                    'Sheriff-Chromium'])
    self.assertEqual(issue.components, ['Tests>Flaky'])
    self.assertEqual(len(issue.comments), 0)

  def test_post_notice(self):
    issue = self.mock_api.create(MockIssue({}))
    monorail_interface.post_notice(issue.project_id, issue.id,
                                   self.fake_flake_types)
    self.assertEqual(len(issue.comments), 1)
    self.assertEqual(
        issue.comments[0],
        'This issue is now used by Chromium Try Flakes to track the following '
        'flake types:\n\n'
        '  Step Name:      some_step\n'
        '  Test Name:      some_test\n'
        '  Config:         some_config\n\n'
        '  Step Name:      some_step\n'
        '  Test Name:      some_test\n'
        '  Config:         None\n\n'
        '  Step Name:      compile\n'
        '  Test Name:      None\n'
        '  Config:         None\n\n'
        '  Step Name:      some_other_step\n'
        '  Test Name:      None\n'
        '  Config:         fake_config\n\n'
        'The mapping of issues to flake types can be edited at [Generic URL '
        'where the user can look for the issue, since we dont know issue number'
        ' yet].\n\n'
    )

  def test_create_issue(self):
    monorail_interface.create_issue('chromium', self.fake_flake_infos)
    self.assertEqual(len(self.mock_api.issues), 1)
    self.assertIn(100000, self.mock_api.issues)
    issue = self.mock_api.issues[100000]
    self.assertEqual(
        issue.summary,
        'New flaky failures have been detected for 4 flake types.')
    self.assertEqual(
        issue.description,
        'New flaky failures have been detected for 4 flake types.\n\n'
        'This issue was created automatically by the chromium-try-flakes app. '
        'Please find the right owner to fix the respective test/step and assign'
        ' this issue to them.\n\n'
        'We have detected 10 recent flakes for the following flake types:\n\n'
        '1 new flaky failures for:\n'
        '  Step Name:      some_step\n'
        '  Test Name:      some_test\n'
        '  Config:         some_config\n'
        'To see them point your browser to:\n'
        '  http://fake_url/recent_flakes?project=webrtc&step_name=some_step'
        '&test_name=some_test&config=some_config&highlight=1'
        '&updated_before=1444438861\n\n'
        '2 new flaky failures for:\n'
        '  Step Name:      some_step\n'
        '  Test Name:      some_test\n'
        '  Config:         None\n'
        'To see them point your browser to:\n'
        '  http://fake_url/recent_flakes?project=webrtc&step_name=some_step&'
        'test_name=some_test&config=&highlight=2&updated_before=1444438861\n\n'
        '3 new flaky failures for:\n'
        '  Step Name:      compile\n'
        '  Test Name:      None\n'
        '  Config:         None\n'
        'To see them point your browser to:\n'
        '  http://fake_url/recent_flakes?project=webrtc&step_name=compile'
        '&test_name=&config=&highlight=3&updated_before=1444438861\n\n'
        '4 new flaky failures for:\n'
        '  Step Name:      some_other_step\n'
        '  Test Name:      None\n'
        '  Config:         fake_config\n'
        'To see them point your browser to:\n'
        '  http://fake_url/recent_flakes?project=webrtc'
        '&step_name=some_other_step&test_name=&config=fake_config&highlight=4'
        '&updated_before=1444438861\n\n\n'
        'The mapping of issues to flake types can be edited at [Generic URL '
        'where the user can look for the issue, since we dont know issue '
        'number yet].\n\n')
    self.assertEqual(issue.status, 'Untriaged')
    self.assertEqual(issue.labels, ['Type-Bug', 'Pri-1', 'Via-TryFlakes',
                                    'Sheriff-Chromium'])
    self.assertEqual(issue.components, ['Tests>Flaky'])
    self.assertEqual(len(issue.comments), 0)

  def test_update_issue(self):
    issue = self.mock_api.create(MockIssue({}))
    monorail_interface.update_issue(issue.project_id, issue.id,
                                    self.fake_flake_infos)
    self.assertEqual(len(issue.comments), 1)
    self.assertEqual(
        issue.comments[0],
        'We have detected 10 recent flakes for the following flake types:\n\n'
        '1 new flaky failures for:\n'
        '  Step Name:      some_step\n'
        '  Test Name:      some_test\n'
        '  Config:         some_config\n'
        'To see them point your browser to:\n'
        '  http://fake_url/recent_flakes?project=webrtc&step_name=some_step'
        '&test_name=some_test&config=some_config&highlight=1'
        '&updated_before=1444438861\n\n'
        '2 new flaky failures for:\n'
        '  Step Name:      some_step\n'
        '  Test Name:      some_test\n'
        '  Config:         None\n'
        'To see them point your browser to:\n'
        '  http://fake_url/recent_flakes?project=webrtc&step_name=some_step&'
        'test_name=some_test&config=&highlight=2&updated_before=1444438861\n\n'
        '3 new flaky failures for:\n'
        '  Step Name:      compile\n'
        '  Test Name:      None\n'
        '  Config:         None\n'
        'To see them point your browser to:\n'
        '  http://fake_url/recent_flakes?project=webrtc&step_name=compile'
        '&test_name=&config=&highlight=3&updated_before=1444438861\n\n'
        '4 new flaky failures for:\n'
        '  Step Name:      some_other_step\n'
        '  Test Name:      None\n'
        '  Config:         fake_config\n'
        'To see them point your browser to:\n'
        '  http://fake_url/recent_flakes?project=webrtc'
        '&step_name=some_other_step&test_name=&config=fake_config&highlight=4'
        '&updated_before=1444438861\n\n')
