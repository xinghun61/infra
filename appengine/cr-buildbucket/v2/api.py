# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import functools

from google.appengine.ext import ndb
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

from v2 import validation
from v2 import default_field_masks
import buildtags
import model
import search
import service
import v2


class StatusCodeError(Exception):

  def __init__(self, code, details):
    super(StatusCodeError, self).__init__('%s: %s' % (code, details))
    self.code = code
    self.details = details


def status_code_error_class(code):
  code_name = code[1]

  class Error(StatusCodeError):

    def __init__(self, details=code_name):
      super(Error, self).__init__(code, details)

  return Error


NotFound = status_code_error_class(prpc.StatusCode.NOT_FOUND)
InvalidArgument = status_code_error_class(prpc.StatusCode.INVALID_ARGUMENT)

METHODS_BY_NAME = {
    m.name: m
    for m in rpc_prpc_pb2.BuildsServiceDescription['service_descriptor'].method
}


def rpc_impl_async(rpc_name):
  """Returns a decorator for an async Builds RPC implementation.

  Handles auth.AuthorizationError and StatusCodeError.

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
            raise InvalidArgument('invalid fields: %s' % ex)

        try:
          res = yield fn_async(req, ctx, mask)
          if mask:  # pragma: no branch
            mask.trim(res)
          raise ndb.Return(res)
        except auth.AuthorizationError:
          raise NotFound()
        except validation.Error as ex:
          raise InvalidArgument(ex.message)

      except StatusCodeError as ex:
        ctx.set_code(ex.code)
        ctx.set_details(ex.details)
        raise ndb.Return(None)

    return decorated

  return decorator


def v1_bucket(builder_id):
  return 'luci.%s.%s' % (builder_id.project, builder_id.bucket)


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
        b.steps.extend(build_steps.parse_steps())

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
    q.buckets = [v1_bucket(predicate.builder)]
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
    bucket = v1_bucket(req.builder)
    tag = buildtags.build_address_tag(
        bucket, req.builder.builder, req.build_number
    )
    found, _ = yield search.search_async(
        search.Query(buckets=[bucket], tags=[tag])
    )
    build_v1 = found[0] if found else None

  if not build_v1:
    raise NotFound()
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
