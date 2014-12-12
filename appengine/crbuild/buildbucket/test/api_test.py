# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import httplib
import json
import mock

from components import auth
from google.appengine.ext import ndb
from google.appengine.ext import testbed
from protorpc import messages
from test.testing_utils import testing
import endpoints

from buildbucket import api
from buildbucket import model
from buildbucket import service
import acl


def raiser(exception):
  """Returns a function that raises the |exception|."""
  def fn(*_, **__):
    raise exception
  return fn


class BuildBucketApiTest(testing.EndpointsTestCase):
  api_service_cls = api.BuildBucketApi

  def setUp(self):
    super(BuildBucketApiTest, self).setUp()
    self.service = mock.Mock()
    self.mock(api.BuildBucketApi, 'service_factory', lambda _: self.service)

    self.test_build = model.Build(
        namespace='chromium',
        properties={
            'buildername': 'linux_rel',
        },
    )

  def test_unavailable_build_to_message(self):
    yesterday = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    self.test_build.available_since = yesterday
    self.test_build.put()

    msg = api.build_to_message(self.test_build)
    self.assertEqual(msg.lease_duration_seconds, 0)

  ##################################### GET ####################################

  def test_get(self):
    lease_duration = datetime.timedelta(days=1)
    lease_duration_seconds = int(lease_duration.total_seconds())
    self.test_build.available_since = (
        datetime.datetime.utcnow() + lease_duration)

    self.test_build.put()
    build_id = self.test_build.key.id()
    self.service.get.return_value = self.test_build

    resp = self.call_api('get', {'id': build_id}).json_body
    self.service.get.assert_called_once_with(build_id)
    self.assertEqual(resp['id'], str(build_id))
    self.assertEqual(resp['namespace'], self.test_build.namespace)
    self.assertGreaterEqual(
        resp['lease_duration_seconds'], lease_duration_seconds - 1)
    self.assertLessEqual(
        resp['lease_duration_seconds'], lease_duration_seconds)
    self.assertEqual(resp['status'], 'SCHEDULED')
    self.assertEqual(resp['properties_json'], '{"buildername": "linux_rel"}')

  def test_get_nonexistent_build(self):
    self.service.get.return_value = None
    with self.call_should_fail(httplib.NOT_FOUND):
      self.call_api('get', {'id': 1})

  ##################################### PUT ####################################

  def test_put(self):
    self.test_build.available_since = (
        datetime.datetime.utcnow() + datetime.timedelta(hours=1))
    self.test_build.put()
    self.service.add.return_value = self.test_build
    req = {
        'namespace': self.test_build.namespace,
        'properties_json': json.dumps(self.test_build.properties),
        'lease_duration_seconds': 10,
    }
    resp = self.call_api('put', req).json_body
    self.service.add.assert_called_once_with(
        namespace=self.test_build.namespace,
        properties=self.test_build.properties,
        lease_duration=datetime.timedelta(seconds=10),
    )
    self.assertEqual(resp['id'], str(self.test_build.key.id()))
    self.assertEqual(resp['namespace'], req['namespace'])
    self.assertEqual(resp['properties_json'], req['properties_json'])
    self.assertGreater(resp['lease_duration_seconds'], 9)

  def test_put_with_id(self):
    with self.call_should_fail(httplib.BAD_REQUEST):
      self.call_api('put', {'id': 123, 'namespace': 'chromium'})

  def test_put_with_empty_namespace(self):
    with self.call_should_fail(httplib.BAD_REQUEST):
      self.call_api('put', {'namespace': ''})

  def test_put_with_malformed_properties_json(self):
    with self.call_should_fail(httplib.BAD_REQUEST):
      self.call_api('put', {
          'namespace':'chromium',
          'properties_json': '}non-json',
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
    self.test_build.put()

    def lease(*_, **__):
      self.test_build.regenerate_lease_key()
      self.test_build.put()
      return True, self.test_build

    self.service.lease.side_effect = lease

    req = {
        'id': self.test_build.key.id(),
        'duration_seconds': 10,
    }
    res = self.call_api('lease', req).json_body
    self.service.lease.assert_called_once_with(
        self.test_build.key.id(),
        duration=datetime.timedelta(seconds=10),
    )
    self.assertTrue(res['success'])
    self.assertEqual(res['build']['id'], str(self.test_build.key.id()))
    self.assertEqual(res['build']['lease_key'], str(self.test_build.lease_key))

  def test_lease_with_bad_duration(self):
    self.service.lease.side_effect = raiser(service.BadLeaseDurationError())
    with self.call_should_fail(httplib.BAD_REQUEST):
      self.call_api('lease', {
          'id': 1,
          'duration_seconds': -1,
      })

  def test_lease_unsuccessful(self):
    self.test_build.put()
    self.service.lease.return_value = (False, self.test_build)
    req = {
        'id': self.test_build.key.id(),
        'duration_seconds': 10,
    }
    res = self.call_api('lease', req).json_body
    self.assertFalse(res['success'])

  #################################### ERRORS ##################################

  def test_auth_error(self):
    self.service.get.side_effect = raiser(auth.AuthorizationError())
    with self.call_should_fail(httplib.FORBIDDEN):
      self.call_api('get', {'id': 123})

  def test_build_not_found_error(self):
    self.service.get.side_effect = raiser(service.BuildNotFoundError())
    with self.call_should_fail(httplib.NOT_FOUND):
      self.call_api('get', {'id': 123})
