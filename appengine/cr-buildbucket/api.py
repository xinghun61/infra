# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import functools
import logging

from google.appengine.ext import ndb
from google.protobuf import field_mask_pb2
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

import buildtags
import config
import creation
import default_field_masks
import errors
import events
import model
import search
import service
import tokens
import user
import validation

# Header for passing token to authenticate build messages, e.g. UpdateBuild RPC.
# Lowercase because metadata is stored in lowercase.
BUILD_TOKEN_HEADER = 'x-build-token'


class StatusError(errors.Error):

  def __init__(self, code, *details_and_args):
    if details_and_args:
      details = details_and_args[0] % details_and_args[1:]
    else:
      details = code[1]

    self.code = code
    super(StatusError, self).__init__(details)


not_found = lambda *args: StatusError(prpc.StatusCode.NOT_FOUND, *args)
failed_precondition = (
    lambda *args: StatusError(prpc.StatusCode.FAILED_PRECONDITION, *args)
)
invalid_argument = (
    lambda *args: StatusError(prpc.StatusCode.INVALID_ARGUMENT, *args)
)


def current_identity_cannot(action_format, *args):
  """Raises a StatusError with a PERMISSION_DENIED code."""
  action = action_format % args
  msg = '%s cannot %s' % (auth.get_current_identity().to_bytes(), action)
  return StatusError(prpc.StatusCode.PERMISSION_DENIED, '%s', msg)


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
    def decorated(req, res, ctx):
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
          yield fn_async(req, res, ctx, mask)
          if mask:  # pragma: no branch
            mask.trim(res)
          raise ndb.Return(res)
        except auth.AuthorizationError:
          raise not_found()
        except validation.Error as ex:
          raise invalid_argument('%s', ex.message)

      except errors.Error as ex:
        ctx.set_code(ex.code)
        ctx.set_details(ex.message)
        raise ndb.Return(None)

    return decorated

  return decorator


def bucket_id_string(builder_id):
  return config.format_bucket_id(builder_id.project, builder_id.bucket)


def builds_to_protos_async(builds, build_mask=None):
  """Converts model.Build instances to build_pb2.Build messages.

  Like model.builds_to_protos_async, but accepts a build mask and mutates
  model.Build entities in addition to build_pb2.Build.
  """
  # Trim model.Build.proto before deep-copying into destination.
  if build_mask:  # pragma: no branch
    for b, _ in builds:
      build_mask.trim(b.proto)

  includes = lambda path: build_mask and build_mask.includes(path)

  return model.builds_to_protos_async(
      builds,
      load_tags=includes('tags'),
      load_output_properties=includes('output.properties'),
      load_input_properties=includes('input.properties'),
      load_steps=includes('steps'),
      load_infra=includes('infra'),
  )


def build_to_proto_async(build, dest, build_mask=None):
  """Converts a model.Build instance to a build_pb2.Build message.

  Like builds_to_protos_async, but singular.
  """
  return builds_to_protos_async([(build, dest)], build_mask)


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
      q.builder = predicate.builder.builder
    else:
      q.project = predicate.builder.project

  # Filter by gerrit changes.
  buildsets = [
      buildtags.gerrit_change_buildset(c) for c in predicate.gerrit_changes
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
    # Convert BuildRange to search.Query.{build_low, build_high}.
    # Note that, unlike build_low/build_high, BuildRange encapsulates the fact
    # that build ids are decreasing. We need to reverse the order.
    if predicate.build.start_build_id:  # pragma: no branch
      # Add 1 because start_build_id is inclusive and build_high is exclusive.
      q.build_high = predicate.build.start_build_id + 1
    if predicate.build.end_build_id:  # pragma: no branch
      # Subtract 1 because end_build_id is exclusive and build_low is inclusive.
      q.build_low = predicate.build.end_build_id - 1

  # Filter by canary.
  if predicate.canary != common_pb2.UNSET:
    q.canary = predicate.canary == common_pb2.YES

  return q


@rpc_impl_async('GetBuild')
@ndb.tasklet
def get_build_async(req, res, _ctx, mask):
  """Retrieves a build by id or number."""
  validation.validate_get_build_request(req)

  if req.id:
    logging.info('Build id: %s', req.id)
    build = yield service.get_async(req.id)
  else:
    logging.info(
        'Build id: %s/%d',
        config.builder_id_string(req.builder),
        req.build_number,
    )
    tag = buildtags.build_address_tag(req.builder, req.build_number)
    q = search.Query(
        bucket_ids=[bucket_id_string(req.builder)],
        tags=[tag],
        include_experimental=True,
    )
    found, _ = yield search.search_async(q)
    build = found[0] if found else None

  if not build:
    raise not_found()
  yield build_to_proto_async(build, res, mask)


@rpc_impl_async('SearchBuilds')
@ndb.tasklet
def search_builds_async(req, res, _ctx, mask):
  """Searches for builds."""
  validation.validate_search_builds_request(req)
  logging.info('Predicate: %s', req.predicate)
  q = build_predicate_to_search_query(req.predicate)
  q.max_builds = req.page_size or None
  q.start_cursor = req.page_token

  builds, next_page_token = yield search.search_async(q)
  res.next_page_token = next_page_token or ''
  yield builds_to_protos_async(
      [(b, res.builds.add()) for b in builds],
      mask.submask('builds.*'),
  )


def validate_build_token(build, ctx):
  """Validates build token stored in RPC metadata."""
  metadata = dict(ctx.invocation_metadata())
  token = metadata.get(BUILD_TOKEN_HEADER)
  if not token:
    raise StatusError(
        prpc.StatusCode.UNAUTHENTICATED,
        'missing token in build update request',
    )

  # TODO(crbug.com/943467): return error code UNAVAILABLE if
  # build.swarming_task_key is None.

  try:
    tokens.validate_build_token(token, build.key.id(), build.swarming_task_key)
  except auth.InvalidTokenError as e:
    raise StatusError(prpc.StatusCode.UNAUTHENTICATED, '%s', e.message)


@rpc_impl_async('UpdateBuild')
@ndb.tasklet
def update_build_async(req, _res, ctx, _mask):
  """Update build as in given request.

  For now, only update build steps.

  Does not mutate res.
  In practice, clients does not need the response, they just want to provide
  the data.
  """
  now = utils.utcnow()
  logging.debug('updating build %d', req.build.id)

  # Validate the request.
  build_steps = model.BuildSteps.make(req.build)
  validation.validate_update_build_request(req, build_steps)

  update_paths = set(req.update_mask.paths)

  if not (yield user.can_update_build_async()):
    raise StatusError(
        prpc.StatusCode.PERMISSION_DENIED, '%s not permitted to update build' %
        auth.get_current_identity().to_bytes()
    )

  @ndb.tasklet
  def get_async():
    build = yield model.Build.get_by_id_async(req.build.id)
    if not build:
      raise not_found(
          'Cannot update nonexisting build with id %s', req.build.id
      )
    if build.is_ended:
      raise failed_precondition('Cannot update an ended build')

    # Ensure a SCHEDULED build does not have steps or output.
    final_status = (
        req.build.status
        if 'build.status' in update_paths else build.proto.status
    )
    if final_status == common_pb2.SCHEDULED:
      if 'build.steps' in update_paths:
        raise invalid_argument(
            'cannot update steps of a SCHEDULED build; '
            'either set status to non-SCHEDULED or do not update steps'
        )
      if any(p.startswith('build.output.') for p in update_paths):
        raise invalid_argument(
            'cannot update build output fields of a SCHEDULED build; '
            'either set status to non-SCHEDULED or do not update build output'
        )

    raise ndb.Return(build)

  build = yield get_async()
  validate_build_token(build, ctx)

  # Prepare a field mask to merge req.build into model.Build.proto.
  # Exclude fields that are stored elsewhere.
  # Note that update_paths was (indirectly) validated by validation.py
  # against a whitelist.
  model_build_proto_mask = protoutil.Mask.from_field_mask(
      field_mask_pb2.FieldMask(
          paths=list(update_paths - {'build.steps', 'build.output.properties'})
      ),
      rpc_pb2.UpdateBuildRequest.DESCRIPTOR,
      update_mask=True,
  ).submask('build')

  out_prop_bytes = req.build.output.properties.SerializeToString()

  @ndb.transactional_tasklet
  def txn_async():
    build = yield get_async()

    orig_status = build.status

    futures = []

    if 'build.output.properties' in update_paths:
      futures.append(
          model.BuildOutputProperties(
              key=model.BuildOutputProperties.key_for(build.key),
              properties=out_prop_bytes,
          ).put_async()
      )

    if model_build_proto_mask:  # pragma: no branch
      # Merge the rest into build.proto using model_build_proto_mask.
      model_build_proto_mask.merge(req.build, build.proto)

    # If we are updating build status, update some other dependent fields
    # and schedule notifications.
    status_changed = orig_status != build.proto.status
    if status_changed:
      if build.proto.status == common_pb2.STARTED:
        if not build.proto.HasField('start_time'):  # pragma: no branch
          build.proto.start_time.FromDatetime(now)
        futures.append(events.on_build_starting_async(build))
      else:
        assert model.is_terminal_status(build.proto.status), build.proto.status
        build.clear_lease()
        if not build.proto.HasField('end_time'):  # pragma: no branch
          build.proto.end_time.FromDatetime(now)
        futures.append(events.on_build_completing_async(build))

    if 'build.steps' in update_paths:
      # TODO(crbug.com/936892): reject requests with a terminal build status
      # and incomplete steps, when
      # https://chromium-review.googlesource.com/c/infra/infra/+/1553291
      # is deployed.
      futures.append(build_steps.put_async())
    elif build.is_ended:
      futures.append(
          model.BuildSteps.cancel_incomplete_steps_async(
              req.build.id, build.proto.end_time
          )
      )

    futures.append(build.put_async())
    yield futures
    raise ndb.Return(build, status_changed)

  build, status_changed = yield txn_async()
  if status_changed:
    if build.proto.status == common_pb2.STARTED:
      events.on_build_started(build)
    else:
      assert model.is_terminal_status(build.proto.status), build.proto.status
      events.on_build_completed(build)


@rpc_impl_async('ScheduleBuild')
@ndb.tasklet
def schedule_build_async(req, res, _ctx, mask):
  """Schedules one build."""
  validation.validate_schedule_build_request(req)

  bucket_id = config.format_bucket_id(req.builder.project, req.builder.bucket)
  if not (yield user.can_add_build_async(bucket_id)):
    raise current_identity_cannot('schedule builds to bucket %s', bucket_id)

  build_req = creation.BuildRequest(schedule_build_request=req)
  build = yield creation.add_async(build_req)
  yield build_to_proto_async(build, res, mask)


# A tuple of a request and response.
_ReqRes = collections.namedtuple('_ReqRes', 'request response')
# A tuple of a request, response and field mask.
# Used internally by schedule_build_multi.
_ScheduleItem = collections.namedtuple('_ScheduleItem', 'request response mask')


def schedule_build_multi(batch):
  """Schedules multiple builds.

  Args:
    batch: list of _ReqRes where
      request is rpc_pb2.ScheduleBuildRequest and
      response is rpc_pb2.BatchResponse.Response.
      Response objects will be mutated.
  """
  # Validate requests.
  valid_items = []
  for rr in batch:
    try:
      validation.validate_schedule_build_request(rr.request)
    except validation.Error as ex:
      rr.response.error.code = prpc.StatusCode.INVALID_ARGUMENT.value
      rr.response.error.message = ex.message
      continue

    # Parse the field mask.
    # Normally it is done by rpc_impl_async.
    mask = None
    if rr.request.HasField('fields'):
      try:
        mask = protoutil.Mask.from_field_mask(
            rr.request.fields, build_pb2.Build.DESCRIPTOR
        )
      except ValueError as ex:
        rr.response.error.code = prpc.StatusCode.INVALID_ARGUMENT.value
        rr.response.error.message = 'invalid fields: %s' % ex.message
        continue

    valid_items.append(_ScheduleItem(rr.request, rr.response, mask))

  # Check permissions.
  def get_bucket_id(req):
    return config.format_bucket_id(req.builder.project, req.builder.bucket)

  bucket_ids = {get_bucket_id(x.request) for x in valid_items}
  can_add = dict(utils.async_apply(bucket_ids, user.can_add_build_async))
  identity_str = auth.get_current_identity().to_bytes()
  to_schedule = []
  for x in valid_items:
    bid = get_bucket_id(x.request)
    if can_add[bid]:
      to_schedule.append(x)
    else:
      x.response.error.code = prpc.StatusCode.PERMISSION_DENIED.value
      x.response.error.message = (
          '%s cannot schedule builds in bucket %s' % (identity_str, bid)
      )

  # Schedule builds.
  if not to_schedule:  # pragma: no cover
    return
  build_requests = [
      creation.BuildRequest(schedule_build_request=x.request)
      for x in to_schedule
  ]
  results = creation.add_many_async(build_requests).get_result()
  futs = []
  for x, (build, ex) in zip(to_schedule, results):
    res = x.response
    err = res.error
    if isinstance(ex, errors.Error):
      err.code = ex.code.value
      err.message = ex.message
    elif isinstance(ex, auth.AuthorizationError):
      err.code = prpc.StatusCode.PERMISSION_DENIED.value
      err.message = ex.message
    elif ex:
      err.code = prpc.StatusCode.INTERNAL.value
      err.message = ex.message
    else:
      futs.append(build_to_proto_async(build, res.schedule_build, x.mask))
  for f in futs:
    f.get_result()


@rpc_impl_async('CancelBuild')
@ndb.tasklet
def cancel_build_async(req, res, _ctx, mask):
  validation.validate_cancel_build_request(req)
  build = yield service.cancel_async(
      req.id, summary_markdown=req.summary_markdown
  )
  yield build_to_proto_async(build, res, mask)


# Maps an rpc_pb2.BatchRequest.Request field name to an async function
#   (req, ctx) => ndb.Future of res.
BATCH_REQUEST_TYPE_TO_RPC_IMPL = {
    'get_build': get_build_async,
    'search_builds': search_builds_async,
    'cancel_build': cancel_build_async,
}
assert set(BATCH_REQUEST_TYPE_TO_RPC_IMPL) | {'schedule_build'} == set(
    rpc_pb2.BatchRequest.Request.DESCRIPTOR.fields_by_name
)


class BuildsApi(object):
  """Implements buildbucket.v2.Builds proto service."""

  # "mask" parameter in RPC implementations is added by rpc_impl_async.
  # pylint: disable=no-value-for-parameter

  DESCRIPTION = rpc_prpc_pb2.BuildsServiceDescription

  def _res_if_ok(self, res, ctx):
    return res if ctx.code == prpc.StatusCode.OK else None

  def GetBuild(self, req, ctx):
    res = build_pb2.Build()
    get_build_async(req, res, ctx).get_result()
    return self._res_if_ok(res, ctx)

  def SearchBuilds(self, req, ctx):
    res = rpc_pb2.SearchBuildsResponse()
    search_builds_async(req, res, ctx).get_result()
    return self._res_if_ok(res, ctx)

  def UpdateBuild(self, req, ctx):
    res = build_pb2.Build()
    update_build_async(req, res, ctx).get_result()
    return self._res_if_ok(res, ctx)

  def ScheduleBuild(self, req, ctx):
    res = build_pb2.Build()
    schedule_build_async(req, res, ctx).get_result()
    return self._res_if_ok(res, ctx)

  def CancelBuild(self, req, ctx):
    res = build_pb2.Build()
    cancel_build_async(req, res, ctx).get_result()
    return self._res_if_ok(res, ctx)

  def Batch(self, req, ctx):
    res = rpc_pb2.BatchResponse()
    batch = [_ReqRes(req, res.responses.add()) for req in req.requests]

    # First, execute ScheduleBuild requests.
    schedule_requests = []
    in_parallel = []
    for rr in batch:
      request_type = rr.request.WhichOneof('request')
      if not request_type:
        rr.response.error.code = prpc.StatusCode.INVALID_ARGUMENT.value
        rr.response.error.message = 'request is not specified'
      elif request_type == 'schedule_build':
        schedule_requests.append(rr)
      else:
        in_parallel.append(rr)
    if schedule_requests:
      schedule_build_multi([
          _ReqRes(rr.request.schedule_build, rr.response)
          for rr in schedule_requests
      ])

    # Then, execute the rest in parallel.

    @ndb.tasklet
    def serve_subrequest_async(rr):
      request_type = rr.request.WhichOneof('request')
      assert request_type != 'schedule_build'
      rpc_impl = BATCH_REQUEST_TYPE_TO_RPC_IMPL[request_type]
      sub_ctx = ctx.clone()
      yield rpc_impl(
          getattr(rr.request, request_type),
          getattr(rr.response, request_type),
          sub_ctx,
      )
      if sub_ctx.code != prpc.StatusCode.OK:
        rr.response.ClearField(request_type)
        rr.response.error.code = sub_ctx.code.value
        rr.response.error.message = sub_ctx.details

    for f in map(serve_subrequest_async, in_parallel):
      f.check_success()

    assert all(r.WhichOneof('response') for r in res.responses), res.responses
    return self._res_if_ok(res, ctx)
