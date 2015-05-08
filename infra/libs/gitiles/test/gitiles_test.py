# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import httplib2
import os
import time

from infra.libs.gitiles import gitiles
from testing_support import auto_stub


DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')


class TestGitiles(auto_stub.TestCase):
  def setUp(self):
    super(TestGitiles, self).setUp()

    self.response = {'status': '200'}
    self.content = None

    class FakeHttp(object):
      def __init__(self, response, content):
        self.response = response
        self.content = content

      def request(self, *_args, **_kwargs):
        return self.response, self.content

    def http_maker():
      return FakeHttp(self.response, self.content)

    self.mock(httplib2, 'Http', http_maker)
    self.mock(time, 'sleep', lambda _x: None)

  def testJson(self):
    with open(os.path.join(DATA_DIR, 'scripts_slave')) as f:
      self.content = f.read()

    result = gitiles.call_gitiles(
        'http://bananas',
        'json',
        os.path.join(DATA_DIR, 'netrc'))
    self.assertEqual(result['id'], '24a7f79e278700fab6dfd3866b1b8508c44ddb55')

  def testText(self):
    with open(os.path.join(DATA_DIR, 'init_py')) as f:
      self.content = f.read()

    result = gitiles.call_gitiles(
        'http://bananas',
        'text',
        os.path.join(DATA_DIR, 'netrc'))

    self.assertTrue(result.startswith('# Copyright 2015'))

  def testInvalidResponse(self):
    self.response = {'status': '500'}
    with self.assertRaises(gitiles.GitilesError):
      gitiles.call_gitiles(
          'http://bananas',
          'text',
          os.path.join(DATA_DIR, 'netrc'))

  def testInvalidJsonResponse(self):
    self.content = 'blerg\ndefinitely does not start with )]}\''
    with self.assertRaises(gitiles.GitilesError):
      gitiles.call_gitiles(
          'http://bananas',
          'json',
          os.path.join(DATA_DIR, 'netrc'))

    self.content = 'definitely does not have a newline'
    with self.assertRaises(gitiles.GitilesError):
      gitiles.call_gitiles(
          'http://bananas',
          'json',
          os.path.join(DATA_DIR, 'netrc'))

  def testQueryInUrl(self):
    with self.assertRaises(AssertionError):
      gitiles.call_gitiles(
          'http://bananas?foster',
          'text',
          os.path.join(DATA_DIR, 'netrc'))

  def testBadAuth(self):
    with self.assertRaises(gitiles.GitilesError):
      gitiles.call_gitiles(
          'http://twirly',
          'json',
          os.path.join(DATA_DIR, 'netrc'))

  def testNoAuth(self):
    with open(os.path.join(DATA_DIR, 'scripts_slave')) as f:
      self.content = f.read()
    result = gitiles.call_gitiles(
        'http://twirly',
        'json'
    )
    self.assertEqual(result['id'], '24a7f79e278700fab6dfd3866b1b8508c44ddb55')
