# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from google.protobuf import field_mask_pb2
from google.protobuf import timestamp_pb2

from components import auth
from components import prpc
from components import protoutil
from components.prpc import context as prpc_context
from testing_utils import testing
import mock

from third_party import annotations_pb2

from proto import build_pb2
from proto import common_pb2
from proto import rpc_pb2
from proto import step_pb2
from test import test_util
from v2 import api
import buildtags
import model
import service

future = test_util.future


class BaseTestCase(testing.AppengineTestCase):
  """Base class for api.py tests."""

  def setUp(self):
    super(BaseTestCase, self).setUp()

    self.patch('user.can_async', return_value=future(True))
    self.patch(
        'user.get_acessible_buckets_async',
        autospec=True,
        return_value=future(['luci.chromium.try']),
    )

    self.now = datetime.datetime(2015, 1, 1)
    self.patch('components.utils.utcnow', side_effect=lambda: self.now)

    self.api = api.BuildsApi()

  def call(
      self,
      method,
      req,
      expected_code=prpc.StatusCode.OK,
      expected_details=None
  ):
    ctx = prpc_context.ServicerContext()
    res = method(req, ctx)
    self.assertEqual(ctx.code, expected_code)
    if expected_details is not None:
      self.assertEqual(ctx.details, expected_details)
    if expected_code != prpc.StatusCode.OK:
      self.assertIsNone(res)
    return res

  def new_build_v1(self, builder_name='linux-try', **kwargs):
    build_kwargs = dict(
        id=model.create_build_ids(self.now, 1)[0],
        project='chromium',
        bucket='luci.chromium.try',
        parameters={
            model.BUILDER_PARAMETER: builder_name,
        },
        status=model.BuildStatus.COMPLETED,
        result=model.BuildResult.SUCCESS,
        created_by=auth.Identity('user', 'johndoe@example.com'),
    )
    build_kwargs['parameters'].update(kwargs.pop('parameters', {}))
    build_kwargs.update(kwargs)
    return model.Build(**build_kwargs)


class ApiMethodDecoratorTests(BaseTestCase):

  def error_handling_test(self, ex, expected_code, expected_details):

    class Service(object):

      @api.api_method
      def GetBuild(self, _req, _ctx, _mask):
        raise ex

    ctx = prpc_context.ServicerContext()
    req = rpc_pb2.GetBuildRequest(id=1)
    Service().GetBuild(req, ctx)  # pylint: disable=no-value-for-parameter
    self.assertEqual(ctx.code, expected_code)
    self.assertEqual(ctx.details, expected_details)

  def test_authorization_error_handling(self):
    self.error_handling_test(
        auth.AuthorizationError(), prpc.StatusCode.NOT_FOUND, 'not found'
    )

  def test_status_code_error_handling(self):
    self.error_handling_test(
        api.InvalidArgument('bad'), prpc.StatusCode.INVALID_ARGUMENT, 'bad'
    )

  def test_invalid_field_mask(self):
    req = rpc_pb2.GetBuildRequest(
        fields=field_mask_pb2.FieldMask(paths=['invalid'])
    )
    self.call(
        self.api.GetBuild,
        req,
        expected_code=prpc.StatusCode.INVALID_ARGUMENT,
        expected_details=(
            'invalid fields: invalid path "invalid": '
            'field "invalid" does not exist in message '
            'buildbucket.v2.Build'
        )
    )

  @mock.patch('service.get', autospec=True)
  def test_trimming_exclude(self, service_get):
    service_get.return_value = self.new_build_v1(
        parameters={'properties': {'a': 'b'}}
    )
    req = rpc_pb2.GetBuildRequest(id=1)
    res = self.call(self.api.GetBuild, req)
    self.assertFalse(res.input.HasField('properties'))

  @mock.patch('service.get', autospec=True)
  def test_trimming_include(self, service_get):
    service_get.return_value = self.new_build_v1(
        parameters={
            'properties': {'a': 'b'},
        }
    )
    req = rpc_pb2.GetBuildRequest(
        id=1, fields=field_mask_pb2.FieldMask(paths=['input.properties'])
    )
    res = self.call(self.api.GetBuild, req)
    self.assertEqual(res.input.properties.items(), [('a', 'b')])


class ToBuildMessagesTests(BaseTestCase):

  def test_steps(self):
    build_v1 = self.new_build_v1()
    annotation_step = annotations_pb2.Step(
        substep=[
            annotations_pb2.Step.Substep(
                step=annotations_pb2.Step(
                    name='a',
                    status=annotations_pb2.SUCCESS,
                )
            ),
            annotations_pb2.Step.Substep(
                step=annotations_pb2.Step(
                    name='b',
                    status=annotations_pb2.RUNNING,
                )
            ),
        ],
    )
    model.BuildAnnotations(
        key=model.BuildAnnotations.key_for(build_v1.key),
        annotation_binary=annotation_step.SerializeToString(),
        annotation_url='logdog://logdog.example.com/project/prefix/+/stream',
    ).put()

    expected_steps = [
        step_pb2.Step(name='a', status=common_pb2.SUCCESS),
        step_pb2.Step(name='b', status=common_pb2.STARTED),
    ]
    mask = protoutil.Mask.from_field_mask(
        field_mask_pb2.FieldMask(paths=['steps']),
        build_pb2.Build.DESCRIPTOR,
    )
    actual = api.builds_to_v2([build_v1], mask)

    self.assertEqual(len(actual), 1)
    self.assertEqual(list(actual[0].steps), expected_steps)


class GetBuildTests(BaseTestCase):
  """Tests for GetBuild RPC."""

  @mock.patch('service.get', autospec=True)
  def test_by_id(self, service_get):
    service_get.return_value = self.new_build_v1(id=54)
    req = rpc_pb2.GetBuildRequest(id=54)
    res = self.call(self.api.GetBuild, req)
    self.assertEqual(res.id, 54)
    service_get.assert_called_once_with(54)

  @mock.patch('service.search', autospec=True)
  def test_by_number(self, service_search):
    build_v1 = self.new_build_v1(
        project='chromium',
        bucket='luci.chromium.try',
        builder_name='linux-try',
        tags=[
            buildtags.build_address_tag('luci.chromium.try', 'linux-try', 2),
        ],
    )
    service_search.return_value = ([build_v1], None)
    builder_id = build_pb2.BuilderID(
        project='chromium', bucket='try', builder='linux-try'
    )
    req = rpc_pb2.GetBuildRequest(builder=builder_id, build_number=2)
    res = self.call(self.api.GetBuild, req)
    self.assertEqual(res.id, build_v1.key.id())
    self.assertEqual(res.builder, builder_id)
    self.assertEqual(res.number, 2)

    service_search.assert_called_once_with(
        service.SearchQuery(
            buckets=['luci.chromium.try'],
            tags=['build_address:luci.chromium.try/linux-try/2'],
        )
    )

  def test_not_found_by_id(self):
    req = rpc_pb2.GetBuildRequest(id=54)
    self.call(self.api.GetBuild, req, expected_code=prpc.StatusCode.NOT_FOUND)

  def test_not_found_by_number(self):
    builder_id = build_pb2.BuilderID(
        project='chromium', bucket='try', builder='linux-try'
    )
    req = rpc_pb2.GetBuildRequest(builder=builder_id, build_number=2)
    self.call(self.api.GetBuild, req, expected_code=prpc.StatusCode.NOT_FOUND)

  def test_empty_request(self):
    req = rpc_pb2.GetBuildRequest()
    self.call(
        self.api.GetBuild, req, expected_code=prpc.StatusCode.INVALID_ARGUMENT
    )

  def test_id_with_number(self):
    req = rpc_pb2.GetBuildRequest(id=1, build_number=1)
    self.call(
        self.api.GetBuild, req, expected_code=prpc.StatusCode.INVALID_ARGUMENT
    )


class SearchTests(BaseTestCase):

  @mock.patch('service.search', autospec=True)
  def test_basic(self, service_search):
    builds_v1 = [self.new_build_v1(id=54), self.new_build_v1(id=55)]
    service_search.return_value = (builds_v1, 'next page token')

    req = rpc_pb2.SearchBuildsRequest(
        predicate=rpc_pb2.BuildPredicate(
            builder=build_pb2.BuilderID(
                project='chromium', bucket='try', builder='linux-try'
            ),
        ),
    )
    res = self.call(self.api.SearchBuilds, req)

    service_search.assert_called_once_with(
        service.SearchQuery(
            buckets=['luci.chromium.try'],
            tags=['builder:linux-try'],
            include_experimental=False,
            status=common_pb2.STATUS_UNSPECIFIED,
            start_cursor='',
        )
    )
    self.assertEqual(len(res.builds), 2)
    self.assertEqual(res.builds[0].id, 54)
    self.assertEqual(res.builds[1].id, 55)
    self.assertEqual(res.next_page_token, 'next page token')


class BuildPredicateToSearchQueryTests(BaseTestCase):

  def test_create_time(self):
    predicate = rpc_pb2.BuildPredicate()
    predicate.create_time.start_time.FromDatetime(datetime.datetime(2018, 1, 1))
    predicate.create_time.end_time.FromDatetime(datetime.datetime(2018, 1, 2))
    q = api.build_predicate_to_search_query(predicate)
    self.assertEqual(q.create_time_low, datetime.datetime(2018, 1, 1))
    self.assertEqual(q.create_time_high, datetime.datetime(2018, 1, 2))
