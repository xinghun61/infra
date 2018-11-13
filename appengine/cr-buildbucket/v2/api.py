# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import functools

from google.appengine.ext import ndb
from google.protobuf import json_format
from google.protobuf import symbol_database

from components import auth
from components import protoutil
from components import prpc
from components import utils

# Some of these imports are required to populate proto symbol db.
from proto import common_pb2
from proto import build_pb2  # pylint: disable=unused-import
from proto import rpc_pb2  # pylint: disable=unused-import
from proto import rpc_prpc_pb2
from proto import step_pb2  # pylint: disable=unused-import

from v2 import tokens
from v2 import validation
from v2 import default_field_masks
import buildtags
import config
import model
import search
import service
import user
import v2

# Header for passing token to authenticate build messages, e.g. UpdateBuild RPC.
# Lowercase because metadata is stored in lowercase.
BUILD_TOKEN_HEADER = 'x-build-token'


class StatusError(Exception):

  def __init__(self, code, *details_and_args):
    if details_and_args:
      details = details_and_args[0] % details_and_args[1:]
    else:
      details = code[1]

    super(StatusError, self).__init__('%s: %s' % (code, details))
    self.code = code
    self.details = details


not_found = lambda *args: StatusError(prpc.StatusCode.NOT_FOUND, *args)
invalid_argument = (
    lambda *args: StatusError(prpc.StatusCode.INVALID_ARGUMENT, *args)
)

METHODS_BY_NAME = {
    m.name: m
    for m in rpc_prpc_pb2.BuildsServiceDescription['service_descriptor'].method
}


def rpc_impl_async(rpc_name):
  """Returns a decorator for an async Builds RPC implementation.

  Handles auth.AuthorizationError and StatusError.

  Adds fourth method argument to the method, a protoutil.Mask.
  If request has "fields" field, treats it as a FieldMask, parses it to a
  protoutil.Mask and passes that.
  After the method returns a response, the response is trimmed according to the
  mask. Requires request message to have "fields" field of type FieldMask.
  The default field masks are defined in default_field_masks.MASKS.
  """

  method_desc = METHODS_BY_NAME[rpc_name]
  res_class = symbol_database.Default().GetSymbol(method_desc.output_type[1:])
  default_mask = default_field_masks.MASKS.get(res_class)

  def decorator(fn_async):

    @functools.wraps(fn_async)
    @ndb.tasklet
    def decorated(req, ctx):
      try:
        mask = default_mask
        # Require that all RPC requests have "fields" field mask.
        if req.HasField('fields'):
          try:
            mask = protoutil.Mask.from_field_mask(
                req.fields, res_class.DESCRIPTOR
            )
          except ValueError as ex:
            raise invalid_argument('invalid fields: %s', ex)

        try:
          res = yield fn_async(req, ctx, mask)
          if mask:  # pragma: no branch
            mask.trim(res)
          raise ndb.Return(res)
        except auth.AuthorizationError:
          raise not_found()
        except validation.Error as ex:
          raise invalid_argument('%s', ex.message)

      except StatusError as ex:
        ctx.set_code(ex.code)
        ctx.set_details(ex.details)
        raise ndb.Return(None)

    return decorated

  return decorator


def bucket_id_string(builder_id):
  return config.format_bucket_id(builder_id.project, builder_id.bucket)


@ndb.tasklet
def builds_to_v2_async(builds, build_mask):
  """Converts model.Build instances to build_pb2.Build messages."""
  builds_msgs = map(v2.build_to_v2, builds)

  if build_mask and build_mask.includes('steps'):  # pragma: no branch
    build_steps_list = yield ndb.get_multi_async([
        model.BuildSteps.key_for(b.key) for b in builds
    ])
    for b, build_steps in zip(builds_msgs, build_steps_list):
      if build_steps:  # pragma: no branch
        b.steps.extend(build_steps.step_container.steps)

  raise ndb.Return(builds_msgs)


def build_predicate_to_search_query(predicate):
  """Converts a rpc_pb2.BuildPredicate to search.Query.

  Assumes predicate is valid.
  """
  q = search.Query(
      tags=[buildtags.unparse(p.key, p.value) for p in predicate.tags],
      created_by=predicate.created_by or None,
      include_experimental=predicate.include_experimental,
      status=(
          search.StatusFilter.COMPLETED
          if predicate.status == common_pb2.ENDED_MASK else predicate.status
      ),
  )

  # Filter by builder.
  if predicate.HasField('builder'):
    if predicate.builder.bucket:
      q.bucket_ids = [bucket_id_string(predicate.builder)]
    else:
      q.project = predicate.builder.project
    if predicate.builder.builder:
      q.tags.append(
          buildtags.unparse(buildtags.BUILDER_KEY, predicate.builder.builder)
      )

  # Filter by gerrit changes.
  buildsets = [
      buildtags.gerrit_change_buildset(c.host, c.change, c.patchset)
      for c in predicate.gerrit_changes
  ]
  q.tags.extend(buildtags.unparse(buildtags.BUILDSET_KEY, b) for b in buildsets)

  # Filter by creation time.
  if predicate.create_time.HasField('start_time'):
    q.create_time_low = predicate.create_time.start_time.ToDatetime()
  if predicate.create_time.HasField('end_time'):
    q.create_time_high = predicate.create_time.end_time.ToDatetime()

  # Filter by build range.
  if predicate.HasField('build'):
    # 0 means no boundary.
    q.build_low = predicate.build.start_build_id or None
    q.build_high = predicate.build.end_build_id or None

  return q


@rpc_impl_async('GetBuild')
@ndb.tasklet
def get_build_async(req, _ctx, mask):
  """Retrieves a build by id or number."""
  validation.validate_get_build_request(req)

  if req.id:
    build_v1 = yield service.get_async(req.id)
  else:
    tag = buildtags.build_address_tag(
        # TODO(crbug.com/851036): migrate build_address to use short buckets.
        'luci.%s.%s' % (req.builder.project, req.builder.bucket),
        req.builder.builder,
        req.build_number,
    )
    found, _ = yield search.search_async(
        search.Query(bucket_ids=[bucket_id_string(req.builder)], tags=[tag])
    )
    build_v1 = found[0] if found else None

  if not build_v1:
    raise not_found()
  raise ndb.Return((yield builds_to_v2_async([build_v1], mask))[0])


@rpc_impl_async('SearchBuilds')
@ndb.tasklet
def search_builds_async(req, _ctx, mask):
  """Searches for builds."""
  validation.validate_search_builds_request(req)
  q = build_predicate_to_search_query(req.predicate)
  q.max_builds = req.page_size or None
  q.start_cursor = req.page_token

  builds_v1, cursor = yield search.search_async(q)
  raise ndb.Return(
      rpc_pb2.SearchBuildsResponse(
          builds=(
              yield builds_to_v2_async(builds_v1, mask.submask('builds.*'))
          ),
          next_page_token=cursor,
      ),
  )


def validate_build_token(req, ctx):
  """Validates build token stored in RPC metadata."""
  metadata = dict(ctx.invocation_metadata())
  token = metadata.get(BUILD_TOKEN_HEADER)
  if not token:
    raise StatusError(
        prpc.StatusCode.UNAUTHENTICATED,
        'missing token in build update request',
    )

  try:
    tokens.validate_build_token(token, req.build.id)
  except auth.InvalidTokenError as e:
    raise StatusError(prpc.StatusCode.UNAUTHENTICATED, '%s', e.message)


@rpc_impl_async('UpdateBuild')
@ndb.tasklet
def update_build_async(req, ctx, _mask):
  """Update build as in given request.

  For now, only update build steps.
  """
  validate_build_token(req, ctx)
  if not (yield user.can_update_build_async()):
    raise StatusError(
        prpc.StatusCode.PERMISSION_DENIED, '%s not permitted to update build' %
        auth.get_current_identity().to_bytes()
    )
  validation.validate_update_build_request(req)

  update_paths = set(req.update_mask.paths)

  @ndb.transactional_tasklet
  def txn_async():
    build_proto = req.build

    # Get an existing build.
    build = yield model.Build.get_by_id_async(build_proto.id)
    if not build:
      raise not_found(
          'Cannot update nonexisting build with id %s', build_proto.id
      )
    to_put = [build]

    if 'build.steps' not in update_paths:
      build_steps = yield model.BuildSteps.key_for(build.key).get_async()
    else:
      # Update build steps.
      build_steps = model.BuildSteps(
          key=model.BuildSteps.key_for(build.key),
          step_container=build_pb2.Build(steps=build_proto.steps),
      )
      to_put.append(build_steps)

    if 'build.output.properties' in update_paths:
      # TODO(nodir): persist it in a separate entity, in Struct binary format.
      # The following is inefficient.
      build.result_details = build.result_details or {}
      build.result_details[model.PROPERTIES_PARAMETER] = json.loads(
          json_format.MessageToJson(build_proto.output.properties)
      )

    # Store and convert back to build_pb2.Build proto for return.
    yield ndb.put_multi_async(to_put)
    raise ndb.Return(build, build_steps)

  build, build_steps = yield txn_async()
  raise ndb.Return(v2.build_to_v2(build, build_steps))


# Maps an rpc_pb2.BatchRequest.Request field name to an async function
#   (req, ctx) => ndb.Future of res.
BATCH_REQUEST_TYPE_TO_RPC_IMPL = {
    'get_build': get_build_async,
    'search_builds': search_builds_async,
}
assert set(BATCH_REQUEST_TYPE_TO_RPC_IMPL) == set(
    rpc_pb2.BatchRequest.Request.DESCRIPTOR.fields_by_name
)


class BuildsApi(object):
  """Implements buildbucket.v2.Builds proto service."""

  # "mask" parameter in RPC implementations is added by rpc_impl_async.
  # pylint: disable=no-value-for-parameter

  DESCRIPTION = rpc_prpc_pb2.BuildsServiceDescription

  def GetBuild(self, req, ctx):
    return get_build_async(req, ctx).get_result()

  def SearchBuilds(self, req, ctx):
    return search_builds_async(req, ctx).get_result()

  def UpdateBuild(self, req, ctx):
    return update_build_async(req, ctx).get_result()

  def Batch(self, req, ctx):

    @ndb.tasklet
    def serve_subrequest_async(sub_req):
      request_type = sub_req.WhichOneof('request')
      sub_res = rpc_pb2.BatchResponse.Response()
      if not request_type:
        sub_res.error.code = prpc.StatusCode.INVALID_ARGUMENT.value
        sub_res.error.message = 'request is not specified'
        raise ndb.Return(sub_res)
      rpc_impl = BATCH_REQUEST_TYPE_TO_RPC_IMPL[request_type]
      sub_ctx = ctx.clone()
      rpc_res = yield rpc_impl(getattr(sub_req, request_type), sub_ctx)
      if sub_ctx.code != prpc.StatusCode.OK:
        sub_res.error.code = sub_ctx.code.value
        sub_res.error.message = sub_ctx.details
      else:
        getattr(sub_res, request_type).MergeFrom(rpc_res)
      raise ndb.Return(sub_res)

    return rpc_pb2.BatchResponse(
        responses=[
            r
            for _, r in utils.async_apply(req.requests, serve_subrequest_async)
        ],
    )
