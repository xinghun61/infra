#!/usr/bin/env python
# Copyright 2011 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for view functions and helpers."""

import datetime
import json
import unittest

import setup
setup.process_args()


from django.http import HttpRequest

from google.appengine.api.users import User
from google.appengine.ext import ndb

from utils import TestCase, load_file

from codereview import models, views
from codereview import engine  # engine must be imported after models :(


class MockRequest(HttpRequest):
  """Mock request class for testing."""

  def __init__(self, user=None, issue=None):
    super(MockRequest, self).__init__()
    self.META['HTTP_HOST'] = 'testserver'
    self.user = user
    self.issue = issue


class TestSearch(TestCase):

  def setUp(self):
    """Create two test issues and users."""
    super(TestSearch, self).setUp()
    user = User('bar@example.com')
    models.Account.get_account_for_user(user)
    user = User('test@groups.example.com')
    models.Account.get_account_for_user(user)
    self.user = User('foo@example.com')
    self.login('foo@example.com')
    issue1 = models.Issue(subject='test')
    issue1.reviewers = ['test@groups.example.com',
              'bar@example.com']
    issue1.local_base = False
    issue1.put()
    issue2 = models.Issue(subject='test')
    issue2.reviewers = ['test2@groups.example.com',
              'bar@example.com']
    issue2.local_base = False
    issue2.put()

  def test_json_get_api(self):
    today = datetime.date.today()
    start = today - datetime.timedelta(days=2)
    end = today + datetime.timedelta(days=2)
    # This search is derived from a real query that comes up in the logs
    # quite regulary. It searches for open issues with a test group as
    # reviewer within a month and requests the returned data to be encoded
    # as JSON.
    response = self.client.get('/search', {
      'closed': 3, 'reviewer': 'test@groups.example.com',
      'private': 1, 'created_before': str(end),
      'created_after': str(start), 'order': 'created',
      'keys_only': False, 'with_messages': False, 'cursor': '',
      'limit': 1000, 'format': 'json'
    })
    self.assertEqual(response.status_code, 200)
    self.assertEqual(response['Content-Type'],
             'application/json; charset=utf-8')
    payload = json.loads(response.content)
    self.assertEqual(len(payload['results']), 1)


if __name__ == '__main__':
  unittest.main()
