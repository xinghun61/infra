# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for gerrit_api.py"""

import mock
import requests
import tempfile
import unittest

from infra.libs import gerrit_api


GERRIT_JSON_HEADER = ')]}\'\n'

HEADERS = {
    'Accept': 'application/json',
    'Accept-encoding': 'gzip',
    'Authorization': 'Basic Z2l0LWNvbW1pdC1ib3RAY2hyb21pdW0ub3JnOnNlY3JldA==',
}


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

  @mock.patch.object(requests.Session, 'request')
  def test_get_account(self, mock_method):
    r = requests.Response()
    r._content = ('%s{"_account_id":1000096,"name":"John Doe","email":'
                  '"john.doe@test.com","username":"john"}') % GERRIT_JSON_HEADER
    r.status_code = 200
    mock_method.return_value = r
    result = self.gerrit.get_account('self')
    mock_method.assert_called_once_with(
        data=None,
        method='GET',
        params=None,
        url='https://chromium-review.googlesource.com/a/accounts/self',
        headers=HEADERS)
    expected_result = {
        '_account_id':1000096,
        'name': 'John Doe',
        'email': 'john.doe@test.com',
        'username': 'john'
    }
    self.assertEqual(result, expected_result)
