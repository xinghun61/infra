# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Creates builds."""

import collections
import contextlib
import copy
import logging
import random

from google.appengine.ext import ndb

from components import auth
from components import net
from components import utils

from proto import build_pb2
from proto import common_pb2
from proto.config import project_config_pb2
import bbutil
import buildtags
import config
import errors
import events
import model
import search
import sequence
import swarming

_BuildRequestBase = collections.namedtuple(
    '_BuildRequestBase', [
        'schedule_build_request',
        'parameters',
        'lease_expiration_date',
        'retry_of',
        'pubsub_callback_auth_token',
    ]
)


class BuildRequest(_BuildRequestBase):
  """A request to add a new build.

  It is a wrapper around rpb_pb2.ScheduleBuildRequest plus legacy.
  """

  def __new__(
      cls,
      schedule_build_request,
      parameters=None,
      lease_expiration_date=None,
      retry_of=None,
      pubsub_callback_auth_token=None,
  ):
    """Creates an BuildRequest.

    Does not perform complete validation, only basic assertions.

    Args:
      schedule_build_request (rpc_pb2.ScheduleBuildRequest): the request.
      parameters (dict): value for model.Build.parameters.
        Must not have "properties", which moved to
        model.Build.proto.input.properties, and must be passed as
        schedule_build_request.properties.
      lease_expiration_date (datetime.datetime): if not None, the build is
        created as leased and its lease_key is not None.
      retry_of (int): value for model.Build.retry_of attribute.
      pubsub_callback_auth_token (str): value for
        model.Build.pubsub_callback.auth_token. Allowed iff r.notify is set.
    """
    assert schedule_build_request
    assert not parameters or 'properties' not in parameters
    assert (
        not pubsub_callback_auth_token or
        schedule_build_request.HasField('notify')
    )

    self = super(BuildRequest, cls).__new__(
        cls,
        schedule_build_request,
        parameters,
        lease_expiration_date,
        retry_of,
        pubsub_callback_auth_token,
    )
    return self

  def _request_id_memcache_key(self, identity=None):
    req_id = self.schedule_build_request.request_id
    if req_id is None:  # pragma: no cover
      return None
    return (
        'request_id/%s/%s/add_build' %
        ((identity or auth.get_current_identity()).to_bytes(), req_id)
    )

  def create_build_proto(self, build_id, created_by, now):
    """Converts the request to a build_pb2.Build.

    Assumes self is valid.
    """
    sbr = self.schedule_build_request

    build_proto = build_pb2.Build(
        id=build_id,
        builder=sbr.builder,
        status=common_pb2.SCHEDULED,
        created_by=created_by.to_bytes(),
        input=dict(
            properties=sbr.properties,
            gerrit_changes=sbr.gerrit_changes,
        ),
        infra=dict(
            buildbucket=dict(
                requested_properties=sbr.properties,
                requested_dimensions=sbr.dimensions,
            ),
        ),
    )
    build_proto.create_time.FromDatetime(now)

    if sbr.HasField('gitiles_commit'):
      build_proto.input.gitiles_commit.CopyFrom(sbr.gitiles_commit)

    if sbr.priority:
      build_proto.infra.swarming.priority = sbr.priority

    return build_proto

  @staticmethod
  def compute_tag_set(sbr):
    """Returns a set of (key, value) tuples for a new build."""
    tags = {(t.key, t.value) for t in sbr.tags}

    if sbr.builder.builder:  # pragma: no branch
      tags.add((buildtags.BUILDER_KEY, sbr.builder.builder))

    if sbr.gitiles_commit.id:
      bs = buildtags.gitiles_commit_buildset(sbr.gitiles_commit)
      tags.add((buildtags.BUILDSET_KEY, bs))
      if sbr.gitiles_commit.ref:  # pragma: no branch
        tags.add((buildtags.GITILES_REF_KEY, sbr.gitiles_commit.ref))

    for cl in sbr.gerrit_changes:
      bs = buildtags.gerrit_change_buildset(cl)
      tags.add((buildtags.BUILDSET_KEY, bs))

    return tags

  def create_build(self, build_id, created_by, now):
    """Converts the request to a build.

    Assumes self is valid.
    """
    sbr = self.schedule_build_request

    build_proto = self.create_build_proto(build_id, created_by, now)
    build = model.Build(
        id=build_id,
        proto=build_proto,
        tags=[
            buildtags.unparse(k, v)
            for k, v in sorted(self.compute_tag_set(sbr))
        ],
        parameters=copy.deepcopy(self.parameters or {}),
        created_by=created_by,
        create_time=now,
        never_leased=self.lease_expiration_date is None,
        retry_of=self.retry_of,
        canary_preference=model.TRINARY_TO_CANARY_PREFERENCE[sbr.canary],
        experimental=bbutil.TRINARY_TO_BOOLISH[sbr.experimental],
    )

    if sbr.builder.builder:  # pragma: no branch
      build.parameters[model.BUILDER_PARAMETER] = sbr.builder.builder

    build.parameters[model.PROPERTIES_PARAMETER] = bbutil.struct_to_dict(
        sbr.properties
    )

    if sbr.HasField('notify'):
      build.pubsub_callback = model.PubSubCallback(
          topic=sbr.notify.pubsub_topic,
          auth_token=self.pubsub_callback_auth_token,
          user_data=sbr.notify.user_data.decode('utf-8'),
      )

    if self.lease_expiration_date is not None:
      build.lease_expiration_date = self.lease_expiration_date
      build.leasee = created_by
      build.regenerate_lease_key()

    return build


@ndb.tasklet
def add_async(req):
  """Adds the build entity to the build bucket.

  Does not check permissions.

  Returns:
    A new Build.

  Raises:
    errors.InvalidInputError: if build creation parameters are invalid.
  """
  ((build, ex),) = yield add_many_async([req])
  if ex:
    raise ex
  raise ndb.Return(build)


@ndb.tasklet
def add_many_async(build_request_list):
  """Adds many builds in a batch, for each BuildRequest.

  Does not check permissions.

  Returns:
    A list of (new_build, exception) tuples in the same order.
    Exactly one item of a tuple will be non-None.
    The exception can be either errors.InvalidInputError or
    auth.AuthorizationError.

  Raises:
    Any exception that datastore operations can raise.
  """
  # When changing this code, make corresponding changes to
  # swarmbucket_api.SwarmbucketApi.get_task_def.

  # Preliminary preparations.
  now = utils.utcnow()
  assert all(isinstance(r, BuildRequest) for r in build_request_list)
  # A list of all requests. If a i-th request is None, it means it is done.
  build_request_list = build_request_list[:]
  results = [None] * len(build_request_list)  # return value of this function
  identity = auth.get_current_identity()
  ctx = ndb.get_context()
  new_builds = {}  # {i: model.Build}

  logging.info(
      '%s is creating %d builds', auth.get_current_identity(),
      len(build_request_list)
  )

  def pending_reqs():
    for i, r in enumerate(build_request_list):
      if results[i] is None:
        yield i, r

  @ndb.tasklet
  def check_cached_builds_async():
    """Look for existing builds by client operation ids.

    For each pending request that has a client operation id, check if a build
    with the same client operation id is in memcache.
    Mark resolved requests as done and save found builds in results.
    """
    with_request_id = ((i, r)
                       for i, r in pending_reqs()
                       if r.schedule_build_request.request_id)
    fetch_build_ids_results = utils.async_apply(
        with_request_id,
        lambda (_, r): ctx.memcache_get(r._request_id_memcache_key()),
    )
    cached_build_ids = {
        build_id: i for (i, _), build_id in fetch_build_ids_results if build_id
    }
    if not cached_build_ids:
      return
    cached_builds = yield ndb.get_multi_async([
        ndb.Key(model.Build, build_id) for build_id in cached_build_ids
    ])
    for b in cached_builds:
      if b:  # pragma: no branch
        # A cached build has been found.
        i = cached_build_ids[b.key.id()]
        results[i] = (b, None)

  def create_new_builds():
    """Initializes new_builds.

    For each pending request, create a Build entity, but don't put it.
    """
    # Ensure that build id order is reverse of build request order
    reqs = list(pending_reqs())
    build_ids = model.create_build_ids(now, len(reqs))
    for (i, r), build_id in zip(reqs, build_ids):
      new_builds[i] = r.create_build(build_id, identity, now)

  @ndb.tasklet
  def update_builders_async():
    """Creates/updates model.Builder entities."""
    builder_ids = set()
    for b in new_builds.itervalues():
      builder_id = b.proto.builder
      if builder_id.builder:  # pragma: no branch
        builder_ids.add(
            '%s:%s:%s' %
            (builder_id.project, builder_id.bucket, builder_id.builder)
        )
    keys = [ndb.Key(model.Builder, bid) for bid in builder_ids]
    builders = yield ndb.get_multi_async(keys)

    to_put = []
    for key, builder in zip(keys, builders):
      if not builder:
        # Register it!
        to_put.append(model.Builder(key=key, last_scheduled=now))
      else:
        since_last_update = now - builder.last_scheduled
        update_probability = since_last_update.total_seconds() / 3600.0
        if _should_update_builder(update_probability):
          builder.last_scheduled = now
          to_put.append(builder)
    if to_put:
      yield ndb.put_multi_async(to_put)

  @ndb.tasklet
  def create_swarming_tasks_async():
    """Creates a swarming task for each new build in a swarming bucket."""

    # Fetch and index swarmbucket builder configs.
    bucket_ids = {b.bucket_id for b in new_builds.itervalues()}
    bucket_cfgs = yield config.get_buckets_async(bucket_ids)
    builder_cfgs = {}  # {bucket_id: {builder_name: cfg}}
    for bucket_id, bucket_cfg in bucket_cfgs.iteritems():
      builder_cfgs[bucket_id] = {
          b.name: b for b in bucket_cfg.swarming.builders
      }

    # For each swarmbucket builder with build numbers, generate numbers.
    # Filter and index new_builds first.
    numbered = {}  # {seq_name: [i]}
    for i, b in new_builds.iteritems():
      cfg = builder_cfgs[b.bucket_id].get(b.proto.builder.builder)
      if cfg and cfg.build_numbers == project_config_pb2.YES:
        seq_name = sequence.builder_seq_name(b.proto.builder)
        numbered.setdefault(seq_name, []).append(i)
    # Now actually generate build numbers.
    build_number_futs = {
        seq_name: sequence.generate_async(seq_name, len(indexes))
        for seq_name, indexes in numbered.iteritems()
    }
    for seq_name, indexes in numbered.iteritems():
      build_number = yield build_number_futs[seq_name]
      for i in sorted(indexes):
        b = new_builds[i]
        b.proto.number = build_number
        b.tags.append(
            buildtags.build_address_tag(b.proto.builder, b.proto.number)
        )
        b.tags.sort()

        build_number += 1

    create_futs = {}
    for i, b in new_builds.iteritems():
      cfg = bucket_cfgs[b.bucket_id]
      if cfg and config.is_swarming_config(cfg):  # pragma: no branch
        create_futs[i] = swarming.create_task_async(b)

    for i, fut in create_futs.iteritems():
      build = new_builds[i]
      success = False
      try:
        with _with_swarming_api_error_converter():
          yield fut
          success = True
      except Exception as ex:
        results[i] = (None, ex)
        del new_builds[i]
      finally:
        if not success and build.proto.number:  # pragma: no branch
          seq_name = sequence.builder_seq_name(build.proto.builder)
          yield _try_return_build_number_async(seq_name, build.proto.number)

  @ndb.tasklet
  def put_and_cache_builds_async():
    """Puts new builds, updates metrics and memcache."""

    # Move Build.input.properties and Build.proto.infra into
    # Build.input_properties_bytes and Build.infra_bytes before putting.
    for b in new_builds.itervalues():
      b.input_properties_bytes = b.proto.input.properties.SerializeToString()
      b.proto.input.ClearField('properties')

      b.is_luci = b.proto.infra.HasField('swarming')
      b.infra_bytes = b.proto.infra.SerializeToString()
      b.proto.ClearField('infra')

    yield ndb.put_multi_async(new_builds.values())
    memcache_sets = []
    for i, b in new_builds.iteritems():
      events.on_build_created(b)
      results[i] = (b, None)

      r = build_request_list[i]
      if r.schedule_build_request.request_id:
        memcache_sets.append(
            ctx.memcache_set(r._request_id_memcache_key(), b.key.id(), 60)
        )
    yield memcache_sets

  @ndb.tasklet
  def cancel_swarming_tasks_async(cancel_all):
    futures = []
    for i, b in new_builds.iteritems():
      sw = b.parse_infra().swarming
      if sw.hostname and sw.task_id and (cancel_all or results[i][1]):
        futures.append(
            (b, sw, swarming.cancel_task_async(sw.hostname, sw.task_id))
        )
    for b, sw, fut in futures:
      try:
        yield fut
      except Exception:
        # This is best effort.
        logging.exception(
            'could not cancel swarming task\nTask: %s/%s', sw.hostname,
            sw.task_id
        )

  yield check_cached_builds_async()
  create_new_builds()
  if new_builds:
    yield update_builders_async()
    yield create_swarming_tasks_async()
    success = False
    try:
      # Update tag indexes after swarming tasks are successfully created,
      # as opposed to before, to avoid creating tag index entries for
      # nonexistent builds in case swarming task creation fails.
      yield search.update_tag_indexes_async(new_builds.itervalues())
      yield put_and_cache_builds_async()
      success = True
    finally:
      yield cancel_swarming_tasks_async(not success)

  # Validate and return results.
  assert all(results), results
  assert all(build or ex for build, ex in results), results
  assert all(not (build and ex) for build, ex in results), results
  raise ndb.Return(results)


def _should_update_builder(probability):  # pragma: no cover
  return random.random() < probability


@ndb.tasklet
def _try_return_build_number_async(seq_name, build_number):
  try:
    returned = yield sequence.try_return_async(seq_name, build_number)
    if not returned:  # pragma: no cover
      # Log an error to alert on high rates of number losses with info
      # on bucket/builder.
      logging.error('lost a build number in builder %s', seq_name)
  except Exception:  # pragma: no cover
    logging.exception('exception when returning a build number')


@contextlib.contextmanager
def _with_swarming_api_error_converter():
  """Converts swarming API errors to errors appropriate for the user."""
  try:
    yield
  except net.AuthError as ex:
    raise auth.AuthorizationError(
        'Auth error while calling swarming on behalf of %s: %s' %
        (auth.get_current_identity().to_bytes(), ex.response)
    )
  except net.Error as ex:
    if ex.status_code == 400:
      # Note that 401, 403 and 404 responses are converted to different
      # error types.

      # In general, it is hard to determine if swarming task creation failed
      # due to user-supplied data or buildbucket configuration values.
      # Notify both buildbucket admins and users about the error by logging
      # it and returning 4xx response respectively.
      msg = 'Swarming API call failed with HTTP 400: %s' % ex.response
      logging.error(msg)
      raise errors.InvalidInputError(msg)
    raise  # pragma: no cover
