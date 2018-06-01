# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import functools

from google.appengine.ext import ndb
from google.protobuf import field_mask_pb2
from google.protobuf import symbol_database

from components import auth
from components import protoutil
from components import prpc

# Some of these imports are required to populate proto symbol db.
from proto import build_pb2
from proto import rpc_pb2  # pylint: disable=unused-import
from proto import rpc_prpc_pb2
from proto import step_pb2  # pylint: disable=unused-import

from v2 import validation
import buildtags
import model
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
    for m in rpc_prpc_pb2.BuildsServiceDescription['descriptor'].method
}


def api_method(default_mask=None):
  """Returns a decorator for a Builds RPC implementation.

  Handles auth.AuthorizationError and StatusCodeError.

  Adds fourth method argument to the method, a protoutil.Mask, defaults to
  default_mask. If request has "fields" field, treats it as a FieldMask, parses
  it to protoutil.Mask and passes that.
  After the method returns a response, the response is trimmed according to the
  mask. Requires request message to have "fields" field of type FieldMask.
  """

  def decorator(fn):
    method_desc = METHODS_BY_NAME[fn.__name__]
    res_class = symbol_database.Default().GetSymbol(method_desc.output_type[1:])

    @functools.wraps(fn)
    def decorated(self, req, ctx):
      try:
        mask = default_mask
        # Require that all RPC requests have "fields" field mask.
        if req.HasField('fields'):
          try:
            mask = protoutil.Mask.from_field_mask(req.fields,
                                                  res_class.DESCRIPTOR)
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

  return decorator


def v1_bucket(builder_id):
  return 'luci.%s.%s' % (builder_id.project, builder_id.bucket)


DEFAULT_BUILD_MASK = protoutil.Mask.from_field_mask(
    field_mask_pb2.FieldMask(paths=[
        'id',
        'builder',
        'number',
        'created_by',
        'view_url',
        'create_time',
        'start_time',
        'end_time',
        'update_time',
        'status',
        'input.gitiles_commit',
        'input.gerrit_changes',
        'input.experimental',
        # TODO(nodir): add the following fields when they are defined in the
        # proto:
        # 'user_duration',
    ]),
    build_pb2.Build.DESCRIPTOR,
)


def to_build_messages(builds, build_mask):
  """Converts model.Build instances to build_pb2.Build messages."""
  builds_msgs = map(v2.build_to_v2_partial, builds)

  if build_mask and build_mask.includes('steps'):  # pragma: no branch
    annotations = ndb.get_multi(
        [model.BuildAnnotations.key_for(b.key) for b in builds])
    for b, build_ann in zip(builds_msgs, annotations):
      if build_ann:  # pragma: no branch
        b.steps.extend(v2.parse_steps(build_ann))

  return builds_msgs


class BuildsApi(object):
  """Implements buildbucket.v2.Builds proto service."""

  DESCRIPTION = rpc_prpc_pb2.BuildsServiceDescription

  @api_method(default_mask=DEFAULT_BUILD_MASK)
  def GetBuild(self, req, _ctx, mask):
    """Retrieves a build by id or number."""
    validation.validate_get_build_request(req)

    if req.id:
      build = service.get(req.id)
    else:
      bucket = v1_bucket(req.builder)
      tag = buildtags.build_address_tag(bucket, req.builder.builder,
                                        req.build_number)
      builds, _ = service.search(
          service.SearchQuery(
              buckets=[bucket],
              tags=[tag],
          ))
      build = builds[0] if builds else None

    if not build:
      raise NotFound()

    return to_build_messages([build], mask)[0]
