# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import datetime
import json

from components import auth
from components import net
from components import utils
from google.appengine.ext import ndb
from testing_utils import testing
import mock

from proto import common_pb2
from proto.config import project_config_pb2
from proto.config import service_config_pb2
from test.test_util import future, future_exception
import api_common
import config
import errors
import model
import notifications
import search
import service
import swarming
import user
import v2


class BuildBucketServiceTest(testing.AppengineTestCase):

  def __init__(self, *args, **kwargs):
    super(BuildBucketServiceTest, self).__init__(*args, **kwargs)
    self.test_build = None

  def setUp(self):
    super(BuildBucketServiceTest, self).setUp()
    user.clear_request_cache()

    self.current_identity = auth.Identity('service', 'unittest')
    self.patch(
        'components.auth.get_current_identity',
        side_effect=lambda: self.current_identity
    )
    self.patch('user.can_async', return_value=future(True))
    self.patch(
        'user.get_acessible_buckets_async',
        autospec=True,
        return_value=future(['chromium']),
    )
    self.now = datetime.datetime(2015, 1, 1)
    self.patch('components.utils.utcnow', side_effect=lambda: self.now)

    self.chromium_bucket = project_config_pb2.Bucket(name='chromium')
    self.chromium_project_id = 'test'
    self.chromium_swarming = project_config_pb2.Swarming(
        hostname='chromium-swarm.appspot.com',
        builders=[
            project_config_pb2.Builder(
                name='infra',
                dimensions=['pool:default'],
                build_numbers=project_config_pb2.YES,
                recipe=project_config_pb2.Builder.Recipe(
                    repository='https://example.com',
                    name='presubmit',
                ),
            ),
        ],
    )
    self.patch(
        'config.get_bucket_async',
        return_value=future(('project', self.chromium_bucket))
    )
    self.patch('swarming.cancel_task_async', return_value=future(None))

    self.test_build = model.Build(
        id=model.create_build_ids(self.now, 1)[0],
        bucket='chromium',
        project=self.chromium_project_id,
        create_time=self.now,
        parameters={
            model.BUILDER_PARAMETER:
                'infra',
            'changes': [{
                'author': 'nodir@google.com',
                'message': 'buildbucket: initial commit'
            }],
        },
        canary=False,
    )

    self.patch(
        'google.appengine.api.app_identity.get_default_version_hostname',
        autospec=True,
        return_value='buildbucket.example.com'
    )

    self.patch(
        'notifications.enqueue_tasks_async',
        autospec=True,
        return_value=future(None)
    )
    self.patch(
        'bq.enqueue_pull_task_async', autospec=True, return_value=future(None)
    )
    self.patch(
        'config.get_settings_async',
        autospec=True,
        return_value=future(service_config_pb2.SettingsCfg())
    )

    self.patch('search.TagIndex.random_shard_index', return_value=0)

  def mock_cannot(self, action, bucket=None):

    def can_async(requested_bucket, requested_action, _identity=None):
      match = (
          requested_action == action and
          (bucket is None or requested_bucket == bucket)
      )
      return future(not match)

    # user.can_async is patched in setUp()
    user.can_async.side_effect = can_async

  def put_many_builds(self, count=100, tags=None):
    tags = tags or []
    builds = []
    for _ in xrange(count):
      b = model.Build(
          id=model.create_build_ids(self.now, 1)[0],
          bucket=self.test_build.bucket,
          tags=tags,
          create_time=self.now
      )
      self.now += datetime.timedelta(seconds=1)
      builds.append(b)
    ndb.put_multi(builds)
    return builds

  #################################### GET #####################################

  def test_get(self):
    self.test_build.put()
    build = service.get_async(self.test_build.key.id()).get_result()
    self.assertEqual(build, self.test_build)

  def test_get_nonexistent_build(self):
    self.assertIsNone(service.get_async(42).get_result())

  def test_get_with_auth_error(self):
    self.mock_cannot(user.Action.VIEW_BUILD)
    self.test_build.put()
    with self.assertRaises(auth.AuthorizationError):
      service.get_async(self.test_build.key.id()).get_result()

  ################################### CANCEL ###################################

  def test_cancel(self):
    self.test_build.put()
    build = service.cancel(self.test_build.key.id())
    self.assertEqual(build.status, model.BuildStatus.COMPLETED)
    self.assertEqual(build.status_changed_time, utils.utcnow())
    self.assertEqual(build.complete_time, utils.utcnow())
    self.assertEqual(build.result, model.BuildResult.CANCELED)
    self.assertEqual(
        build.cancelation_reason, model.CancelationReason.CANCELED_EXPLICITLY
    )

  def test_cancel_is_idempotent(self):
    self.test_build.put()
    service.cancel(self.test_build.key.id())
    service.cancel(self.test_build.key.id())

  def test_cancel_started_build(self):
    self.lease()
    self.start()
    service.cancel(self.test_build.key.id())

  def test_cancel_nonexistent_build(self):
    with self.assertRaises(errors.BuildNotFoundError):
      service.cancel(1)

  def test_cancel_with_auth_error(self):
    self.test_build.put()
    self.mock_cannot(user.Action.CANCEL_BUILD)
    with self.assertRaises(auth.AuthorizationError):
      service.cancel(self.test_build.key.id())

  def test_cancel_completed_build(self):
    self.test_build.status = model.BuildStatus.COMPLETED
    self.test_build.result = model.BuildResult.SUCCESS
    self.test_build.complete_time = utils.utcnow()
    self.test_build.put()
    with self.assertRaises(errors.BuildIsCompletedError):
      service.cancel(self.test_build.key.id())

  @mock.patch('swarming.cancel_task_transactionally_async', autospec=True)
  def test_cancel_swarmbucket_build(self, cancel_task_async):
    cancel_task_async.return_value = future(None)
    self.test_build.swarming_hostname = 'chromium-swarm.appspot.com'
    self.test_build.swarming_task_id = 'deadbeef'
    self.test_build.put()
    service.cancel(self.test_build.key.id())
    cancel_task_async.assert_called_with(
        'chromium-swarm.appspot.com', 'deadbeef'
    )

  def test_cancel_result_details(self):
    self.test_build.put()
    result_details = {'message': 'bye bye build'}
    build = service.cancel(
        self.test_build.key.id(), result_details=result_details
    )
    self.assertEqual(build.result_details, result_details)

  def test_peek(self):
    self.test_build.put()
    builds, _ = service.peek(buckets=[self.test_build.bucket])
    self.assertEqual(builds, [self.test_build])

  def test_peek_multi(self):
    self.test_build.key = ndb.Key(model.Build, 10)
    self.test_build.put()
    # We test that peek returns builds in decreasing order of the build key. The
    # build key is derived from the inverted current time, so later builds get
    # smaller ids. Only exception: if the time is the same, randomness decides
    # the order. So artificially create an id here to avoid flakiness.
    build2 = model.Build(id=self.test_build.key.id() - 1, bucket='bucket2')
    build2.put()
    builds, _ = service.peek(buckets=[self.test_build.bucket, 'bucket2'])
    self.assertEqual(builds, [self.test_build, build2])

  def test_peek_with_paging(self):
    self.put_many_builds()
    first_page, next_cursor = service.peek(buckets=[self.test_build.bucket])
    self.assertTrue(first_page)
    self.assertTrue(next_cursor)

    second_page, _ = service.peek(
        buckets=[self.test_build.bucket], start_cursor=next_cursor
    )

    self.assertTrue(all(b not in second_page for b in first_page))

  def test_peek_with_bad_cursor(self):
    self.put_many_builds()
    with self.assertRaises(errors.InvalidInputError):
      service.peek(buckets=[self.test_build.bucket], start_cursor='abc')

  def test_peek_without_buckets(self):
    with self.assertRaises(errors.InvalidInputError):
      service.peek(buckets=[])

  def test_peek_with_auth_error(self):
    self.mock_cannot(user.Action.SEARCH_BUILDS)
    self.test_build.put()
    with self.assertRaises(auth.AuthorizationError):
      service.peek(buckets=[self.test_build.bucket])

  def test_peek_does_not_return_leased_builds(self):
    self.test_build.put()
    self.lease()
    builds, _ = service.peek([self.test_build.bucket])
    self.assertFalse(builds)

  def test_peek_200_builds(self):
    for _ in xrange(200):
      model.Build(bucket=self.test_build.bucket).put()
    builds, _ = service.peek([self.test_build.bucket], max_builds=200)
    self.assertTrue(len(builds) <= 100)

  #################################### LEASE ###################################

  def lease(self, lease_expiration_date=None):
    if not (self.test_build.key and self.test_build.key.get()):
      self.test_build.put()
    success, self.test_build = service.lease(
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
    self.mock_cannot(user.Action.LEASE_BUILD)
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
      service.lease(build_id=42)

  def test_leasing_regenerates_lease_key(self):
    orig_lease_key = 42
    self.lease()
    self.assertNotEqual(self.test_build.lease_key, orig_lease_key)

  def test_cannot_lease_completed_build(self):
    build = self.test_build
    build.status = model.BuildStatus.COMPLETED
    build.result = model.BuildResult.SUCCESS
    build.complete_time = utils.utcnow()
    build.put()
    self.assertFalse(self.lease())

  ################################### UNELASE ##################################

  def test_reset(self):
    self.lease()
    build = service.reset(self.test_build.key.id())
    self.assertEqual(build.status, model.BuildStatus.SCHEDULED)
    self.assertEqual(build.status_changed_time, utils.utcnow())
    self.assertIsNone(build.lease_key)
    self.assertIsNone(build.lease_expiration_date)
    self.assertIsNone(build.leasee)
    self.assertIsNone(build.canary)
    self.assertTrue(self.lease())

  def test_reset_is_idempotent(self):
    self.lease()
    build_id = self.test_build.key.id()
    service.reset(build_id)
    service.reset(build_id)

  def test_reset_completed_build(self):
    self.test_build.status = model.BuildStatus.COMPLETED
    self.test_build.result = model.BuildResult.SUCCESS
    self.test_build.complete_time = utils.utcnow()
    self.test_build.put()

    with self.assertRaises(errors.BuildIsCompletedError):
      service.reset(self.test_build.key.id())

  def test_cannot_reset_nonexistent_build(self):
    with self.assertRaises(errors.BuildNotFoundError):
      service.reset(123)

  def test_reset_with_auth_error(self):
    self.lease()
    self.mock_cannot(user.Action.RESET_BUILD)
    with self.assertRaises(auth.AuthorizationError):
      service.reset(self.test_build.key.id())

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

  def start(self, url=None, lease_key=None, canary=False):
    self.test_build = service.start(
        self.test_build.key.id(), lease_key or self.test_build.lease_key, url,
        canary
    )

  def test_start(self):
    self.lease()
    self.start(url='http://localhost', canary=True)
    self.assertEqual(self.test_build.status, model.BuildStatus.STARTED)
    self.assertEqual(self.test_build.url, 'http://localhost')
    self.assertEqual(self.test_build.start_time, self.now)
    self.assertTrue(self.test_build.canary)

  def test_start_started_build(self):
    self.lease()
    build_id = self.test_build.key.id()
    lease_key = self.test_build.lease_key
    url = 'http://localhost/'

    service.start(build_id, lease_key, url, False)
    service.start(build_id, lease_key, url, False)
    service.start(build_id, lease_key, url + '1', False)

  def test_start_non_leased_build(self):
    self.test_build.put()
    with self.assertRaises(errors.LeaseExpiredError):
      service.start(self.test_build.key.id(), 42, None, False)

  def test_start_completed_build(self):
    self.test_build.status = model.BuildStatus.COMPLETED
    self.test_build.result = model.BuildResult.SUCCESS
    self.test_build.complete_time = utils.utcnow()
    self.test_build.put()
    with self.assertRaises(errors.BuildIsCompletedError):
      service.start(self.test_build.key.id(), 42, None, False)

  def test_start_without_lease_key(self):
    with self.assertRaises(errors.InvalidInputError):
      service.start(1, None, None, False)

  @contextlib.contextmanager
  def callback_test(self):
    self.test_build.key = ndb.Key(model.Build, 1)
    self.test_build.pubsub_callback = model.PubSubCallback(
        topic='projects/example/topics/buildbucket',
        user_data='hello',
        auth_token='secret',
    )
    self.test_build.put()
    yield
    notifications.enqueue_tasks_async.assert_called_with(
        'backend-default', [
            {
                'url':
                    '/internal/task/buildbucket/notify/1',
                'payload':
                    json.dumps({
                        'id': 1,
                        'mode': 'global',
                    }, sort_keys=True),
                'age_limit_sec':
                    model.BUILD_TIMEOUT.total_seconds(),
            },
            {
                'url':
                    '/internal/task/buildbucket/notify/1',
                'payload':
                    json.dumps({
                        'id': 1,
                        'mode': 'callback',
                    }, sort_keys=True),
                'age_limit_sec':
                    model.BUILD_TIMEOUT.total_seconds(),
            },
        ]
    )

  def test_start_creates_notification_task(self):
    self.lease()
    with self.callback_test():
      self.start()

  ################################## HEARTBEAT #################################

  def test_heartbeat(self):
    self.lease()
    new_expiration_date = utils.utcnow() + datetime.timedelta(minutes=1)
    build = service.heartbeat(
        self.test_build.key.id(),
        self.test_build.lease_key,
        lease_expiration_date=new_expiration_date
    )
    self.assertEqual(build.lease_expiration_date, new_expiration_date)

  def test_heartbeat_completed(self):
    self.test_build.status = model.BuildStatus.COMPLETED
    self.test_build.result = model.BuildResult.CANCELED
    self.test_build.cancelation_reason = (
        model.CancelationReason.CANCELED_EXPLICITLY
    )
    self.test_build.complete_time = utils.utcnow()
    self.test_build.put()

    new_expiration_date = utils.utcnow() + datetime.timedelta(minutes=1)
    with self.assertRaises(errors.BuildIsCompletedError):
      service.heartbeat(
          self.test_build.key.id(),
          0,
          lease_expiration_date=new_expiration_date
      )

  def test_heartbeat_timed_out(self):
    self.test_build.status = model.BuildStatus.COMPLETED
    self.test_build.result = model.BuildResult.CANCELED
    self.test_build.cancelation_reason = model.CancelationReason.TIMEOUT
    self.test_build.complete_time = utils.utcnow()
    self.test_build.put()

    new_expiration_date = utils.utcnow() + datetime.timedelta(minutes=1)
    exc_regex = (
        'Build was marked as timed out '
        'because it did not complete for 2 days'
    )
    with self.assertRaisesRegexp(errors.BuildIsCompletedError, exc_regex):
      service.heartbeat(
          self.test_build.key.id(),
          0,
          lease_expiration_date=new_expiration_date
      )

  def test_heartbeat_batch(self):
    self.lease()
    new_expiration_date = utils.utcnow() + datetime.timedelta(minutes=1)
    results = service.heartbeat_batch([
        {
            'build_id': self.test_build.key.id(),
            'lease_key': self.test_build.lease_key,
            'lease_expiration_date': new_expiration_date,
        },
        {
            'build_id': 42,
            'lease_key': 42,
            'lease_expiration_date': new_expiration_date,
        },
    ])

    self.assertEqual(len(results), 2)

    self.test_build = self.test_build.key.get()
    self.assertEqual(
        results[0], (self.test_build.key.id(), self.test_build, None)
    )

    self.assertIsNone(results[1][1])
    self.assertTrue(isinstance(results[1][2], errors.BuildNotFoundError))

  def test_heartbeat_without_expiration_date(self):
    self.lease()
    with self.assertRaises(errors.InvalidInputError):
      service.heartbeat(
          self.test_build.key.id(),
          self.test_build.lease_key,
          lease_expiration_date=None
      )

  ################################### COMPLETE #################################

  def succeed(self, **kwargs):
    self.test_build = service.succeed(
        self.test_build.key.id(), self.test_build.lease_key, **kwargs
    )

  def test_succeed(self):
    self.lease()
    self.start()
    self.succeed()
    self.assertEqual(self.test_build.status, model.BuildStatus.COMPLETED)
    self.assertEqual(self.test_build.status_changed_time, utils.utcnow())
    self.assertEqual(self.test_build.result, model.BuildResult.SUCCESS)
    self.assertIsNotNone(self.test_build.complete_time)

  def test_succeed_timed_out_build(self):
    self.test_build.status = model.BuildStatus.COMPLETED
    self.test_build.result = model.BuildResult.CANCELED
    self.test_build.cancelation_reason = model.CancelationReason.TIMEOUT
    self.test_build.complete_time = utils.utcnow()
    self.test_build.put()
    with self.assertRaises(errors.BuildIsCompletedError):
      service.succeed(self.test_build.key.id(), 42)

  def test_succeed_is_idempotent(self):
    self.lease()
    self.start()
    build_id = self.test_build.key.id()
    lease_key = self.test_build.lease_key
    service.succeed(build_id, lease_key)
    service.succeed(build_id, lease_key)

  def test_succeed_with_new_tags(self):
    self.test_build.tags = ['a:1']
    self.test_build.put()
    self.lease()
    self.start()
    self.succeed(new_tags=['b:2'])
    self.assertEqual(self.test_build.tags, ['a:1', 'b:2'])

  def test_fail(self):
    self.lease()
    self.start()
    self.test_build = service.fail(
        self.test_build.key.id(), self.test_build.lease_key
    )
    self.assertEqual(self.test_build.status, model.BuildStatus.COMPLETED)
    self.assertEqual(self.test_build.status_changed_time, utils.utcnow())
    self.assertEqual(self.test_build.result, model.BuildResult.FAILURE)
    self.assertIsNotNone(self.test_build.complete_time)

  def test_fail_with_details(self):
    self.lease()
    self.start()
    result_details = {'transient_failure': True}
    self.test_build = service.fail(
        self.test_build.key.id(),
        self.test_build.lease_key,
        result_details=result_details
    )
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

  def test_completion_creates_notification_task(self):
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

    service.check_expired_builds()
    build = self.test_build.key.get()
    self.assertEqual(build.status, model.BuildStatus.SCHEDULED)
    self.assertIsNone(build.lease_key)

  def test_completed_builds_are_not_reset(self):
    self.test_build.status = model.BuildStatus.COMPLETED
    self.test_build.result = model.BuildResult.SUCCESS
    self.test_build.complete_time = utils.utcnow()
    self.test_build.put()
    service.check_expired_builds()
    build = self.test_build.key.get()
    self.assertEqual(build.status, model.BuildStatus.COMPLETED)

  def test_build_timeout(self):
    self.test_build.create_time = utils.utcnow() - datetime.timedelta(days=365)
    self.test_build.put()

    service.check_expired_builds()
    build = self.test_build.key.get()
    self.assertEqual(build.status, model.BuildStatus.COMPLETED)
    self.assertEqual(build.result, model.BuildResult.CANCELED)
    self.assertEqual(build.cancelation_reason, model.CancelationReason.TIMEOUT)
    self.assertIsNone(build.lease_key)

  ########################## RESET EXPIRED BUILDS ##############################

  def test_delete_many_scheduled_builds(self):
    self.test_build.put()
    completed_build = model.Build(
        bucket=self.test_build.bucket,
        status=model.BuildStatus.COMPLETED,
        result=model.BuildResult.SUCCESS,
        create_time=utils.utcnow(),
        complete_time=utils.utcnow() + datetime.timedelta(seconds=1),
        canary=False,
    )
    completed_build.put()
    self.assertIsNotNone(self.test_build.key.get())
    self.assertIsNotNone(completed_build.key.get())
    service._task_delete_many_builds(
        self.test_build.bucket, model.BuildStatus.SCHEDULED
    )
    self.assertIsNone(self.test_build.key.get())
    self.assertIsNotNone(completed_build.key.get())

  def test_delete_many_started_builds(self):
    self.test_build.put()

    started_build = model.Build(
        bucket=self.test_build.bucket,
        status=model.BuildStatus.STARTED,
        create_time=utils.utcnow(),
        start_time=utils.utcnow(),
        canary=False,
    )
    started_build.put()

    completed_build = model.Build(
        bucket=self.test_build.bucket,
        status=model.BuildStatus.COMPLETED,
        result=model.BuildResult.SUCCESS,
        create_time=utils.utcnow(),
        complete_time=utils.utcnow(),
        canary=False,
    )
    completed_build.put()

    service._task_delete_many_builds(
        self.test_build.bucket, model.BuildStatus.STARTED
    )
    self.assertIsNotNone(self.test_build.key.get())
    self.assertIsNone(started_build.key.get())
    self.assertIsNotNone(completed_build.key.get())

  def test_delete_many_builds_with_tags(self):
    self.test_build.tags = ['tag:1']
    self.test_build.put()

    service._task_delete_many_builds(
        self.test_build.bucket, model.BuildStatus.SCHEDULED, tags=['tag:0']
    )
    self.assertIsNotNone(self.test_build.key.get())

    service._task_delete_many_builds(
        self.test_build.bucket, model.BuildStatus.SCHEDULED, tags=['tag:1']
    )
    self.assertIsNone(self.test_build.key.get())

  def test_delete_many_builds_created_by(self):
    self.test_build.created_by = auth.Identity('user', 'nodir@google.com')
    self.test_build.put()
    other_build = model.Build(bucket=self.test_build.bucket)
    other_build.put()

    service._task_delete_many_builds(
        self.test_build.bucket,
        model.BuildStatus.SCHEDULED,
        created_by='nodir@google.com'
    )
    self.assertIsNone(self.test_build.key.get())
    self.assertIsNotNone(other_build.key.get())

  def test_delete_many_builds_auth_error(self):
    self.mock_cannot(user.Action.DELETE_SCHEDULED_BUILDS)
    with self.assertRaises(auth.AuthorizationError):
      service.delete_many_builds(
          self.test_build.bucket, model.BuildStatus.SCHEDULED
      )

  def test_delete_many_builds_schedule_task(self):
    service.delete_many_builds(
        self.test_build.bucket, model.BuildStatus.SCHEDULED
    )

  def test_delete_many_completed_builds(self):
    with self.assertRaises(errors.InvalidInputError):
      service.delete_many_builds(
          self.test_build.bucket, model.BuildStatus.COMPLETED
      )

  @mock.patch('swarming.cancel_task_transactionally_async', autospec=True)
  def test_delete_many_swarmbucket_builds(self, cancel_task_async):
    cancel_task_async.return_value = future(None)
    self.test_build.swarming_hostname = 'swarming.example.com'
    self.test_build.swarming_task_id = 'deadbeef'
    self.test_build.put()

    service._task_delete_many_builds(
        self.test_build.bucket, model.BuildStatus.SCHEDULED
    )

    cancel_task_async.assert_called_with('swarming.example.com', 'deadbeef')

  ################################ PAUSE BUCKET ################################

  def test_pause_bucket(self):
    self.test_build.bucket = 'foo'
    self.put_many_builds(5)

    self.test_build.bucket = 'bar'
    self.put_many_builds(5)

    service.pause('foo', True)
    builds, _ = service.peek(['foo', 'bar'])
    self.assertEqual(len(builds), 5)
    self.assertFalse(any(b.bucket == 'foo' for b in builds))

  def test_pause_all_requested_buckets(self):
    self.test_build.bucket = 'foo'
    self.put_many_builds(5)

    service.pause('foo', True)
    builds, _ = service.peek(['foo'])
    self.assertEqual(len(builds), 0)

  def test_pause_then_unpause(self):
    self.test_build.bucket = 'foo'
    self.test_build.put()

    service.pause('foo', True)
    service.pause('foo', True)  # Again, to cover equality case.
    builds, _ = service.peek(['foo'])
    self.assertEqual(len(builds), 0)

    service.pause('foo', False)
    builds, _ = service.peek(['foo'])
    self.assertEqual(len(builds), 1)

  def test_pause_bucket_invalid_bucket_name(self):
    with self.assertRaises(errors.InvalidInputError):
      service.pause('wharbl|gharbl', True)

  def test_pause_bucket_auth_error(self):
    self.mock_cannot(user.Action.PAUSE_BUCKET)
    with self.assertRaises(auth.AuthorizationError):
      service.pause('test', True)

  def test_pause_invalid_bucket(self):
    config.get_bucket_async.return_value = future((None, None))
    with self.assertRaises(errors.InvalidInputError):
      service.pause('test', True)

  def test_pause_swarming_bucket(self):
    self.chromium_bucket.swarming.MergeFrom(self.chromium_swarming)
    with self.assertRaises(errors.InvalidInputError):
      service.pause('test', True)

  ############################ UNREGISTER BUILDERS #############################

  def test_unregister_builders(self):
    model.Builder(
        id='chromium:try:linux_rel',
        last_scheduled=self.now - datetime.timedelta(weeks=8),
    ).put()
    service.unregister_builders()
    builders = model.Builder.query().fetch()
    self.assertFalse(builders)
