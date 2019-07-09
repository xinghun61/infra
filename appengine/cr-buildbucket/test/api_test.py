# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import datetime

from google.appengine.ext import ndb
from google.protobuf import text_format

from components import auth
from components import prpc
from components import protoutil
from components.prpc import context as prpc_context
from testing_utils import testing
import mock

from proto import build_pb2
from proto import common_pb2
from proto import rpc_pb2
from test import test_util
import api
import bbutil
import creation
import errors
import model
import search
import user
import validation

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


class RpcImplTests(BaseTestCase):

  def error_handling_test(self, ex, expected_code, expected_details):

    @api.rpc_impl_async('GetBuild')
    @ndb.tasklet
    def get_build_async(_req, _res, _ctx, _mask):
      raise ex

    ctx = prpc_context.ServicerContext()
    req = rpc_pb2.GetBuildRequest(id=1)
    res = build_pb2.Build()
    # pylint: disable=no-value-for-parameter
    get_build_async(req, res, ctx).get_result()
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
    req = rpc_pb2.GetBuildRequest(fields=dict(paths=['invalid']))
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
        test_util.build(
            input=dict(properties=bbutil.dict_to_struct({'a': 'b'}))
        ),
    )
    req = rpc_pb2.GetBuildRequest(id=1)
    res = self.call(self.api.GetBuild, req)
    self.assertFalse(res.input.HasField('properties'))

  @mock.patch('service.get_async', autospec=True)
  def test_trimming_include(self, get_async):
    bundle = test_util.build_bundle(
        input=dict(properties=bbutil.dict_to_struct({'a': 'b'}))
    )
    bundle.put()
    get_async.return_value = future(bundle.build)
    req = rpc_pb2.GetBuildRequest(id=1, fields=dict(paths=['input.properties']))
    res = self.call(self.api.GetBuild, req)
    self.assertEqual(res.input.properties.items(), [('a', 'b')])


class GetBuildTests(BaseTestCase):
  """Tests for GetBuild RPC."""

  @mock.patch('service.get_async', autospec=True)
  def test_by_id(self, get_async):
    get_async.return_value = future(test_util.build(id=54))
    req = rpc_pb2.GetBuildRequest(id=54)
    res = self.call(self.api.GetBuild, req)
    self.assertEqual(res.id, 54)
    get_async.assert_called_once_with(54)

  @mock.patch('search.search_async', autospec=True)
  def test_by_number(self, search_async):
    builder_id = build_pb2.BuilderID(
        project='chromium', bucket='try', builder='linux-try'
    )
    build = test_util.build(id=1, builder=builder_id, number=2)
    search_async.return_value = future(([build], None))
    req = rpc_pb2.GetBuildRequest(builder=builder_id, build_number=2)
    res = self.call(self.api.GetBuild, req)
    self.assertEqual(res.id, 1)
    self.assertEqual(res.builder, builder_id)
    self.assertEqual(res.number, 2)

    search_async.assert_called_once_with(
        search.Query(
            bucket_ids=['chromium/try'],
            tags=['build_address:luci.chromium.try/linux-try/2'],
            include_experimental=True,
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
    builds = [test_util.build(id=54), test_util.build(id=55)]
    search_async.return_value = future((builds, 'next page token'))

    req = rpc_pb2.SearchBuildsRequest(
        predicate=dict(
            builder=dict(project='chromium', bucket='try', builder='linux-try'),
        ),
        page_size=10,
        page_token='page token',
    )
    res = self.call(self.api.SearchBuilds, req)

    search_async.assert_called_once_with(
        search.Query(
            bucket_ids=['chromium/try'],
            builder='linux-try',
            include_experimental=False,
            tags=[],
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
        'tokens.validate_build_token',
        autospec=True,
        return_value=None,
    )

    self.can_update_build_async = self.patch(
        'user.can_update_build_async',
        autospec=True,
        return_value=future(True),
    )

  def _mk_update_req(self, build, token='token', paths=None):
    build_req = rpc_pb2.UpdateBuildRequest(
        build=build,
        update_mask=dict(paths=paths or []),
    )
    ctx = prpc_context.ServicerContext()
    if token:
      metadata = ctx.invocation_metadata()
      metadata.append((api.BUILD_TOKEN_HEADER, token))
    return build_req, ctx

  def test_update_steps(self):
    build = test_util.build(id=123, status=common_pb2.STARTED)
    build.put()

    build_proto = build_pb2.Build(id=123)
    with open(os.path.join(THIS_DIR, 'steps.pb.txt')) as f:
      text = protoutil.parse_multiline(f.read())
      text_format.Merge(text, build_proto)

    req, ctx = self._mk_update_req(build_proto, paths=['build.steps'])
    self.call(self.api.UpdateBuild, req, ctx=ctx)

    persisted = model.BuildSteps.key_for(build.key).get()
    persisted_container = build_pb2.Build()
    persisted.read_steps(persisted_container)
    self.assertEqual(persisted_container.steps, build_proto.steps)

  def test_update_steps_of_scheduled_build(self):
    test_util.build(id=123, status=common_pb2.SCHEDULED).put()

    build_proto = build_pb2.Build(id=123)
    req, ctx = self._mk_update_req(build_proto, paths=['build.steps'])
    self.call(
        self.api.UpdateBuild,
        req,
        ctx=ctx,
        expected_code=prpc.StatusCode.INVALID_ARGUMENT,
    )

  def test_update_properties(self):
    build = test_util.build(id=123, status=common_pb2.STARTED)
    build.put()

    expected_props = {'a': 1}

    build_proto = build_pb2.Build(id=123)
    build_proto.output.properties.update(expected_props)

    req, ctx = self._mk_update_req(
        build_proto, paths=['build.output.properties']
    )
    self.call(self.api.UpdateBuild, req, ctx=ctx)

    out_props = model.BuildOutputProperties.key_for(build.key).get()
    self.assertEqual(test_util.msg_to_dict(out_props.parse()), expected_props)

  def test_update_properties_of_scheduled_build(self):
    test_util.build(id=123, status=common_pb2.SCHEDULED).put()

    build_proto = build_pb2.Build(id=123)
    req, ctx = self._mk_update_req(
        build_proto, paths=['build.output.properties']
    )
    self.call(
        self.api.UpdateBuild,
        req,
        ctx=ctx,
        expected_code=prpc.StatusCode.INVALID_ARGUMENT,
    )

  @mock.patch('events.on_build_starting_async', autospec=True)
  @mock.patch('events.on_build_started', autospec=True)
  def test_started(self, on_build_started, on_build_starting_async):
    on_build_starting_async.return_value = future(None)
    build = test_util.build(id=123)
    build.put()

    req, ctx = self._mk_update_req(
        build_pb2.Build(id=123, status=common_pb2.STARTED),
        paths=['build.status'],
    )
    self.call(self.api.UpdateBuild, req, ctx=ctx)

    build = build.key.get()
    self.assertEqual(build.proto.status, common_pb2.STARTED)
    self.assertEqual(build.proto.start_time.ToDatetime(), self.now)
    on_build_starting_async.assert_called_once_with(build)
    on_build_started.assert_called_once_with(build)

  @mock.patch('events.on_build_completing_async', autospec=True)
  @mock.patch('events.on_build_completed', autospec=True)
  def test_failed(self, on_build_completed, on_build_completing_async):
    steps = model.BuildSteps.make(
        build_pb2.Build(
            id=123,
            steps=[dict(name='step', status=common_pb2.SCHEDULED)],
        )
    )
    steps.put()
    on_build_completing_async.return_value = future(None)
    build = test_util.build(id=123)
    build.put()

    req, ctx = self._mk_update_req(
        build_pb2.Build(
            id=123,
            status=common_pb2.FAILURE,
            summary_markdown='bad',
        ),
        paths=['build.status', 'build.summary_markdown'],
    )
    self.call(self.api.UpdateBuild, req, ctx=ctx)

    build = build.key.get()
    self.assertEqual(build.proto.status, common_pb2.FAILURE)
    self.assertEqual(build.proto.summary_markdown, 'bad')
    self.assertEqual(build.proto.end_time.ToDatetime(), self.now)
    on_build_completing_async.assert_called_once_with(build)
    on_build_completed.assert_called_once_with(build)

    steps = steps.key.get()
    step_container = build_pb2.Build()
    steps.read_steps(step_container)
    self.assertEqual(step_container.steps[0].status, common_pb2.CANCELED)

  def test_empty_summary(self):
    build = test_util.build(
        id=123, status=common_pb2.STARTED, summary_markdown='ok'
    )
    build.put()

    req, ctx = self._mk_update_req(
        # No summary in the build.
        build_pb2.Build(id=123),
        paths=['build.summary_markdown'],
    )
    self.call(self.api.UpdateBuild, req, ctx=ctx)

    build = build.key.get()
    self.assertEqual(build.proto.summary_markdown, '')

  def test_missing_token(self):
    test_util.build(id=123).put()

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
    test_util.build(id=123).put()

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

  @mock.patch('validation.validate_update_build_request', autospec=True)
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

  def test_invalid_id(self):
    req, ctx = self._mk_update_req(
        build_pb2.Build(
            id=123,
            status=common_pb2.STARTED,
        )
    )
    self.call(
        self.api.UpdateBuild,
        req,
        ctx=ctx,
        expected_code=prpc.StatusCode.NOT_FOUND,
        expected_details='Cannot update nonexisting build with id 123',
    )

  def test_ended_build(self):
    test_util.build(id=123, status=common_pb2.SUCCESS).put()

    req, ctx = self._mk_update_req(build_pb2.Build(id=123))
    self.call(
        self.api.UpdateBuild,
        req,
        ctx=ctx,
        expected_code=prpc.StatusCode.FAILED_PRECONDITION,
        expected_details='Cannot update an ended build',
    )

  def test_invalid_user(self):
    test_util.build(id=123).put()
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


class ScheduleBuildTests(BaseTestCase):

  @mock.patch('creation.add_async', autospec=True)
  def test_schedule(self, add_async):
    add_async.return_value = future(
        test_util.build(
            id=54,
            builder=dict(project='chromium', bucket='try', builder='linux'),
        ),
    )
    req = rpc_pb2.ScheduleBuildRequest(
        builder=dict(project='chromium', bucket='try', builder='linux'),
    )
    res = self.call(self.api.ScheduleBuild, req)
    self.assertEqual(res.id, 54)
    add_async.assert_called_once_with(
        creation.BuildRequest(schedule_build_request=req)
    )

  def test_forbidden(self):
    user.can_async.return_value = future(False)
    req = rpc_pb2.ScheduleBuildRequest(
        builder=dict(project='chromium', bucket='try', builder='linux'),
    )
    self.call(
        self.api.ScheduleBuild,
        req,
        expected_code=prpc.StatusCode.PERMISSION_DENIED
    )


class CancelBuildTests(BaseTestCase):

  @mock.patch('service.cancel_async', autospec=True)
  def test_cancel(self, cancel_async):
    cancel_async.return_value = future(
        test_util.build(id=54, status=common_pb2.CANCELED),
    )
    req = rpc_pb2.CancelBuildRequest(id=54, summary_markdown='unnecesary')
    res = self.call(self.api.CancelBuild, req)
    self.assertEqual(res.id, 54)
    self.assertEqual(res.status, common_pb2.CANCELED)
    cancel_async.assert_called_once_with(54, summary_markdown='unnecesary')


class BatchTests(BaseTestCase):

  @mock.patch('service.get_async', autospec=True)
  @mock.patch('search.search_async', autospec=True)
  def test_get_and_search(self, search_async, get_async):
    search_async.return_value = future(([
        test_util.build(id=1), test_util.build(id=2)
    ], ''))
    get_async.return_value = future(test_util.build(id=3))

    req = rpc_pb2.BatchRequest(
        requests=[
            dict(
                search_builds=dict(
                    predicate=dict(
                        builder=dict(
                            project='chromium',
                            bucket='try',
                            builder='linux-rel',
                        ),
                    ),
                ),
            ),
            dict(get_build=dict(id=3)),
        ],
    )
    res = self.call(self.api.Batch, req)
    search_async.assert_called_once_with(
        search.Query(
            bucket_ids=['chromium/try'],
            builder='linux-rel',
            status=common_pb2.STATUS_UNSPECIFIED,
            include_experimental=False,
            tags=[],
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
            dict(get_build=dict(id=1)),
            dict(),
        ],
    )
    self.assertEqual(
        self.call(self.api.Batch, req),
        rpc_pb2.BatchResponse(
            responses=[
                dict(
                    error=dict(
                        code=prpc.StatusCode.NOT_FOUND.value,
                        message='not found',
                    ),
                ),
                dict(
                    error=dict(
                        code=prpc.StatusCode.INVALID_ARGUMENT.value,
                        message='request is not specified',
                    ),
                ),
            ]
        )
    )

  @mock.patch('creation.add_many_async', autospec=True)
  def test_schedule_build_requests(self, add_many_async):
    add_many_async.return_value = future([
        (test_util.build(id=42), None),
        (test_util.build(id=43), None),
        (None, errors.InvalidInputError('bad')),
        (None, Exception('unexpected')),
        (None, auth.AuthorizationError('bad')),
    ])

    user.can_async.side_effect = (
        lambda bucket_id, _: future('forbidden' not in bucket_id)
    )

    linux_builder = dict(project='chromium', bucket='try', builder='linux')
    win_builder = dict(project='chromium', bucket='try', builder='windows')
    req = rpc_pb2.BatchRequest(
        requests=[
            dict(schedule_build=dict(builder=linux_builder)),
            dict(
                schedule_build=dict(
                    builder=linux_builder, fields=dict(paths=['tags'])
                )
            ),
            dict(
                schedule_build=dict(
                    builder=linux_builder, fields=dict(paths=['wrong-field'])
                )
            ),
            dict(schedule_build=dict(builder=win_builder)),
            dict(schedule_build=dict(builder=win_builder)),
            dict(schedule_build=dict(builder=win_builder)),
            dict(
                schedule_build=dict(
                    builder=dict(
                        project='chromium', bucket='forbidden', builder='nope'
                    ),
                )
            ),
            dict(
                schedule_build=dict(),  # invalid request
            ),
        ],
    )

    res = self.call(self.api.Batch, req)

    codes = [r.error.code for r in res.responses]
    self.assertEqual(
        codes, [
            prpc.StatusCode.OK.value,
            prpc.StatusCode.OK.value,
            prpc.StatusCode.INVALID_ARGUMENT.value,
            prpc.StatusCode.INVALID_ARGUMENT.value,
            prpc.StatusCode.INTERNAL.value,
            prpc.StatusCode.PERMISSION_DENIED.value,
            prpc.StatusCode.PERMISSION_DENIED.value,
            prpc.StatusCode.INVALID_ARGUMENT.value,
        ]
    )
    self.assertEqual(res.responses[0].schedule_build.id, 42)
    self.assertFalse(len(res.responses[0].schedule_build.tags))
    self.assertTrue(len(res.responses[1].schedule_build.tags))


class BuildPredicateToSearchQueryTests(BaseTestCase):

  def test_project(self):
    predicate = rpc_pb2.BuildPredicate(builder=dict(project='chromium'),)
    q = api.build_predicate_to_search_query(predicate)
    self.assertEqual(q.project, 'chromium')
    self.assertFalse(q.bucket_ids)
    self.assertFalse(q.tags)

  def test_project_bucket(self):
    predicate = rpc_pb2.BuildPredicate(
        builder=dict(project='chromium', bucket='try'),
    )
    q = api.build_predicate_to_search_query(predicate)
    self.assertFalse(q.project)
    self.assertEqual(q.bucket_ids, ['chromium/try'])
    self.assertFalse(q.tags)

  def test_project_bucket_builder(self):
    predicate = rpc_pb2.BuildPredicate(
        builder=dict(project='chromium', bucket='try', builder='linux-rel'),
    )
    q = api.build_predicate_to_search_query(predicate)
    self.assertFalse(q.project)
    self.assertEqual(q.bucket_ids, ['chromium/try'])
    self.assertEqual(q.builder, 'linux-rel')

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
    self.assertEqual(q.build_low, 89)
    self.assertEqual(q.build_high, 101)

  def test_canary(self):
    predicate = rpc_pb2.BuildPredicate(canary=common_pb2.YES)
    q = api.build_predicate_to_search_query(predicate)
    self.assertEqual(q.canary, True)

  def test_non_canary(self):
    predicate = rpc_pb2.BuildPredicate(canary=common_pb2.NO)
    q = api.build_predicate_to_search_query(predicate)
    self.assertEqual(q.canary, False)
