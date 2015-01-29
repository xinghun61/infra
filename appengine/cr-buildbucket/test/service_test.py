# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import datetime
import json

from components import auth
from components import utils
from google.appengine.ext import testbed
from testing_utils import testing
import mock

import acl
import errors
import model
import service


class BuildBucketServiceTest(testing.AppengineTestCase):
  def __init__(self, *args, **kwargs):
    super(BuildBucketServiceTest, self).__init__(*args, **kwargs)
    self.test_build = None

  def mock_acls(self):
    ops = [
        'add_build',
        'search_builds',
        'lease_build',
        'cancel_build',
        'view_build',
        'reset_build',
    ]
    for op in ops:
      self.mock(acl, 'can_%s' % op, lambda *_, **__: True)

  def mock_cannot(self, operation):
    self.mock(acl, 'can_%s' % operation, lambda *_, **__: False)

  def setUp(self):
    super(BuildBucketServiceTest, self).setUp()
    self.service = service.BuildBucketService()
    self.test_build = model.Build(
        bucket='chromium',
        parameters={
            'buildername': 'infra',
            'changes': [{
                'author': 'nodir@google.com',
                'message': 'buildbucket: initial commit'
            }]
        }
    )

    self.current_identity = auth.Identity('service', 'unittest')
    self.mock(auth, 'get_current_identity', lambda: self.current_identity)
    self.mock_acls()

  def put_many_builds(self):
    for _ in xrange(100):
      b = model.Build(bucket=self.test_build.bucket)
      b.put()

  #################################### ADD #####################################

  def test_add(self):
    params = {'buildername': 'linux_rel'}
    build = self.service.add(
        bucket='chromium',
        parameters=params,
    )
    self.assertIsNotNone(build.key)
    self.assertIsNotNone(build.key.id())
    self.assertEqual(build.bucket, 'chromium')
    self.assertEqual(build.parameters, params)
    self.assertEqual(build.created_by, auth.get_current_identity())

  def test_add_with_bad_bucket_name(self):
    with self.assertRaises(errors.InvalidInputError):
      self.service.add(bucket='chromium as')
    with self.assertRaises(errors.InvalidInputError):
      self.service.add(bucket='')

  def test_add_with_leasing(self):
    build = self.service.add(
        bucket='chromium',
        lease_expiration_date=utils.utcnow () + datetime.timedelta(seconds=10),
    )
    self.assertTrue(build.is_leased)
    self.assertGreater(build.lease_expiration_date, utils.utcnow())
    self.assertIsNotNone(build.lease_key)

  def test_add_with_auth_error(self):
    self.mock_cannot('add_build')
    with self.assertRaises(auth.AuthorizationError):
      self.service.add(self.test_build.bucket)

  #################################### GET #####################################

  def test_get(self):
    self.test_build.put()
    build = self.service.get(self.test_build.key.id())
    self.assertEqual(build, self.test_build)

  def test_get_nonexistent_build(self):
    self.assertIsNone(self.service.get(42))

  def test_get_with_auth_error(self):
    self.mock_cannot('view_build')
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
    with self.assertRaises(errors.BuildNotFoundError):
      self.service.cancel(1)

  def test_cancel_with_auth_error(self):
    self.test_build.put()
    self.mock_cannot('cancel_build')
    with self.assertRaises(auth.AuthorizationError):
      self.service.cancel(self.test_build.key.id())

  def test_cancel_completed_build(self):
    self.test_build.status = model.BuildStatus.COMPLETED
    self.test_build.result = model.BuildResult.SUCCESS
    self.test_build.put()
    with self.assertRaises(errors.InvalidBuildStateError):
      self.service.cancel(self.test_build.key.id())

  #################################### SEARCH ##################################

  def test_search(self):
    build2 = model.Build(bucket=self.test_build.bucket)
    build2.put()

    self.test_build.tags = ['important:true']
    self.test_build.put()
    builds, _ = self.service.search(
        buckets=[self.test_build.bucket],
        tags=self.test_build.tags,
    )
    self.assertEqual(builds, [self.test_build])

  def test_search_many_tags(self):
    self.test_build.tags = ['important:true', 'author:ivan']
    self.test_build.put()
    build2 = model.Build(
        bucket=self.test_build.bucket,
        tags=self.test_build.tags[:1],  # only one of two tags.
    )
    build2.put()

    # Search by both tags.
    builds, _ = self.service.search(
        buckets=[self.test_build.bucket],
        tags=self.test_build.tags,
    )
    self.assertEqual(builds, [self.test_build])

  def test_search_bucket(self):
    self.test_build.put()
    build2 = model.Build(
        bucket='other bucket',
    )
    build2.put()

    builds, _ = self.service.search(buckets=[self.test_build.bucket])
    self.assertEqual(builds, [self.test_build])

  def test_search_with_paging(self):
    self.put_many_builds()

    first_page, next_cursor = self.service.search(
        buckets=[self.test_build.bucket],
        max_builds=10,
    )
    self.assertEqual(len(first_page), 10)
    self.assertTrue(next_cursor)

    second_page, _ = self.service.search(
        buckets=[self.test_build.bucket],
        max_builds=10,
        start_cursor=next_cursor)
    self.assertEqual(len(second_page), 10)
    self.assertTrue(any(new not in first_page for new in second_page))

  def test_search_with_bad_tags(self):
    def test_bad_tag(tags):
      with self.assertRaises(errors.InvalidInputError):
        self.service.search(buckets=['bucket'], tags=tags)
    test_bad_tag(['x'])
    test_bad_tag([1])
    test_bad_tag({})
    test_bad_tag(1)

  def test_search_with_bad_buckets(self):
    with self.assertRaises(errors.InvalidInputError):
      self.service.search(buckets={})
    with self.assertRaises(errors.InvalidInputError):
      self.service.search(buckets=[1])

  def test_search_with_non_number_max_builds(self):
    with self.assertRaises(errors.InvalidInputError):
      self.service.search(buckets=['b'], tags=['a:b'], max_builds='a')

  def test_search_with_negative_max_builds(self):
    with self.assertRaises(errors.InvalidInputError):
      self.service.search(buckets=['b'], tags=['a:b'], max_builds=-2)

  #################################### PEEK ####################################

  def test_peek(self):
    self.test_build.put()
    builds, _ = self.service.peek(buckets=[self.test_build.bucket])
    self.assertEqual(builds, [self.test_build])

  def test_peek_with_paging(self):
    self.put_many_builds()
    first_page, next_cursor = self.service.peek(
        buckets=[self.test_build.bucket])
    self.assertTrue(first_page)
    self.assertTrue(next_cursor)

    second_page, _ = self.service.peek(
        buckets=[self.test_build.bucket], start_cursor=next_cursor)

    self.assertTrue(all(b not in second_page for b in first_page))

  def test_peek_with_bad_cursor(self):
    self.put_many_builds()
    with self.assertRaises(errors.InvalidInputError):
      self.service.peek(buckets=[self.test_build.bucket], start_cursor='abc')

  def test_peek_without_buckets(self):
    with self.assertRaises(errors.InvalidInputError):
      self.service.peek(buckets=[])

  def test_peek_with_auth_error(self):
    self.mock_cannot('search_builds')
    self.test_build.put()
    with self.assertRaises(auth.AuthorizationError):
      self.service.peek(buckets=[self.test_build.bucket])

  def test_peek_does_not_return_leased_builds(self):
    self.test_build.put()
    self.lease()
    builds, _ = self.service.peek([self.test_build.bucket])
    self.assertFalse(builds)

  def test_peek_200_builds(self):
    for _ in xrange(200):
      model.Build(bucket=self.test_build.bucket).put()
    builds, _ = self.service.peek([self.test_build.bucket], max_builds=200)
    self.assertTrue(len(builds) <= 100)

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
    self.mock_cannot('lease_build')
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
    with self.assertRaises(errors.BuildNotFoundError):
      self.service.lease(build_id=42)

  def test_cannot_lease_for_whole_day(self):
    with self.assertRaises(errors.InvalidInputError):
      self.lease(
          lease_expiration_date=utils.utcnow() + datetime.timedelta(days=1))

  def test_cannot_set_expiration_date_to_past(self):
    with self.assertRaises(errors.InvalidInputError):
      yesterday = utils.utcnow() - datetime.timedelta(days=1)
      self.lease(lease_expiration_date=yesterday)

  def test_cannot_lease_with_non_datetime_expiration_date(self):
    with self.assertRaises(errors.InvalidInputError):
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

  def test_reset(self):
    self.lease()
    build = self.service.reset(self.test_build.key.id())
    self.assertEqual(build.status, model.BuildStatus.SCHEDULED)
    self.assertIsNone(build.lease_key)
    self.assertIsNone(build.lease_expiration_date)
    self.assertIsNone(build.leasee)
    self.assertTrue(self.lease())

  def test_reset_is_idempotent(self):
    self.lease()
    build_id = self.test_build.key.id()
    self.service.reset(build_id)
    self.service.reset(build_id)

  def test_reset_completed_build(self):
    self.test_build.status = model.BuildStatus.COMPLETED
    self.test_build.result = model.BuildResult.SUCCESS
    self.test_build.put()

    with self.assertRaises(errors.InvalidBuildStateError):
      self.service.reset(self.test_build.key.id())

  def test_cannot_reset_nonexistent_build(self):
    with self.assertRaises(errors.BuildNotFoundError):
      self.service.reset(123)

  def test_reset_with_auth_error(self):
    self.lease()
    self.mock_cannot('reset_build')
    with self.assertRaises(auth.AuthorizationError):
      self.service.reset(self.test_build.key.id())

  #################################### START ###################################

  def test_validate_malformed_url(self):
    with self.assertRaises(errors.InvalidInputError):
      service.validate_url('svn://sdfsf')

  def test_validate_relative_url(self):
    with self.assertRaises(errors.InvalidInputError):
      service.validate_url('sdfsf')

  def test_validate_nonstring_url(self):
    with self.assertRaises(errors.InvalidInputError):
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

  def test_start_started_build(self):
    self.lease()
    build_id = self.test_build.key.id()
    lease_key = self.test_build.lease_key
    url = 'http://localhost/'

    self.service.start(build_id, lease_key, url)
    self.service.start(build_id, lease_key, url)
    self.service.start(build_id, lease_key, url + '1')

  def test_start_non_leased_build(self):
    self.test_build.put()
    with self.assertRaises(errors.LeaseExpiredError):
      self.service.start(self.test_build.key.id(), 42)

  def test_start_completed_build(self):
    self.test_build.status = model.BuildStatus.COMPLETED
    self.test_build.result = model.BuildResult.SUCCESS
    self.test_build.put()
    with self.assertRaises(errors.InvalidBuildStateError):
      self.service.start(self.test_build.key.id(), 42)

  def test_start_without_lease_key(self):
    with self.assertRaises(errors.InvalidInputError):
      self.service.start(1, None)

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
    with self.assertRaises(errors.InvalidInputError):
      self.service.heartbeat(
          self.test_build.key.id(), self.test_build.lease_key,
          lease_expiration_date=None)

  ################################### COMPLETE #################################

  def succeed(self, **kwargs):
    self.test_build = self.service.succeed(
        self.test_build.key.id(), self.test_build.lease_key, **kwargs)

  def test_succeed(self):
    self.lease()
    self.start()
    self.succeed()
    self.assertEqual(self.test_build.status, model.BuildStatus.COMPLETED)
    self.assertEqual(self.test_build.result, model.BuildResult.SUCCESS)
    self.assertIsNotNone(self.test_build.complete_time)

  def test_succeed_timed_out_build(self):
    self.test_build.status = model.BuildStatus.COMPLETED
    self.test_build.result = model.BuildResult.CANCELED
    self.test_build.cancelation_reason = model.CancelationReason.TIMEOUT
    self.test_build.put()
    with self.assertRaises(errors.InvalidBuildStateError):
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
    self.assertIsNotNone(self.test_build.complete_time)

  def test_fail_with_details(self):
    self.lease()
    self.start()
    result_details = {'transient_failure': True}
    self.test_build = self.service.fail(
        self.test_build.key.id(), self.test_build.lease_key,
        result_details=result_details)
    self.assertEqual(self.test_build.result_details, result_details)

  def test_complete_with_url(self):
    self.lease()
    self.start()
    url = 'http://localhost/1'
    self.succeed(url=url)
    self.assertEqual(self.test_build.url, url)

  def test_complete_not_started_build(self):
    self.lease()
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
