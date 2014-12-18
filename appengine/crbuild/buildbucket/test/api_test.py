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
from test.testing_utils import testing
import endpoints

from buildbucket import api
from buildbucket import model
from buildbucket import service
import acl


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
        namespace='chromium',
        parameters={
            'buildername': 'linux_rel',
        },
    )

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
    self.assertEqual(resp['id'], str(build_id))
    self.assertEqual(resp['namespace'], self.test_build.namespace)
    self.assertEqual(resp['lease_expiration_ts'], self.future_ts)
    self.assertEqual(resp['status'], 'SCHEDULED')
    self.assertEqual(resp['parameters_json'], '{"buildername": "linux_rel"}')

  def test_get_nonexistent_build(self):
    self.service.get.return_value = None
    with self.call_should_fail(httplib.NOT_FOUND):
      self.call_api('get', {'id': 1})

  ##################################### PUT ####################################

  def test_put(self):
    self.service.add.return_value = self.test_build
    req = {
        'namespace': self.test_build.namespace,
    }
    resp = self.call_api('put', req).json_body
    self.service.add.assert_called_once_with(
        namespace=self.test_build.namespace,
        parameters=None,
        lease_expiration_date=None,
    )
    self.assertEqual(resp['id'], str(self.test_build.key.id()))
    self.assertEqual(resp['namespace'], req['namespace'])

  def test_put_with_parameters(self):
    self.service.add.return_value = self.test_build
    req = {
        'namespace': self.test_build.namespace,
        'parameters_json': json.dumps(self.test_build.parameters),
    }
    resp = self.call_api('put', req).json_body
    self.assertEqual(resp['parameters_json'], req['parameters_json'])

  def test_put_with_leasing(self):
    self.test_build.lease_expiration_date = self.future_date
    self.service.add.return_value = self.test_build
    req = {
        'namespace': self.test_build.namespace,
        'lease_expiration_ts': self.future_ts,
    }
    resp = self.call_api('put', req).json_body
    self.service.add.assert_called_once_with(
        namespace=self.test_build.namespace,
        parameters=None,
        lease_expiration_date=self.future_date,
    )
    self.assertEqual(resp['lease_expiration_ts'], req['lease_expiration_ts'])

  def test_put_with_id(self):
    with self.call_should_fail(httplib.BAD_REQUEST):
      self.call_api('put', {'id': 123, 'namespace': 'chromium'})

  def test_put_with_empty_namespace(self):
    with self.call_should_fail(httplib.BAD_REQUEST):
      self.call_api('put', {'namespace': ''})

  def test_put_with_malformed_parameters_json(self):
    with self.call_should_fail(httplib.BAD_REQUEST):
      self.call_api('put', {
          'namespace':'chromium',
          'parameters_json': '}non-json',
      })

  ##################################### PEEK ###################################

  def test_peek(self):
    self.test_build.put()
    self.service.peek.return_value = [self.test_build]
    self.test_build.put()
    req = {'namespace': [self.test_build.namespace]}
    res = self.call_api('peek', req).json_body
    self.assertEqual(len(res['builds']), 1)
    peeked_build = res['builds'][0]
    self.assertEqual(peeked_build['id'], str(self.test_build.key.id()))

  def test_peek_without_namespaces(self):
    with self.call_should_fail(httplib.BAD_REQUEST):
      self.call_api('peek', {})

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
    self.assertTrue(res['success'])
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
    with self.call_should_fail(httplib.BAD_REQUEST):
      self.call_api('lease', req)

  def test_lease_unsuccessful(self):
    self.test_build.put()
    self.service.lease.return_value = (False, self.test_build)
    req = {
        'id': self.test_build.key.id(),
        'lease_expiration_ts': self.future_ts,
    }
    res = self.call_api('lease', req).json_body
    self.assertFalse(res['success'])

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
    self.assertEqual(int(res['id']), req['id'])
    self.assertEqual(res['url'], req['url'])

  #################################### HEATBEAT ################################

  def test_heartbeat(self):
    self.test_build.lease_expiration_date = self.future_date
    self.service.heartbeat.return_value = self.test_build
    req = {
        'id': self.test_build.key.id(),
        'lease_key': 42,
        'lease_expiration_ts': self.future_ts,
    }
    res = self.call_api('hearbeat', req).json_body
    self.service.heartbeat.assert_called_once_with(
        req['id'], req['lease_key'], self.future_date)
    self.assertEqual(int(res['id']), req['id'])
    self.assertEqual(
        res['lease_expiration_ts'],
        req['lease_expiration_ts'],
    )

  ################################## SUCCEED ###################################

  def test_succeed(self):
    self.service.succeed.return_value = self.test_build
    req = {
        'id': self.test_build.key.id(),
        'lease_key': 42,
        'success': True,
    }
    res = self.call_api('succeed', req).json_body
    self.service.succeed.assert_called_once_with(req['id'], req['lease_key'])
    self.assertEqual(int(res['id']), req['id'])

  #################################### FAIL ####################################

  def test_infra_failure(self):
    self.service.fail.return_value = self.test_build
    req = {
        'id': self.test_build.key.id(),
        'lease_key': 42,
        'failure_reason': 'INFRA_FAILURE',
    }
    res = self.call_api('fail', req).json_body
    self.service.fail.assert_called_once_with(
        req['id'], req['lease_key'],
        failure_reason=model.FailureReason.INFRA_FAILURE)
    self.assertEqual(int(res['id']), req['id'])

  #################################### CANCEL ##################################

  def test_cancel(self):
    self.service.cancel.return_value = self.test_build
    req = {
        'id': self.test_build.key.id(),
    }
    res = self.call_api('cancel', req).json_body
    self.service.cancel.assert_called_once_with(req['id'])
    self.assertEqual(int(res['id']), req['id'])

  #################################### ERRORS ##################################

  def error_test(self, service_error_class, status_code):
    def raise_service_error(*_, **__):
      raise service_error_class()
    self.service.get.side_effect = raise_service_error
    with self.call_should_fail(status_code):
      self.call_api('get', {'id': 123})

  def test_auth_error(self):
    self.error_test(auth.AuthorizationError, httplib.FORBIDDEN)

  def test_build_not_found_error(self):
    self.error_test(service.BuildNotFoundError, httplib.NOT_FOUND)

  def test_invalid_input_error(self):
    self.error_test(service.InvalidInputError, httplib.BAD_REQUEST)

  def test_invalid_build_state_error(self):
    self.error_test(service.InvalidBuildStateError, httplib.BAD_REQUEST)
