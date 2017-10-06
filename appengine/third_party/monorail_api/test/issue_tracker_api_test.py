# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import mock
import unittest

import monorail_api


class IssueTrackerAPITestCase(unittest.TestCase):

  def setUp(self):
    super(IssueTrackerAPITestCase, self).setUp()
    self.maxDiff = None
    self.client = mock.Mock()
    self.build_client = mock.Mock(return_value=self.client)
    self.patchers = [
        mock.patch('endpoints_client.endpoints.build_client',
                   self.build_client),
        mock.patch('endpoints_client.endpoints.retry_request',
                   lambda request: request.execute()),
    ]
    for patcher in self.patchers:
      patcher.start()

  def tearDown(self):
    super(IssueTrackerAPITestCase, self).tearDown()
    for patcher in self.patchers:
      patcher.stop()

  def test_construct_issue_and_then_create_it_on_tracker(self):
    api = monorail_api.IssueTrackerAPI('my-project')
    insert_method = self.client.issues.return_value.insert
    insert_method.return_value.execute.return_value = {'id': '123'}
    issue = api.create(
        monorail_api.Issue({
            'summary':
                'TestSummary',
            'description':
                'TestDescription',
            'status':
                'Assigned',
            'owner': {
                'name': 'test@example.com'
            },
            'labels': ['My-Label-1', 'My-Label-2'],
            'components': ['Component-1', 'Component-2'],
            'cc': [{
                'name': 'test2@example.com'
            }, {
                'name': 'test3@example.com'
            }],
        }))
    self.assertEquals(issue.id, '123')
    self.assertEquals(insert_method.call_count, 1)
    self.assertEquals(insert_method.call_args[1]['projectId'], 'my-project')
    self.assertEquals(insert_method.call_args[1]['sendEmail'], True)
    self.assertDictEqual(insert_method.call_args[1]['body'], {
        'summary': 'TestSummary',
        'description': 'TestDescription',
        'status': 'Assigned',
        'owner': {
            'name': 'test@example.com'
        },
        'labels': ['My-Label-1', 'My-Label-2'],
        'components': ['Component-1', 'Component-2'],
        'cc': [{
            'name': 'test2@example.com'
        }, {
            'name': 'test3@example.com'
        }],
    })

  def test_create_issue_clears_dirty_flag_and_does_not_send_email(self):
    api = monorail_api.IssueTrackerAPI('my-project')
    issue = monorail_api.Issue({'summary': 'TestSummary'})
    issue.dirty = True
    insert_method = self.client.issues.return_value.insert
    insert_method.return_value.execute.return_value = {'id': '123'}
    api.create(issue, send_email=False)
    self.assertFalse(issue.dirty)
    self.assertEquals(insert_method.call_count, 1)
    self.assertEquals(insert_method.call_args[1]['sendEmail'], False)
    self.assertDictEqual(insert_method.call_args[1]['body'],
                         {'summary': 'TestSummary'})

  def test_does_not_update_issue_if_no_changes_or_comment(self):
    api = monorail_api.IssueTrackerAPI('my-project')
    issue = monorail_api.Issue({'summary': 'TestSummary'})
    api.update(issue)
    self.assertEquals(self.client.issues.call_count, 0)

  def test_updates_issue(self):
    api = monorail_api.IssueTrackerAPI('my-project')
    issue = monorail_api.Issue({
        'id': '123',
        'summary': 'TestSummary',
        'labels': ['Label-Y']
    })
    issue.summary = 'NewSummary'
    issue.status = 'Assigned'
    issue.owner = '----'
    issue.blocked_on.append('12345')
    issue.labels.append('Label-X')
    issue.labels.remove('Label-Y')
    issue.components.append('Test>Flaky')
    issue.cc.append('test2@example.com')
    insert_method = self.client.issues.return_value.comments.return_value.insert
    insert_method.return_value.execute.return_value = {'id': '345'}
    self.assertTrue(issue.dirty)
    self.assertEqual(issue, api.update(issue))
    self.assertFalse(issue.dirty)
    self.assertEquals(insert_method.call_count, 1)
    self.assertEquals(insert_method.call_args[1]['projectId'], 'my-project')
    self.assertEquals(insert_method.call_args[1]['issueId'], '123')
    self.assertEquals(insert_method.call_args[1]['sendEmail'], True)
    self.assertDictEqual(insert_method.call_args[1]['body'], {
        'id': '123',
        'updates': {
            'blockedOn': ['12345'],
            'cc': ['test2@example.com'],
            'labels': ['Label-X', '-Label-Y'],
            'components': ['Test>Flaky'],
            'owner': '----',
            'status': 'Assigned',
            'summary': 'NewSummary'
        }
    })

  def test_updates_issue_with_comment(self):
    api = monorail_api.IssueTrackerAPI('my-project')
    issue = monorail_api.Issue({'id': '123'})
    insert_method = self.client.issues.return_value.comments.return_value.insert
    insert_method.return_value.execute.return_value = {'id': '345'}
    api.update(issue, comment='TestComment', send_email=False)
    self.assertEquals(insert_method.call_count, 1)
    self.assertEquals(insert_method.call_args[1]['sendEmail'], False)
    self.assertDictEqual(insert_method.call_args[1]['body'], {
        'id': '123',
        'content': 'TestComment',
        'updates': {},
    })

  def test_post_comment(self):
    api = monorail_api.IssueTrackerAPI('my-project')
    issue_id = '123'
    insert_method = self.client.issues.return_value.comments.return_value.insert
    insert_method.return_value.execute.return_value = {'id': '345'}
    api.postComment(issue_id, comment='TestComment', send_email=False)
    self.assertEquals(insert_method.call_count, 1)
    self.assertEquals(insert_method.call_args[1]['projectId'], 'my-project')
    self.assertEquals(insert_method.call_args[1]['issueId'], issue_id)
    self.assertEquals(insert_method.call_args[1]['sendEmail'], False)
    self.assertDictEqual(insert_method.call_args[1]['body'],
                         {'content': 'TestComment'})

  def test_get_comment_count(self):
    api = monorail_api.IssueTrackerAPI('my-project')
    list_method = self.client.issues.return_value.comments.return_value.list
    list_method.return_value.execute.return_value = {'totalResults': '1'}

    api.getCommentCount('123')

    self.assertEquals(list_method.call_count, 1)
    self.assertEquals(list_method.call_args[1]['projectId'], 'my-project')
    self.assertEquals(list_method.call_args[1]['issueId'], '123')
    self.assertEquals(list_method.call_args[1]['startIndex'], 1)
    self.assertEquals(list_method.call_args[1]['maxResults'], 0)

  def test_get_comments(self):
    api = monorail_api.IssueTrackerAPI('my-project')
    list_method = self.client.issues.return_value.comments.return_value.list
    list_method.return_value.execute.side_effect = [
        {
            'totalResults':
                '2',
            'items': [{
                'id': '345',
                'author': {
                    'name': 'test@example.com'
                },
                'content': '',
                'published': '2016-10-05T22:33:44.123456Z',
            },],
        },
        {
            'totalResults':
                '2',
            'items': [{
                'id': '678',
                'author': {
                    'name': 'test@example.com'
                },
                'content': 'TestComment',
                'published': '2016-10-05T23:33:44',
            },],
        },
    ]

    comments = api.getComments('123')
    self.assertEquals(comments[0].id, '345')
    self.assertEquals(comments[0].author, 'test@example.com')
    self.assertEquals(comments[0].comment, '')
    self.assertEquals(comments[0].created,
                      datetime.datetime(2016, 10, 5, 22, 33, 44, 123456))
    self.assertEquals(comments[1].id, '678')
    self.assertEquals(comments[1].author, 'test@example.com')
    self.assertEquals(comments[1].comment, 'TestComment')
    self.assertEquals(comments[1].created,
                      datetime.datetime(2016, 10, 5, 23, 33, 44))

    self.assertEquals(list_method.call_count, 2)
    call1_kwargs = list_method.call_args_list[0][1]
    self.assertEquals(call1_kwargs['projectId'], 'my-project')
    self.assertEquals(call1_kwargs['issueId'], '123')

    call2_kwargs = list_method.call_args_list[1][1]
    self.assertEquals(call2_kwargs['projectId'], 'my-project')
    self.assertEquals(call2_kwargs['issueId'], '123')
    self.assertEquals(call2_kwargs['startIndex'], 1)

  def test_get_issue(self):
    api = monorail_api.IssueTrackerAPI('my-project')
    get_method = self.client.issues.return_value.get
    get_method.return_value.execute.return_value = {'id': '123'}
    issue = api.getIssue('123')
    self.assertEquals(issue.id, '123')
    self.assertEquals(get_method.call_count, 1)
    self.assertEquals(get_method.call_args[1]['projectId'], 'my-project')
    self.assertEquals(get_method.call_args[1]['issueId'], '123')

  def test_get_issues(self):
    api = monorail_api.IssueTrackerAPI('my-project')
    list_method = self.client.issues.return_value.list
    list_method.return_value.execute.side_effect = [
        {
            'totalResults':
                '2',
            'items': [{
                'id': '345',
                'updated': '2016-10-05T23:33:44',
                'title': 'test',
                'summary': 'test',
                'status': 'Assigned',
            }, {
                'id': '123',
                'updated': '2016-10-05T23:33:44',
                'title': 'test',
                'summary': 'test',
                'status': 'Assigned',
            }],
        },
    ]

    issues = api.getIssues('my-project')
    self.assertEquals(len(issues), 2)
    self.assertEquals(issues[0].id, '345')
    self.assertEquals(issues[1].id, '123')

  def test_get_issue_on_another_project(self):
    api = monorail_api.IssueTrackerAPI('my-project')
    get_method = self.client.issues.return_value.get
    get_method.return_value.execute.return_value = {'id': '123'}
    issue = api.getIssue('123', project_id='webrtc')
    self.assertEquals(issue.id, '123')
    self.assertEquals(get_method.call_count, 1)
    self.assertEquals(get_method.call_args[1]['projectId'], 'webrtc')
    self.assertEquals(get_method.call_args[1]['issueId'], '123')

  def test_uses_staging_instance(self):
    monorail_api.IssueTrackerAPI('my-project', use_staging=True)
    self.build_client.assert_called_once_with(
        'monorail',
        'v1',
        'https://monorail-staging.appspot.com/_ah/api/'
        'discovery/v1/apis/{api}/{apiVersion}/rest',
        http=mock.ANY)
    self.assertEqual(self.build_client.call_args[1]["http"].timeout, 60)

  def test_uses_prod_instance_by_default(self):
    monorail_api.IssueTrackerAPI('my-project')
    self.build_client.assert_called_once_with(
        'monorail',
        'v1',
        'https://monorail-prod.appspot.com/_ah/api/'
        'discovery/v1/apis/{api}/{apiVersion}/rest',
        http=mock.ANY)
    self.assertEqual(self.build_client.call_args[1]["http"].timeout, 60)
