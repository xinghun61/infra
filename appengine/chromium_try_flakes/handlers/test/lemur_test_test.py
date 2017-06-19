# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import mock

from google.appengine.datastore import datastore_stub_util
from google.appengine.ext import ndb

import gae_ts_mon
from common import data_interface
from common.test.mocks import MockIssue, MockIssueTrackerAPI, MonorailDB
import main
import handlers.lemur_test
from model.flake import Issue, FlakeType
from testing_utils import testing


class FlakeIssuesTestCase(testing.AppengineTestCase):
  app_module = main.app

  # This is needed to be able to test handlers using cross-group transactions.
  datastore_stub_consistency_policy = (
      datastore_stub_util.PseudoRandomHRConsistencyPolicy(probability=1))

  def setUp(self):
    super(FlakeIssuesTestCase, self).setUp()
    gae_ts_mon.reset_for_unittest(disable=True)
    self.monorail_db = MonorailDB()

    mock.patch(
        'common.monorail_interface.IssueTrackerAPI',
        lambda *args: MockIssueTrackerAPI(self.monorail_db, *args)).start()
    mock.patch('common.monorail_interface.MonorailIssue',
               MockIssue).start()

  def tearDown(self):
    super(FlakeIssuesTestCase, self).tearDown()
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

  def test_creates_issue(self):
    # We only generate data for failure_utc_msec, since it's the only field we
    # care about. The rest of the fields (master_name, builder_name,
    # fail_build_id, etc) are not used to create or update the issues.
    fake_flakes_data = {
        ('webrtc', 'step_name1', 'test_name1', 'config'): [
            [str(failure_time)] for failure_time in range(10)
        ],
        ('webrtc', 'step_name1', None, None): [
            [str(failure_time)] for failure_time in range(15)
        ],
    }
    fake_bq_response = [
        self._desanitize_row(list(key) + [value])
        for key, value in fake_flakes_data.items()
    ]

    with mock.patch('common.data_interface._execute_query',
                    lambda *args, **kwargs: fake_bq_response):
      self.test_app.get('/lemur_test')

    issues = Issue.query().fetch()
    self.assertEqual(len(issues), 1)

    issue = issues[0]
    monorail_issue = self.monorail_db.getIssue(issue.issue_id, issue.project)

    self.assertEqual(issue.project, 'webrtc')
    self.assertIsNotNone(monorail_issue)
    self.assertEqual(
        monorail_issue.summary,
        'New flaky failures have been detected for 2 flake types.')
    self.assertEqual(
        monorail_issue.description.split('\n'),
        'New flaky failures have been detected for 2 flake types.\n\n'
        'This issue was created automatically by the chromium-try-flakes app. '
        'Please find the right owner to fix the respective test/step and assign'
        ' this issue to them.\n\n'
        'We have detected 25 recent flakes for the following flake types:\n\n'
        '15 new flaky failures for:\n'
        '  Step Name:      step_name1\n'
        '  Test Name:      None\n'
        '  Config:         None\n'
        'To see them point your browser to:\n'
        '  http://fake_url/recent_flakes?project=webrtc&step_name=step_name1'
        '&test_name=&config=&highlight=15&updated_before=0\n\n'
        '10 new flaky failures for:\n'
        '  Step Name:      step_name1\n'
        '  Test Name:      test_name1\n'
        '  Config:         config\n'
        'To see them point your browser to:\n'
        '  http://fake_url/recent_flakes?project=webrtc&step_name=step_name1'
        '&test_name=test_name1&config=config&highlight=10&updated_before=0\n\n'
        '\n'
        'The mapping of issues to flake types can be edited at [Generic URL '
        'where the user can look for the issue, since we dont know issue number'
        ' yet].\n\n'.split('\n'))
    self.assertEqual(len(monorail_issue.comments), 0)
    self.assertEqual(monorail_issue.status, 'Untriaged')
    self.assertEqual(monorail_issue.labels,
                     ['Type-Bug', 'Pri-1', 'Via-TryFlakes','Sheriff-WebRTC'])
    self.assertEqual(monorail_issue.components, ['Tests>Flaky'])

  def test_creates_issues_by_project(self):
    # We only generate data for failure_utc_msec, since it's the only field we
    # Acare about. The rest of the fields (master_name, builder_name,
    # fail_build_id, etc) are not used to create or update the issues.
    fake_flakes_data = {
        ('webrtc', 'step_name1', 'test_name1', 'config'): [
            [str(1000 * failure_time)] for failure_time in range(10)
        ],
        ('webrtc', 'step_name1', None, None): [
            [str(1000 * failure_time)] for failure_time in range(1, 16)
        ],
        ('chromium', 'step_name2', 'test_name2', None): [
            [str(1000 * failure_time)] for failure_time in range(2, 7)
        ],
        ('chromium', 'step_name1', None, None): [
            [str(1000 * failure_time)] for failure_time in range(3, 5)
        ],
        ('chromium', 'step_name3', 'test_name3', 'config2'): [
            [str(1000 * failure_time)] for failure_time in range(4, 9)
        ],
    }
    fake_bq_response = [
        self._desanitize_row(list(key) + [value])
        for key, value in fake_flakes_data.items()
    ]

    with mock.patch('common.data_interface._execute_query',
                    lambda *args, **kwargs: fake_bq_response):
      self.test_app.get('/lemur_test')

    issues = Issue.query().order(Issue.project).fetch()
    self.assertEqual(len(issues), 2)

    monorail_issue = self.monorail_db.getIssue(issues[0].issue_id,
                                               issues[0].project)
    self.assertEqual(issues[0].project, 'chromium')
    self.assertIsNotNone(monorail_issue)
    self.assertEqual(
        monorail_issue.summary,
        'New flaky failures have been detected for 3 flake types.')
    self.assertEqual(
        monorail_issue.description.split('\n'),
        'New flaky failures have been detected for 3 flake types.\n\n'
        'This issue was created automatically by the chromium-try-flakes app. '
        'Please find the right owner to fix the respective test/step and assign'
        ' this issue to them.\n\n'
        'We have detected 12 recent flakes for the following flake types:\n\n'
        '2 new flaky failures for:\n'
        '  Step Name:      step_name1\n'
        '  Test Name:      None\n'
        '  Config:         None\n'
        'To see them point your browser to:\n'
        '  http://fake_url/recent_flakes?project=chromium&step_name=step_name1'
        '&test_name=&config=&highlight=2&updated_before=4\n\n'
        '5 new flaky failures for:\n'
        '  Step Name:      step_name2\n'
        '  Test Name:      test_name2\n'
        '  Config:         None\n'
        'To see them point your browser to:\n'
        '  http://fake_url/recent_flakes?project=chromium&step_name=step_name2'
        '&test_name=test_name2&config=&highlight=5&updated_before=6\n\n'
        '5 new flaky failures for:\n'
        '  Step Name:      step_name3\n'
        '  Test Name:      test_name3\n'
        '  Config:         config2\n'
        'To see them point your browser to:\n'
        '  http://fake_url/recent_flakes?project=chromium&step_name=step_name3'
        '&test_name=test_name3&config=config2&highlight=5'
        '&updated_before=8\n\n'
        '\n'
        'The mapping of issues to flake types can be edited at [Generic URL '
        'where the user can look for the issue, since we dont know issue number'
        ' yet].\n\n'.split('\n'))
    self.assertEqual(len(monorail_issue.comments), 0)
    self.assertEqual(monorail_issue.status, 'Untriaged')
    self.assertEqual(monorail_issue.labels,
                     ['Type-Bug', 'Pri-1', 'Via-TryFlakes','Sheriff-Chromium'])
    self.assertEqual(monorail_issue.components, ['Tests>Flaky'])

    monorail_issue = self.monorail_db.getIssue(issues[1].issue_id,
                                               issues[1].project)
    self.assertEqual(issues[1].project, 'webrtc')
    self.assertIsNotNone(monorail_issue)
    self.assertEqual(
        monorail_issue.summary,
        'New flaky failures have been detected for 2 flake types.')
    self.assertEqual(
        monorail_issue.description.split('\n'),
        'New flaky failures have been detected for 2 flake types.\n\n'
        'This issue was created automatically by the chromium-try-flakes app. '
        'Please find the right owner to fix the respective test/step and assign'
        ' this issue to them.\n\n'
        'We have detected 25 recent flakes for the following flake types:\n\n'
        '15 new flaky failures for:\n'
        '  Step Name:      step_name1\n'
        '  Test Name:      None\n'
        '  Config:         None\n'
        'To see them point your browser to:\n'
        '  http://fake_url/recent_flakes?project=webrtc&step_name=step_name1'
        '&test_name=&config=&highlight=15&updated_before=15\n\n'
        '10 new flaky failures for:\n'
        '  Step Name:      step_name1\n'
        '  Test Name:      test_name1\n'
        '  Config:         config\n'
        'To see them point your browser to:\n'
        '  http://fake_url/recent_flakes?project=webrtc&step_name=step_name1'
        '&test_name=test_name1&config=config&highlight=10&updated_before=9\n\n'
        '\n'
        'The mapping of issues to flake types can be edited at [Generic URL '
        'where the user can look for the issue, since we dont know issue number'
        ' yet].\n\n'.split('\n'))
    self.assertEqual(len(monorail_issue.comments), 0)
    self.assertEqual(monorail_issue.status, 'Untriaged')
    self.assertEqual(monorail_issue.labels,
                     ['Type-Bug', 'Pri-1', 'Via-TryFlakes','Sheriff-WebRTC'])
    self.assertEqual(monorail_issue.components, ['Tests>Flaky'])

  def test_updates_issues(self):
    # We only generate data for failure_utc_msec, since it's the only field we
    # Acare about. The rest of the fields (master_name, builder_name,
    # fail_build_id, etc) are not used to create or update the issues.
    fake_flakes_data = {
        ('webrtc', 'step_name1', 'test_name1', 'config'): [
            [str(1000 * failure_time)] for failure_time in range(10)
        ],
        ('webrtc', 'step_name1', None, None): [
            [str(1000 * failure_time)] for failure_time in range(1, 16)
        ],
    }

    flake_type_keys = [
        FlakeType(project='webrtc',
                  step_name='step_name1',
                  test_name='test_name1',
                  config='config',
                  last_updated=datetime.datetime.min).put(),
        FlakeType(project='webrtc',
                  step_name='step_name1',
                  last_updated=datetime.datetime.min).put(),
    ]
    monorail_issue = self.monorail_db.create(MockIssue({}), 'webrtc')
    Issue(project=monorail_issue.project_id, issue_id=monorail_issue.id,
          flake_type_keys=flake_type_keys).put()

    fake_bq_response = [
        self._desanitize_row(list(key) + [value])
        for key, value in fake_flakes_data.items()
    ]

    with mock.patch('common.data_interface._execute_query',
                    lambda *args, **kwargs: fake_bq_response):
      self.test_app.get('/lemur_test')

    self.assertEqual(len(monorail_issue.comments), 1)
    self.assertEqual(
        monorail_issue.comments[0].split('\n'),
        'We have detected 25 recent flakes for the following flake types:\n\n'
        '15 new flaky failures for:\n'
        '  Step Name:      step_name1\n'
        '  Test Name:      None\n'
        '  Config:         None\n'
        'To see them point your browser to:\n'
        '  http://fake_url/recent_flakes?project=webrtc&step_name=step_name1'
        '&test_name=&config=&highlight=15&updated_before=15\n\n'
        '10 new flaky failures for:\n'
        '  Step Name:      step_name1\n'
        '  Test Name:      test_name1\n'
        '  Config:         config\n'
        'To see them point your browser to:\n'
        '  http://fake_url/recent_flakes?project=webrtc&step_name=step_name1'
        '&test_name=test_name1&config=config&highlight=10&updated_before=9\n'
        '\n'.split('\n'))

  def test_no_new_updates_issues(self):
    # We only generate data for failure_utc_msec, since it's the only field we
    # Acare about. The rest of the fields (master_name, builder_name,
    # fail_build_id, etc) are not used to create or update the issues.
    fake_flakes_data = {
        ('webrtc', 'step_name1', 'test_name1', 'config'): [
            [str(1000 * failure_time)] for failure_time in range(10)
        ],
        ('webrtc', 'step_name1', None, None): [
            [str(1000 * failure_time)] for failure_time in range(1, 16)
        ],
    }

    flake_type_keys = [
        FlakeType(project='webrtc',
                  step_name='step_name1',
                  test_name='test_name1',
                  config='config',
                  last_updated=datetime.datetime.max).put(),
        FlakeType(project='webrtc',
                  step_name='step_name1',
                  last_updated=datetime.datetime.max).put(),
    ]
    monorail_issue = self.monorail_db.create(MockIssue({}), 'webrtc')
    Issue(project=monorail_issue.project_id, issue_id=monorail_issue.id,
          flake_type_keys=flake_type_keys).put()

    fake_bq_response = [
        self._desanitize_row(list(key) + [value])
        for key, value in fake_flakes_data.items()
    ]

    with mock.patch('common.data_interface._execute_query',
                    lambda *args, **kwargs: fake_bq_response):
      self.test_app.get('/lemur_test')

    self.assertEqual(len(monorail_issue.comments), 0)
