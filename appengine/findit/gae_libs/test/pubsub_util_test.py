# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import functools
import mock

from gae_libs import pubsub_util
from gae_libs.testcase import TestCase


def Execute(func):

  @functools.wraps(func)
  def Wrapped(*args, **kwargs):

    class Executable(object):

      def __init__(self, func, *args, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs

      def execute(self):
        return self.func(*self.args, **self.kwargs)

    return Executable(func, *args, **kwargs)

  return Wrapped


class MockSubscription(object):

  def __init__(self, results=None):
    if results is None:
      self.results = []
      self.ids = []
    else:
      self.results = {'receivedMessages': results}
      self.ids = [result['ackId'] for result in results]

  @Execute
  def pull(self, subscription=None, body=None):
    assert subscription is not None
    assert body is not None
    assert isinstance(body.get('returnImmediately'), bool)
    assert isinstance(body.get('maxMessages'), int)
    return self.results

  @Execute
  def acknowledge(self, subscription=None, body=None):
    assert subscription is not None
    assert body is not None
    assert body['ackIds'] == self.ids


def MockCreatePubSubClient(subscriptions=None):

  class MockPubSubClient(object):

    def projects(self):
      class MockProject(object):

        def subscriptions(self):
          return subscriptions

      return MockProject()

  return MockPubSubClient


class PubSubUtilTest(TestCase):

  @mock.patch('gae_libs.pubsub_util.CreatePubSubClient',
              new=MockCreatePubSubClient(subscriptions=MockSubscription()))
  def testPullMessagesFromEmptySubscription(self):
    """Tests pull messages from empty subscription."""
    messages = pubsub_util.PullMessagesFromSubscription('sub')
    self.assertEqual(messages, [])

  @mock.patch('gae_libs.pubsub_util.CreatePubSubClient',
              new=MockCreatePubSubClient(subscriptions=MockSubscription(
                  results=[{'ackId': '1', 'message': 'dummy'}])))
  def testPullMessagesFromNoneEmptySubscription(self):
    """Tests pulling messages from non empty subscription."""
    messages = pubsub_util.PullMessagesFromSubscription('sub')
    self.assertListEqual(messages, ['dummy'])
