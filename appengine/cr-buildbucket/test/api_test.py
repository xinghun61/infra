# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import os
import sys

REPO_ROOT_DIR = os.path.abspath(
    os.path.join(os.path.realpath(__file__), '..', '..', '..', '..')
)
sys.path.insert(
    0, os.path.join(REPO_ROOT_DIR, 'luci', 'appengine', 'third_party_local')
)

from components import auth
from components import utils
from testing_utils import testing
import mock
import gae_ts_mon

from proto.config import project_config_pb2
from test import config_test
from test.test_util import future, future_exception
import api
import backfill_tag_index
import config
import creation
import errors
import model
import search
import service
import v2
import user


class EndpointsApiTest(testing.EndpointsTestCase):
  api_service_cls = api.BuildBucketApi

  test_build = None
  test_bucket = None
  future_ts = None
  future_date = None

  def setUp(self):
    super(EndpointsApiTest, self).setUp()
    gae_ts_mon.reset_for_unittest(disable=True)
    auth.disable_process_cache()
    user.clear_request_cache()

    self.patch(
        'components.utils.utcnow', return_value=datetime.datetime(2017, 1, 1)
    )
    self.future_date = utils.utcnow() + datetime.timedelta(days=1)
    # future_ts is str because INT64 values are formatted as strings.
    self.future_ts = str(utils.datetime_to_timestamp(self.future_date))
    self.test_build = model.Build(
        id=1,
        bucket='chromium',
        create_time=datetime.datetime(2017, 1, 1),
        parameters={
            'buildername': 'linux_rel',
        },
    )
    self.project_id = 'test'
    config.put_bucket(
        self.project_id, 'a' * 40, project_config_pb2.Bucket(name='chromium')
    )

  def expect_error(self, method_name, req, error_reason):
    res = self.call_api(method_name, req).json_body
    self.assertIsNotNone(res.get('error'))
    self.assertEqual(res['error']['reason'], error_reason)

  @mock.patch('service.get_async', autospec=True)
  def test_get(self, get_async):
    self.test_build.lease_expiration_date = self.future_date

    build_id = self.test_build.key.id()
    get_async.return_value = future(self.test_build)

    resp = self.call_api('get', {'id': build_id}).json_body
    get_async.assert_called_once_with(build_id)
    self.assertEqual(resp['build']['id'], str(build_id))
    self.assertEqual(resp['build']['bucket'], self.test_build.bucket)
    self.assertEqual(resp['build']['lease_expiration_ts'], self.future_ts)
    self.assertEqual(resp['build']['status'], 'SCHEDULED')
    self.assertEqual(
        resp['build']['parameters_json'], '{"buildername": "linux_rel"}'
    )

  @mock.patch('service.get_async', autospec=True)
  def test_get_auth_error(self, get_async):
    get_async.return_value = future_exception(auth.AuthorizationError())
    self.expect_error('get', {'id': 1}, 'BUILD_NOT_FOUND')

  @mock.patch('service.get_async', autospec=True)
  def test_get_nonexistent_build(self, get_async):
    get_async.return_value = future(None)
    self.expect_error('get', {'id': 1}, 'BUILD_NOT_FOUND')

  ####### PUT ##################################################################

  @mock.patch('creation.add_async', autospec=True)
  def test_put(self, add_async):
    self.test_build.tags = ['owner:ivan']
    add_async.return_value = future(self.test_build)
    req = {
        'client_operation_id': '42',
        'bucket': self.test_build.bucket,
        'tags': self.test_build.tags,
        'pubsub_callback': {
            'topic': 'projects/foo/topic/bar',
            'user_data': 'hello',
            'auth_token': 'secret',
        },
    }
    resp = self.call_api('put', req).json_body
    add_async.assert_called_once_with(
        creation.BuildRequest(
            bucket=self.test_build.bucket,
            project=self.project_id,
            tags=req['tags'],
            client_operation_id='42',
            pubsub_callback=model.PubSubCallback(
                topic='projects/foo/topic/bar',
                user_data='hello',
                auth_token='secret',
            ),
        )
    )
    self.assertEqual(resp['build']['id'], str(self.test_build.key.id()))
    self.assertEqual(resp['build']['bucket'], req['bucket'])
    self.assertEqual(resp['build']['tags'], req['tags'])

  @mock.patch('creation.add_async', autospec=True)
  def test_put_with_parameters(self, add_async):
    add_async.return_value = future(self.test_build)
    req = {
        'bucket': self.test_build.bucket,
        'parameters_json': json.dumps(self.test_build.parameters),
    }
    resp = self.call_api('put', req).json_body
    self.assertEqual(resp['build']['parameters_json'], req['parameters_json'])

  @mock.patch('creation.add_async', autospec=True)
  def test_put_with_leasing(self, add_async):
    self.test_build.lease_expiration_date = self.future_date
    add_async.return_value = future(self.test_build)
    req = {
        'bucket': self.test_build.bucket,
        'lease_expiration_ts': self.future_ts,
    }
    resp = self.call_api('put', req).json_body
    add_async.assert_called_once_with(
        creation.BuildRequest(
            bucket=self.test_build.bucket,
            project=self.project_id,
            lease_expiration_date=self.future_date,
            tags=[],
        )
    )
    self.assertEqual(
        resp['build']['lease_expiration_ts'], req['lease_expiration_ts']
    )

  def test_put_with_malformed_parameters_json(self):
    req = {
        'bucket': 'chromium',
        'parameters_json': '}non-json',
    }
    self.expect_error('put', req, 'INVALID_INPUT')

  ####### RETRY ################################################################

  @mock.patch('creation.retry', autospec=True)
  def test_retry(self, retry):
    build = model.Build(
        bucket='chromium',
        parameters={model.BUILDER_PARAMETER: 'debug'},
        tags=['a:b'],
        retry_of=2,
    )
    build.put()
    retry.return_value = build

    req = {
        'id': build.key.id(),
        'client_operation_id': '42',
        'pubsub_callback': {
            'topic': 'projects/foo/topic/bar',
            'user_data': 'hello',
            'auth_token': 'secret',
        },
    }
    resp = self.call_api('retry', req).json_body
    retry.assert_called_once_with(
        build.key.id(),
        client_operation_id='42',
        lease_expiration_date=None,
        pubsub_callback=model.PubSubCallback(
            topic='projects/foo/topic/bar',
            user_data='hello',
            auth_token='secret',
        ),
    )
    self.assertEqual(resp['build']['id'], str(build.key.id()))
    self.assertEqual(resp['build']['bucket'], build.bucket)
    self.assertEqual(
        json.loads(resp['build']['parameters_json']), build.parameters
    )
    self.assertEqual(resp['build']['retry_of'], '2')

  @mock.patch('creation.retry', autospec=True)
  def test_retry_not_found(self, retry):
    retry.side_effect = errors.BuildNotFoundError
    self.expect_error('retry', {'id': 42}, 'BUILD_NOT_FOUND')

  ####### PUT_BATCH ############################################################

  @mock.patch('creation.add_many_async', autospec=True)
  def test_put_batch(self, add_many_async):
    self.test_build.tags = ['owner:ivan']

    build2 = model.Build(id=2, bucket='v8')
    config.put_bucket(
        self.project_id, 'a' * 40, project_config_pb2.Bucket(name='v8')
    )

    add_many_async.return_value = future([
        (self.test_build,
         None), (build2, None), (None, errors.InvalidInputError('Just bad'))
    ])
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
    add_many_async.assert_called_once_with([
        creation.BuildRequest(
            bucket=self.test_build.bucket,
            project=self.project_id,
            tags=self.test_build.tags,
            client_operation_id='0',
        ),
        creation.BuildRequest(
            bucket=build2.bucket,
            project=self.project_id,
            tags=[],
            client_operation_id='1',
        ),
        creation.BuildRequest(
            bucket='bad name',
            project=None,
            tags=[],
            client_operation_id='2',
        ),
    ])

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
    self.assertEqual(
        res2, {
            'client_operation_id': '2',
            'error': {'reason': 'INVALID_INPUT', 'message': 'Just bad'},
        }
    )

  @mock.patch('creation.add_many_async', autospec=True)
  def test_put_batch_with_exception(self, add_many_async):
    add_many_async.return_value = future([(None, Exception())])
    req = {
        'builds': [{'bucket': 'chromium'}],
    }
    self.call_api('put_batch', req, status=500)

  ####### SEARCH ###############################################################

  @mock.patch('search.search_async', autospec=True)
  def test_search(self, search_async):
    self.test_build.put()
    search_async.return_value = future(([self.test_build], 'the cursor'))

    time_low = model.BEGINING_OF_THE_WORLD
    time_high = datetime.datetime(2120, 5, 4)
    req = {
        'bucket': ['chromium'],
        'cancelation_reason': 'CANCELED_EXPLICITLY',
        'created_by': 'user:x@chromium.org',
        'result': 'CANCELED',
        'status': 'COMPLETED',
        'tag': ['important'],
        'retry_of': '42',
        'canary': True,
        'creation_ts_low': utils.datetime_to_timestamp(time_low),
        'creation_ts_high': utils.datetime_to_timestamp(time_high),
    }

    res = self.call_api('search', req).json_body

    search_async.assert_called_once_with(
        search.Query(
            buckets=req['bucket'],
            tags=req['tag'],
            status=search.StatusFilter.COMPLETED,
            result=model.BuildResult.CANCELED,
            failure_reason=None,
            cancelation_reason=model.CancelationReason.CANCELED_EXPLICITLY,
            created_by='user:x@chromium.org',
            max_builds=None,
            start_cursor=None,
            retry_of=42,
            canary=True,
            create_time_low=time_low,
            create_time_high=time_high,
        )
    )
    self.assertEqual(len(res['builds']), 1)
    self.assertEqual(res['builds'][0]['id'], str(self.test_build.key.id()))
    self.assertEqual(res['next_cursor'], 'the cursor')

  ####### PEEK #################################################################

  @mock.patch('service.peek', autospec=True)
  def test_peek(self, peek):
    self.test_build.put()
    peek.return_value = ([self.test_build], 'the cursor')
    req = {'bucket': [self.test_build.bucket]}
    res = self.call_api('peek', req).json_body
    peek.assert_called_once_with(
        req['bucket'],
        max_builds=None,
        start_cursor=None,
    )
    self.assertEqual(len(res['builds']), 1)
    peeked_build = res['builds'][0]
    self.assertEqual(peeked_build['id'], str(self.test_build.key.id()))
    self.assertEqual(res['next_cursor'], 'the cursor')

  ####### LEASE ################################################################

  @mock.patch('service.lease', autospec=True)
  def test_lease(self, lease):
    self.test_build.lease_expiration_date = self.future_date
    self.test_build.lease_key = 42
    lease.return_value = (True, self.test_build)

    req = {
        'id': self.test_build.key.id(),
        'lease_expiration_ts': self.future_ts,
    }
    res = self.call_api('lease', req).json_body
    lease.assert_called_once_with(
        self.test_build.key.id(),
        lease_expiration_date=self.future_date,
    )
    self.assertIsNone(res.get('error'))
    self.assertEqual(res['build']['id'], str(self.test_build.key.id()))
    self.assertEqual(res['build']['lease_key'], str(self.test_build.lease_key))
    self.assertEqual(
        res['build']['lease_expiration_ts'], req['lease_expiration_ts']
    )

  def test_lease_with_negative_expiration_date(self):
    req = {
        'id': self.test_build.key.id(),
        'lease_expiration_ts': 242894728472423847289472398,
    }
    self.expect_error('lease', req, 'INVALID_INPUT')

  @mock.patch('service.lease', autospec=True)
  def test_lease_unsuccessful(self, lease):
    self.test_build.put()
    lease.return_value = (False, self.test_build)
    req = {
        'id': self.test_build.key.id(),
        'lease_expiration_ts': self.future_ts,
    }
    self.expect_error('lease', req, 'CANNOT_LEASE_BUILD')

  ####### RESET ################################################################

  @mock.patch('service.reset', autospec=True)
  def test_reset(self, reset):
    reset.return_value = self.test_build
    req = {
        'id': self.test_build.key.id(),
    }
    res = self.call_api('reset', req).json_body
    reset.assert_called_once_with(self.test_build.key.id())
    self.assertIsNone(res.get('error'))
    self.assertEqual(res['build']['id'], str(self.test_build.key.id()))
    self.assertFalse('lease_key' in res['build'])

  ####### START ################################################################

  @mock.patch('service.start', autospec=True)
  def test_start(self, start):
    self.test_build.url = 'http://localhost/build/1'
    start.return_value = self.test_build
    req = {
        'id': self.test_build.key.id(),
        'lease_key': 42,
        'url': self.test_build.url,
        'canary': True,
    }
    res = self.call_api('start', req).json_body
    start.assert_called_once_with(
        req['id'], req['lease_key'], req['url'], req['canary']
    )
    self.assertEqual(int(res['build']['id']), req['id'])
    self.assertEqual(res['build']['url'], req['url'])

  @mock.patch('service.start', autospec=True)
  def test_start_completed_build(self, start):
    start.side_effect = errors.BuildIsCompletedError
    req = {
        'id': self.test_build.key.id(),
        'lease_key': 42,
    }
    res = self.call_api('start', req).json_body
    self.assertEqual(res['error']['reason'], 'BUILD_IS_COMPLETED')

  ####### HEATBEAT #############################################################

  @mock.patch('service.heartbeat', autospec=True)
  def test_heartbeat(self, heartbeat):
    self.test_build.lease_expiration_date = self.future_date
    heartbeat.return_value = self.test_build
    req = {
        'id': self.test_build.key.id(),
        'lease_key': 42,
        'lease_expiration_ts': self.future_ts,
    }
    res = self.call_api('heartbeat', req).json_body
    heartbeat.assert_called_once_with(
        req['id'], req['lease_key'], self.future_date
    )
    self.assertEqual(int(res['build']['id']), req['id'])
    self.assertEqual(
        res['build']['lease_expiration_ts'],
        req['lease_expiration_ts'],
    )

  @mock.patch('service.heartbeat_batch', autospec=True)
  def test_heartbeat_batch(self, heartbeat_batch):
    self.test_build.lease_expiration_date = self.future_date
    build2 = model.Build(
        id=2,
        bucket='chromium',
        lease_expiration_date=self.future_date,
    )

    heartbeat_batch.return_value = [
        (self.test_build.key.id(), self.test_build,
         None), (build2.key.id(), None, errors.LeaseExpiredError())
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
    heartbeat_batch.assert_called_with([{
        'build_id': self.test_build.key.id(),
        'lease_key': 42,
        'lease_expiration_date': self.future_date,
    }, {
        'build_id': build2.key.id(),
        'lease_key': 42,
        'lease_expiration_date': self.future_date,
    }])

    result1 = res['results'][0]
    self.assertEqual(int(result1['build_id']), self.test_build.key.id())
    self.assertEqual(result1['lease_expiration_ts'], self.future_ts)

    result2 = res['results'][1]
    self.assertEqual(int(result2['build_id']), build2.key.id())
    self.assertTrue(result2['error']['reason'] == 'LEASE_EXPIRED')

  @mock.patch('service.heartbeat_batch', autospec=True)
  def test_heartbeat_batch_with_internal_server_error(self, heartbeat_batch):
    self.test_build.lease_expiration_date = self.future_date

    heartbeat_batch.return_value = [
        (self.test_build.key.id(), None, ValueError())
    ]
    req = {
        'heartbeats': [{
            'build_id': self.test_build.key.id(),
            'lease_key': 42,
            'lease_expiration_ts': self.future_ts,
        }],
    }
    self.call_api('heartbeat_batch', req, status=500)

  ####### SUCCEED ##############################################################

  @mock.patch('service.succeed', autospec=True)
  def test_succeed(self, succeed):
    succeed.return_value = self.test_build
    req = {
        'id': self.test_build.key.id(),
        'lease_key': 42,
        'new_tags': ['bot_id:bot42'],
    }
    res = self.call_api('succeed', req).json_body
    succeed.assert_called_once_with(
        req['id'],
        req['lease_key'],
        result_details=None,
        url=None,
        new_tags=['bot_id:bot42']
    )
    self.assertEqual(int(res['build']['id']), req['id'])

  @mock.patch('service.succeed', autospec=True)
  def test_succeed_with_result_details(self, succeed):
    self.test_build.result_details = {'test_coverage': 100}
    self.test_build.tags = ['bot_id:bot42']
    succeed.return_value = self.test_build
    req = {
        'id': self.test_build.key.id(),
        'lease_key': 42,
        'result_details_json': json.dumps(self.test_build.result_details),
    }
    res = self.call_api('succeed', req).json_body
    _, kwargs = service.succeed.call_args
    self.assertEqual(kwargs['result_details'], self.test_build.result_details)
    self.assertEqual(
        res['build']['result_details_json'], req['result_details_json']
    )
    self.assertIn('bot_id:bot42', res['build']['tags'])

  ####### FAIL #################################################################

  @mock.patch('service.fail', autospec=True)
  def test_infra_failure(self, fail):
    self.test_build.result_details = {'transient_error': True}
    self.test_build.failure_reason = model.FailureReason.INFRA_FAILURE
    self.test_build.tags = ['bot_id:bot42']
    fail.return_value = self.test_build
    req = {
        'id': self.test_build.key.id(),
        'lease_key': 42,
        'failure_reason': 'INFRA_FAILURE',
        'result_details_json': json.dumps(self.test_build.result_details),
        'new_tags': ['bot_id:bot42'],
    }
    res = self.call_api('fail', req).json_body
    fail.assert_called_once_with(
        req['id'],
        req['lease_key'],
        result_details=self.test_build.result_details,
        failure_reason=model.FailureReason.INFRA_FAILURE,
        url=None,
        new_tags=['bot_id:bot42']
    )
    self.assertEqual(int(res['build']['id']), req['id'])
    self.assertEqual(res['build']['failure_reason'], req['failure_reason'])
    self.assertEqual(
        res['build']['result_details_json'], req['result_details_json']
    )

  ####### CANCEL ###############################################################

  @mock.patch('service.cancel', autospec=True)
  def test_cancel(self, cancel):
    cancel.return_value = self.test_build
    req = {
        'id': self.test_build.key.id(),
    }
    res = self.call_api('cancel', req).json_body
    cancel.assert_called_once_with(req['id'], result_details=None)
    self.assertEqual(int(res['build']['id']), req['id'])

  @mock.patch('service.cancel', autospec=True)
  def test_cancel_with_details(self, cancel):
    self.test_build.result_details = {'message': 'bye bye build'}
    cancel.return_value = self.test_build
    req = {
        'id': self.test_build.key.id(),
        'result_details_json': '{"message": "bye bye build"}',
    }
    res = self.call_api('cancel', req).json_body
    cancel.assert_called_once_with(
        req['id'], result_details=self.test_build.result_details
    )
    self.assertEqual(
        res['build']['result_details_json'], req['result_details_json']
    )

  def test_cancel_bad_details(self):
    req = {
        'id': self.test_build.key.id(),
        'result_details_json': '["no", "lists"]',
    }
    res = self.call_api('cancel', req).json_body
    self.assertEqual(res['error']['reason'], 'INVALID_INPUT')

  ####### CANCEL_BATCH #########################################################

  @mock.patch('service.cancel')
  def test_cancel_batch(self, cancel):
    self.test_build.result_details = {'message': 'bye bye build'}
    cancel.side_effect = [self.test_build, errors.BuildIsCompletedError]
    req = {
        'build_ids': [self.test_build.key.id(), 2],
        'result_details_json': '{"message": "bye bye build"}',
    }
    res = self.call_api('cancel_batch', req).json_body

    res0 = res['results'][0]
    self.assertEqual(int(res0['build_id']), self.test_build.key.id())
    self.assertEqual(int(res0['build']['id']), self.test_build.key.id())
    cancel.assert_any_call(
        self.test_build.key.id(), result_details=self.test_build.result_details
    )

    res1 = res['results'][1]
    self.assertEqual(int(res1['build_id']), 2)
    self.assertEqual(res1['error']['reason'], 'BUILD_IS_COMPLETED')
    cancel.assert_any_call(2, result_details=self.test_build.result_details)

  ####### DELETE_MANY_BUILDS ###################################################

  @mock.patch('service.delete_many_builds', autospec=True)
  def test_delete_many_builds(self, delete_many_builds):
    req = {
        'bucket': 'chromium',
        'status': 'SCHEDULED',
        'tag': ['tag:0'],
        'created_by': 'nodir@google.com',
    }
    self.call_api('delete_many_builds', req)
    delete_many_builds.assert_called_once_with(
        'chromium',
        model.BuildStatus.SCHEDULED,
        tags=['tag:0'],
        created_by='nodir@google.com'
    )

  ####### PAUSE ################################################################

  @mock.patch('service.pause', autospec=True)
  def test_pause(self, pause):
    req = {
        'bucket': 'foo.bar.baz',
        'is_paused': True,
    }
    res = self.call_api('pause', req).json_body
    pause.assert_called_once_with('foo.bar.baz', True)
    self.assertEqual(res, {})

  ####### GET_BUCKET ###########################################################

  @mock.patch('config.get_buildbucket_cfg_url', autospec=True)
  def test_get_bucket(self, get_buildbucket_cfg_url):
    get_buildbucket_cfg_url.return_value = 'https://example.com/buildbucket.cfg'

    bucket_cfg = config_test.parse_bucket_cfg(
        '''
      name: "master.tryserver.chromium.linux"
      acls {
        role: READER
        identity: "anonymous:anonymous"
      }
    '''
    )
    config.put_bucket('chromium', 'deadbeef', bucket_cfg)
    req = {
        'bucket': 'master.tryserver.chromium.linux',
    }
    res = self.call_api('get_bucket', req).json_body
    self.assertEqual(
        res, {
            'name': 'master.tryserver.chromium.linux',
            'project_id': 'chromium',
            'config_file_content': config_test.to_text(bucket_cfg),
            'config_file_url': 'https://example.com/buildbucket.cfg',
            'config_file_rev': 'deadbeef',
        }
    )

  @mock.patch('components.auth.is_admin', autospec=True)
  def test_get_bucket_not_found(self, is_admin):
    is_admin.return_value = True

    req = {
        'bucket': 'non-existent',
    }
    self.call_api('get_bucket', req, status=403)

  def test_get_bucket_with_auth_error(self):
    req = {
        'bucket': 'secret-project',
    }
    self.call_api('get_bucket', req, status=403)

  ####### ERRORS ###############################################################

  @mock.patch('service.get_async', autospec=True)
  def error_test(self, error_class, reason, get_async):
    get_async.return_value = future_exception(error_class(reason))
    self.expect_error('get', {'id': 123}, reason)

  def test_build_not_found_error(self):
    # pylint: disable=no-value-for-parameter
    self.error_test(errors.BuildNotFoundError, 'BUILD_NOT_FOUND')

  def test_invalid_input_error(self):
    # pylint: disable=no-value-for-parameter
    self.error_test(errors.InvalidInputError, 'INVALID_INPUT')

  def test_lease_expired_error(self):
    # pylint: disable=no-value-for-parameter
    self.error_test(errors.LeaseExpiredError, 'LEASE_EXPIRED')

  ####### BACKFILL_TAG_INDEX ###################################################

  @mock.patch('backfill_tag_index.launch')
  def test_backfill_tag_index(self, launch_tag_index_backfilling):
    auth.bootstrap_group(auth.ADMIN_GROUP, [auth.Anonymous])
    req = {'tag_key': 'buildset'}
    self.call_api('backfill_tag_index', req, status=(200, 204))
    launch_tag_index_backfilling.assert_called_once_with('buildset')

  def test_backfill_tag_index_fails(self):
    auth.bootstrap_group(auth.ADMIN_GROUP, [auth.Anonymous])
    self.call_api('backfill_tag_index', {}, status=400)
    self.call_api('backfill_tag_index', {'tag_key': 'a:b'}, status=400)
