# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for gerrit_api.py"""

import json
import mock
import requests
import tempfile
import time
import unittest

from infra.libs import gerrit_api


GERRIT_JSON_HEADER = ')]}\'\n'

HEADERS = {
    'Accept': 'application/json',
    'Accept-encoding': 'gzip',
    'Authorization': 'Basic Z2l0LWNvbW1pdC1ib3RAY2hyb21pdW0ub3JnOnNlY3JldA==',
}

HEADERS_WITH_CONTENT_TYPE = HEADERS.copy()
HEADERS_WITH_CONTENT_TYPE['Content-Type'] = 'application/json;charset=UTF-8'

TEST_CHANGE_INFO = {
    'id': 'project~branch~12345~change',
    'change_id': 12345,
    'created': '2014-02-11 12:14:28.135200000',
    'updated': '2014-03-11 00:20:08.946000000',
    'current_revision': 'THIRD',
    'owner': {
        'name': 'Some Person',
    },
    'revisions': {
        'THIRD': {
            '_number': 3,
        },
        'SECOND': {
            '_number': 2,
        },
        'FIRST': {
            '_number': 1,
        },
    },
    'labels': {
        'Commit-Queue': {
            'recommended': { '_account_id': 1 }
        },
        'Test-Label': {
            'disliked': { '_account_id' : 42 }
        },
        'Code-Review': {
            'approved': { '_account_id': 2 }
        },
    },
    'messages': [
        {
            'id': 1,
            'author': 'test-user@test.org',
            'date': '2014-02-11 12:10:14.311200000',
            'message': 'MESSAGE1',
        },
        {
            'id': 2,
            'date': '2014-02-11 12:11:14.311200000',
            'message': 'MESSAGE2',
            '_revision_number': 2,
        },
    ],
}

def _create_mock_return(content, code):
  r = requests.Response()
  r._content = content
  r.status_code = code
  return r


class MockCredentials(object):
  def __init__(self, login='git-commit-bot@chromium.org',
               secret_token='secret'):
    self.login = login
    self.secret_token = secret_token

  def __getitem__(self, host):
    return (self.login, self.secret_token)


# TODO(akuegel): Add more test cases and remove the pragma no covers.
class GerritAgentTestCase(unittest.TestCase):

  def setUp(self):
    self.gerrit = gerrit_api.Gerrit('chromium-review.googlesource.com',
                                    MockCredentials())
    self.gerrit_read_only = gerrit_api.Gerrit(
        'chromium-review.googlesource.com', MockCredentials(), read_only=True)

  @mock.patch.object(requests.Session, 'request')
  def test_request_no_leading_slash(self, mock_method):
    mock_method.return_value = _create_mock_return(
        '%s[]' % GERRIT_JSON_HEADER, 200)
    result = self.gerrit._request(method='GET',
                                  request_path='changes/?q=query:no_results')
    mock_method.assert_called_once_with(
        data=None,
        method='GET',
        params=None,
        url=('https://chromium-review.googlesource.com/a/changes/'
             '?q=query:no_results'),
        headers=HEADERS)
    self.assertEqual(result, (200, []))

  @mock.patch.object(gerrit_api.Gerrit, '_sleep')
  @mock.patch.object(time, 'time')
  @mock.patch.object(requests.Session, 'request')
  def test_request_throttled(self, mock_method, time_mock_method, sleep_mock):
    gerrit_throttled = gerrit_api.Gerrit('chromium-review.googlesource.com',
                                         MockCredentials(), 0.1)
    mock_method.return_value = _create_mock_return(None, 404)
    time_mock_method.return_value = 100
    gerrit_throttled._request(method='GET', request_path='/accounts/self')
    # Call it twice to test the throttling.
    gerrit_throttled._request(method='GET', request_path='/accounts/self')
    sleep_mock.assert_called_once_with(0)
    time_mock_method.return_value = 101
    # Call it again after exceeding the throttle to cover the other branch.
    gerrit_throttled._request(method='GET', request_path='/accounts/self')

  @mock.patch.object(requests.Session, 'request')
  def test_get_account(self, mock_method):
    mock_method.return_value = _create_mock_return(
        ('%s{"_account_id":1000096,"name":"John Doe","email":'
         '"john.doe@test.com","username":"john"}') % GERRIT_JSON_HEADER,
        200)
    result = self.gerrit.get_account('self')
    mock_method.assert_called_once_with(
        data=None,
        method='GET',
        params=None,
        url='https://chromium-review.googlesource.com/a/accounts/self',
        headers=HEADERS)
    expected_result = {
        '_account_id': 1000096,
        'name': 'John Doe',
        'email': 'john.doe@test.com',
        'username': 'john'
    }
    self.assertEqual(result, expected_result)

  @mock.patch.object(requests.Session, 'request')
  def test_get_account_404(self, mock_method):
    mock_method.return_value = _create_mock_return(None, 404)
    result = self.gerrit.get_account('does.not@exist.com')
    mock_method.assert_called_once_with(
        data=None,
        method='GET',
        params=None,
        url=('https://chromium-review.googlesource.com'
             '/a/accounts/does.not@exist.com'),
        headers=HEADERS)
    self.assertEqual(result, None)

  @mock.patch.object(requests.Session, 'request')
  def test_get_account_unexpected_response(self, mock_method):
    mock_method.return_value = _create_mock_return(None, 201)
    self.assertRaises(gerrit_api.UnexpectedResponseException,
                      self.gerrit.get_account, 'self')

  @mock.patch.object(requests.Session, 'request')
  def test_add_group_members(self, mock_method):
    mock_method.return_value = _create_mock_return(
        ('%s[{"_account_id":1000057,"name":"Jane Roe","email":'
         '"jane.roe@example.com","username": "jane"}]') % GERRIT_JSON_HEADER,
        200)
    members = ['jane.roe@example.com']
    payload = { 'members': members }
    result = self.gerrit.add_group_members('test-group', members)
    mock_method.assert_called_once_with(
        data=json.dumps(payload),
        method='POST',
        params=None,
        url=('https://chromium-review.googlesource.com/a/groups/'
             'test-group/members.add'),
        headers=HEADERS_WITH_CONTENT_TYPE)
    expected_result = [{
        '_account_id': 1000057,
        'name': 'Jane Roe',
        'email': 'jane.roe@example.com',
        'username': 'jane'
    }]
    self.assertEqual(result, expected_result)

  @mock.patch.object(requests.Session, 'request')
  def test_add_group_members_unexpected_response(self, mock_method):
    mock_method.return_value = _create_mock_return(None, 400)
    self.assertRaises(gerrit_api.UnexpectedResponseException,
                      self.gerrit.add_group_members, 'test-group', ['a@b.com'])

  def test_add_group_members_wrong_group(self):
    self.assertRaises(ValueError, self.gerrit.add_group_members, 'a/b/c', [])

  def test_add_group_members_read_only(self):
    self.assertRaises(gerrit_api.AccessViolationException,
                      self.gerrit_read_only.add_group_members,
                      'test-group', ['a@b.com'])

  @mock.patch.object(requests.Session, 'request')
  def test_set_project_parent(self, mock_method):
    mock_method.return_value = _create_mock_return(
        '%s"parent"' % GERRIT_JSON_HEADER, 200)
    result = self.gerrit.set_project_parent('project', 'parent')
    payload = {
        'parent': 'parent',
        'commit_message': 'Changing parent project to parent'
    }
    mock_method.assert_called_once_with(
        data=json.dumps(payload),
        method='PUT',
        params=None,
        url=('https://chromium-review.googlesource.com/a/projects/'
             'project/parent'),
        headers=HEADERS_WITH_CONTENT_TYPE)
    self.assertEqual(result, 'parent')

  @mock.patch.object(requests.Session, 'request')
  def test_set_project_parent_unexpected_response(self, mock_method):
    mock_method.return_value = _create_mock_return(None, 400)
    self.assertRaises(gerrit_api.UnexpectedResponseException,
                      self.gerrit.set_project_parent, 'a', 'b')

  @mock.patch.object(requests.Session, 'request')
  def test_query(self, mock_method):
    mock_method.return_value = _create_mock_return(
        '%s%s' % (GERRIT_JSON_HEADER, json.dumps([TEST_CHANGE_INFO])), 200)
    result = self.gerrit.query(project='test', with_labels=False,
                                with_revisions=False, owner='test@chromium.org')
    mock_method.assert_called_once_with(
        data=None,
        method='GET',
        params={'q':'project:test owner:test@chromium.org', 'o': ['MESSAGES']},
        url='https://chromium-review.googlesource.com/a/changes/',
        headers=HEADERS)
    self.assertEquals(result, [TEST_CHANGE_INFO])

  @mock.patch.object(requests.Session, 'request')
  def test_query_with_query_name(self, mock_method):
    mock_method.return_value = _create_mock_return(
        '%s%s' % (GERRIT_JSON_HEADER, json.dumps([TEST_CHANGE_INFO])), 200)
    result = self.gerrit.query(project='test', query_name='pending_cls',
                               owner='1012155')
    mock_method.assert_called_once_with(
        data=None,
        method='GET',
        params={'q':'project:test query:pending_cls owner:1012155',
                'o': ['MESSAGES', 'LABELS', 'ALL_REVISIONS']},
        url='https://chromium-review.googlesource.com/a/changes/',
        headers=HEADERS)
    self.assertEquals(result, [TEST_CHANGE_INFO])

  @mock.patch.object(requests.Session, 'request')
  def test_query_unexpected_response(self, mock_method):
    mock_method.return_value = _create_mock_return(None, 400)
    self.assertRaises(gerrit_api.UnexpectedResponseException,
                      self.gerrit.query, 'a', with_messages=False,
                      with_labels=False, with_revisions=False)
