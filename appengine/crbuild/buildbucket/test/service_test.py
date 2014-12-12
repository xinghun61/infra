# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json

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
        parameters={
            'buildername': 'infra',
            'changes': [{
                'author': 'nodir@google.com',
                'message': 'crbuild: initial commit'
            }]
        }
    )

    self.current_user = mock.Mock()
    self.mock(acl, 'current_user', mock.Mock(return_value=self.current_user))

  ##################################### ADD ####################################

  def test_add(self):
    params = {'buildername': 'linux_rel'}
    build = self.service.add(
        namespace='chromium',
        parameters=params,
    )
    self.assertIsNotNone(build.key)
    self.assertIsNotNone(build.key.id())
    self.assertEqual(build.namespace, 'chromium')
    self.assertEqual(build.parameters, params)

  def test_add_with_leasing(self):
    build = self.service.add(
        namespace='chromium',
        lease_duration=datetime.timedelta(seconds=1)
    )
    self.assertGreater(build.available_since, datetime.datetime.utcnow())
    self.assertIsNotNone(build.lease_key)

  def test_add_with_auth_error(self):
    self.current_user.can_add_build_to_namespace.return_value = False
    with self.assertRaises(auth.AuthorizationError):
      self.service.add(self.test_build.namespace)

  ##################################### GET ####################################

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

  ##################################### PEEK ###################################

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

  #################################### LEASE ###################################

  def lease(self, duration=None):
    if self.test_build.key is None:
      self.test_build.put()
    success, self.test_build = self.service.lease(
        self.test_build.key.id(),
        duration=duration,
    )
    return success

  def test_can_lease(self):
    self.assertTrue(self.lease())

  def test_lease_build_with_auth_error(self):
    self.current_user.can_lease_build.return_value = False
    with self.assertRaises(auth.AuthorizationError):
      self.lease()

  def test_cannot_lease_a_leased_build(self):
    self.assertTrue(self.lease())
    self.assertFalse(self.lease())

  def test_cannot_lease_a_nonexistent_build(self):
    with self.assertRaises(service.BuildNotFoundError):
      self.service.lease(build_id=42)

  def test_cannot_lease_for_whole_day(self):
    with self.assertRaises(service.BadLeaseDurationError):
      self.lease(duration=datetime.timedelta(days=1))

  def test_cannot_lease_for_negative_duration(self):
    with self.assertRaises(service.BadLeaseDurationError):
      self.lease(duration=datetime.timedelta(days=-1))

  def test_cannot_lease_for_non_timedelta_duration(self):
    with self.assertRaises(service.BadLeaseDurationError):
      self.lease(duration=2)

  def test_leasing_regenerates_lease_key(self):
    orig_lease_key = 42
    self.lease()
    self.assertNotEqual(self.test_build.lease_key, orig_lease_key)

  def test_cannot_lease_completed_build(self):
    self.test_build.status = model.BuildStatus.COMPLETE
    self.test_build.put()
    self.assertFalse(self.lease())

  ################################### UPDATE ###################################

  def test_unlease(self):
    self.test_build.put()
    self.lease()
    build = self.service.update(
        self.test_build.key.id(),
        lease_key=self.test_build.lease_key,
        lease_duration=datetime.timedelta(0),
    )
    self.assertIsNone(build.lease_key)
    self.assertTrue(self.lease())

  def test_cannot_update_nonexistent_build(self):
    with self.assertRaises(service.BuildNotFoundError):
      self.service.update(123, lease_key=321)

  def test_update(self):
    self.test_build.put()
    self.service.update(self.test_build.key.id(),
                        status=model.BuildStatus.COMPLETE,
                        state={'result': 'success'})
    build = self.test_build.key.get()
    self.assertEqual(build.status, model.BuildStatus.COMPLETE)
    self.assertEqual(build.state, {'result': 'success'})

  def test_update_with_auth_error(self):
    self.test_build.put()
    self.current_user.can_lease_build.return_value = False
    with self.assertRaises(auth.AuthorizationError):
      self.service.update(self.test_build.key.id(), lease_key=321)

  def test_cannot_update_with_wrong_lease_key(self):
    self.test_build.put()
    self.lease()
    with self.assertRaises(service.BadLeaseKeyError):
      self.service.update(self.test_build.key.id(),
                          self.test_build.lease_key + 1,
                          status=model.BuildStatus.BUILDING)

  def test_cannot_transition_build_from_final_state(self):
    self.test_build.status = model.BuildStatus.COMPLETE
    self.test_build.put()
    with self.assertRaises(service.StatusIsFinalError):
      self.service.update(self.test_build.key.id(),
                          status=model.BuildStatus.BUILDING)

  ################################# OTHER STUFF ################################

  def test_status_changes_creates_notification_task(self):
    self.test_build.callback = model.Callback(
        url = '/tasks/notify',
        queue_name='default',
    )
    self.test_build.status = model.BuildStatus.BUILDING
    self.test_build.put()
    self.service.update(self.test_build.key.id(),
                        status=model.BuildStatus.COMPLETE)

    taskq = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
    tasks = taskq.GetTasks('default')
    assert any(t.get('url') == self.test_build.callback.url for t in tasks)
