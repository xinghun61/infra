# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import copy
import os
import datetime

from google.appengine.ext import ndb
from google.protobuf import field_mask_pb2
from google.protobuf import timestamp_pb2
from google.protobuf import text_format
from google.rpc import status_pb2

from components import auth
from components import prpc
from components import protoutil
from components import utils
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
from v2 import tokens
from v2 import validation
import annotations
import buildtags
import model
import search
import service

future = test_util.future

THIS_DIR = os.path.dirname(os.path.abspath(__file__))


class BaseTestCase(testing.AppengineTestCase):
  """Base class for api.py tests."""

  def setUp(self):
    super(BaseTestCase, self).setUp()

    self.patch('user.can_async', return_value=future(True))
    self.patch(
        'user.get_accessible_buckets_async',
        autospec=True,
        return_value=future({'chromium/try'}),
    )

    self.now = datetime.datetime(2015, 1, 1)
    self.patch('components.utils.utcnow', side_effect=lambda: self.now)

    self.api = api.BuildsApi()

  def call(
      self,
      method,
      req,
      ctx=None,
      expected_code=prpc.StatusCode.OK,
      expected_details=None
  ):
    ctx = ctx or prpc_context.ServicerContext()
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
        bucket_id='chromium/try',
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


class RpcImplTests(BaseTestCase):

  def error_handling_test(self, ex, expected_code, expected_details):

    @api.rpc_impl_async('GetBuild')
    @ndb.tasklet
    def get_build_async(_req, _ctx, _mask):
      raise ex

    ctx = prpc_context.ServicerContext()
    req = rpc_pb2.GetBuildRequest(id=1)
    # pylint: disable=no-value-for-parameter
    get_build_async(req, ctx).get_result()
    self.assertEqual(ctx.code, expected_code)
    self.assertEqual(ctx.details, expected_details)

  def test_authorization_error_handling(self):
    self.error_handling_test(
        auth.AuthorizationError(), prpc.StatusCode.NOT_FOUND, 'not found'
    )

  def test_status_code_error_handling(self):
    self.error_handling_test(
        api.invalid_argument('bad'), prpc.StatusCode.INVALID_ARGUMENT, 'bad'
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

  @mock.patch('service.get_async', autospec=True)
  def test_trimming_exclude(self, get_async):
    get_async.return_value = future(
        self.new_build_v1(parameters={model.PROPERTIES_PARAMETER: {'a': 'b'}})
    )
    req = rpc_pb2.GetBuildRequest(id=1)
    res = self.call(self.api.GetBuild, req)
    self.assertFalse(res.input.HasField('properties'))

  @mock.patch('service.get_async', autospec=True)
  def test_trimming_include(self, get_async):
    get_async.return_value = future(
        self.new_build_v1(parameters={
            model.PROPERTIES_PARAMETER: {'a': 'b'},
        }),
    )
    req = rpc_pb2.GetBuildRequest(
        id=1, fields=field_mask_pb2.FieldMask(paths=['input.properties'])
    )
    res = self.call(self.api.GetBuild, req)
    self.assertEqual(res.input.properties.items(), [('a', 'b')])


class ToBuildMessagesTests(BaseTestCase):

  def test_steps(self):
    build_v1 = self.new_build_v1()
    steps = [
        step_pb2.Step(name='a', status=common_pb2.SUCCESS),
        step_pb2.Step(name='b', status=common_pb2.STARTED),
    ]
    model.BuildSteps(
        key=model.BuildSteps.key_for(build_v1.key),
        step_container=build_pb2.Build(steps=steps),
    ).put()

    mask = protoutil.Mask.from_field_mask(
        field_mask_pb2.FieldMask(paths=['steps']),
        build_pb2.Build.DESCRIPTOR,
    )
    actual = api.builds_to_v2_async([build_v1], mask).get_result()

    self.assertEqual(len(actual), 1)
    self.assertEqual(list(actual[0].steps), steps)


class GetBuildTests(BaseTestCase):
  """Tests for GetBuild RPC."""

  @mock.patch('service.get_async', autospec=True)
  def test_by_id(self, get_async):
    get_async.return_value = future(self.new_build_v1(id=54))
    req = rpc_pb2.GetBuildRequest(id=54)
    res = self.call(self.api.GetBuild, req)
    self.assertEqual(res.id, 54)
    get_async.assert_called_once_with(54)

  @mock.patch('search.search_async', autospec=True)
  def test_by_number(self, search_async):
    build_v1 = self.new_build_v1(
        bucket_id='chromium/try',
        builder_name='linux-try',
        tags=[
            buildtags.build_address_tag('luci.chromium.try', 'linux-try', 2),
        ],
    )
    search_async.return_value = future(([build_v1], None))
    builder_id = build_pb2.BuilderID(
        project='chromium', bucket='try', builder='linux-try'
    )
    req = rpc_pb2.GetBuildRequest(builder=builder_id, build_number=2)
    res = self.call(self.api.GetBuild, req)
    self.assertEqual(res.id, build_v1.key.id())
    self.assertEqual(res.builder, builder_id)
    self.assertEqual(res.number, 2)

    search_async.assert_called_once_with(
        search.Query(
            bucket_ids=['chromium/try'],
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

  @mock.patch('search.search_async', autospec=True)
  def test_basic(self, search_async):
    builds_v1 = [self.new_build_v1(id=54), self.new_build_v1(id=55)]
    search_async.return_value = future((builds_v1, 'next page token'))

    req = rpc_pb2.SearchBuildsRequest(
        predicate=rpc_pb2.BuildPredicate(
            builder=build_pb2.BuilderID(
                project='chromium', bucket='try', builder='linux-try'
            ),
        ),
        page_size=10,
        page_token='page token',
    )
    res = self.call(self.api.SearchBuilds, req)

    search_async.assert_called_once_with(
        search.Query(
            bucket_ids=['chromium/try'],
            tags=['builder:linux-try'],
            include_experimental=False,
            status=common_pb2.STATUS_UNSPECIFIED,
            max_builds=10,
            start_cursor='page token',
        )
    )
    self.assertEqual(len(res.builds), 2)
    self.assertEqual(res.builds[0].id, 54)
    self.assertEqual(res.builds[1].id, 55)
    self.assertEqual(res.next_page_token, 'next page token')


class UpdateBuildTests(BaseTestCase):

  def setUp(self):
    super(UpdateBuildTests, self).setUp()
    self.validate_build_token = self.patch(
        'v2.tokens.validate_build_token',
        autospec=True,
        return_value=None,
    )

    self.can_update_build_async = self.patch(
        'user.can_update_build_async',
        autospec=True,
        return_value=future(True),
    )

  def _mk_update_req(self, build, token='token'):
    build_req = rpc_pb2.UpdateBuildRequest(build=build)
    build_req.update_mask.paths[:] = ['build.steps']
    ctx = prpc_context.ServicerContext()
    if token:
      metadata = ctx.invocation_metadata()
      metadata.append((api.BUILD_TOKEN_HEADER, token))
    return build_req, ctx

  @contextlib.contextmanager
  def mock_build(self, build_id):
    build = model.Build(
        id=build_id,
        status=model.BuildStatus.STARTED,
        bucket_id='chromium/try',
        created_by=auth.Identity('user', 'foo@google.com'),
        create_time=utils.utcnow(),
        start_time=utils.utcnow(),
        parameters_actual=dict(),
    )
    build.put()
    yield build

  def test_update_steps(self):
    with self.mock_build(build_id=123) as build:
      build_proto = build_pb2.Build(id=123)
      with open(os.path.join(THIS_DIR, 'steps.pb.txt')) as f:
        text = protoutil.parse_multiline(f.read())
        text_format.Merge(text, build_proto)

      req, ctx = self._mk_update_req(build_proto)
      req.fields.paths[:] = ['id', 'steps']
      actual = self.call(self.api.UpdateBuild, req, ctx=ctx)
      self.assertEqual(actual, build_proto)

      persisted = model.BuildSteps.key_for(build.key).get()
      self.assertEqual(persisted.step_container.steps, build_proto.steps)

  def test_update_properties(self):
    with self.mock_build(build_id=123) as build:
      expected_props = {'a': 1}
      build_steps = model.BuildSteps(
          key=model.BuildSteps.key_for(build.key),
          step_container=build_pb2.Build(
              steps=[step_pb2.Step(name='bot_update')],
          ),
      )
      build_steps.put()

      build_proto = build_pb2.Build(id=123)
      build_proto.output.properties.update(expected_props)

      req, ctx = self._mk_update_req(build_proto)
      req.update_mask.paths[:] = ['build.output.properties']
      req.fields.paths[:] = ['id', 'steps', 'output.properties']
      actual = self.call(self.api.UpdateBuild, req, ctx=ctx)
      expected = copy.deepcopy(build_proto)
      expected.MergeFrom(build_steps.step_container)
      self.assertEqual(actual, expected)

      build = build.key.get()
      self.assertEqual(
          build.result_details[model.PROPERTIES_PARAMETER], expected_props
      )

  def test_missing_token(self):
    build = build_pb2.Build(
        id=123,
        status=common_pb2.STARTED,
    )
    req, ctx = self._mk_update_req(build, token=None)
    self.call(
        self.api.UpdateBuild,
        req,
        ctx=ctx,
        expected_code=prpc.StatusCode.UNAUTHENTICATED,
        expected_details='missing token in build update request',
    )

  def test_invalid_token(self):
    self.validate_build_token.side_effect = auth.InvalidTokenError

    build = build_pb2.Build(
        id=123,
        status=common_pb2.STARTED,
    )

    req, ctx = self._mk_update_req(build)
    self.call(
        self.api.UpdateBuild,
        req,
        ctx=ctx,
        expected_code=prpc.StatusCode.UNAUTHENTICATED,
    )

  @mock.patch('v2.validation.validate_update_build_request', autospec=True)
  def test_invalid_build_proto(self, mock_validation):
    mock_validation.side_effect = validation.Error('invalid build proto')

    build = build_pb2.Build(id=123)

    req, ctx = self._mk_update_req(build)
    self.call(
        self.api.UpdateBuild,
        req,
        ctx=ctx,
        expected_code=prpc.StatusCode.INVALID_ARGUMENT,
        expected_details='invalid build proto',
    )

  @mock.patch('service.get_async', autospec=True)
  def test_invalid_id(self, mock_get_async):
    mock_get_async.return_value = future(None)

    build = build_pb2.Build(
        id=123,
        status=common_pb2.STARTED,
    )

    req, ctx = self._mk_update_req(build)
    self.call(
        self.api.UpdateBuild,
        req,
        ctx=ctx,
        expected_code=prpc.StatusCode.NOT_FOUND,
        expected_details='Cannot update nonexisting build with id 123',
    )

  def test_invalid_user(self):
    self.can_update_build_async.return_value = future(False)

    build = build_pb2.Build(
        id=123,
        status=common_pb2.STARTED,
    )

    req, ctx = self._mk_update_req(build)
    self.call(
        self.api.UpdateBuild,
        req,
        ctx=ctx,
        expected_code=prpc.StatusCode.PERMISSION_DENIED,
        expected_details='anonymous:anonymous not permitted to update build',
    )


class BatchTests(BaseTestCase):

  @mock.patch('service.get_async', autospec=True)
  @mock.patch('search.search_async', autospec=True)
  def test_get_and_search(self, search_async, get_async):
    search_async.return_value = future(([
        self.new_build_v1(id=1),
        self.new_build_v1(id=2)
    ], ''))
    get_async.return_value = future(self.new_build_v1(id=3))

    req = rpc_pb2.BatchRequest(
        requests=[
            rpc_pb2.BatchRequest.Request(
                search_builds=rpc_pb2.SearchBuildsRequest(
                    predicate=rpc_pb2.BuildPredicate(
                        builder=build_pb2.BuilderID(
                            project='chromium',
                            bucket='try',
                            builder='linux-rel',
                        ),
                    ),
                ),
            ),
            rpc_pb2.BatchRequest.Request(
                get_build=rpc_pb2.GetBuildRequest(id=3),
            ),
        ],
    )
    res = self.call(self.api.Batch, req)
    search_async.assert_called_once_with(
        search.Query(
            bucket_ids=['chromium/try'],
            tags=['builder:linux-rel'],
            status=common_pb2.STATUS_UNSPECIFIED,
            include_experimental=False,
            start_cursor='',
        ),
    )
    get_async.assert_called_once_with(3)
    self.assertEqual(len(res.responses), 2)
    self.assertEqual(len(res.responses[0].search_builds.builds), 2)
    self.assertEqual(res.responses[0].search_builds.builds[0].id, 1L)
    self.assertEqual(res.responses[0].search_builds.builds[1].id, 2L)
    self.assertEqual(res.responses[1].get_build.id, 3L)

  @mock.patch('service.get_async', autospec=True)
  def test_errors(self, get_async):
    get_async.return_value = future(None)

    req = rpc_pb2.BatchRequest(
        requests=[
            rpc_pb2.BatchRequest.Request(
                get_build=rpc_pb2.GetBuildRequest(id=1),
            ),
            rpc_pb2.BatchRequest.Request(),
        ],
    )
    res = self.call(self.api.Batch, req)
    self.assertEqual(
        res,
        rpc_pb2.BatchResponse(
            responses=[
                rpc_pb2.BatchResponse.Response(
                    error=status_pb2.Status(
                        code=prpc.StatusCode.NOT_FOUND.value,
                        message='not found',
                    ),
                ),
                rpc_pb2.BatchResponse.Response(
                    error=status_pb2.Status(
                        code=prpc.StatusCode.INVALID_ARGUMENT.value,
                        message='request is not specified',
                    ),
                ),
            ]
        )
    )


class BuildPredicateToSearchQueryTests(BaseTestCase):

  def test_project(self):
    predicate = rpc_pb2.BuildPredicate(
        builder=build_pb2.BuilderID(project='chromium'),
    )
    q = api.build_predicate_to_search_query(predicate)
    self.assertEqual(q.project, 'chromium')
    self.assertFalse(q.bucket_ids)
    self.assertFalse(q.tags)

  def test_project_bucket(self):
    predicate = rpc_pb2.BuildPredicate(
        builder=build_pb2.BuilderID(project='chromium', bucket='try'),
    )
    q = api.build_predicate_to_search_query(predicate)
    self.assertFalse(q.project)
    self.assertEqual(q.bucket_ids, ['chromium/try'])
    self.assertFalse(q.tags)

  def test_project_bucket_builder(self):
    predicate = rpc_pb2.BuildPredicate(
        builder=build_pb2.BuilderID(
            project='chromium', bucket='try', builder='linux-rel'
        ),
    )
    q = api.build_predicate_to_search_query(predicate)
    self.assertFalse(q.project)
    self.assertEqual(q.bucket_ids, ['chromium/try'])
    self.assertEqual(q.tags, ['builder:linux-rel'])

  def test_create_time(self):
    predicate = rpc_pb2.BuildPredicate()
    predicate.create_time.start_time.FromDatetime(datetime.datetime(2018, 1, 1))
    predicate.create_time.end_time.FromDatetime(datetime.datetime(2018, 1, 2))
    q = api.build_predicate_to_search_query(predicate)
    self.assertEqual(q.create_time_low, datetime.datetime(2018, 1, 1))
    self.assertEqual(q.create_time_high, datetime.datetime(2018, 1, 2))

  def test_build_range(self):
    predicate = rpc_pb2.BuildPredicate(
        build=rpc_pb2.BuildRange(start_build_id=100, end_build_id=90),
    )
    q = api.build_predicate_to_search_query(predicate)
    self.assertEqual(q.build_low, 100)
    self.assertEqual(q.build_high, 90)
