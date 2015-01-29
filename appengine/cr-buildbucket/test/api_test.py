# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import httplib
import json
import mock

from components import auth
from components import utils
from google.appengine.ext import ndb
from google.appengine.ext import testbed
from protorpc import messages
from testing_utils import testing
import endpoints

import acl
import api
import errors
import model
import service


class BuildBucketApiTest(testing.EndpointsTestCase):
  api_service_cls = api.BuildBucketApi

  def setUp(self):
    super(BuildBucketApiTest, self).setUp()
    self.service = mock.Mock()
    self.mock(api.BuildBucketApi, 'service_factory', lambda _: self.service)

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
    self.service.get.return_value = self.test_build

    resp = self.call_api('get', {'id': build_id}).json_body
    self.service.get.assert_called_once_with(build_id)
    self.assertEqual(resp['build']['id'], str(build_id))
    self.assertEqual(resp['build']['bucket'], self.test_build.bucket)
    self.assertEqual(resp['build']['lease_expiration_ts'], self.future_ts)
    self.assertEqual(resp['build']['status'], 'SCHEDULED')
    self.assertEqual(
        resp['build']['parameters_json'], '{"buildername": "linux_rel"}')

  def test_get_nonexistent_build(self):
    self.service.get.return_value = None
    self.expect_error('get', {'id': 1}, 'BUILD_NOT_FOUND')

  ##################################### PUT ####################################

  def test_put(self):
    self.test_build.tags = ['owner=ivan']
    self.service.add.return_value = self.test_build
    req = {
        'bucket': self.test_build.bucket,
        'tags': self.test_build.tags,
    }
    resp = self.call_api('put', req).json_body
    self.service.add.assert_called_once_with(
        bucket=self.test_build.bucket,
        tags=req['tags'],
        parameters=None,
        lease_expiration_date=None,
    )
    self.assertEqual(resp['build']['id'], str(self.test_build.key.id()))
    self.assertEqual(resp['build']['bucket'], req['bucket'])
    self.assertEqual(resp['build']['tags'], req['tags'])

  def test_put_with_parameters(self):
    self.service.add.return_value = self.test_build
    req = {
        'bucket': self.test_build.bucket,
        'parameters_json': json.dumps(self.test_build.parameters),
    }
    resp = self.call_api('put', req).json_body
    self.assertEqual(resp['build']['parameters_json'], req['parameters_json'])

  def test_put_with_leasing(self):
    self.test_build.lease_expiration_date = self.future_date
    self.service.add.return_value = self.test_build
    req = {
        'bucket': self.test_build.bucket,
        'lease_expiration_ts': self.future_ts,
    }
    resp = self.call_api('put', req).json_body
    self.service.add.assert_called_once_with(
        bucket=self.test_build.bucket,
        tags=[],
        parameters=None,
        lease_expiration_date=self.future_date,
    )
    self.assertEqual(
        resp['build']['lease_expiration_ts'], req['lease_expiration_ts'])

  def test_put_with_empty_bucket(self):
    self.expect_error('put', {'bucket': ''}, 'INVALID_INPUT')

  def test_put_with_malformed_parameters_json(self):
    req = {
        'bucket':'chromium',
        'parameters_json': '}non-json',
    }
    self.expect_error('put', req, 'INVALID_INPUT')

  #################################### SEARCH ##################################

  def test_search(self):
    self.test_build.put()
    self.service.search.return_value = ([self.test_build], 'the cursor')
    req = {
        'tag': ['important'],
        'bucket': ['chromium'],
    }

    res = self.call_api('search', req).json_body

    self.service.search.assert_called_once_with(
        tags=req['tag'],
        buckets=req['bucket'],
        max_builds=None,
        start_cursor=None)
    self.assertEqual(len(res['builds']), 1)
    self.assertEqual(res['builds'][0]['id'], str(self.test_build.key.id()))
    self.assertEqual(res['next_cursor'], 'the cursor')

  ##################################### PEEK ###################################

  def test_peek(self):
    self.test_build.put()
    self.service.peek.return_value = ([self.test_build], 'the cursor')
    req = {'bucket': [self.test_build.bucket]}
    res = self.call_api('peek', req).json_body
    self.service.peek.assert_called_once_with(
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
    self.service.lease.return_value = True, self.test_build

    req = {
        'id': self.test_build.key.id(),
        'lease_expiration_ts': self.future_ts,
    }
    res = self.call_api('lease', req).json_body
    self.service.lease.assert_called_once_with(
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
    self.service.lease.return_value = (False, self.test_build)
    req = {
        'id': self.test_build.key.id(),
        'lease_expiration_ts': self.future_ts,
    }
    self.expect_error('lease', req, 'CANNOT_LEASE_BUILD')

  #################################### RESET ###################################

  def test_reset(self):
    self.service.reset.return_value = self.test_build
    req = {
        'id': self.test_build.key.id(),
    }
    res = self.call_api('reset', req).json_body
    self.service.reset.assert_called_once_with(self.test_build.key.id())
    self.assertIsNone(res.get('error'))
    self.assertEqual(res['build']['id'], str(self.test_build.key.id()))
    self.assertFalse('lease_key' in res['build'])

  #################################### START ###################################

  def test_start(self):
    self.test_build.url = 'http://localhost/build/1'
    self.service.start.return_value = self.test_build
    req = {
        'id': self.test_build.key.id(),
        'lease_key': 42,
        'url': self.test_build.url,
    }
    res = self.call_api('start', req).json_body
    self.service.start.assert_called_once_with(
        req['id'], req['lease_key'], url=req['url'])
    self.assertEqual(int(res['build']['id']), req['id'])
    self.assertEqual(res['build']['url'], req['url'])

  def test_start_completed_build(self):
    def raise_completed(*_, **__):
      raise errors.BuildIsCompletedError()
    self.service.start.side_effect = raise_completed
    req = {
        'id': self.test_build.key.id(),
        'lease_key': 42,
    }
    res = self.call_api('start', req).json_body
    self.assertEqual(res['error']['reason'], 'BUILD_IS_COMPLETED')

  #################################### HEATBEAT ################################

  def test_heartbeat(self):
    self.test_build.lease_expiration_date = self.future_date
    self.service.heartbeat.return_value = self.test_build
    req = {
        'id': self.test_build.key.id(),
        'lease_key': 42,
        'lease_expiration_ts': self.future_ts,
    }
    res = self.call_api('heartbeat', req).json_body
    self.service.heartbeat.assert_called_once_with(
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

    def service_heartbeat(build_id, *_, **__):
      if build_id == self.test_build.key.id():
        return self.test_build
      raise errors.LeaseExpiredError()
    self.service.heartbeat.side_effect = service_heartbeat

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
    self.service.heartbeat_batch.assert_called_any_with(
        self.test_build.key.id(), 42, self.future_date)
    self.service.heartbeat_batch.assert_called_any_with(
        build2.key.id(), 42, self.future_date)

    result1 = res['results'][0]
    self.assertEqual(int(result1['build_id']), self.test_build.key.id())
    self.assertEqual(result1['lease_expiration_ts'], self.future_ts)

    result2 = res['results'][1]
    self.assertEqual(int(result2['build_id']), build2.key.id())
    self.assertTrue(result2['error']['reason'] == 'LEASE_EXPIRED')

  ################################## SUCCEED ###################################

  def test_succeed(self):
    self.service.succeed.return_value = self.test_build
    req = {
        'id': self.test_build.key.id(),
        'lease_key': 42,
    }
    res = self.call_api('succeed', req).json_body
    self.service.succeed.assert_called_once_with(
        req['id'], req['lease_key'], result_details=None, url=None)
    self.assertEqual(int(res['build']['id']), req['id'])

  def test_succeed_with_result_details(self):
    self.test_build.result_details = {'test_coverage': 100}
    self.service.succeed.return_value = self.test_build
    req = {
        'id': self.test_build.key.id(),
        'lease_key': 42,
        'result_details_json': json.dumps(self.test_build.result_details),
    }
    res = self.call_api('succeed', req).json_body
    _, kwargs = self.service.succeed.call_args
    self.assertEqual(
            kwargs['result_details'], self.test_build.result_details)
    self.assertEqual(
            res['build']['result_details_json'], req['result_details_json'])

  #################################### FAIL ####################################

  def test_infra_failure(self):
    self.test_build.result_details = {'transient_error': True}
    self.test_build.failure_reason = model.FailureReason.INFRA_FAILURE
    self.service.fail.return_value = self.test_build
    req = {
        'id': self.test_build.key.id(),
        'lease_key': 42,
        'failure_reason': 'INFRA_FAILURE',
        'result_details_json': json.dumps(self.test_build.result_details),
    }
    res = self.call_api('fail', req).json_body
    self.service.fail.assert_called_once_with(
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
    self.service.cancel.return_value = self.test_build
    req = {
        'id': self.test_build.key.id(),
    }
    res = self.call_api('cancel', req).json_body
    self.service.cancel.assert_called_once_with(req['id'])
    self.assertEqual(int(res['build']['id']), req['id'])


  #################################### ACL ##################################

  def test_get_acl(self):
    bucket_acl = acl.BucketAcl(
        rules=[
            acl.Rule(role='READER', group='readers'),
            acl.Rule(role='WRITER', group='writers'),
        ],
        modified_time=datetime.datetime(2015, 1, 1),
        modified_by=auth.Identity.from_bytes('user:a@example.com'),
    )
    self.mock(acl, 'get_acl', mock.Mock(return_value=bucket_acl))

    req = {
        'bucket': 'bucket',
    }
    res = self.call_api('get_acl', req).json_body
    acl.get_acl.assert_called_once_with('bucket')
    self.assertEqual(res, {
        'acl': {
            'rules': [
                {'role': 'READER', 'group': 'readers'},
                {'role': 'WRITER', 'group': 'writers'},
            ],
            'modified_ts': '1420070400000000',
            'modified_by': 'user:a@example.com',
        },
    })

  def test_get_empty_acl(self):
    self.mock(acl, 'get_acl', mock.Mock(return_value=None))
    req = {
        'bucket': 'bucket',
    }
    res = self.call_api('get_acl', req).json_body
    self.assertEqual(res, {})

  def test_set_acl(self):
    rules = [
        acl.Rule(role='READER', group='readers'),
        acl.Rule(role='WRITER', group='writers'),
    ]
    get_acl_result = acl.BucketAcl(
        rules=rules,
        modified_time=datetime.datetime(2015, 1, 1),
        modified_by=auth.Identity.from_bytes('user:a@example.com'),
    )
    self.mock(acl, 'get_acl', mock.Mock(return_value=get_acl_result))
    self.mock(acl, 'set_acl', mock.Mock())
    req = {
        'bucket': 'bucket',
        'rules': [
            {'role': 'READER', 'group': 'readers'},
            {'role': 'WRITER', 'group': 'writers'},
        ],
    }
    res = self.call_api('set_acl', req).json_body

    expected = acl.BucketAcl(rules=rules)
    acl.set_acl.assert_called_once_with('bucket', expected)
    self.assertEqual(res, {
        'acl': {
            'rules': req['rules'],
            'modified_ts': '1420070400000000',
            'modified_by': 'user:a@example.com',
        },
    })


  def test_set_acl_with_invalid_input(self):
    def expect_invalid_input_error(rule, bucket='bucket'):
      req = {
          'bucket': bucket,
          'rules': [rule],
      }
      res = self.call_api('set_acl', req).json_body
      self.assertTrue('error' in res)
      self.assertEqual(res['error']['reason'], 'INVALID_INPUT')

    expect_invalid_input_error(
        {'role': 'READER', 'group': 'good group'}, bucket='bad bucket')
    expect_invalid_input_error({'role': 'bad role', 'group': 'good group'})
    expect_invalid_input_error({'role': 'READER', 'group': 'bad/ group'})

  #################################### ERRORS ##################################

  def error_test(self, error_class, reason):
    def raise_service_error(*_, **__):
      raise error_class()
    self.service.get.side_effect = raise_service_error
    self.expect_error('get', {'id': 123}, reason)

  def test_build_not_found_error(self):
    self.error_test(errors.BuildNotFoundError, 'BUILD_NOT_FOUND')

  def test_invalid_input_error(self):
    self.error_test(errors.InvalidInputError, 'INVALID_INPUT')

  def test_invalid_build_state_error(self):
    self.error_test(errors.InvalidBuildStateError, 'INVALID_BUILD_STATE')

  def test_lease_expired_error(self):
    self.error_test(errors.LeaseExpiredError, 'LEASE_EXPIRED')
