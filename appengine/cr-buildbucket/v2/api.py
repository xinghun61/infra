# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import functools

from google.appengine.ext import ndb
from google.protobuf import symbol_database

from components import auth
from components import protoutil
from components import prpc

# Some of these imports are required to populate proto symbol db.
from proto import common_pb2
from proto import build_pb2
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


def api_method(fn):
  """Decorates a Builds RPC implementation.

  Handles auth.AuthorizationError and StatusCodeError.

  Adds fourth method argument to the method, a protoutil.Mask.
  If request has "fields" field, treats it as a FieldMask, parses it to a
  protoutil.Mask and passes that.
  After the method returns a response, the response is trimmed according to the
  mask. Requires request message to have "fields" field of type FieldMask.
  The default field masks are defined in default_field_masks.MASKS.
  """

  method_desc = METHODS_BY_NAME[fn.__name__]
  res_class = symbol_database.Default().GetSymbol(method_desc.output_type[1:])
  default_mask = default_field_masks.MASKS.get(res_class)

  @functools.wraps(fn)
  def decorated(self, req, ctx):
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
        res = fn(self, req, ctx, mask)
        if mask:  # pragma: no branch
          mask.trim(res)
        return res
      except auth.AuthorizationError:
        raise NotFound()
      except validation.Error as ex:
        raise InvalidArgument(ex.message)

    except StatusCodeError as ex:
      ctx.set_code(ex.code)
      ctx.set_details(ex.details)
      return None

  return decorated


def v1_bucket(builder_id):
  return 'luci.%s.%s' % (builder_id.project, builder_id.bucket)


def builds_to_v2(builds, build_mask):
  """Converts model.Build instances to build_pb2.Build messages."""
  builds_msgs = map(v2.build_to_v2_partial, builds)

  if build_mask and build_mask.includes('steps'):  # pragma: no branch
    annotations = ndb.get_multi([
        model.BuildAnnotations.key_for(b.key) for b in builds
    ])
    for b, build_ann in zip(builds_msgs, annotations):
      if build_ann:  # pragma: no branch
        b.steps.extend(v2.parse_steps(build_ann))

  return builds_msgs


def build_predicate_to_search_query(predicate):
  """Converts a rpc_pb2.BuildPredicate to search.Query."""
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

  return q


class BuildsApi(object):
  """Implements buildbucket.v2.Builds proto service."""

  DESCRIPTION = rpc_prpc_pb2.BuildsServiceDescription

  @api_method
  def GetBuild(self, req, _ctx, mask):
    """Retrieves a build by id or number."""
    validation.validate_get_build_request(req)

    if req.id:
      build_v1 = service.get(req.id)
    else:
      bucket = v1_bucket(req.builder)
      tag = buildtags.build_address_tag(
          bucket, req.builder.builder, req.build_number
      )
      build_v1, _ = search.search(search.Query(
          buckets=[bucket],
          tags=[tag],
      ))
      build_v1 = build_v1[0] if build_v1 else None

    if not build_v1:
      raise NotFound()

    return builds_to_v2([build_v1], mask)[0]

  @api_method
  def SearchBuilds(self, req, _ctx, mask):
    """Searches for builds."""
    validation.validate_search_builds_request(req)
    q = build_predicate_to_search_query(req.predicate)
    q.start_cursor = req.page_token

    builds_v1, cursor = search.search(q)
    return rpc_pb2.SearchBuildsResponse(
        builds=builds_to_v2(builds_v1, mask.submask('builds.*')),
        next_page_token=cursor,
    )
