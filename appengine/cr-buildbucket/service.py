# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import contextlib
import datetime
import logging
import random
import urlparse

from google.appengine.api import taskqueue
from google.appengine.api import modules
from google.appengine.ext import deferred
from google.appengine.ext import ndb

from components import auth
from components import net
from components import utils
import gae_ts_mon

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

MAX_RETURN_BUILDS = 100
MAX_LEASE_DURATION = datetime.timedelta(hours=2)
DEFAULT_LEASE_DURATION = datetime.timedelta(minutes=1)

validate_bucket_name = errors.validate_bucket_name

# A cumlative counter of access denied errors in peek() method.
# This metric exists because defining it on the buildbucket server is easier
# than modifying Buildbot. It is very specific intentionally.
PEEK_ACCESS_DENIED_ERROR_COUNTER = gae_ts_mon.CounterMetric(
    'buildbucket/peek_access_denied_errors', 'Number of errors in peek API',
    [gae_ts_mon.StringField('bucket')]
)


def validate_lease_key(lease_key):
  if lease_key is None:
    raise errors.InvalidInputError('Lease key is not provided')


def validate_lease_expiration_date(expiration_date):
  """Raises errors.InvalidInputError if |expiration_date| is invalid."""
  if expiration_date is None:
    return
  if not isinstance(expiration_date, datetime.datetime):
    raise errors.InvalidInputError(
        'Lease expiration date must be datetime.datetime'
    )
  duration = expiration_date - utils.utcnow()
  if duration <= datetime.timedelta(0):
    raise errors.InvalidInputError(
        'Lease expiration date cannot be in the past'
    )
  if duration > MAX_LEASE_DURATION:
    raise errors.InvalidInputError(
        'Lease duration cannot exceed %s' % MAX_LEASE_DURATION
    )


def validate_url(url):
  if url is None:
    return
  if not isinstance(url, basestring):
    raise errors.InvalidInputError('url must be string')
  parsed = urlparse.urlparse(url)
  if not parsed.netloc:
    raise errors.InvalidInputError('url must be absolute')
  if parsed.scheme.lower() not in ('http', 'https'):
    raise errors.InvalidInputError(
        'Unexpected url scheme: "%s"' % parsed.scheme
    )


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
      experimental=None
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
    """
    self = super(BuildRequest, cls).__new__(
        cls, project, bucket, tags, parameters, lease_expiration_date,
        client_operation_id, pubsub_callback, retry_of, canary_preference,
        experimental
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
    validate_bucket_name(self.bucket)
    buildtags.validate_tags(
        self.tags,
        'new',
        builder=(self.parameters or {}).get(model.BUILDER_PARAMETER)
    )
    if self.parameters is not None and not isinstance(self.parameters, dict):
      raise errors.InvalidInputError('parameters must be a dict or None')
    validate_lease_expiration_date(self.lease_expiration_date)
    if self.client_operation_id is not None:
      if not isinstance(self.client_operation_id,
                        basestring):  # pragma: no cover
        raise errors.InvalidInputError('client_operation_id must be string')
      if '/' in self.client_operation_id:  # pragma: no cover
        raise errors.InvalidInputError('client_operation_id must not contain /')

    # Normalize.
    normalized_tags = sorted(set(self.tags or []))
    return BuildRequest(
        self.project, self.bucket, normalized_tags, self.parameters,
        self.lease_expiration_date, self.client_operation_id,
        self.pubsub_callback, self.retry_of, self.canary_preference,
        self.experimental
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
        bucket=self.bucket,
        project=self.project,
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


def add(build_request):
  """Sync version of add_async."""
  return add_async(build_request).get_result()


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


def unregister_builders():
  """Unregisters builders that didn't have builds for 4 weeks."""
  threshold = utils.utcnow() - model.BUILDER_EXPIRATION_DURATION
  q = model.Builder.query(model.Builder.last_scheduled < threshold)
  keys = q.fetch(keys_only=True)
  if keys:  # pragma: no branch
    logging.warning('unregistered builders: %s', [k.id() for k in keys])
    ndb.delete_multi(keys)


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
  return add(
      BuildRequest(
          build.project,
          build.bucket,
          tags=build.initial_tags
          if build.initial_tags is not None else build.tags,
          parameters=build.parameters,
          lease_expiration_date=lease_expiration_date,
          client_operation_id=client_operation_id,
          pubsub_callback=pubsub_callback,
          retry_of=build_id,
          canary_preference=build.canary_preference or
          model.CanaryPreference.AUTO,
      )
  )


@ndb.tasklet
def get_async(build_id):
  """Gets a build by |build_id|.

  Requires the current user to have permissions to view the build.
  """
  build = yield model.Build.get_by_id_async(build_id)
  if not build:
    raise ndb.Return(None)
  if not (yield user.can_view_build_async(build)):
    raise user.current_identity_cannot('view build %s', build.key.id())
  raise ndb.Return(build)


def peek(buckets, max_builds=None, start_cursor=None):
  """Returns builds available for leasing in the specified |buckets|.

  Builds are sorted by creation time, oldest first.

  Args:
    buckets (list of string): fetch only builds in any of |buckets|.
    max_builds (int): maximum number of builds to return. Defaults to 10.
    start_cursor (string): a value of "next" cursor returned by previous
      peek call. If not None, return next builds in the query.

  Returns:
    A tuple:
      builds (list of Builds): available builds.
      next_cursor (str): cursor for the next page.
        None if there are no more builds.
  """
  if not buckets:
    raise errors.InvalidInputError('No buckets specified')
  buckets = sorted(set(buckets))
  search.check_acls_async(
      buckets, inc_metric=PEEK_ACCESS_DENIED_ERROR_COUNTER
  ).get_result()
  max_builds = search.fix_max_builds(max_builds)

  # Prune any buckets that are paused.
  bucket_states = _get_bucket_states(buckets)
  active_buckets = []
  for b in buckets:
    if bucket_states[b].is_paused:
      logging.warning('Ignoring paused bucket: %s.', b)
      continue
    active_buckets.append(b)

  # Short-circuit: if there are no remaining buckets to query, then we're done.
  if not active_buckets:
    return ([], None)

  q = model.Build.query(
      model.Build.status == model.BuildStatus.SCHEDULED,
      model.Build.is_leased == False,
      model.Build.bucket.IN(active_buckets),
  )
  q = q.order(-model.Build.key)  # oldest first.

  # Check once again locally because an ndb query may return an entity not
  # satisfying the query.
  def local_predicate(b):
    return (
        b.status == model.BuildStatus.SCHEDULED and not b.is_leased and
        b.bucket in active_buckets
    )

  return search.fetch_page_async(
      q, max_builds, start_cursor, predicate=local_predicate
  ).get_result()


def _get_leasable_build(build_id):
  build = model.Build.get_by_id(build_id)
  if build is None:
    raise errors.BuildNotFoundError()
  if not user.can_lease_build_async(build).get_result():
    raise user.current_identity_cannot('lease build %s', build.key.id())
  return build


def lease(build_id, lease_expiration_date=None):
  """Leases the build, makes it unavailable for the leasing.

  Changes lease_key to a different value.

  After the lease expires, a cron task will make the build leasable again.

  Args:
    build_id (int): build id.
    lease_expiration_date (datetime.datetime): lease expiration date.
      Defaults to 10 seconds from now.

  Returns:
    Tuple:
      success (bool): True if the build was leased
      build (ndb.Build)
  """
  validate_lease_expiration_date(lease_expiration_date)
  if lease_expiration_date is None:
    lease_expiration_date = utils.utcnow() + DEFAULT_LEASE_DURATION

  @ndb.transactional
  def try_lease():
    build = _get_leasable_build(build_id)

    if build.status != model.BuildStatus.SCHEDULED or build.is_leased:
      return False, build

    build.lease_expiration_date = lease_expiration_date
    build.regenerate_lease_key()
    build.leasee = auth.get_current_identity()
    build.never_leased = False
    build.put()
    return True, build

  updated, build = try_lease()
  if updated:
    events.on_build_leased(build)
  return updated, build


def _check_lease(build, lease_key):
  if lease_key != build.lease_key:
    raise errors.LeaseExpiredError(
        'lease_key for build %s is incorrect. Your lease might be expired.' %
        build.key.id()
    )


def reset(build_id):
  """Forcibly unleases the build and resets its state.

  Resets status, url and lease_key.

  Returns:
    The reset Build.
  """

  @ndb.transactional
  def txn():
    build = _get_leasable_build(build_id)
    if not user.can_reset_build_async(build).get_result():
      raise user.current_identity_cannot('reset build %s', build.key.id())
    if build.status == model.BuildStatus.COMPLETED:
      raise errors.BuildIsCompletedError('Cannot reset a completed build')
    build.status = model.BuildStatus.SCHEDULED
    build.status_changed_time = utils.utcnow()
    build.clear_lease()
    build.url = None
    build.canary = None
    _fut_results(build.put_async(), events.on_build_resetting_async(build))
    return build

  build = txn()
  events.on_build_reset(build)
  return build


def start(build_id, lease_key, url, canary):
  """Marks build as STARTED. Idempotent.

  Args:
    build_id: id of the started build.
    lease_key: current lease key.
    url (str): a URL to a build-system-specific build, viewable by a human.
    canary (bool): True if canary build infrastructure is used for this build.

  Returns:
    The updated Build.
  """
  assert isinstance(canary, bool), canary
  validate_lease_key(lease_key)
  validate_url(url)

  @ndb.transactional
  def txn():
    build = _get_leasable_build(build_id)

    if build.status == model.BuildStatus.STARTED:
      if build.url == url:
        return False, build
      build.url = url
      build.put()
      return True, build

    if build.status == model.BuildStatus.COMPLETED:
      raise errors.BuildIsCompletedError('Cannot start a completed build')

    assert build.status == model.BuildStatus.SCHEDULED

    _check_lease(build, lease_key)

    build.start_time = utils.utcnow()
    build.status = model.BuildStatus.STARTED
    build.status_changed_time = build.start_time
    build.url = url
    build.canary = canary
    _fut_results(build.put_async(), events.on_build_starting_async(build))
    return True, build

  updated, build = txn()
  if updated:
    events.on_build_started(build)
  return build


def _get_bucket_states(buckets):
  """Returns the list of bucket states for all named buckets.

  Args:
    buckets (list): A list of bucket name strings. The bucket names are assumed
      to have already been validated.

  Returns (dict):
    A map of bucket name to BucketState for that bucket.
  """
  # Get bucket keys and deduplicate.
  default_states = [model.BucketState(id=b) for b in buckets]
  states = ndb.get_multi(state.key for state in default_states)
  for i, state in enumerate(states):
    if not state:
      states[i] = default_states[i]
  return dict(zip(buckets, states))


@ndb.tasklet
def heartbeat_async(build_id, lease_key, lease_expiration_date):
  """Extends build lease.

  Args:
    build_id: id of the build.
    lease_key: current lease key.
    lease_expiration_date (datetime.timedelta): new lease expiration date.

  Returns:
    The updated Build as Future.
  """

  @ndb.transactional_tasklet
  def txn():
    validate_lease_key(lease_key)
    if lease_expiration_date is None:
      raise errors.InvalidInputError('Lease expiration date not specified')
    validate_lease_expiration_date(lease_expiration_date)
    build = yield model.Build.get_by_id_async(build_id)
    if build is None:
      raise errors.BuildNotFoundError()
    if build.status == model.BuildStatus.COMPLETED:
      msg = ''
      if (build.result == model.BuildResult.CANCELED and
          build.cancelation_reason == model.CancelationReason.TIMEOUT):
        msg = (
            'Build was marked as timed out '
            'because it did not complete for %s' % model.BUILD_TIMEOUT
        )
      raise errors.BuildIsCompletedError(msg)
    _check_lease(build, lease_key)
    build.lease_expiration_date = lease_expiration_date
    yield build.put_async()
    raise ndb.Return(build)

  try:
    build = yield txn()
  except Exception as ex:
    events.on_heartbeat_failure(build_id, ex)
    raise
  raise ndb.Return(build)


def heartbeat(build_id, lease_key, lease_expiration_date):
  future = heartbeat_async(build_id, lease_key, lease_expiration_date)
  return future.get_result()


def heartbeat_batch(heartbeats):
  """Extends build leases in a batch.

  Args:
    heartbeats (list of dict): list of builds to update. Each dict is kwargs
    for heartbeat() method.

  Returns:
    List of (build_id, build, exception) tuples.
  """
  build_ids = [h['build_id'] for h in heartbeats]
  logging.info('Batch heartbeat: %s', build_ids)
  futures = [(h, heartbeat_async(**h)) for h in heartbeats]

  def get_result(hb, future):
    build_id = hb['build_id']
    exc = future.get_exception()
    if not exc:
      return build_id, future.get_result(), None
    else:
      return build_id, None, exc

  return [get_result(h, f) for h, f in futures]


def _complete(
    build_id,
    lease_key,
    result,
    result_details,
    failure_reason=None,
    url=None,
    new_tags=None
):
  """Marks a build as completed. Used by succeed and fail methods."""
  validate_lease_key(lease_key)
  validate_url(url)
  buildtags.validate_tags(new_tags, 'append')
  assert result in (model.BuildResult.SUCCESS, model.BuildResult.FAILURE)

  @ndb.transactional
  def txn():
    build = _get_leasable_build(build_id)

    if build.status == model.BuildStatus.COMPLETED:
      if (build.result == result and build.failure_reason == failure_reason and
          build.result_details == result_details and build.url == url):
        return False, build
      raise errors.BuildIsCompletedError(
          'Build %s has already completed' % build_id
      )
    _check_lease(build, lease_key)

    build.status = model.BuildStatus.COMPLETED
    build.status_changed_time = utils.utcnow()
    build.complete_time = utils.utcnow()
    build.result = result
    if url is not None:  # pragma: no branch
      build.url = url
    build.result_details = result_details
    build.failure_reason = failure_reason
    if new_tags:
      build.tags.extend(new_tags)
      build.tags = sorted(set(build.tags))
    build.clear_lease()
    _fut_results(build.put_async(), events.on_build_completing_async(build))
    return True, build

  updated, build = txn()
  if updated:
    events.on_build_completed(build)
  return build


def succeed(build_id, lease_key, result_details=None, url=None, new_tags=None):
  """Marks a build as succeeded. Idempotent.

  Args:
    build_id: id of the build to complete.
    lease_key: current lease key.
    result_details (dict): build result description.
    new_tags (list of str): list of new tags to add to the Build.

  Returns:
    The succeeded Build.
  """
  return _complete(
      build_id,
      lease_key,
      model.BuildResult.SUCCESS,
      result_details,
      url=url,
      new_tags=new_tags
  )


def fail(
    build_id,
    lease_key,
    result_details=None,
    failure_reason=None,
    url=None,
    new_tags=None
):
  """Marks a build as failed. Idempotent.

  Args:
    build_id: id of the build to complete.
    lease_key: current lease key.
    failure_reason (model.FailureReason): why the build failed.
      Defaults to model.FailureReason.BUILD_FAILURE.
    result_details (dict): build result description.
    new_tags (list of str): list of new tags to add to the Build.

  Returns:
    The failed Build.
  """
  failure_reason = failure_reason or model.FailureReason.BUILD_FAILURE
  return _complete(
      build_id,
      lease_key,
      model.BuildResult.FAILURE,
      result_details,
      failure_reason,
      url=url,
      new_tags=new_tags
  )


def cancel(build_id, result_details=None):
  """Cancels build. Does not require a lease key.

  The current user has to have a permission to cancel a build in the
  bucket.

  Args:
    build_id: id of the build to cancel.
    result_details (dict): build result description.

  Returns:
    Canceled Build.
  """

  @ndb.transactional
  def txn():
    build = model.Build.get_by_id(build_id)
    if build is None:
      raise errors.BuildNotFoundError()
    if not user.can_cancel_build_async(build).get_result():
      raise user.current_identity_cannot('cancel build %s', build.key.id())
    if build.status == model.BuildStatus.COMPLETED:
      if build.result == model.BuildResult.CANCELED:
        return False, build
      raise errors.BuildIsCompletedError('Cannot cancel a completed build')
    now = utils.utcnow()
    build.status = model.BuildStatus.COMPLETED
    build.status_changed_time = now
    build.result = model.BuildResult.CANCELED
    build.result_details = result_details
    build.cancelation_reason = model.CancelationReason.CANCELED_EXPLICITLY
    build.complete_time = now
    build.clear_lease()
    futs = [build.put_async(), events.on_build_completing_async(build)]
    if build.swarming_hostname and build.swarming_task_id is not None:
      futs.append(
          swarming.cancel_task_transactionally_async(
              build.swarming_hostname, build.swarming_task_id
          )
      )
    _fut_results(*futs)
    return True, build

  updated, build = txn()
  if updated:
    events.on_build_completed(build)
  return build


@ndb.tasklet
def _reset_expired_build_async(build_id):

  @ndb.transactional_tasklet
  def txn_async():
    build = yield model.Build.get_by_id_async(build_id)
    if not build or build.lease_expiration_date is None:  # pragma: no cover
      raise ndb.Return(False, build)
    is_expired = build.lease_expiration_date <= utils.utcnow()
    if not is_expired:  # pragma: no cover
      raise ndb.Return(False, build)

    assert build.status != model.BuildStatus.COMPLETED, (
        'Completed build is leased'
    )
    build.clear_lease()
    build.status = model.BuildStatus.SCHEDULED
    build.status_changed_time = utils.utcnow()
    build.url = None
    yield build.put_async(), events.on_build_resetting_async(build)
    raise ndb.Return(True, build)

  updated, build = yield txn_async()
  if updated:  # pragma: no branch
    events.on_expired_build_reset(build)


@ndb.tasklet
def _timeout_async(build_id):

  @ndb.transactional_tasklet
  def txn_async():
    build = yield model.Build.get_by_id_async(build_id)
    if not build or build.status == model.BuildStatus.COMPLETED:
      raise ndb.Return(False, build)  # pragma: no cover

    now = utils.utcnow()
    build.clear_lease()
    build.status = model.BuildStatus.COMPLETED
    build.complete_time = now
    build.status_changed_time = now
    build.result = model.BuildResult.CANCELED
    build.cancelation_reason = model.CancelationReason.TIMEOUT
    yield build.put_async(), events.on_build_completing_async(build)
    raise ndb.Return(True, build)

  # This is the only yield in this function, but it is not performance-critical.
  updated, build = yield txn_async()
  if updated:  # pragma: no branch
    events.on_build_completed(build)


def check_expired_builds():
  """For all building expired builds, resets their lease_key and state."""
  futures = []

  q = model.Build.query(
      model.Build.is_leased == True,
      model.Build.lease_expiration_date <= datetime.datetime.utcnow(),
  )
  for key in q.iter(keys_only=True):
    futures.append(_reset_expired_build_async(key.id()))

  too_long_ago = utils.utcnow() - model.BUILD_TIMEOUT
  q = model.Build.query(
      model.Build.create_time < too_long_ago,
      # Cannot use >1 inequality fitlers per query.
      model.Build.status.IN([
          model.BuildStatus.SCHEDULED, model.BuildStatus.STARTED
      ]),
  )
  for key in q.iter(keys_only=True):
    futures.append(_timeout_async(key.id()))

  _fut_results(*futures)


def delete_many_builds(bucket, status, tags=None, created_by=None):
  if status not in (model.BuildStatus.SCHEDULED, model.BuildStatus.STARTED):
    raise errors.InvalidInputError(
        'status can be STARTED or SCHEDULED, not %s' % status
    )
  if not user.can_delete_scheduled_builds_async(bucket).get_result():
    raise user.current_identity_cannot('delete scheduled builds of %s', bucket)
  # Validate created_by prior scheduled a push task.
  created_by = user.parse_identity(created_by)
  deferred.defer(
      _task_delete_many_builds,
      bucket,
      status,
      tags=tags,
      created_by=created_by,
      # Schedule it on the backend module of the same version.
      # This assumes that both frontend and backend are uploaded together.
      _target='%s.backend' % modules.get_current_version_name(),
      # Retry immediatelly.
      _retry_options=taskqueue.TaskRetryOptions(
          min_backoff_seconds=0,
          max_backoff_seconds=1,
      ),
  )


def _task_delete_many_builds(bucket, status, tags=None, created_by=None):

  @ndb.transactional_tasklet
  def txn(key):
    build = yield key.get_async()
    if not build or build.status != status:  # pragma: no cover
      raise ndb.Return(False)
    futs = [key.delete_async()]
    if build.swarming_hostname and build.swarming_task_id:
      futs.append(
          swarming.cancel_task_transactionally_async(
              build.swarming_hostname, build.swarming_task_id
          )
      )
    yield futs
    raise ndb.Return(True)

  @ndb.tasklet
  def del_if_unchanged(key):
    if (yield txn(key)):  # pragma: no branch
      logging.debug('Deleted %s', key.id())

  assert status in (model.BuildStatus.SCHEDULED, model.BuildStatus.STARTED)
  tags = tags or []
  created_by = user.parse_identity(created_by)
  q = model.Build.query(
      model.Build.bucket == bucket, model.Build.status == status
  )
  for t in tags:
    q = q.filter(model.Build.tags == t)
  if created_by:
    q = q.filter(model.Build.created_by == created_by)
  q.map(del_if_unchanged, keys_only=True)


def pause(bucket, is_paused):
  if not user.can_pause_buckets_async(bucket).get_result():
    raise user.current_identity_cannot('pause bucket of %s', bucket)

  validate_bucket_name(bucket)
  _, cfg = config.get_bucket(bucket)
  if not cfg:
    raise errors.InvalidInputError('Invalid bucket: %s' % (bucket,))
  if config.is_swarming_config(cfg):
    raise errors.InvalidInputError('Cannot pause a Swarming bucket')

  @ndb.transactional
  def try_set_pause():
    state = (
        model.BucketState.get_by_id(id=bucket) or model.BucketState(id=bucket)
    )
    if state.is_paused != is_paused:
      state.is_paused = is_paused
      state.put()

  try_set_pause()


def _fut_results(*futures):
  return [f.get_result() for f in futures]
