# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import contextlib
import datetime
import json

from components import auth
from components import config as config_component
from components import net
from components import utils
from google.appengine.ext import ndb
from testing_utils import testing
from webob import exc
import mock
import webapp2

from swarming import swarming
from proto import project_config_pb2
import config
import errors
import model


def futuristic(result):
  f = ndb.Future()
  f.set_result(result)
  return f


class SwarmingTest(testing.AppengineTestCase):
  def setUp(self):
    super(SwarmingTest, self).setUp()
    self.mock(utils, 'utcnow', lambda: datetime.datetime(2015, 11, 30))
    bucket_cfg = project_config_pb2.Bucket(
      name='bucket',
      swarming=project_config_pb2.Swarming(
        hostname='chromium-swarm.appspot.com',
        url_format='https://example.com/{swarming_hostname}/{task_id}',
        common_swarming_tags=['commontag:yes'],
        common_dimensions=[
          project_config_pb2.Swarming.Dimension(key='cores', value='8'),
        ],
        builders=[
          project_config_pb2.Swarming.Builder(
            name='builder',
            swarming_tags=['buildertag:yes'],
            dimensions=[
              project_config_pb2.Swarming.Dimension(key='os', value='Linux'),
            ],
            recipe=project_config_pb2.Swarming.Recipe(
              repository='https://example.com/repo',
              name='recipe',
            ),
            priority=108,
          ),
        ],
      ),
    )
    self.mock(config, 'get_bucket_async', lambda name: futuristic(bucket_cfg))

    task_template = {
      'name': 'buildbucket-$bucket-$builder',
      'priority': '100',
      'expiration_secs': '3600',
      'properties': {
        'execution_timeout_secs': '3600',
        'inputs_ref': {
          'isolatedserver': 'https://isolateserver.appspot.com',
          'namespace': 'default-gzip',
          'isolated': 'cbacbdcbabcd'
        },
        'extra_args': ['$recipe in $repository @ $revision'],
      },
      'numerical_value_for_coverage_in_format_obj': 42,
    }
    self.mock(config_component, 'get_self_config_async', mock.Mock())
    config_component.get_self_config_async.return_value = (
      futuristic((None, json.dumps(task_template))))

    self.mock(auth, 'delegate_async', mock.Mock())
    auth.delegate_async.return_value = futuristic('blah')

  def test_is_for_swarming(self):
    build = model.Build(
      bucket='bucket',
      parameters={'builder_name': 'builder'}
    )
    self.assertTrue(swarming.is_for_swarming_async(build).get_result())

    build.parameters['builder_name'] = 'other'
    self.assertFalse(swarming.is_for_swarming_async(build).get_result())

  def test_is_for_swarming_no_template(self):
    build = model.Build(
        bucket='bucket',
        parameters={'builder_name': 'builder'}
    )
    self.assertTrue(swarming.is_for_swarming_async(build).get_result())

    config_component.get_self_config_async.return_value = futuristic(
      (None, None))
    self.assertFalse(swarming.is_for_swarming_async(build).get_result())

  def test_validate_swarming_param(self):
    swarming.validate_swarming_param(None)
    swarming.validate_swarming_param({})
    swarming.validate_swarming_param({'recipe': {}})
    swarming.validate_swarming_param({'recipe': {'revision': 'deadbeef'}})

    bad = [
      [],
      {'junk': 1},
      {'recipe': []},
      {'recipe': {'junk': 1}},
      {'recipe': {'revision': 1}},
    ]
    for p in bad:
      with self.assertRaises(errors.InvalidInputError):
        swarming.validate_swarming_param(p)

  def test_create_task_async(self):
    build = model.Build(
      bucket='bucket',
      tags=['builder:builder'],
      parameters={
        'builder_name': 'builder',
        'swarming': {
          'recipe': {'revision': 'badcoffee'},
        },
      },
    )

    self.mock(net, 'json_request_async', mock.Mock(return_value=futuristic({
      'task_id': 'deadbeef',
      'request': {
        'properties': {
          'dimensions': [
            {'key': 'cores', 'value': '8'},
            {'key': 'os', 'value': 'Linux'},
          ],
        },
        'tags': [
          'builder:builder',
          'buildertag:yes',
          'commontag:yes',
          'master:master.bucket',
          'priority:108',
          'recipe_name:recipe',
          'recipe_repository:https://example.com/repo',
          'recipe_revision:badcoffee',
        ]
      }
    })))

    swarming.create_task_async(build).get_result()

    # Test swarming request.
    self.assertEqual(
      net.json_request_async.call_args[0][0],
      'https://chromium-swarm.appspot.com/_ah/api/swarming/v1/tasks/new')
    actual_task_def = net.json_request_async.call_args[1]['payload']
    del actual_task_def['pubsub_auth_token']
    self.maxDiff =24566
    expected_task_def = {
      'name': 'buildbucket-bucket-builder',
      'priority': 108,
      'expiration_secs': '3600',
      'tags': [
        'buildbucket_bucket:bucket',
        'buildbucket_hostname:None',
        'builder:builder',
        'buildertag:yes',
        'commontag:yes',
        'recipe_name:recipe',
        'recipe_repository:https://example.com/repo',
        'recipe_revision:badcoffee',
      ],
      'properties': {
        'execution_timeout_secs': '3600',
        'inputs_ref': {
          'isolatedserver': 'https://isolateserver.appspot.com',
          'namespace': 'default-gzip',
          'isolated': 'cbacbdcbabcd'
        },
        'extra_args': ['recipe in https://example.com/repo @ badcoffee'],
        'dimensions': [
          {'key': 'cores', 'value': '8'},
          {'key': 'os', 'value': 'Linux'},
        ],
      },
      'pubsub_topic': 'projects/testbed-test/topics/swarming',
      'pubsub_userdata': json.dumps({
        'created_ts': utils.datetime_to_timestamp(utils.utcnow()),
        'swarming_hostname': 'chromium-swarm.appspot.com',
      }, sort_keys=True),
      'numerical_value_for_coverage_in_format_obj': 42,
    }
    self.assertEqual(actual_task_def, expected_task_def)

    self.assertEqual(set(build.tags), {
      'builder:builder',
      'swarming_dimension:cores:8',
      'swarming_dimension:os:Linux',
      'swarming_hostname:chromium-swarm.appspot.com',
      'swarming_tag:builder:builder',
      'swarming_tag:buildertag:yes',
      'swarming_tag:commontag:yes',
      'swarming_tag:master:master.bucket',
      'swarming_tag:priority:108',
      'swarming_tag:recipe_name:recipe',
      'swarming_tag:recipe_repository:https://example.com/repo',
      'swarming_tag:recipe_revision:badcoffee',
      'swarming_task_id:deadbeef',
    })
    self.assertEqual(
      build.url, 'https://example.com/chromium-swarm.appspot.com/deadbeef')

  def test_create_task_async_on_leased_build(self):
    build = model.Build(
      bucket='bucket',
      parameters={'builder_name': 'builder'},
      lease_key=12345,
    )
    with self.assertRaises(errors.InvalidInputError):
      swarming.create_task_async(build).get_result()

  def test_create_task_async_403(self):
    build = model.Build(
      bucket='bucket',
      parameters={
        'builder_name': 'builder',
      },
    )

    http403 = net.AuthError('403', 403, 'nope')
    self.mock(net, 'json_request_async', mock.Mock(side_effect=http403))

    with self.assertRaises(auth.AuthorizationError):
      swarming.create_task_async(build).get_result()

  def test_cancel_task(self):
    self.mock(net, 'json_request_async', mock.Mock(return_value=futuristic({})))
    build = model.Build(
      bucket='whatever',
      swarming_hostname='chromium-swarm.appspot.com',
      swarming_task_id='deadbeef',
    )
    swarming.cancel_task_async(build).get_result()
    net.json_request_async.assert_called_with(
      ('https://chromium-swarm.appspot.com/'
       '_ah/api/swarming/v1/task/deadbeef/cancel'),
      method='POST',
      scopes=net.EMAIL_SCOPE,
      delegation_token='blah',
      payload=None)

  def test_update_build_success(self):
    cases = [
      {
        'task_result': {
          'state': 'PENDING',
        },
        'status': model.BuildStatus.STARTED,
      },

      {
        'task_result': {
          'state': 'RUNNING',
        },
        'status': model.BuildStatus.STARTED,
      },

      {
        'task_result': {
          'state': 'COMPLETED',
        },
        'status': model.BuildStatus.COMPLETED,
        'result': model.BuildResult.SUCCESS,
      },

      {
        'task_result': {
          'state': 'COMPLETED',
          'failure': True,
        },
        'status': model.BuildStatus.COMPLETED,
        'result': model.BuildResult.FAILURE,
        'failure_reason': model.FailureReason.BUILD_FAILURE,
      },

      {
        'task_result': {
          'state': 'COMPLETED',
          'failure': True,
          'internal_failure': True
        },
        'status': model.BuildStatus.COMPLETED,
        'result': model.BuildResult.FAILURE,
        'failure_reason': model.FailureReason.INFRA_FAILURE,
      },

      {
        'task_result': {
          'state': 'BOT_DIED',
        },
        'status': model.BuildStatus.COMPLETED,
        'result': model.BuildResult.FAILURE,
        'failure_reason': model.FailureReason.INFRA_FAILURE,
      },

      {
        'task_result': {
          'state': 'TIMED_OUT',
        },
        'status': model.BuildStatus.COMPLETED,
        'result': model.BuildResult.CANCELED,
        'cancelation_reason': model.CancelationReason.TIMEOUT,
      },

      {
        'task_result': {
          'state': 'EXPIRED',
        },
        'status': model.BuildStatus.COMPLETED,
        'result': model.BuildResult.CANCELED,
        'cancelation_reason': model.CancelationReason.TIMEOUT,
      },

      {
        'task_result': {
          'state': 'CANCELED',
        },
        'status': model.BuildStatus.COMPLETED,
        'result': model.BuildResult.CANCELED,
        'cancelation_reason': model.CancelationReason.CANCELED_EXPLICITLY,
      },
    ]

    for case in cases:
      build = model.Build(bucket='bucket')
      build.put()
      swarming._update_build(build, case['task_result'])
      self.assertEqual(build.status, case['status'])
      self.assertEqual(build.result, case.get('result'))
      self.assertEqual(build.failure_reason, case.get('failure_reason'))
      self.assertEqual(build.cancelation_reason, case.get('cancelation_reason'))


class SubNotifyTest(testing.AppengineTestCase):
  def setUp(self):
    super(SubNotifyTest, self).setUp()
    self.mock(utils, 'utcnow', lambda: datetime.datetime(2015, 11, 30))
    self.handler = swarming.SubNotify(response=webapp2.Response())

  def test_unpack_msg(self):
    self.assertEqual(
      self.handler.unpack_msg({
        'data': b64json({
          'task_id': 'deadbeef',
          'userdata': json.dumps({
            'created_ts': 1448841600000000,
            'swarming_hostname': 'chromium-swarm.appspot.com',
          })
        })
      }),
      (
        'chromium-swarm.appspot.com',
        datetime.datetime(2015, 11, 30),
        'deadbeef')
    )

  def test_unpack_msg_with_err(self):
    with self.assert_bad_message():
      self.handler.unpack_msg({})
    with self.assert_bad_message():
      self.handler.unpack_msg({'data': b64json([])})

    bad_data = [
      # Bad task id.
      {
        'userdata': json.dumps({
          'created_ts': 1448841600000,
          'swarming_hostname': 'chromium-swarm.appspot.com',
        })
      },

      # Bad swarming hostname.
      {
        'task_id': 'deadbeef',
      },
      {
        'task_id': 'deadbeef',
        'userdata': '{}',
      },
      {
        'task_id': 'deadbeef',
        'userdata': json.dumps({
          'swarming_hostname': 1,
        })
      },

      # Bad creation time
      {
        'task_id': 'deadbeef',
        'userdata': json.dumps({
          'swarming_hostname': 'chromium-swarm.appspot.com',
        })
      },
      {
        'task_id': 'deadbeef',
        'userdata': json.dumps({
          'created_ts': 'foo',
          'swarming_hostname': 'chromium-swarm.appspot.com',
        })
      },
    ]

    for data in bad_data:
      with self.assert_bad_message():
        self.handler.unpack_msg({'data': b64json(data)})

  def test_post(self):
    build = model.Build(
      bucket='chromium',
      parameters={
        'builder_name': 'release'
      },
      status=model.BuildStatus.SCHEDULED,
      swarming_hostname='chromium-swarm.appspot.com',
      swarming_task_id='deadbeef',
    )
    build.put()

    self.handler.request = mock.Mock(json={
      'message': {
        'attributes': {
          'auth_token': swarming.TaskToken.generate(),
        },
        'data': b64json({
          'task_id': 'deadbeef',
          'userdata': json.dumps({
            'created_ts': 1448841600000000,
            'swarming_hostname': 'chromium-swarm.appspot.com',
          })
        })
      }
    })
    self.mock(swarming, '_load_task_result_async', mock.Mock())
    swarming._load_task_result_async.return_value = futuristic({
      'task_id': 'deadbeef',
      'state': 'COMPLETED',
    })

    self.handler.post()

    build = build.key.get()
    self.assertEqual(build.status, model.BuildStatus.COMPLETED)
    self.assertEqual(build.result, model.BuildResult.SUCCESS)

  def test_post_without_valid_auth_token(self):
    self.handler.request = mock.Mock(json={
      'message': {
        'attributes': {},
      },
    })

    with self.assert_bad_message():
      self.handler.post()

    self.handler.request.json['message']['attributes']['auth_token'] = 'blah'
    with self.assert_bad_message():
      self.handler.post()

  def test_post_without_build(self):
    userdata = {
      'created_ts': 1448841600000000,
      'swarming_hostname': 'chromium-swarm.appspot.com',
    }
    msg_data = {
      'task_id': 'deadbeef',
      'userdata': json.dumps(userdata)
    }
    self.handler.request = mock.Mock(json={
      'message': {
        'attributes': {
          'auth_token': swarming.TaskToken.generate(),
        },
        'data': b64json(msg_data)
      }
    })
    self.mock(swarming, '_load_task_result_async', mock.Mock())
    swarming._load_task_result_async.return_value = futuristic({
      'task_id': 'deadbeef',
      'state': 'COMPLETED',
    })

    with self.assert_bad_message(expect_redelivery=True):
      self.handler.post()

    userdata['created_ts'] = 1438841600000000
    msg_data['userdata'] = json.dumps(userdata)
    self.handler.request.json['message']['data'] = b64json(msg_data)
    with self.assert_bad_message(expect_redelivery=False):
      self.handler.post()

  @contextlib.contextmanager
  def assert_bad_message(self, expect_redelivery=False):
    self.handler.bad_message = False
    err = exc.HTTPInternalServerError if expect_redelivery else exc.HTTPOk
    with self.assertRaises(err):
      yield
    self.assertTrue(self.handler.bad_message)


class CronUpdateTest(testing.AppengineTestCase):
  def setUp(self):
    super(CronUpdateTest, self).setUp()
    self.build = model.Build(
      bucket='bucket',
      parameters={
        'builder_name': 'release',
      },
      swarming_hostname='chromium-swarm.appsot.com',
      swarming_task_id='deadeef',
      status=model.BuildStatus.STARTED,
      lease_key=123,
      lease_expiration_date=utils.utcnow() + datetime.timedelta(minutes=5),
      leasee=auth.Anonymous,
    )
    self.build.put()

  def test_update_build_async(self):
    self.mock(swarming, '_load_task_result_async', mock.Mock())
    swarming._load_task_result_async.return_value = futuristic({
      'state': 'COMPLETED',
    })

    build = self.build
    swarming.CronUpdateBuilds().update_build_async(build).get_result()
    build = build.key.get()
    self.assertEqual(build.status, model.BuildStatus.COMPLETED)
    self.assertEqual(build.result, model.BuildResult.SUCCESS)
    self.assertIsNone(build.lease_key)
    self.assertIsNotNone(build.complete_time)

  def test_update_build_async_no_task(self):
    self.mock(swarming, '_load_task_result_async', mock.Mock())
    swarming._load_task_result_async.return_value = futuristic(None)

    build = self.build
    swarming.CronUpdateBuilds().update_build_async(build).get_result()
    self.assertEqual(build.status, model.BuildStatus.COMPLETED)
    self.assertEqual(build.result, model.BuildResult.FAILURE)
    self.assertEqual(build.failure_reason, model.FailureReason.INFRA_FAILURE)
    self.assertIsNotNone(build.result_details)
    self.assertIsNone(build.lease_key)
    self.assertIsNotNone(build.complete_time)


def b64json(data):
  return base64.b64encode(json.dumps(data))
