# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import datetime

from components import auth
from components import utils
from google.appengine.ext import ndb
from testing_utils import testing
import mock

from proto import build_pb2
from proto import common_pb2
from proto.config import service_config_pb2
from test import test_util
from test.test_util import future
import config
import errors
import model
import notifications
import service
import user


class BuildBucketServiceTest(testing.AppengineTestCase):

  def setUp(self):
    super(BuildBucketServiceTest, self).setUp()
    user.clear_request_cache()

    self.current_identity = auth.Identity('service', 'unittest')
    self.patch(
        'components.auth.get_current_identity',
        side_effect=lambda: self.current_identity
    )
    self.patch('user.can_async', return_value=future(True))
    self.now = datetime.datetime(2015, 1, 1)
    self.patch('components.utils.utcnow', side_effect=lambda: self.now)

    config.put_bucket(
        'chromium',
        'a' * 40,
        test_util.parse_bucket_cfg(
            '''
            name: "try"
            acls {
              role: READER
              identity: "anonymous:anonymous"
            }
            '''
        ),
    )
    config.put_bucket(
        'chromium',
        'a' * 40,
        test_util.parse_bucket_cfg(
            '''
            name: "luci"
            acls {
              role: READER
              identity: "anonymous:anonymous"
            }
            swarming {
              builders {
                name: "linux"
                swarming_host: "chromium-swarm.appspot.com"
                build_numbers: YES
                recipe {
                  cipd_package: "infra/recipe_bundle"
                  cipd_version: "refs/heads/master"
                  name: "recipe"
                }
              }
            }
            '''
        ),
    )

    self.patch('swarming.cancel_task_async', return_value=future(None))

    self.patch(
        'google.appengine.api.app_identity.get_default_version_hostname',
        autospec=True,
        return_value='buildbucket.example.com'
    )

    self.patch('tq.enqueue_async', autospec=True, return_value=future(None))
    self.patch(
        'config.get_settings_async',
        autospec=True,
        return_value=future(service_config_pb2.SettingsCfg())
    )
    self.patch(
        'swarming.cancel_task_transactionally_async',
        autospec=True,
        return_value=future(None)
    )

    self.patch('search.TagIndex.random_shard_index', return_value=0)

  def mock_cannot(self, action, bucket_id=None):

    def can_async(requested_bucket_id, requested_action, _identity=None):
      match = (
          requested_action == action and
          (bucket_id is None or requested_bucket_id == bucket_id)
      )
      return future(not match)

    # user.can_async is patched in setUp()
    user.can_async.side_effect = can_async

  def put_many_builds(self, count=100, **build_proto_fields):
    builds = []
    build_ids = model.create_build_ids(utils.utcnow(), count)
    for build_id in build_ids:
      builds.append(self.classic_build(id=build_id, **build_proto_fields))
      self.now += datetime.timedelta(seconds=1)
    ndb.put_multi(builds)
    return builds

  @staticmethod
  def classic_build(**build_proto_fields):
    build = test_util.build(**build_proto_fields)
    build.infra_bytes = None
    build.is_luci = False
    return build

  #################################### GET #####################################

  def test_get(self):
    self.classic_build(id=1).put()
    build = service.get_async(1).get_result()
    self.assertEqual(build, build)

  def test_get_nonexistent_build(self):
    self.assertIsNone(service.get_async(42).get_result())

  def test_get_with_auth_error(self):
    self.mock_cannot(user.Action.VIEW_BUILD)
    self.classic_build(id=1).put()
    with self.assertRaises(auth.AuthorizationError):
      service.get_async(1).get_result()

  ################################### CANCEL ###################################

  @mock.patch('swarming.cancel_task_async', autospec=True)
  def test_cancel(self, cancel_task_async):
    test_util.build(id=1).put()
    build = service.cancel_async(1, summary_markdown='nope').get_result()
    self.assertEqual(build.proto.status, common_pb2.CANCELED)
    self.assertEqual(build.proto.end_time.ToDatetime(), utils.utcnow())
    self.assertEqual(build.proto.summary_markdown, 'nope')
    self.assertEqual(
        build.proto.cancel_reason,
        build_pb2.CancelReason(canceled_by=self.current_identity.to_bytes()),
    )
    cancel_task_async.assert_called_with('swarming.example.com', 'deadbeef')
    self.assertEqual(build.status_changed_time, utils.utcnow())

  def test_cancel_is_idempotent(self):
    build = self.classic_build(id=1)
    build.put()
    service.cancel_async(1).get_result()
    service.cancel_async(1).get_result()

  def test_cancel_started_build(self):
    self.new_started_build(id=1).put()
    service.cancel_async(1).get_result()

  def test_cancel_nonexistent_build(self):
    with self.assertRaises(errors.BuildNotFoundError):
      service.cancel_async(1).get_result()

  def test_cancel_with_auth_error(self):
    self.new_started_build(id=1)
    self.mock_cannot(user.Action.CANCEL_BUILD)
    with self.assertRaises(auth.AuthorizationError):
      service.cancel_async(1).get_result()

  def test_cancel_completed_build(self):
    build = self.classic_build(id=1, status=common_pb2.SUCCESS)
    build.put()
    with self.assertRaises(errors.BuildIsCompletedError):
      service.cancel_async(1).get_result()

  def test_cancel_result_details(self):
    self.classic_build(id=1).put()
    result_details = {'message': 'bye bye build'}
    build = service.cancel_async(1, result_details=result_details).get_result()
    self.assertEqual(build.result_details, result_details)

  def test_peek(self):
    build = self.classic_build()
    build.put()
    builds, _ = service.peek(bucket_ids=[build.bucket_id])
    self.assertEqual(builds, [build])

  def test_peek_multi(self):
    build1 = self.classic_build(
        id=1,
        builder=dict(project='chromium', bucket='try'),
    )
    build2 = self.classic_build(
        id=2,
        builder=dict(project='chromium', bucket='try'),
    )
    assert build1.bucket_id == build2.bucket_id
    ndb.put_multi([build1, build2])
    builds, _ = service.peek(bucket_ids=['chromium/try'])
    self.assertEqual(builds, [build2, build1])

  def test_peek_with_paging(self):
    self.put_many_builds(builder=dict(project='chromium', bucket='try'))
    first_page, next_cursor = service.peek(
        bucket_ids=['chromium/try'], max_builds=10
    )
    self.assertTrue(first_page)
    self.assertTrue(next_cursor)

    second_page, _ = service.peek(
        bucket_ids=['chromium/try'], start_cursor=next_cursor
    )

    self.assertTrue(all(b not in second_page for b in first_page))

  def test_peek_with_bad_cursor(self):
    self.put_many_builds(builder=dict(project='chromium', bucket='try'))
    with self.assertRaises(errors.InvalidInputError):
      service.peek(bucket_ids=['chromium/try'], start_cursor='abc')

  def test_peek_without_buckets(self):
    with self.assertRaises(errors.InvalidInputError):
      service.peek(bucket_ids=[])

  def test_peek_with_auth_error(self):
    self.mock_cannot(user.Action.SEARCH_BUILDS)
    build = self.classic_build(builder=dict(project='chromium', bucket='try'))
    build.put()
    with self.assertRaises(auth.AuthorizationError):
      service.peek(bucket_ids=['chromium/try'])

  def test_peek_does_not_return_leased_builds(self):
    self.new_leased_build(builder=dict(project='chromium', bucket='try'))
    builds, _ = service.peek(['chromium/try'])
    self.assertFalse(builds)

  #################################### LEASE ###################################

  def lease(self, build_id, lease_expiration_date=None, expect_success=True):
    success, build = service.lease(
        build_id,
        lease_expiration_date=lease_expiration_date,
    )
    self.assertEqual(success, expect_success)
    return build

  def new_leased_build(self, **build_proto_fields):
    build = self.classic_build(**build_proto_fields)
    build.put()
    return self.lease(build.key.id())

  def test_lease(self):
    expiration_date = utils.utcnow() + datetime.timedelta(minutes=1)
    self.classic_build(id=1).put()
    build = self.lease(1, lease_expiration_date=expiration_date)
    self.assertTrue(build.is_leased)
    self.assertGreater(build.lease_expiration_date, utils.utcnow())
    self.assertEqual(build.leasee, self.current_identity)

  def test_lease_build_with_auth_error(self):
    self.mock_cannot(user.Action.LEASE_BUILD)
    self.classic_build(id=1).put()
    with self.assertRaises(auth.AuthorizationError):
      self.lease(1)

  def test_cannot_lease_a_leased_build(self):
    self.new_leased_build(id=1)
    self.lease(1, expect_success=False)

  def test_cannot_lease_a_nonexistent_build(self):
    with self.assertRaises(errors.BuildNotFoundError):
      service.lease(build_id=42)

  def test_cannot_lease_completed_build(self):
    build = self.classic_build(id=1, status=common_pb2.SUCCESS)
    build.put()
    self.lease(1, expect_success=False)

  def test_cannot_lease_luci_build(self):
    build = test_util.build(id=1)
    build.put()
    with self.assertRaises(errors.InvalidInputError):
      self.lease(1)

  ################################### UNELASE ##################################

  def test_reset(self):
    build = self.new_started_build(id=1)
    build = service.reset(1)
    self.assertEqual(build.proto.status, common_pb2.SCHEDULED)
    self.assertEqual(build.status_changed_time, utils.utcnow())
    self.assertIsNone(build.lease_key)
    self.assertIsNone(build.lease_expiration_date)
    self.assertIsNone(build.leasee)
    self.assertIsNone(build.canary)
    self.lease(1)

  def test_reset_is_idempotent(self):
    self.new_leased_build(id=1)
    service.reset(1)
    service.reset(1)

  def test_reset_completed_build(self):
    self.classic_build(id=1, status=common_pb2.SUCCESS).put()
    with self.assertRaises(errors.BuildIsCompletedError):
      service.reset(1)

  def test_cannot_reset_nonexistent_build(self):
    with self.assertRaises(errors.BuildNotFoundError):
      service.reset(123)

  def test_reset_with_auth_error(self):
    self.new_leased_build(id=1)
    self.mock_cannot(user.Action.RESET_BUILD)
    with self.assertRaises(auth.AuthorizationError):
      service.reset(1)

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

  def start(self, build, url=None, lease_key=None, canary=False):
    return service.start(
        build.key.id(), lease_key or build.lease_key, url, canary
    )

  def test_start(self):
    build = self.new_leased_build()
    build = self.start(build, url='http://localhost', canary=True)
    self.assertEqual(build.proto.status, common_pb2.STARTED)
    self.assertEqual(build.url, 'http://localhost')
    self.assertEqual(build.proto.start_time.ToDatetime(), self.now)
    self.assertTrue(build.canary)

  def test_start_started_build(self):
    build = self.new_leased_build(id=1)
    lease_key = build.lease_key
    url = 'http://localhost/'

    service.start(1, lease_key, url, False)
    service.start(1, lease_key, url, False)
    service.start(1, lease_key, url + '1', False)

  def test_start_non_leased_build(self):
    self.classic_build(id=1).put()
    with self.assertRaises(errors.LeaseExpiredError):
      service.start(1, 42, None, False)

  def test_start_completed_build(self):
    self.classic_build(id=1, status=common_pb2.SUCCESS).put()
    with self.assertRaises(errors.BuildIsCompletedError):
      service.start(1, 42, None, False)

  def test_start_without_lease_key(self):
    with self.assertRaises(errors.InvalidInputError):
      service.start(1, None, None, False)

  @contextlib.contextmanager
  def callback_test(self, build):
    with mock.patch('notifications.enqueue_notifications_async', autospec=True):
      notifications.enqueue_notifications_async.return_value = future(None)
      build.pubsub_callback = model.PubSubCallback(
          topic='projects/example/topics/buildbucket',
          user_data='hello',
          auth_token='secret',
      )
      build.put()
      yield
      build = build.key.get()
      notifications.enqueue_notifications_async.assert_called_with(build)

  def test_start_creates_notification_task(self):
    build = self.new_leased_build()
    with self.callback_test(build):
      self.start(build)

  ################################## HEARTBEAT #################################

  def test_heartbeat(self):
    build = self.new_leased_build(id=1)
    new_expiration_date = utils.utcnow() + datetime.timedelta(minutes=1)
    build = service.heartbeat(
        1, build.lease_key, lease_expiration_date=new_expiration_date
    )
    self.assertEqual(build.lease_expiration_date, new_expiration_date)

  def test_heartbeat_completed(self):
    self.classic_build(id=1, status=common_pb2.CANCELED).put()
    new_expiration_date = utils.utcnow() + datetime.timedelta(minutes=1)
    with self.assertRaises(errors.BuildIsCompletedError):
      service.heartbeat(1, 0, lease_expiration_date=new_expiration_date)

  def test_heartbeat_resource_exhaustion(self):
    build = self.classic_build(
        id=1,
        status=common_pb2.INFRA_FAILURE,
        infra_failure_reason=dict(resource_exhaustion=True),
    )
    build.put()

    new_expiration_date = utils.utcnow() + datetime.timedelta(minutes=1)
    exc_regex = (
        'Build was marked as timed out '
        'because it did not complete for 2 days'
    )
    with self.assertRaisesRegexp(errors.BuildIsCompletedError, exc_regex):
      service.heartbeat(1, 0, lease_expiration_date=new_expiration_date)

  def test_heartbeat_batch(self):
    build = self.new_leased_build(id=1)
    new_expiration_date = utils.utcnow() + datetime.timedelta(minutes=1)
    results = service.heartbeat_batch([
        {
            'build_id': 1,
            'lease_key': build.lease_key,
            'lease_expiration_date': new_expiration_date,
        },
        {
            'build_id': 2,
            'lease_key': 42,
            'lease_expiration_date': new_expiration_date,
        },
    ])

    self.assertEqual(len(results), 2)

    build = build.key.get()
    self.assertEqual(results[0], (1, build, None))

    self.assertIsNone(results[1][1])
    self.assertTrue(isinstance(results[1][2], errors.BuildNotFoundError))

  def test_heartbeat_without_expiration_date(self):
    build = self.new_leased_build(id=1)
    with self.assertRaises(errors.InvalidInputError):
      service.heartbeat(1, build.lease_key, lease_expiration_date=None)

  ################################### COMPLETE #################################

  def new_started_build(self, **build_proto_fields):
    build = self.new_leased_build(**build_proto_fields)
    build = self.start(build)
    return build

  def succeed(self, build, **kwargs):
    return service.succeed(build.key.id(), build.lease_key, **kwargs)

  def test_succeed(self):
    build = self.new_started_build()
    build = self.succeed(build, result_details={'properties': {'foo': 'bar'}})
    self.assertEqual(build.proto.status, common_pb2.SUCCESS)
    self.assertEqual(build.status_changed_time, utils.utcnow())
    self.assertTrue(build.proto.HasField('end_time'))

    out_props = model.BuildOutputProperties.key_for(build.key).get()
    self.assertEqual(test_util.msg_to_dict(out_props.parse()), {'foo': 'bar'})

  def test_succeed_failed(self):
    build = self.classic_build(id=1, status=common_pb2.FAILURE)
    build.put()
    with self.assertRaises(errors.BuildIsCompletedError):
      service.succeed(1, 42)

  def test_succeed_is_idempotent(self):
    build = self.new_started_build(id=1)
    service.succeed(1, build.lease_key)
    service.succeed(1, build.lease_key)

  def test_succeed_with_new_tags(self):
    build = self.new_started_build(id=1, tags=[dict(key='a', value='1')])
    build = self.succeed(build, new_tags=['b:2'])
    self.assertIn('a:1', build.tags)
    self.assertIn('b:2', build.tags)

  def test_fail(self):
    build = self.new_started_build(id=1)
    build = service.fail(1, build.lease_key)
    self.assertEqual(build.proto.status, common_pb2.FAILURE)
    self.assertEqual(build.status_changed_time, utils.utcnow())

  def test_infra_fail(self):
    build = self.new_started_build(id=1)
    build = service.fail(
        1, build.lease_key, failure_reason=model.FailureReason.INFRA_FAILURE
    )
    self.assertEqual(build.proto.status, common_pb2.INFRA_FAILURE)

  def test_fail_with_details(self):
    build = self.new_started_build(id=1)
    result_details = {'transient_failure': True}
    build = service.fail(1, build.lease_key, result_details=result_details)
    self.assertEqual(build.result_details, result_details)

  def test_complete_with_url(self):
    build = self.new_started_build(id=1)
    url = 'http://localhost/1'
    build = self.succeed(build, url=url)
    self.assertEqual(build.url, url)

  def test_complete_not_started_build(self):
    build = self.new_leased_build()
    self.succeed(build)

  def test_completion_creates_notification_task(self):
    build = self.new_started_build()
    with self.callback_test(build):
      self.succeed(build)

  ########################## RESET EXPIRED BUILDS ##############################

  def test_delete_many_scheduled_builds(self):
    scheduled_build = test_util.build(id=1, status=common_pb2.SCHEDULED)
    completed_build = test_util.build(id=2, status=common_pb2.SUCCESS)
    scheduled_build.put()
    completed_build.put()
    self.assertIsNotNone(scheduled_build.key.get())
    self.assertIsNotNone(completed_build.key.get())
    service._task_delete_many_builds(
        scheduled_build.bucket_id, model.BuildStatus.SCHEDULED
    )
    self.assertIsNone(scheduled_build.key.get())
    self.assertIsNotNone(completed_build.key.get())

  def test_delete_many_started_builds(self):
    scheduled_build = test_util.build(id=1, status=common_pb2.SCHEDULED)
    started_build = test_util.build(id=2, status=common_pb2.STARTED)
    completed_build = test_util.build(id=3, status=common_pb2.SUCCESS)
    ndb.put_multi([scheduled_build, started_build, completed_build])

    service._task_delete_many_builds(
        scheduled_build.bucket_id, model.BuildStatus.STARTED
    )
    self.assertIsNotNone(scheduled_build.key.get())
    self.assertIsNone(started_build.key.get())
    self.assertIsNotNone(completed_build.key.get())

  def test_delete_many_builds_with_tags(self):
    build = test_util.build(tags=[dict(key='tag', value='1')])
    build.put()

    service._task_delete_many_builds(
        build.bucket_id, model.BuildStatus.SCHEDULED, tags=['tag:0']
    )
    self.assertIsNotNone(build.key.get())

    service._task_delete_many_builds(
        build.bucket_id, model.BuildStatus.SCHEDULED, tags=['tag:1']
    )
    self.assertIsNone(build.key.get())

  def test_delete_many_builds_created_by(self):
    build1 = test_util.build(id=1, created_by='user:1@example.com')
    build2 = test_util.build(id=2, created_by='user:2@example.com')
    ndb.put_multi([build1, build2])

    service._task_delete_many_builds(
        build1.bucket_id,
        model.BuildStatus.SCHEDULED,
        created_by=build2.created_by,
    )
    self.assertIsNone(build2.key.get())
    self.assertIsNotNone(build1.key.get())

  def test_delete_many_builds_auth_error(self):
    self.mock_cannot(user.Action.DELETE_SCHEDULED_BUILDS)
    with self.assertRaises(auth.AuthorizationError):
      service.delete_many_builds('chromium/try', model.BuildStatus.SCHEDULED)

  def test_delete_many_builds_schedule_task(self):
    service.delete_many_builds('chromium/try', model.BuildStatus.SCHEDULED)

  def test_delete_many_completed_builds(self):
    with self.assertRaises(errors.InvalidInputError):
      service.delete_many_builds('chromium/try', model.BuildStatus.COMPLETED)

  ################################ PAUSE BUCKET ################################

  def test_pause_bucket(self):
    config.put_bucket(
        'chromium',
        'a' * 40,
        test_util.parse_bucket_cfg('name: "master.foo"'),
    )
    config.put_bucket(
        'chromium',
        'a' * 40,
        test_util.parse_bucket_cfg('name: "master.bar"'),
    )

    self.put_many_builds(
        5, builder=dict(project='chromium', bucket='master.foo')
    )
    self.put_many_builds(
        5, builder=dict(project='chromium', bucket='master.bar')
    )

    service.pause('chromium/master.foo', True)
    builds, _ = service.peek(['chromium/master.foo', 'chromium/master.bar'])
    self.assertEqual(len(builds), 5)
    self.assertTrue(all(b.bucket_id == 'chromium/master.bar' for b in builds))

  def test_pause_all_requested_buckets(self):
    config.put_bucket(
        'chromium',
        'a' * 40,
        test_util.parse_bucket_cfg('name: "master.foo"'),
    )
    self.put_many_builds(
        5, builder=dict(project='chromium', bucket='master.foo')
    )

    service.pause('chromium/master.foo', True)
    builds, _ = service.peek(['chromium/master.foo'])
    self.assertEqual(len(builds), 0)

  def test_pause_then_unpause(self):
    build = self.classic_build(builder=dict(project='chromium', bucket='try'))
    build.put()

    config.put_bucket(
        'chromium',
        'a' * 40,
        test_util.parse_bucket_cfg('name: "ci"'),
    )

    service.pause(build.bucket_id, True)
    service.pause(build.bucket_id, True)  # Again, to cover equality case.
    builds, _ = service.peek([build.bucket_id])
    self.assertEqual(len(builds), 0)

    service.pause(build.bucket_id, False)
    builds, _ = service.peek([build.bucket_id])
    self.assertEqual(len(builds), 1)

  def test_pause_bucket_auth_error(self):
    self.mock_cannot(user.Action.PAUSE_BUCKET)
    with self.assertRaises(auth.AuthorizationError):
      service.pause('chromium/no.such.bucket', True)

  def test_pause_invalid_bucket(self):
    config.get_bucket_async.return_value = future((None, None))
    with self.assertRaises(errors.InvalidInputError):
      service.pause('a/#', True)

  def test_pause_luci_bucket(self):
    with self.assertRaises(errors.InvalidInputError):
      service.pause('chromium/luci', True)

  ############################ UNREGISTER BUILDERS #############################

  def test_unregister_builders(self):
    model.Builder(
        id='chromium:try:linux_rel',
        last_scheduled=self.now - datetime.timedelta(weeks=8),
    ).put()
    service.unregister_builders()
    builders = model.Builder.query().fetch()
    self.assertFalse(builders)
