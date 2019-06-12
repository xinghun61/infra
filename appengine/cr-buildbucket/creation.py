# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Creates builds."""

import collections
import copy
import datetime
import hashlib
import itertools
import logging
import random

from google.appengine.ext import ndb

from components import auth
from components import net
from components import utils

from proto import build_pb2
from proto import common_pb2
from proto import project_config_pb2
import bbutil
import buildtags
import config
import flatten_swarmingcfg
import errors
import events
import model
import search
import sequence
import swarming
import swarmingcfg
import tq

# The default percentage of builds that are marked as canary.
# This number is relatively high so we treat canary seriously and that we have
# a strong signal if the canary is broken.
_DEFAULT_CANARY_PERCENTAGE = 10

# Default value of Build.infra.swarming.priority.
_DEFAULT_SWARMING_PRIORITY = 30
# Default value of Build.scheduling_timeout.
_DEFAULT_SCHEDULING_TIMEOUT = datetime.timedelta(hours=6)
# Default value of Build.execution_timeout.
_DEFAULT_EXECUTION_TIMEOUT = datetime.timedelta(hours=3)
_DEFAULT_BUILDER_CACHE_EXPIRATION = datetime.timedelta(minutes=4)

_BuildRequestBase = collections.namedtuple(
    '_BuildRequestBase', [
        'schedule_build_request',
        'parameters',
        'lease_expiration_date',
        'retry_of',
        'pubsub_callback_auth_token',
        'override_builder_cfg',
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
      override_builder_cfg=None,
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
      override_builder_cfg: a function (project_config_pb2.Builder) => None
        that may modify the config in-place before deriving a build from it.
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
        override_builder_cfg,
    )
    return self

  @property
  def bucket_id(self):
    builder_id = self.schedule_build_request.builder
    return config.format_bucket_id(builder_id.project, builder_id.bucket)

  def _request_id_memcache_key(self, identity=None):
    req_id = self.schedule_build_request.request_id
    if not req_id:  # pragma: no cover
      return None
    return (
        'request_id/%s/%s/add_build' %
        ((identity or auth.get_current_identity()).to_bytes(), req_id)
    )

  def _ensure_builder_cache(self, build_proto):
    """Ensures that build_proto has a "builder" cache."""
    caches = build_proto.infra.swarming.caches
    if not any(c.path == 'builder' for c in caches):
      h = hashlib.sha256(config.builder_id_string(build_proto.builder))
      builder_cache = caches.add(
          path='builder',
          name='builder_%s_v2' % h.hexdigest(),
      )
      builder_cache.wait_for_warm_cache.FromTimedelta(
          _DEFAULT_BUILDER_CACHE_EXPIRATION
      )

  @ndb.tasklet
  def create_build_proto_async(self, build_id, builder_cfg, created_by, now):
    """Converts the request to a build_pb2.Build.

    Assumes self is valid.
    """
    sbr = self.schedule_build_request

    bp = build_pb2.Build()
    if builder_cfg:  # pragma: no branch
      yield _apply_builder_config_async(builder_cfg, bp)

    bp.id = build_id
    bp.builder.CopyFrom(sbr.builder)
    bp.status = common_pb2.SCHEDULED
    bp.created_by = created_by.to_bytes()
    bp.create_time.FromDatetime(now)
    bp.critical = sbr.critical
    bp.exe.cipd_version = sbr.exe.cipd_version or bp.exe.cipd_version
    # If the SBR expressed canary preference, override what the config said.
    if sbr.canary != common_pb2.UNSET:
      bp.canary = sbr.canary == common_pb2.YES

    # Populate input.
    # Override properties from the config with values in the request.
    bbutil.update_struct(bp.input.properties, sbr.properties)
    if sbr.HasField('gitiles_commit'):
      bp.input.gitiles_commit.CopyFrom(sbr.gitiles_commit)
    bp.input.gerrit_changes.extend(sbr.gerrit_changes)
    bp.infra.buildbucket.requested_properties.CopyFrom(sbr.properties)
    bp.infra.buildbucket.requested_dimensions.extend(sbr.dimensions)
    if sbr.experimental != common_pb2.UNSET:
      bp.input.experimental = sbr.experimental == common_pb2.YES

    # Populate swarming-specific fields.
    sw = bp.infra.swarming
    configured_task_dims = list(sw.task_dimensions)
    sw.ClearField('task_dimensions')
    sw.task_dimensions.extend(
        _apply_dimension_overrides(configured_task_dims, sbr.dimensions)
    )

    if sbr.priority:
      sw.priority = sbr.priority
    elif bp.input.experimental:
      sw.priority = min(255, sw.priority * 2)

    self._ensure_builder_cache(bp)
    raise ndb.Return(bp)

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

  @ndb.tasklet
  def create_build_async(self, build_id, builder_cfg, created_by, now):
    """Converts the request to a build.

    Assumes self is valid.
    """
    sbr = self.schedule_build_request

    build_proto = yield self.create_build_proto_async(
        build_id, builder_cfg, created_by, now
    )
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

    raise ndb.Return(build)


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
  if ex:  # pragma: no cover
    raise ex
  raise ndb.Return(build)


class NewBuild(object):
  """A build being created.

  A mutable object that lives during add_many_async call, holds temporary
  state.
  """

  def __init__(self, request, builder_cfg):
    assert isinstance(request, BuildRequest)
    assert isinstance(builder_cfg, (type(None), project_config_pb2.Builder))
    self.request = request
    self.builder_cfg = builder_cfg

    self.build = None
    self.exception = None

  @property
  def final(self):
    return self.build or self.exception

  def result(self):
    """Returns (build, exception) tuple where one of items is None."""
    if self.exception:
      return None, self.exception
    return self.build, None

  @ndb.tasklet
  def check_cache_async(self):
    """Look for an existing build by request id.

    If request id is set, check if a build with the same request id is in
    memcache. If so, set self.build.
    """
    assert not self.build
    assert not self.exception

    cache_key = self.request._request_id_memcache_key()
    if not cache_key:  # pragma: no cover
      return

    build_id = yield ndb.get_context().memcache_get(cache_key)
    if build_id:
      self.build = yield model.Build.get_by_id_async(build_id)

  @ndb.tasklet
  def put_and_cache_async(self, settings):
    """Puts a build, updates metrics and memcache."""
    assert self.build
    assert not self.exception

    b = self.build
    bp = b.proto

    sync_task = None
    if self.builder_cfg:  # pragma: no branch
      # This is a LUCI builder.
      try:
        sync_task = yield swarming.create_sync_task_async(
            b, self.builder_cfg, settings.swarming
        )
      except errors.Error as ex:
        self.exception = ex
        return

    # Move Build.input.properties to Build.input_properties_bytes.
    b.input_properties_bytes = bp.input.properties.SerializeToString()
    bp.input.ClearField('properties')

    # Move Build.proto.infra to Build.infra_bytes.
    b.is_luci = bool(self.builder_cfg)
    b.infra_bytes = bp.infra.SerializeToString()
    bp.ClearField('infra')

    @ndb.transactional_tasklet
    def txn_async():
      if (yield b.key.get_async()):  # pragma: no cover
        raise errors.Error('build number collision')

      futs = [b.put_async()]
      if sync_task:
        futs.append(tq.enqueue_async(swarming.SYNC_QUEUE_NAME, [sync_task]))
      yield futs

    yield txn_async()
    events.on_build_created(b)

    # Memcache the build by request id for 1m.
    cache_key = self.request._request_id_memcache_key()
    if cache_key:  # pragma: no branch
      yield ndb.get_context().memcache_set(cache_key, b.key.id(), 60)


@ndb.tasklet
def add_many_async(build_requests):
  """Adds many builds in a batch.

  Does not check permissions.
  Assumes build_requests is valid.

  Returns:
    A list of (new_build, exception) tuples in the same order.
    Exactly one item of a tuple will be non-None.
    The exception can be errors.InvalidInputError.

  Raises:
    Any exception that datastore operations can raise.
  """
  # When changing this code, make corresponding changes to
  # swarmbucket_api.SwarmbucketApi.get_task_def.

  now = utils.utcnow()
  identity = auth.get_current_identity()

  logging.info(
      '%s is creating %d builds', identity.to_bytes(), len(build_requests)
  )

  # Fetch and index configs.
  bucket_ids = {br.bucket_id for br in build_requests}
  bucket_cfgs = yield config.get_buckets_async(bucket_ids)
  builder_cfgs = {}  # {bucket_id: {builder_name: cfg}}
  for bucket_id, bucket_cfg in bucket_cfgs.iteritems():
    builder_cfgs[bucket_id] = {b.name: b for b in bucket_cfg.swarming.builders}

  # Prepare NewBuild objects.
  new_builds = []
  for r in build_requests:
    builder = r.schedule_build_request.builder.builder
    bucket_builder_cfgs = builder_cfgs[r.bucket_id]
    builder_cfg = bucket_builder_cfgs.get(builder)

    # Apply builder config overrides, if any.
    # Exists for backward compatibility, runs only in V1 code path.
    if builder_cfg and r.override_builder_cfg:  # pragma: no cover
      builder_cfg = copy.deepcopy(builder_cfg)
      r.override_builder_cfg(builder_cfg)

    nb = NewBuild(r, builder_cfg)
    if bucket_builder_cfgs and not builder_cfg:
      nb.exception = errors.BuilderNotFoundError(
          'builder "%s" not found in bucket "%s"' % (builder, r.bucket_id)
      )
    new_builds.append(nb)

  # Check memcache.
  yield [nb.check_cache_async() for nb in new_builds if not nb.final]

  # Create and put builds.
  to_create = [nb for nb in new_builds if not nb.final]
  if to_create:
    build_ids = model.create_build_ids(now, len(to_create))
    builds = yield [
        nb.request.create_build_async(build_id, nb.builder_cfg, identity, now)
        for nb, build_id in zip(to_create, build_ids)
    ]
    for nb, build in zip(to_create, builds):
      nb.build = build

    yield _update_builders_async(to_create, now)
    yield _generate_build_numbers_async(to_create)
    yield search.update_tag_indexes_async([nb.build for nb in to_create])

    settings = yield config.get_settings_async()
    yield [nb.put_and_cache_async(settings) for nb in to_create]

  raise ndb.Return([nb.result() for nb in new_builds])


@ndb.tasklet
def _update_builders_async(new_builds, now):
  """Creates/updates model.Builder entities."""
  keys = sorted({
      model.Builder.make_key(nb.build.proto.builder) for nb in new_builds
  })
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
def _generate_build_numbers_async(new_builds):
  """Sets build number and adds build_address tag."""

  # For new builds with a builder that has build numbers enabled,
  # index builds by sequence name.
  by_seq = {}  # {seq_name: [NewBuild]}
  for nb in new_builds:
    cfg = nb.builder_cfg
    if cfg and cfg.build_numbers == project_config_pb2.YES:
      seq_name = sequence.builder_seq_name(nb.build.proto.builder)
      by_seq.setdefault(seq_name, []).append(nb)

  # Now actually generate build numbers.
  build_number_futs = {
      seq_name: sequence.generate_async(seq_name, len(nbs))
      for seq_name, nbs in by_seq.iteritems()
  }
  for seq_name, nbs in by_seq.iteritems():
    build_number = yield build_number_futs[seq_name]
    for nb in nbs:
      bp = nb.build.proto
      bp.number = build_number
      nb.build.tags.append(buildtags.build_address_tag(bp.builder, bp.number))
      nb.build.tags.sort()

      build_number += 1


def _should_update_builder(probability):  # pragma: no cover
  return random.random() < probability


def _should_be_canary(percentage):  # pragma: no cover
  return random.randint(0, 99) < percentage


def _apply_dimension_overrides(base, overrides):
  """Applies overrides to base.

  Both base and overrides must be a list of common_pb2.RequestedDimension.
  Returns another list, a result of overriding.
  """

  def by_key(dims):
    ret = collections.defaultdict(list)
    for d in dims:
      ret[d.key].append(d)
    return ret

  overridden = by_key(base)
  overridden.update(by_key(overrides))

  ret = itertools.chain(*overridden.itervalues())
  return sorted(ret, key=lambda d: (d.key, d.expiration.seconds, d.value))


@ndb.tasklet
def _apply_builder_config_async(builder_cfg, build_proto):
  """Applies project_config_pb2.Builder to a builds_pb2.Build."""
  # Decide if the build will be canary.
  canary_percentage = _DEFAULT_CANARY_PERCENTAGE
  if builder_cfg.HasField(  # pragma: no branch
      'task_template_canary_percentage'):
    canary_percentage = builder_cfg.task_template_canary_percentage.value
  build_proto.canary = _should_be_canary(canary_percentage)

  # Populate timeouts.
  build_proto.scheduling_timeout.seconds = builder_cfg.expiration_secs
  if not build_proto.scheduling_timeout.seconds:
    build_proto.scheduling_timeout.FromTimedelta(_DEFAULT_SCHEDULING_TIMEOUT)

  build_proto.execution_timeout.seconds = builder_cfg.execution_timeout_secs
  if not build_proto.execution_timeout.seconds:
    build_proto.execution_timeout.FromTimedelta(_DEFAULT_EXECUTION_TIMEOUT)

  # Populate input.
  build_proto.input.properties.update(
      flatten_swarmingcfg.read_properties(builder_cfg.recipe)
  )

  is_prod = yield _is_migrating_builder_prod_async(builder_cfg, build_proto)
  if is_prod is not None:  # pragma: no cover | TODO(nodir): remove branch
    build_proto.input.experimental = not is_prod
  else:
    build_proto.input.experimental = (
        builder_cfg.experimental == project_config_pb2.YES
    )

  # Populate exe.
  build_proto.exe.CopyFrom(builder_cfg.exe)
  # TODO(nodir): remove builder_cfg.recipe. Use only builder_cfg.exe.
  if builder_cfg.HasField('recipe'):  # pragma: no branch
    build_proto.exe.cipd_package = builder_cfg.recipe.cipd_package
    build_proto.exe.cipd_version = (
        builder_cfg.recipe.cipd_version or 'refs/heads/master'
    )
    build_proto.input.properties['recipe'] = builder_cfg.recipe.name
    build_proto.infra.recipe.cipd_package = builder_cfg.recipe.cipd_package
    build_proto.infra.recipe.name = builder_cfg.recipe.name

  # Populate swarming fields.
  sw = build_proto.infra.swarming
  sw.hostname = builder_cfg.swarming_host
  sw.task_service_account = builder_cfg.service_account
  sw.priority = builder_cfg.priority or _DEFAULT_SWARMING_PRIORITY

  for key, vs in swarmingcfg.read_dimensions(builder_cfg).iteritems():
    if vs == {('', 0)}:
      # This is a tombstone left from merging.
      # Skip it.
      continue

    for value, expiration_sec in vs:
      sw.task_dimensions.add(
          key=key, value=value, expiration=dict(seconds=expiration_sec)
      )

  # Populate caches.
  for c in builder_cfg.caches:
    sw.caches.add(
        name=c.name,
        path=c.path,
        wait_for_warm_cache=dict(seconds=c.wait_for_warm_cache_secs),
    )


@ndb.tasklet
def _is_migrating_builder_prod_async(
    builder_cfg, build_proto
):  # pragma: no cover | TODO(nodir): delete this code
  """Returns True if the builder is prod according to the migration app.

  See also 'luci_migration_host' in the project config.

  If unknown, returns None.
  On failures, logs them and returns None.

  TODO(nodir): remove this function when Buildbot is turned down.
  """
  ret = None

  master = None
  props_list = (
      build_proto.input.properties,
      bbutil.dict_to_struct(
          flatten_swarmingcfg.read_properties(builder_cfg.recipe)
      ),
  )
  for prop_name in ('luci_migration_master_name', 'mastername'):
    for props in props_list:
      if prop_name in props:
        master = props[prop_name]
        break
    if master:  # pragma: no branch
      break

  host = _clear_dash(builder_cfg.luci_migration_host)
  if master and host:
    try:
      url = 'https://%s/masters/%s/builders/%s/' % (
          host, master, builder_cfg.name
      )
      res = yield net.json_request_async(
          url, params={'format': 'json'}, scopes=net.EMAIL_SCOPE
      )
      ret = res.get('luci_is_prod')
    except net.NotFoundError:
      logging.warning(
          'missing migration status for %r/%r', master, builder_cfg.name
      )
    except net.Error:
      logging.exception(
          'failed to get migration status for %r/%r', master, builder_cfg.name
      )
  raise ndb.Return(ret)


def _clear_dash(s):
  """Returns s if it is not '-', otherwise returns ''."""
  return s if s != '-' else ''
