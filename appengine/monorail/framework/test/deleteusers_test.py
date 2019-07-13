# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for deleteusers classes."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import mock
import os
import unittest

from google.appengine.ext import testbed

from framework import deleteusers
from framework import urls
from services import service_manager
from testing import fake
from testing import testing_helpers

class TestWipeoutSyncCron(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_taskqueue_stub()
    self.taskqueue_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
    self.taskqueue_stub._root_path = os.path.dirname(
        os.path.dirname(os.path.dirname( __file__ )))

    self.services = service_manager.Services(user=fake.UserService())
    self.task = deleteusers.WipeoutSyncCron(
        request=None, response=None, services=self.services)
    self.user_1 = self.services.user.TestAddUser('user1@example.com', 111)
    self.user_2 = self.services.user.TestAddUser('user2@example.com', 222)
    self.user_3 = self.services.user.TestAddUser('user3@example.com', 333)

  def tearDown(self):
    self.testbed.deactivate()

  def testHandleRequest(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='url/url?batchsize=2',
        services=self.services)
    self.task.HandleRequest(mr)

    tasks = self.taskqueue_stub.get_filtered_tasks(
        url=urls.SEND_WIPEOUT_USER_LISTS_TASK + '.do')
    self.assertEqual(2, len(tasks))
    self.assertEqual(tasks[0].payload, 'limit=2&offset=0')
    self.assertEqual(tasks[1].payload, 'limit=2&offset=2')

  def testHandleRequest_NoBatchSizeParam(self):
    mr = testing_helpers.MakeMonorailRequest(services=self.services)
    self.task.HandleRequest(mr)

    tasks = self.taskqueue_stub.get_filtered_tasks(
        url=urls.SEND_WIPEOUT_USER_LISTS_TASK + '.do')
    self.assertEqual(1, len(tasks))
    self.assertEqual(
        tasks[0].payload, 'limit=%s&offset=0' % deleteusers.MAX_BATCH_SIZE)

  def testHandleRequest_NoUsers(self):
    mr = testing_helpers.MakeMonorailRequest()
    self.services.user.users_by_id = {}
    self.task.HandleRequest(mr)

    tasks = self.taskqueue_stub.get_filtered_tasks(
        url=urls.SEND_WIPEOUT_USER_LISTS_TASK + '.do')
    self.assertEqual(0, len(tasks))


class SendWipeoutUserListsTaskTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(user=fake.UserService())
    self.task = deleteusers.SendWipeoutUserListsTask(
        request=None, response=None, services=self.services)
    self.task.sendUserLists = mock.Mock()
    deleteusers.authorize = mock.Mock(return_value='service')
    self.user_1 = self.services.user.TestAddUser('user1@example.com', 111)
    self.user_2 = self.services.user.TestAddUser('user2@example.com', 222)
    self.user_3 = self.services.user.TestAddUser('user3@example.com', 333)

  def testHandleRequest_NoBatchSizeParam(self):
    mr = testing_helpers.MakeMonorailRequest(path='url/url?limit=2&offset=1')
    self.task.HandleRequest(mr)
    deleteusers.authorize.assert_called_once_with()
    self.task.sendUserLists.assert_called_once_with(
        'service', [
            {'id': self.user_2.email},
            {'id': self.user_3.email}])

  def testHandleRequest_NoLimit(self):
    mr = testing_helpers.MakeMonorailRequest()
    self.services.user.users_by_id = {}
    with self.assertRaisesRegexp(AssertionError, 'Missing param limit'):
      self.task.HandleRequest(mr)

  def testHandleRequest_NoOffset(self):
    mr = testing_helpers.MakeMonorailRequest(path='url/url?limit=3')
    self.services.user.users_by_id = {}
    with self.assertRaisesRegexp(AssertionError, 'Missing param offset'):
      self.task.HandleRequest(mr)

  def testHandleRequest_ZeroOffset(self):
    mr = testing_helpers.MakeMonorailRequest(path='url/url?limit=2&offset=0')
    self.task.HandleRequest(mr)
    self.task.sendUserLists.assert_called_once_with(
        'service', [
            {'id': self.user_1.email},
            {'id': self.user_2.email}])
