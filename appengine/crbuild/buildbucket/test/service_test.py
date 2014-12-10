# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from google.appengine.ext import testbed
import mock

from buildbucket import model
from buildbucket import service
from components import auth
from test import CrBuildTestCase
import acl

class BuildBucketServiceTest(CrBuildTestCase):
  def __init__(self, *args, **kwargs):
    super(BuildBucketServiceTest, self).__init__(*args, **kwargs)
    self.test_build = None

  def setUp(self):
    super(BuildBucketServiceTest, self).setUp()
    self.service = service.BuildBucketService()
    self.test_build = model.Build(
        owner='owner',
        namespace='chromium',
        properties={
            'buildername': 'infra',
            'changes': [{
                'author': 'nodir@google.com',
                'message': 'crbuild: initial commit'
            }]
        }
    )

    self.current_user = mock.Mock()
    self.mock(acl, 'current_user', mock.Mock(return_value=self.current_user))

  def test_add(self):
    build = self.test_build
    self.service.add(build)
    self.assertIsNotNone(build.key)
    self.assertIsNotNone(build.key.id())

  def test_add_with_auth_error(self):
    self.current_user.can_add_build_to_namespace.return_value = False
    with self.assertRaises(auth.AuthorizationError):
      self.service.add(self.test_build)

  def test_get(self):
    self.test_build.put()
    build = self.service.get(self.test_build.key.id())
    self.assertEqual(build, self.test_build)

  def test_get_nonexistent_build(self):
    self.assertIsNone(self.service.get(42))

  def test_get_with_auth_error(self):
    self.current_user.can_view_build.return_value = False
    self.test_build.put()
    with self.assertRaises(auth.AuthorizationError):
      self.service.get(self.test_build.key.id())

  def test_peek(self):
    self.test_build.put()
    builds = self.service.peek(namespaces=[self.test_build.namespace])
    self.assertEqual(builds, [self.test_build])

  def test_peek_with_auth_error(self):
    self.current_user.can_peek_namespace.return_value = False
    self.test_build.put()
    with self.assertRaises(auth.AuthorizationError):
      self.service.peek(namespaces=[self.test_build.namespace])

  def test_peek_does_not_return_leased_builds(self):
    self.test_build.put()
    self.lease()
    builds = self.service.peek([self.test_build.namespace])
    self.assertFalse(builds)

  def test_cannot_peek_1000_builds(self):
    with self.assertRaises(AssertionError):
      self.service.peek([self.test_build.namespace], max_builds=1000)

  def lease(self):
    success, self.test_build = self.service.lease(self.test_build.key.id())
    return success

  def test_lease_build_with_auth_error(self):
    self.current_user.can_lease_build.return_value = False
    build = self.test_build
    build.put()
    with self.assertRaises(auth.AuthorizationError):
      self.lease()

  def test_cannot_lease_a_leased_build(self):
    build = self.test_build
    build.put()
    self.assertTrue(self.lease())
    self.assertFalse(self.lease())

  def test_cannot_lease_a_nonexistent_build(self):
    with self.assertRaises(service.BuildNotFoundError):
      self.service.lease(build_id=42)

  def test_cannot_lease_for_whole_day(self):
    self.test_build.put()
    with self.assertRaises(AssertionError):
      self.service.lease(
          self.test_build.key.id(),
          duration=datetime.timedelta(days=1),
      )

  def test_leasing_changes_lease_key(self):
    self.test_build.put()
    orig_lease_key = self.test_build.lease_key
    self.lease()
    self.assertNotEqual(self.test_build.lease_key, orig_lease_key)

  def test_cannot_lease_completed_build(self):
    build = self.test_build
    build.status = model.BuildStatus.SUCCESS
    build.put()
    self.assertFalse(self.lease())

  def test_unlease(self):
    self.test_build.put()
    build_id = self.test_build.key.id()
    _, build = self.service.lease(build_id)
    self.service.update(build_id, build.lease_key,
        lease_duration=datetime.timedelta(seconds=0))
    self.assertTrue(self.lease())

  def test_cannot_update_nonexistent_build(self):
    with self.assertRaises(service.BuildNotFoundError):
      self.service.update(123, lease_key=321)

  def test_update(self):
    self.test_build.put()
    self.service.update(self.test_build.key.id(),
                        url='http://a.com',
                        status=model.BuildStatus.SUCCESS)
    build = self.test_build.key.get()
    self.assertEqual(build.status, model.BuildStatus.SUCCESS)
    self.assertEqual(build.url, 'http://a.com')

  def test_update_with_auth_error(self):
    self.test_build.put()
    self.lease()

    self.current_user.can_lease_build.return_value = False
    with self.assertRaises(auth.AuthorizationError):
      self.service.update(self.test_build.key.id(), lease_key=321)

  def test_cannot_update_with_wrong_lease_key(self):
    self.test_build.put()
    self.lease()
    with self.assertRaises(service.BadLeaseKeyError):
      self.service.update(self.test_build.key.id(),
                          self.test_build.lease_key + 1, url='http://a.com')

  def test_cannot_transition_build_from_final_state(self):
    self.test_build.put()
    self.lease()
    self.test_build.status = model.BuildStatus.SUCCESS
    self.test_build.put()

    with self.assertRaises(service.StatusIsFinalError):
      self.service.update(self.test_build.key.id(), self.test_build.lease_key,
                          status=model.BuildStatus.BUILDING)

  def test_status_changes_creates_notification_task(self):
    self.test_build.callback = model.Callback(
        url = '/tasks/notify',
        queue_name='default',
    )
    self.test_build.status = model.BuildStatus.BUILDING
    self.test_build.put()
    self.service.update(self.test_build.key.id(),
                        status=model.BuildStatus.SUCCESS)

    taskq = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
    tasks = taskq.GetTasks('default')
    assert any(t.get('url') == self.test_build.callback.url for t in tasks)
