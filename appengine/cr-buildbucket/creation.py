# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Creates builds."""

import collections
import contextlib
import logging
import random

from google.appengine.ext import ndb

from components import auth
from components import net
from components import utils

from proto import common_pb2
from proto.config import project_config_pb2
import buildtags
import config
import errors
import events
import model
import search
import sequence
import swarming
import user

_BuildRequestBase = collections.namedtuple(
    '_BuildRequestBase', [
        'project',
        'bucket',
        'tags',
        'parameters',
        'lease_expiration_date',
        'client_operation_id',
        'pubsub_callback',
        'retry_of',
        'canary_preference',
        'experimental',
        'gitiles_commit',
    ]
)


class BuildRequest(_BuildRequestBase):
  """A request to add a new build. Immutable."""

  def __new__(
      cls,
      project,
      bucket,
      tags=None,
      parameters=None,
      lease_expiration_date=None,
      client_operation_id=None,
      pubsub_callback=None,
      retry_of=None,
      canary_preference=model.CanaryPreference.AUTO,
      experimental=None,
      gitiles_commit=None,
  ):
    """Creates an BuildRequest. Does not perform validation.

    Args:
      project (str): project ID for the destination bucket. Required, but may
        be None.
      bucket (str): destination bucket. Required.
      tags (model.Tags): build tags.
      parameters (dict): arbitrary build parameters. Cannot be changed after
        build creation.
      lease_expiration_date (datetime.datetime): if not None, the build is
        created as leased and its lease_key is not None.
      client_operation_id (str): client-supplied operation id. If an
        a build with the same client operation id was added during last minute,
        it will be returned instead.
      pubsub_callback (model.PubsubCallback): callback parameters.
      retry_of (int): value for model.Build.retry_of attribute.
      canary_preference (model.CanaryPreference): specifies whether canary of
        the build infrastructure should be used.
      experimental (bool): whether this build is experimental.
      gitiles_commit (common_pb2.GitilesCommit): value of
        build_pb2.Build.input.gitiles_commit.
    """
    self = super(BuildRequest, cls).__new__(
        cls, project, bucket, tags, parameters, lease_expiration_date,
        client_operation_id, pubsub_callback, retry_of, canary_preference,
        experimental, gitiles_commit
    )
    return self

  def normalize(self):
    """Returns a validated and normalized BuildRequest.

    Raises:
      errors.InvalidInputError if arguments are invalid.
    """
    # Validate.
    if not isinstance(self.canary_preference, model.CanaryPreference):
      raise errors.InvalidInputError(
          'invalid canary_preference %r' % self.canary_preference
      )
    errors.validate_bucket_name(self.bucket)
    buildtags.validate_tags(
        self.tags,
        'new',
        builder=(self.parameters or {}).get(model.BUILDER_PARAMETER)
    )
    if self.parameters is not None and not isinstance(self.parameters, dict):
      raise errors.InvalidInputError('parameters must be a dict or None')
    errors.validate_lease_expiration_date(self.lease_expiration_date)
    if self.client_operation_id is not None:
      if not isinstance(self.client_operation_id,
                        basestring):  # pragma: no cover
        raise errors.InvalidInputError('client_operation_id must be string')
      if '/' in self.client_operation_id:  # pragma: no cover
        raise errors.InvalidInputError('client_operation_id must not contain /')
    if (self.gitiles_commit is not None and
        not isinstance(self.gitiles_commit, common_pb2.GitilesCommit)):
      raise errors.InvalidInputError(
          'gitiles_commit is not a common_pb2.GitilesCommit'
      )

    # Normalize.
    normalized_tags = sorted(set(self.tags or []))
    return BuildRequest(
        self.project, self.bucket, normalized_tags, self.parameters,
        self.lease_expiration_date, self.client_operation_id,
        self.pubsub_callback, self.retry_of, self.canary_preference,
        self.experimental, self.gitiles_commit
    )

  def _client_op_memcache_key(self, identity=None):
    if self.client_operation_id is None:  # pragma: no cover
      return None
    return (
        'client_op/%s/%s/add_build' %
        ((identity or auth.get_current_identity()).to_bytes(),
         self.client_operation_id)
    )

  def create_build(self, build_id, created_by, now):
    """Converts the request to a build."""
    build = model.Build(
        id=build_id,
        project=self.project,
        bucket=self.bucket,
        initial_tags=self.tags,
        tags=self.tags,
        parameters=self.parameters or {},
        status=model.BuildStatus.SCHEDULED,
        created_by=created_by,
        create_time=now,
        never_leased=self.lease_expiration_date is None,
        pubsub_callback=self.pubsub_callback,
        retry_of=self.retry_of,
        canary_preference=self.canary_preference,
        experimental=self.experimental,
        input_gitiles_commit=self.gitiles_commit,
    )
    if self.lease_expiration_date is not None:
      build.lease_expiration_date = self.lease_expiration_date
      build.leasee = created_by
      build.regenerate_lease_key()

    # Auto-add builder tag.
    # Note that we leave build.initial_tags intact.
    builder = build.parameters.get(model.BUILDER_PARAMETER)
    if builder:
      builder_tag = buildtags.builder_tag(builder)
      if builder_tag not in build.tags:
        build.tags.append(builder_tag)

    return build


@ndb.tasklet
def add_async(req):
  """Adds the build entity to the build bucket.

  Requires the current user to have permissions to add builds to the
  |bucket|.

  Returns:
    A new Build.

  Raises:
    errors.InvalidInputError: if build creation parameters are invalid.
    auth.AuthorizationError: if the current user does not have permissions to
      add a build to req.bucket.
  """
  ((build, ex),) = yield add_many_async([req])
  if ex:
    raise ex
  raise ndb.Return(build)


@ndb.tasklet
def add_many_async(build_request_list):
  """Adds many builds in a batch, for each BuildRequest.

  Returns:
    A list of (new_build, exception) tuples in the same order.
    Exactly one item of a tuple will be non-None.
    The exception can only be errors.InvalidInputError.

  Raises:
    auth.AuthorizationError if any of the build requests is denied.
      No builds will be created in this case.
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

  def validate_and_normalize():
    """Validates and normalizes requests.

    For each invalid request, mark it as done and save the exception in results.
    """
    for i, r in pending_reqs():
      try:
        build_request_list[i] = r.normalize()
      except errors.InvalidInputError as ex:
        build_request_list[i] = None
        results[i] = (None, ex)

  @ndb.tasklet
  def check_access_async():
    """For each pending request, check ACLs.

    Make one ACL query per bucket.
    Raise an exception if at least one request is denied, as opposed to saving
    the exception in results, for backward compatibility.
    """
    buckets = sorted({r.bucket for _, r in pending_reqs()})
    for b, can in utils.async_apply(buckets, user.can_add_build_async):
      if not can:
        raise user.current_identity_cannot('add builds to bucket %s', b)

  @ndb.tasklet
  def check_cached_builds_async():
    """Look for existing builds by client operation ids.

    For each pending request that has a client operation id, check if a build
    with the same client operation id is in memcache.
    Mark resolved requests as done and save found builds in results.
    """
    with_client_op = ((i, r)
                      for i, r in pending_reqs()
                      if r.client_operation_id is not None)
    fetch_build_ids_results = utils.async_apply(
        with_client_op,
        lambda (_, r): ctx.memcache_get(r._client_op_memcache_key()),
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
      builder = b.parameters.get(model.BUILDER_PARAMETER)
      if builder:
        builder_ids.add('%s:%s:%s' % (b.project, b.bucket, builder))
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
    buckets = set(b.bucket for b in new_builds.itervalues())
    bucket_cfg_futs = {b: config.get_bucket_async(b) for b in buckets}
    builder_cfgs = {}  # {(bucket, builder): cfg}
    for bucket, fut in bucket_cfg_futs.iteritems():
      _, bucket_cfg = yield fut
      for builder_cfg in bucket_cfg.swarming.builders:
        builder_cfgs[(bucket, builder_cfg.name)] = builder_cfg

    # For each swarmbucket builder with build numbers, generate numbers.
    # Filter and index new_builds first.
    numbered = {}  # {(bucket, builder): [i]}
    for i, b in new_builds.iteritems():
      builder = (b.parameters or {}).get(model.BUILDER_PARAMETER)
      builder_id = (b.bucket, builder)
      cfg = builder_cfgs.get(builder_id)
      if cfg and cfg.build_numbers == project_config_pb2.YES:
        numbered.setdefault(builder_id, []).append(i)
    # Now actually generate build numbers.
    build_number_futs = []  # [(indexes, seq_name, build_number_fut)]
    for builder_id, indexes in numbered.iteritems():
      seq_name = sequence.builder_seq_name(builder_id[0], builder_id[1])
      fut = sequence.generate_async(seq_name, len(indexes))
      build_number_futs.append((indexes, seq_name, fut))
    # {i: (seq_name, build_number)}
    build_numbers = collections.defaultdict(lambda: (None, None))
    for indexes, seq_name, fut in build_number_futs:
      build_number = yield fut
      for i in sorted(indexes):
        build_numbers[i] = (seq_name, build_number)
        build_number += 1

    create_futs = {}
    for i, b in new_builds.iteritems():
      _, cfg = yield bucket_cfg_futs[b.bucket]
      if cfg and config.is_swarming_config(cfg):
        create_futs[i] = swarming.create_task_async(b, build_numbers[i][1])

    for i, fut in create_futs.iteritems():
      success = False
      try:
        with _with_swarming_api_error_converter():
          yield fut
          success = True
      except Exception as ex:
        results[i] = (None, ex)
        del new_builds[i]
      finally:
        seq_name, build_number = build_numbers[i]
        if not success and build_number is not None:  # pragma: no branch
          yield _try_return_build_number_async(seq_name, build_number)

  @ndb.tasklet
  def put_and_cache_builds_async():
    """Puts new builds, updates metrics and memcache."""
    yield ndb.put_multi_async(new_builds.values())
    memcache_sets = []
    for i, b in new_builds.iteritems():
      events.on_build_created(b)
      results[i] = (b, None)

      r = build_request_list[i]
      if r.client_operation_id:
        memcache_sets.append(
            ctx.memcache_set(r._client_op_memcache_key(), b.key.id(), 60)
        )
    yield memcache_sets

  @ndb.tasklet
  def cancel_swarming_tasks_async(cancel_all):
    futures = [(
        b, swarming.cancel_task_async(b.swarming_hostname, b.swarming_task_id)
    ) for i, b in new_builds.iteritems() if (
        b.swarming_hostname and b.swarming_task_id and
        (cancel_all or results[i][1])
    )]
    for b, fut in futures:
      try:
        yield fut
      except Exception:
        # This is best effort.
        logging.exception(
            'could not cancel swarming task\nTask: %s/%s', b.swarming_hostname,
            b.swarming_task_id
        )

  validate_and_normalize()
  yield check_access_async()
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


def retry(
    build_id,
    lease_expiration_date=None,
    client_operation_id=None,
    pubsub_callback=None
):
  """Adds a build with same bucket, parameters and tags as the given one."""
  build = model.Build.get_by_id(build_id)
  if not build:
    raise errors.BuildNotFoundError('Build %s not found' % build_id)
  req = BuildRequest(
      build.project,
      build.bucket,
      tags=build.initial_tags if build.initial_tags is not None else build.tags,
      parameters=build.parameters,
      lease_expiration_date=lease_expiration_date,
      client_operation_id=client_operation_id,
      pubsub_callback=pubsub_callback,
      retry_of=build_id,
      canary_preference=build.canary_preference or model.CanaryPreference.AUTO,
  )
  return add_async(req).get_result()
