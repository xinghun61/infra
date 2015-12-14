# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json

from components import utils
from google.appengine.ext import ndb
import mock

from testing_utils import testing
import api
import errors
import model
import service


class BuildBucketApiTest(testing.EndpointsTestCase):
  api_service_cls = api.BuildBucketApi

  def setUp(self):
    super(BuildBucketApiTest, self).setUp()
    for a in dir(service):
      self.mock(service, a, mock.Mock())

    self.future_date = utils.utcnow() + datetime.timedelta(minutes=1)
    # future_ts is str because INT64 values are formatted as strings.
    self.future_ts = str(utils.datetime_to_timestamp(self.future_date))
    self.test_build = model.Build(
      id=1,
      bucket='chromium',
      parameters={
        'buildername': 'linux_rel',
      },
    )

  def expect_error(self, method_name, req, error_reason):
    res = self.call_api(method_name, req).json_body
    self.assertIsNotNone(res.get('error'))
    self.assertEqual(res['error']['reason'], error_reason)

  def test_expired_build_to_message(self):
    yesterday = utils.utcnow() - datetime.timedelta(days=1)
    yesterday_timestamp = utils.datetime_to_timestamp(yesterday)
    self.test_build.lease_key = 1
    self.test_build.lease_expiration_date = yesterday
    msg = api.build_to_message(self.test_build)
    self.assertEqual(msg.lease_expiration_ts, yesterday_timestamp)

  ##################################### GET ####################################

  def test_get(self):
    self.test_build.lease_expiration_date = self.future_date

    build_id = self.test_build.key.id()
    service.get.return_value = self.test_build

    resp = self.call_api('get', {'id': build_id}).json_body
    service.get.assert_called_once_with(build_id)
    self.assertEqual(resp['build']['id'], str(build_id))
    self.assertEqual(resp['build']['bucket'], self.test_build.bucket)
    self.assertEqual(resp['build']['lease_expiration_ts'], self.future_ts)
    self.assertEqual(resp['build']['status'], 'SCHEDULED')
    self.assertEqual(
      resp['build']['parameters_json'], '{"buildername": "linux_rel"}')

  def test_get_nonexistent_build(self):
    service.get.return_value = None
    self.expect_error('get', {'id': 1}, 'BUILD_NOT_FOUND')

  ##################################### PUT ####################################

  def test_put(self):
    self.test_build.tags = ['owner:ivan']
    service.add.return_value = self.test_build
    req = {
      'bucket': self.test_build.bucket,
      'tags': self.test_build.tags,
      'pubsub_callback': {
        'topic': 'projects/foo/topic/bar',
        'user_data': 'hello',
        'auth_token': 'secret',
      }
    }
    resp = self.call_api('put', req).json_body
    service.add.assert_called_once_with(
      bucket=self.test_build.bucket,
      tags=req['tags'],
      parameters=None,
      lease_expiration_date=None,
      client_operation_id=None,
      pubsub_callback=model.PubSubCallback(
        topic='projects/foo/topic/bar',
        user_data='hello',
        auth_token='secret',
      ),
    )
    self.assertEqual(resp['build']['id'], str(self.test_build.key.id()))
    self.assertEqual(resp['build']['bucket'], req['bucket'])
    self.assertEqual(resp['build']['tags'], req['tags'])

  def test_put_with_parameters(self):
    service.add.return_value = self.test_build
    req = {
      'bucket': self.test_build.bucket,
      'parameters_json': json.dumps(self.test_build.parameters),
    }
    resp = self.call_api('put', req).json_body
    self.assertEqual(resp['build']['parameters_json'], req['parameters_json'])

  def test_put_with_leasing(self):
    self.test_build.lease_expiration_date = self.future_date
    service.add.return_value = self.test_build
    req = {
      'bucket': self.test_build.bucket,
      'lease_expiration_ts': self.future_ts,
    }
    resp = self.call_api('put', req).json_body
    service.add.assert_called_once_with(
      bucket=self.test_build.bucket,
      tags=[],
      parameters=None,
      lease_expiration_date=self.future_date,
      client_operation_id=None,
      pubsub_callback=None,
    )
    self.assertEqual(
      resp['build']['lease_expiration_ts'], req['lease_expiration_ts'])

  def test_put_with_malformed_parameters_json(self):
    req = {
      'bucket': 'chromium',
      'parameters_json': '}non-json',
    }
    self.expect_error('put', req, 'INVALID_INPUT')

  ################################## PUT_BATCH #################################

  def test_put_batch(self):
    self.test_build.tags = ['owner:ivan']
    build1_future = ndb.Future()
    build1_future.set_result(self.test_build)

    build2 = model.Build(id=2, bucket='v8')
    build2_future = ndb.Future()
    build2_future.set_result(build2)

    bad_build_future = ndb.Future()
    bad_build_future.set_exception(errors.InvalidInputError('Just bad'))

    service.add_async.side_effect = [
      build1_future, build2_future, bad_build_future]
    req = {
      'builds': [
        {
          'bucket': self.test_build.bucket,
          'tags': self.test_build.tags,
          'client_operation_id': '0',
        },
        {
          'bucket': build2.bucket,
          'client_operation_id': '1',
        },
        {
          'bucket': 'bad name',
          'client_operation_id': '2',
        },
      ],
    }
    resp = self.call_api('put_batch', req).json_body
    service.add_async.assert_any_call(
      bucket=self.test_build.bucket,
      tags=self.test_build.tags,
      parameters=None,
      lease_expiration_date=None,
      client_operation_id='0',
      pubsub_callback=None,
    )
    service.add_async.assert_any_call(
      bucket=build2.bucket,
      tags=[],
      parameters=None,
      lease_expiration_date=None,
      client_operation_id='1',
      pubsub_callback=None,
    )

    res0 = resp['results'][0]
    self.assertEqual(res0['client_operation_id'], '0')
    self.assertEqual(res0['build']['id'], str(self.test_build.key.id()))
    self.assertEqual(res0['build']['bucket'], self.test_build.bucket)
    self.assertEqual(res0['build']['tags'], self.test_build.tags)

    res1 = resp['results'][1]
    self.assertEqual(res1['client_operation_id'], '1')
    self.assertEqual(res1['build']['id'], str(build2.key.id()))
    self.assertEqual(res1['build']['bucket'], build2.bucket)

    res2 = resp['results'][2]
    self.assertEqual(res2, {
      'client_operation_id': '2',
      'error': {'reason': 'INVALID_INPUT', 'message': 'Just bad'},
    })

  #################################### SEARCH ##################################

  def test_search(self):
    self.test_build.put()
    service.search.return_value = ([self.test_build], 'the cursor')
    req = {
      'bucket': ['chromium'],
      'cancelation_reason': 'CANCELED_EXPLICITLY',
      'created_by': 'user:x@chromium.org',
      'result': 'CANCELED',
      'status': 'COMPLETED',
      'tag': ['important'],
    }

    res = self.call_api('search', req).json_body

    service.search.assert_called_once_with(
      buckets=req['bucket'],
      tags=req['tag'],
      status=model.BuildStatus.COMPLETED,
      result=model.BuildResult.CANCELED,
      failure_reason=None,
      cancelation_reason=model.CancelationReason.CANCELED_EXPLICITLY,
      created_by='user:x@chromium.org',
      max_builds=None,
      start_cursor=None)
    self.assertEqual(len(res['builds']), 1)
    self.assertEqual(res['builds'][0]['id'], str(self.test_build.key.id()))
    self.assertEqual(res['next_cursor'], 'the cursor')

  ##################################### PEEK ###################################

  def test_peek(self):
    self.test_build.put()
    service.peek.return_value = ([self.test_build], 'the cursor')
    req = {'bucket': [self.test_build.bucket]}
    res = self.call_api('peek', req).json_body
    service.peek.assert_called_once_with(
      req['bucket'],
      max_builds=None,
      start_cursor=None,
    )
    self.assertEqual(len(res['builds']), 1)
    peeked_build = res['builds'][0]
    self.assertEqual(peeked_build['id'], str(self.test_build.key.id()))
    self.assertEqual(res['next_cursor'], 'the cursor')

  #################################### LEASE ###################################

  def test_lease(self):
    self.test_build.lease_expiration_date = self.future_date
    self.test_build.lease_key = 42
    service.lease.return_value = True, self.test_build

    req = {
      'id': self.test_build.key.id(),
      'lease_expiration_ts': self.future_ts,
    }
    res = self.call_api('lease', req).json_body
    service.lease.assert_called_once_with(
      self.test_build.key.id(),
      lease_expiration_date=self.future_date,
    )
    self.assertIsNone(res.get('error'))
    self.assertEqual(res['build']['id'], str(self.test_build.key.id()))
    self.assertEqual(res['build']['lease_key'], str(self.test_build.lease_key))
    self.assertEqual(
      res['build']['lease_expiration_ts'],
      req['lease_expiration_ts'])

  def test_lease_with_negative_expiration_date(self):
    req = {
      'id': self.test_build.key.id(),
      'lease_expiration_ts': 242894728472423847289472398,
    }
    self.expect_error('lease', req, 'INVALID_INPUT')

  def test_lease_unsuccessful(self):
    self.test_build.put()
    service.lease.return_value = (False, self.test_build)
    req = {
      'id': self.test_build.key.id(),
      'lease_expiration_ts': self.future_ts,
    }
    self.expect_error('lease', req, 'CANNOT_LEASE_BUILD')

  #################################### RESET ###################################

  def test_reset(self):
    service.reset.return_value = self.test_build
    req = {
      'id': self.test_build.key.id(),
    }
    res = self.call_api('reset', req).json_body
    service.reset.assert_called_once_with(self.test_build.key.id())
    self.assertIsNone(res.get('error'))
    self.assertEqual(res['build']['id'], str(self.test_build.key.id()))
    self.assertFalse('lease_key' in res['build'])

  #################################### START ###################################

  def test_start(self):
    self.test_build.url = 'http://localhost/build/1'
    service.start.return_value = self.test_build
    req = {
      'id': self.test_build.key.id(),
      'lease_key': 42,
      'url': self.test_build.url,
    }
    res = self.call_api('start', req).json_body
    service.start.assert_called_once_with(
      req['id'], req['lease_key'], url=req['url'])
    self.assertEqual(int(res['build']['id']), req['id'])
    self.assertEqual(res['build']['url'], req['url'])

  def test_start_completed_build(self):
    service.start.side_effect = errors.BuildIsCompletedError
    req = {
      'id': self.test_build.key.id(),
      'lease_key': 42,
    }
    res = self.call_api('start', req).json_body
    self.assertEqual(res['error']['reason'], 'BUILD_IS_COMPLETED')

  #################################### HEATBEAT ################################

  def test_heartbeat(self):
    self.test_build.lease_expiration_date = self.future_date
    service.heartbeat.return_value = self.test_build
    req = {
      'id': self.test_build.key.id(),
      'lease_key': 42,
      'lease_expiration_ts': self.future_ts,
    }
    res = self.call_api('heartbeat', req).json_body
    service.heartbeat.assert_called_once_with(
      req['id'], req['lease_key'], self.future_date)
    self.assertEqual(int(res['build']['id']), req['id'])
    self.assertEqual(
      res['build']['lease_expiration_ts'], req['lease_expiration_ts'],
    )

  def test_heartbeat_batch(self):
    self.test_build.lease_expiration_date = self.future_date
    build2 = model.Build(
      id=2,
      bucket='chromium',
      lease_expiration_date=self.future_date,
    )

    service.heartbeat_batch.return_value = [
      (self.test_build.key.id(), self.test_build, None),
      (build2.key.id(), None, errors.LeaseExpiredError())
    ]

    req = {
      'heartbeats': [{
        'build_id': self.test_build.key.id(),
        'lease_key': 42,
        'lease_expiration_ts': self.future_ts,
      }, {
        'build_id': build2.key.id(),
        'lease_key': 42,
        'lease_expiration_ts': self.future_ts,
      }],
    }
    res = self.call_api('heartbeat_batch', req).json_body
    service.heartbeat_batch.assert_called_any_with(
      self.test_build.key.id(), 42, self.future_date)
    service.heartbeat_batch.assert_called_any_with(
      build2.key.id(), 42, self.future_date)

    result1 = res['results'][0]
    self.assertEqual(int(result1['build_id']), self.test_build.key.id())
    self.assertEqual(result1['lease_expiration_ts'], self.future_ts)

    result2 = res['results'][1]
    self.assertEqual(int(result2['build_id']), build2.key.id())
    self.assertTrue(result2['error']['reason'] == 'LEASE_EXPIRED')

  def test_heartbeat_batch_with_internal_server_error(self):
    self.test_build.lease_expiration_date = self.future_date

    service.heartbeat_batch.return_value = [
      (self.test_build.key.id(), None, ValueError())
    ]

    req = {
      'heartbeats': [{
        'build_id': self.test_build.key.id(),
        'lease_key': 42,
        'lease_expiration_ts': self.future_ts,
      }],
    }
    with self.call_should_fail(500):
      self.call_api('heartbeat_batch', req)

  ################################## SUCCEED ###################################

  def test_succeed(self):
    service.succeed.return_value = self.test_build
    req = {
      'id': self.test_build.key.id(),
      'lease_key': 42,
    }
    res = self.call_api('succeed', req).json_body
    service.succeed.assert_called_once_with(
      req['id'], req['lease_key'], result_details=None, url=None)
    self.assertEqual(int(res['build']['id']), req['id'])

  def test_succeed_with_result_details(self):
    self.test_build.result_details = {'test_coverage': 100}
    service.succeed.return_value = self.test_build
    req = {
      'id': self.test_build.key.id(),
      'lease_key': 42,
      'result_details_json': json.dumps(self.test_build.result_details),
    }
    res = self.call_api('succeed', req).json_body
    _, kwargs = service.succeed.call_args
    self.assertEqual(
      kwargs['result_details'], self.test_build.result_details)
    self.assertEqual(
      res['build']['result_details_json'], req['result_details_json'])

  #################################### FAIL ####################################

  def test_infra_failure(self):
    self.test_build.result_details = {'transient_error': True}
    self.test_build.failure_reason = model.FailureReason.INFRA_FAILURE
    service.fail.return_value = self.test_build
    req = {
      'id': self.test_build.key.id(),
      'lease_key': 42,
      'failure_reason': 'INFRA_FAILURE',
      'result_details_json': json.dumps(self.test_build.result_details),
    }
    res = self.call_api('fail', req).json_body
    service.fail.assert_called_once_with(
      req['id'], req['lease_key'],
      result_details=self.test_build.result_details,
      failure_reason=model.FailureReason.INFRA_FAILURE,
      url=None)
    self.assertEqual(int(res['build']['id']), req['id'])
    self.assertEqual(res['build']['failure_reason'], req['failure_reason'])
    self.assertEqual(
      res['build']['result_details_json'], req['result_details_json'])

  #################################### CANCEL ##################################

  def test_cancel(self):
    service.cancel.return_value = self.test_build
    req = {
      'id': self.test_build.key.id(),
    }
    res = self.call_api('cancel', req).json_body
    service.cancel.assert_called_once_with(req['id'])
    self.assertEqual(int(res['build']['id']), req['id'])

  ################################# CANCEL_BATCH ###############################

  def test_cancel_batch(self):
    service.cancel.side_effect = [
      self.test_build, errors.BuildIsCompletedError]

    req = {
      'build_ids': [self.test_build.key.id(), 2],
    }
    res = self.call_api('cancel_batch', req).json_body

    res0 = res['results'][0]
    self.assertEqual(int(res0['build_id']), self.test_build.key.id())
    self.assertEqual(int(res0['build']['id']), self.test_build.key.id())
    service.cancel.assert_any_call(self.test_build.key.id())

    res1 = res['results'][1]
    self.assertEqual(int(res1['build_id']), 2)
    self.assertEqual(res1['error']['reason'], 'BUILD_IS_COMPLETED')
    service.cancel.assert_any_call(2)

  ##########################  DELETE_MANY_BUILDS  #############################

  def test_delete_many_builds(self):
    req = {
      'bucket': 'chromium',
      'status': 'SCHEDULED',
      'tags': ['tag:0'],
      'created_by': 'nodir@google.com',
    }
    self.call_api('delete_many_builds', req)

  #################################### ERRORS ##################################

  def error_test(self, error_class, reason):
    service.get.side_effect = error_class
    self.expect_error('get', {'id': 123}, reason)

  def test_build_not_found_error(self):
    self.error_test(errors.BuildNotFoundError, 'BUILD_NOT_FOUND')

  def test_invalid_input_error(self):
    self.error_test(errors.InvalidInputError, 'INVALID_INPUT')

  def test_lease_expired_error(self):
    self.error_test(errors.LeaseExpiredError, 'LEASE_EXPIRED')
