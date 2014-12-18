# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import datetime
import json

from components import auth
from components import utils
from google.appengine.ext import testbed
import mock

from buildbucket import model
from buildbucket import service
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

    self.current_identity = auth.Identity('service', 'unittest')
    self.mock(auth, 'get_current_identity', lambda: self.current_identity)
    self.current_user = mock.Mock()
    self.mock(acl, 'current_user', lambda: self.current_user)


  #################################### ADD #####################################

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
        lease_expiration_date=utils.utcnow () + datetime.timedelta(seconds=10),
    )
    self.assertTrue(build.is_leased)
    self.assertGreater(build.lease_expiration_date, utils.utcnow())
    self.assertIsNotNone(build.lease_key)

  def test_add_with_auth_error(self):
    self.current_user.can_add_build_to_namespace.return_value = False
    with self.assertRaises(auth.AuthorizationError):
      self.service.add(self.test_build.namespace)

  #################################### GET #####################################

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

  ################################### CANCEL ###################################

  def test_cancel(self):
    self.test_build.put()
    build = self.service.cancel(self.test_build.key.id())
    self.assertEqual(build.status, model.BuildStatus.COMPLETED)
    self.assertEqual(build.result, model.BuildResult.CANCELED)
    self.assertEqual(
        build.cancelation_reason, model.CancelationReason.CANCELED_EXPLICITLY)

  def test_cancel_is_idempotent(self):
    self.test_build.put()
    self.service.cancel(self.test_build.key.id())
    self.service.cancel(self.test_build.key.id())

  def test_cancel_started_build(self):
    self.lease()
    self.start()
    self.service.cancel(self.test_build.key.id())

  def test_cancel_nonexistent_build(self):
    with self.assertRaises(service.BuildNotFoundError):
      self.service.cancel(1)

  def test_cancel_with_auth_error(self):
    self.test_build.put()
    self.current_user.can_cancel_build.return_value = False
    with self.assertRaises(auth.AuthorizationError):
      self.service.cancel(self.test_build.key.id())

  def test_cancel_completed_build(self):
    self.test_build.status = model.BuildStatus.COMPLETED
    self.test_build.result = model.BuildResult.SUCCESS
    self.test_build.put()
    with self.assertRaises(service.InvalidBuildStateError):
      self.service.cancel(self.test_build.key.id())

  #################################### PEEK ####################################

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

  def lease(self, lease_expiration_date=None):
    if self.test_build.key is None:
      self.test_build.put()
    success, self.test_build = self.service.lease(
        self.test_build.key.id(),
        lease_expiration_date=lease_expiration_date,
    )
    return success

  def test_lease(self):
    expiration_date = utils.utcnow() + datetime.timedelta(minutes=1)
    self.assertTrue(self.lease(lease_expiration_date=expiration_date))
    self.assertTrue(self.test_build.is_leased)
    self.assertGreater(self.test_build.lease_expiration_date, utils.utcnow())
    self.assertEqual(self.test_build.leasee, self.current_identity)

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
    with self.assertRaises(service.InvalidInputError):
      self.lease(
          lease_expiration_date=utils.utcnow() + datetime.timedelta(days=1))

  def test_cannot_set_expiration_date_to_past(self):
    with self.assertRaises(service.InvalidInputError):
      yesterday = utils.utcnow() - datetime.timedelta(days=1)
      self.lease(lease_expiration_date=yesterday)

  def test_cannot_lease_with_non_datetime_expiration_date(self):
    with self.assertRaises(service.InvalidInputError):
      self.lease(lease_expiration_date=1)

  def test_leasing_regenerates_lease_key(self):
    orig_lease_key = 42
    self.lease()
    self.assertNotEqual(self.test_build.lease_key, orig_lease_key)

  def test_cannot_lease_completed_build(self):
    build = self.test_build
    build.status = model.BuildStatus.COMPLETED
    build.result = model.BuildResult.SUCCESS
    build.put()
    self.assertFalse(self.lease())

  ################################### UNELASE ##################################

  def test_unlease(self):
    self.lease()
    build = self.service.unlease(
        self.test_build.key.id(), self.test_build.lease_key)
    self.assertEqual(build.status, model.BuildStatus.SCHEDULED)
    self.assertIsNone(build.lease_key)
    self.assertIsNone(build.lease_expiration_date)
    self.assertIsNone(build.leasee)
    self.assertTrue(self.lease())

  def test_unlease_is_idempotent(self):
    self.lease()
    build_id = self.test_build.key.id()
    lease_key = self.test_build.lease_key
    self.service.unlease(build_id, lease_key)
    self.service.unlease(build_id, lease_key)

  def test_unlease_completed_build(self):
    self.test_build.status = model.BuildStatus.COMPLETED
    self.test_build.result = model.BuildResult.SUCCESS
    self.test_build.put()
    with self.assertRaises(service.InvalidBuildStateError):
      self.service.unlease(self.test_build.key.id(), 42)

  def test_cannot_unlease_nonexistent_build(self):
    with self.assertRaises(service.BuildNotFoundError):
      self.service.unlease(123, lease_key=321)

  def test_unlease_without_lease_key(self):
    self.lease()
    with self.assertRaises(service.InvalidInputError):
      self.service.unlease(self.test_build.key.id(), None)

  def test_cannot_unlease_with_wrong_lease_key(self):
    self.lease()
    with self.assertRaises(service.InvalidInputError):
      self.service.unlease(
          self.test_build.key.id(), self.test_build.lease_key + 1)

  def test_unlease_with_auth_error(self):
    self.lease()
    self.current_user.can_lease_build.return_value = False
    with self.assertRaises(auth.AuthorizationError):
      self.service.unlease(self.test_build.key.id(), lease_key=321)

  #################################### START ###################################

  def test_validate_malformed_url(self):
    with self.assertRaises(service.InvalidInputError):
      service.validate_url('svn://sdfsf')

  def test_validate_relative_url(self):
    with self.assertRaises(service.InvalidInputError):
      service.validate_url('sdfsf')

  def test_validate_nonstring_url(self):
    with self.assertRaises(service.InvalidInputError):
      service.validate_url(123)

  def start(self, url=None, lease_key=None):
    self.test_build = self.service.start(
        self.test_build.key.id(),
        lease_key or self.test_build.lease_key,
        url=url)

  def test_start(self):
    self.lease()
    self.start(url='http://localhost')
    self.assertEqual(self.test_build.status, model.BuildStatus.STARTED)
    self.assertEqual(self.test_build.url, 'http://localhost')

  def test_start_is_idempotent(self):
    self.lease()
    build_id = self.test_build.key.id()
    lease_key = self.test_build.lease_key
    url = 'http://localhost/'

    self.service.start(build_id, lease_key, url)
    self.service.start(build_id, lease_key, url)

    with self.assertRaises(service.InvalidBuildStateError):
      self.service.start(build_id, lease_key, url + '/1')

  def test_start_non_leased_build(self):
    self.test_build.put()
    with self.assertRaises(service.InvalidBuildStateError):
      self.service.start(self.test_build.key.id(), 42)

  def test_start_completed_build(self):
    self.test_build.status = model.BuildStatus.COMPLETED
    self.test_build.result = model.BuildResult.SUCCESS
    self.test_build.put()
    with self.assertRaises(service.InvalidBuildStateError):
      self.service.start(self.test_build.key.id(), 42)

  @contextlib.contextmanager
  def callback_test(self):
    self.test_build.callback = model.Callback(
        url = '/tasks/notify',
        queue_name='default',
    )
    self.test_build.put()
    yield
    taskq = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
    tasks = taskq.GetTasks('default')
    self.assertTrue(
        any(t.get('url') == self.test_build.callback.url for t in tasks))

  def test_start_creates_notification_task(self):
    self.lease()
    with self.callback_test():
      self.start()

  ################################## HEARTBEAT #################################

  def test_heartbeat(self):
    self.lease()
    new_expiration_date = utils.utcnow() + datetime.timedelta(minutes=1)
    build = self.service.heartbeat(
        self.test_build.key.id(), self.test_build.lease_key,
        lease_expiration_date=new_expiration_date)
    self.assertEqual(build.lease_expiration_date, new_expiration_date)

  def test_heartbeat_without_expiration_date(self):
    self.lease()
    with self.assertRaises(service.InvalidInputError):
      self.service.heartbeat(
          self.test_build.key.id(), self.test_build.lease_key,
          lease_expiration_date=None)

  ################################### COMPLETE #################################

  def succeed(self):
    self.test_build = self.service.succeed(
        self.test_build.key.id(), self.test_build.lease_key)

  def test_succeed(self):
    self.lease()
    self.start()
    self.succeed()
    self.assertEqual(self.test_build.status, model.BuildStatus.COMPLETED)
    self.assertEqual(self.test_build.result, model.BuildResult.SUCCESS)

  def test_succeed_timed_out_build(self):
    self.test_build.status = model.BuildStatus.COMPLETED
    self.test_build.result = model.BuildResult.CANCELED
    self.test_build.cancelation_reason = model.CancelationReason.TIMEOUT
    self.test_build.put()
    with self.assertRaises(service.InvalidBuildStateError):
      self.service.succeed(self.test_build.key.id(), 42)

  def test_succeed_is_idempotent(self):
    self.lease()
    self.start()
    build_id = self.test_build.key.id()
    lease_key = self.test_build.lease_key
    self.service.succeed(build_id, lease_key)
    self.service.succeed(build_id, lease_key)

  def test_fail(self):
    self.lease()
    self.start()
    self.test_build = self.service.fail(
        self.test_build.key.id(), self.test_build.lease_key)
    self.assertEqual(self.test_build.status, model.BuildStatus.COMPLETED)
    self.assertEqual(self.test_build.result, model.BuildResult.FAILURE)

  def test_fail_with_details(self):
    self.lease()
    self.start()
    result_details = {'transient_failure': True}
    self.test_build = self.service.fail(
        self.test_build.key.id(), self.test_build.lease_key,
        result_details=result_details)
    self.assertEqual(self.test_build.result_details, result_details)

  def test_complete_not_started_build(self):
    self.lease()
    with self.assertRaises(service.InvalidBuildStateError):
      self.succeed()

  def test_completion_callback_works(self):
    self.lease()
    self.start()
    with self.callback_test():
      self.succeed()

  ########################## RESET EXPIRED BUILDS ##############################

  def test_reschedule_expired_builds(self):
    self.test_build.lease_expiration_date = utils.utcnow()
    self.test_build.lease_key = 1
    self.test_build.leasee = self.current_identity
    self.test_build.put()

    self.service.reset_expired_builds()
    build = self.test_build.key.get()
    self.assertEqual(build.status, model.BuildStatus.SCHEDULED)
    self.assertIsNone(build.lease_key)

  def test_completed_builds_are_not_reset(self):
    self.test_build.status = model.BuildStatus.COMPLETED
    self.test_build.result = model.BuildResult.SUCCESS
    self.test_build.put()
    self.service.reset_expired_builds()
    build = self.test_build.key.get()
    self.assertEqual(build.status, model.BuildStatus.COMPLETED)
