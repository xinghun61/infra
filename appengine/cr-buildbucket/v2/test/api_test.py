# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from components import auth
from components import prpc
from components.prpc import context as prpc_context
from testing_utils import testing
import mock

from proto import build_pb2
from proto import rpc_pb2
from test import test_util
from v2 import api
import model
import service
import swarming

future = test_util.future

BUILDER_PARAMETER = swarming.BUILDER_PARAMETER


class BaseTestCase(testing.AppengineTestCase):
  """Base class for api.py tests."""

  def setUp(self):
    super(BaseTestCase, self).setUp()

    self.patch('acl.can_async', return_value=future(True))
    self.patch(
        'acl.get_acessible_buckets',
        autospec=True,
        return_value=['luci.chromium.try'])

    self.now = datetime.datetime(2015, 1, 1)
    self.patch('components.utils.utcnow', side_effect=lambda: self.now)

    self.api = api.BuildsApi()

  def call(self, method, req, expected_code=prpc.StatusCode.OK):
    ctx = prpc_context.ServicerContext()
    res = method(req, ctx)
    self.assertEqual(ctx.code, expected_code)
    if expected_code != prpc.StatusCode.OK:
      self.assertIsNone(res)
    return res

  def new_build(self, builder_name='linux-try', **kwargs):
    build_kwargs = dict(
        id=model.create_build_ids(self.now, 1)[0],
        project='chromium',
        bucket='luci.chromium.try',
        parameters={
            BUILDER_PARAMETER: builder_name,
        },
        status=model.BuildStatus.COMPLETED,
        result=model.BuildResult.SUCCESS,
        created_by=auth.Identity('user', 'johndoe@example.com'),
    )
    build_kwargs.update(kwargs)
    return model.Build(**build_kwargs)


class ApiMethodDecoratorTests(BaseTestCase):

  def error_handling_test(self, ex, expected_code, expected_details):
    method = api.api_method(mock.Mock(__name__='rpc', side_effect=ex))
    ctx = prpc_context.ServicerContext()
    method(None, None, ctx)
    self.assertEqual(ctx.code, expected_code)
    self.assertEqual(ctx.details, expected_details)

  def test_authorization_error_handling(self):
    self.error_handling_test(auth.AuthorizationError(),
                             prpc.StatusCode.NOT_FOUND, 'not found')

  def test_status_code_error_handling(self):
    self.error_handling_test(
        api.InvalidArgument('bad'), prpc.StatusCode.INVALID_ARGUMENT, 'bad')


class GetBuildTests(BaseTestCase):
  """Tests for GetBuild RPC."""

  @mock.patch('service.get', autospec=True)
  def test_by_id(self, service_get):
    service_get.return_value = self.new_build(id=54)
    req = rpc_pb2.GetBuildRequest(id=54)
    res = self.call(self.api.GetBuild, req)
    self.assertEqual(res.id, 54)
    service_get.assert_called_once_with(54)

  @mock.patch('service.search', autospec=True)
  def test_by_number(self, service_search):
    ds_build = self.new_build(
        project='chromium',
        bucket='luci.chromium.try',
        builder_name='linux-try',
        tags=[
            swarming.build_address_tag('luci.chromium.try', 'linux-try', 2),
        ],
    )
    service_search.return_value = ([ds_build], None)
    builder_id = build_pb2.Builder.ID(
        project='chromium', bucket='try', builder='linux-try')
    req = rpc_pb2.GetBuildRequest(builder=builder_id, build_number=2)
    res = self.call(self.api.GetBuild, req)
    self.assertEqual(res.id, ds_build.key.id())
    self.assertEqual(res.builder, builder_id)
    self.assertEqual(res.number, 2)

    service_search.assert_called_once_with(
        service.SearchQuery(
            buckets=['luci.chromium.try'],
            tags=['build_address:luci.chromium.try/linux-try/2'],
        ))

  def test_not_found_by_id(self):
    req = rpc_pb2.GetBuildRequest(id=54)
    self.call(self.api.GetBuild, req, expected_code=prpc.StatusCode.NOT_FOUND)

  def test_not_found_by_number(self):
    builder_id = build_pb2.Builder.ID(
        project='chromium', bucket='try', builder='linux-try')
    req = rpc_pb2.GetBuildRequest(builder=builder_id, build_number=2)
    self.call(self.api.GetBuild, req, expected_code=prpc.StatusCode.NOT_FOUND)

  def test_empty_request(self):
    req = rpc_pb2.GetBuildRequest()
    self.call(
        self.api.GetBuild, req, expected_code=prpc.StatusCode.INVALID_ARGUMENT)

  def test_id_with_number(self):
    req = rpc_pb2.GetBuildRequest(id=1, build_number=1)
    self.call(
        self.api.GetBuild, req, expected_code=prpc.StatusCode.INVALID_ARGUMENT)
