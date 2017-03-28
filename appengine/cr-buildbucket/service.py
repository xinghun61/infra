# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import contextlib
import datetime
import logging
import sys
import urlparse

from google.appengine.api import taskqueue
from google.appengine.api import modules
from google.appengine.ext import db
from google.appengine.ext import deferred
from google.appengine.ext import ndb

from components import auth
from components import net
from components import utils

import acl
import config
import errors
import metrics
import model
import notifications
import swarming

MAX_RETURN_BUILDS = 100
MAX_LEASE_DURATION = datetime.timedelta(hours=2)
DEFAULT_LEASE_DURATION = datetime.timedelta(minutes=1)
MAX_BUILDSET_LENGTH = 1024

validate_bucket_name = errors.validate_bucket_name


def validate_lease_key(lease_key):
  if lease_key is None:
    raise errors.InvalidInputError('Lease key is not provided')


def validate_lease_expiration_date(expiration_date):
  """Raises errors.InvalidInputError if |expiration_date| is invalid."""
  if expiration_date is None:
    return
  if not isinstance(expiration_date, datetime.datetime):
    raise errors.InvalidInputError(
        'Lease expiration date must be datetime.datetime')
  duration = expiration_date - utils.utcnow()
  if duration <= datetime.timedelta(0):
    raise errors.InvalidInputError(
        'Lease expiration date cannot be in the past')
  if duration > MAX_LEASE_DURATION:
    raise errors.InvalidInputError(
        'Lease duration cannot exceed %s' % MAX_LEASE_DURATION)


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
        'Unexpected url scheme: "%s"' % parsed.scheme)


def fix_max_builds(max_builds):
  max_builds = max_builds or 10
  if not isinstance(max_builds, int):
    raise errors.InvalidInputError('max_builds must be an integer')
  if max_builds < 0:
    raise errors.InvalidInputError('max_builds must be positive')
  return min(MAX_RETURN_BUILDS, max_builds)


def validate_tags(tags):
  if tags is None:
    return
  if not isinstance(tags, list):
    raise errors.InvalidInputError('tags must be a list')
  for t in tags:
    if not isinstance(t, basestring):
      raise errors.InvalidInputError('Invalid tag "%s": must be a string')
    if ':' not in t:
      raise errors.InvalidInputError('Invalid tag "%s": does not contain ":"')
    if t[0] == ':':
      raise errors.InvalidInputError('Invalid tag "%s": starts with ":"')
    if t.startswith('buildset:') and len(t) > MAX_BUILDSET_LENGTH:
      raise errors.InvalidInputError('Tag "buildset" is too long: %s', t)
    if t.startswith('build_address:'):
      raise errors.InvalidInputError('Tag "build_address" is reserved')


_BuildRequestBase = collections.namedtuple('_BuildRequestBase', [
  'bucket', 'tags', 'parameters', 'lease_expiration_date',
  'client_operation_id', 'pubsub_callback', 'retry_of',
])


class BuildRequest(_BuildRequestBase):
  """A request to add a new build. Immutable."""

  def __new__(
      cls, bucket, tags=None, parameters=None, lease_expiration_date=None,
      client_operation_id=None, pubsub_callback=None, retry_of=None):
    """Creates an BuildRequest. Does not perform validation.

    Args:
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
    """
    self = super(BuildRequest, cls).__new__(
        cls, bucket, tags, parameters, lease_expiration_date,
        client_operation_id, pubsub_callback, retry_of)
    return self

  def normalize(self):
    """Returns a validated and normalized BuildRequest.

    Raises:
      errors.InvalidInputError if arguments are invalid.
    """
    # Validate.
    validate_bucket_name(self.bucket)
    validate_tags(self.tags)
    if self.parameters is not None and not isinstance(self.parameters, dict):
      raise errors.InvalidInputError('parameters must be a dict or None')
    validate_lease_expiration_date(self.lease_expiration_date)
    if self.client_operation_id is not None:
      if not isinstance(
          self.client_operation_id, basestring):  # pragma: no cover
        raise errors.InvalidInputError('client_operation_id must be string')
      if '/' in self.client_operation_id:  # pragma: no cover
        raise errors.InvalidInpuutError(
            'client_operation_id must not contain /')

    # Normalize.
    normalized_tags = self._add_builder_tag(self.tags, self.parameters)
    normalized_tags = sorted(set(normalized_tags))

    if normalized_tags == self.tags:
      return self
    return BuildRequest(
        self.bucket, normalized_tags, self.parameters,
        self.lease_expiration_date, self.client_operation_id,
        self.pubsub_callback, self.retry_of)

  @staticmethod
  def _add_builder_tag(tags, parameters):
    """Returns the tags with an additional builder: tag if necessary.

    If no builder_name parameter is specified, returns the tags unchanged.
    If the tags contain a builder: tag which conflicts with other pre-specified
    tags or the calculated tag, raises an error.
    """
    if tags is None:
      tags = []

    prefix = 'builder:'
    values = list(set(t[len(prefix):] for t in tags if t.startswith(prefix)))
    if len(values) > 1:
      raise errors.InvalidInputError(
          'Invalid builder tags %s: different values' % values)

    if not parameters or 'builder_name' not in parameters:
      return tags

    builder = parameters.get('builder_name')
    if len(values) == 0:
      return tags + [prefix + builder]

    if builder != values[0]:
      raise errors.InvalidInputError(
          'Invalid builder tag "%s": conflicts with builder_name parameter "%s"'
          % (values[0], builder))

    return tags

  def _client_op_memcache_key(self, identity=None):
    if self.client_operation_id is None:  # pragma: no cover
      return None
    return (
      'client_op/%s/%s/add_build' % (
        (identity or auth.get_current_identity()).to_bytes(),
        self.client_operation_id))

  def create_build(self, build_id, created_by):
    """Converts the request to a build."""
    build = model.Build(
        id=build_id,
        bucket=self.bucket,
        tags=self.tags,
        parameters=self.parameters,
        status=model.BuildStatus.SCHEDULED,
        created_by=created_by,
        never_leased=self.lease_expiration_date is None,
        pubsub_callback=self.pubsub_callback,
        retry_of=self.retry_of,
    )
    if self.lease_expiration_date is not None:
      build.lease_expiration_date = self.lease_expiration_date
      build.leasee = created_by
      build.regenerate_lease_key()
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

  # Preliminary preparations.
  assert all(isinstance(r, BuildRequest) for r in build_request_list)
  # A list of all requests. If a i-th request is None, it means it is done.
  build_request_list = build_request_list[:]
  pending_reqs = lambda: ((i, r) for i, r in enumerate(build_request_list) if r)
  results = [None] * len(build_request_list)  # return value of this function
  identity = auth.get_current_identity()
  ctx = ndb.get_context()
  new_builds = {}

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
    buckets = set(r.bucket for _, r in pending_reqs())
    can_add_futs = {b: acl.can_add_build_async(b) for b in buckets}
    yield can_add_futs.values()
    for b, can_fut in can_add_futs.iteritems():
      if not can_fut.get_result():
        raise acl.current_identity_cannot('add builds to bucket %s', b)

  @ndb.tasklet
  def check_cached_builds_async():
    """Look for existing builds by client operation ids.

    For each pending request that has a client operation id, check if a build
    with the same client operation id is in memcache.
    Mark resolved requests as done and save found builds in results.
    """
    cached_build_id_futs = {
      i: ctx.memcache_get(r._client_op_memcache_key())
      for i, r in pending_reqs()
      if r.client_operation_id is not None
    }
    if not cached_build_id_futs:
      return

    yield cached_build_id_futs.values()
    cached_build_ids = {
      f.get_result(): i
      for i, f in cached_build_id_futs.iteritems()
      if f.get_result() is not None
    }
    if not cached_build_ids:
      return
    cached_builds = yield ndb.get_multi_async([
      ndb.Key(model.Build, build_id)
      for build_id in cached_build_ids
    ])
    for b in cached_builds:
      if b:  # pragma: no branch
        # A cached build has been found.
        i = cached_build_ids[b.key.id()]
        build_request_list[i] = None
        results[i] = (b, None)

  def create_new_builds():
    """Initializes new_builds.

    For each pending request, create a Build entity, but don't put it.
    """
    build_ids = set()
    for i, r in pending_reqs():
      while True:
        build_id = model.new_build_id()
        if build_id not in build_ids:  # pragma: no branch
          break
      build_ids.add(build_id)
      new_builds[i] = r.create_build(build_id, identity)

  @ndb.tasklet
  def create_swarming_tasks_async():
    """Creates a swarming task for each new build in a swarming bucket."""
    buckets = set(b.bucket for b in new_builds.itervalues())
    bucket_cfg_futs = {b: config.get_bucket_async(b) for b in buckets}
    yield bucket_cfg_futs.values()
    create_tasks = []
    for b in new_builds.itervalues():
      _, cfg = bucket_cfg_futs[b.bucket].get_result()
      if cfg and config.is_swarming_config(cfg):
        create_tasks.append(swarming.create_task_async(b))
    yield create_tasks

  def cancel_swarming_tasks_async():
    cancel_tasks = []
    for b in new_builds.values():
      if b.swarming_hostname and b.swarming_task_id:
        cancel_tasks.append(swarming.cancel_task_async(
            b.swarming_hostname, b.swarming_task_id))
    return cancel_tasks

  def update_tag_indexes_async():
    """Updates tag indexes.

    For each new build, for each indexed tag, add an entry to a tag index.
    """
    index_entries = collections.defaultdict(list)
    for b in new_builds.itervalues():
      for t in _indexed_tags(b.tags):
        index_entries[t].append(model.TagIndexEntry(
            build_id=b.key.id(), bucket=b.bucket))
    return [
      _add_to_tag_index_async(tag, entries)
      for tag, entries in index_entries.iteritems()
    ]

  @ndb.tasklet
  def put_and_cache_builds_async():
    """Puts new builds, updates metrics and memcache."""
    yield ndb.put_multi_async(new_builds.values())
    memcache_sets = []
    for i, b in new_builds.iteritems():
      logging.info(
          'Build %s for bucket %s was created by %s',
          b.key.id(), b.bucket, identity.to_bytes())
      metrics.increment(metrics.CREATE_COUNT, b)
      results[i] = (b, None)

      r = build_request_list[i]
      if r.client_operation_id:
        memcache_sets.append(
            ctx.memcache_set(r._client_op_memcache_key(), b.key.id(), 60))
    yield memcache_sets

  validate_and_normalize()
  yield check_access_async()
  yield check_cached_builds_async()
  create_new_builds()
  if new_builds:
    try:
      with _with_swarming_api_error_converter():
        yield create_swarming_tasks_async()
      # Update tag indexes after swarming tasks are successfully created,
      # as opposed to before, to avoid creating tag index entries for
      # nonexistent builds in case swarming task creation fails.
      yield update_tag_indexes_async()
      yield put_and_cache_builds_async()
    except:  # pragma: no cover
      # Save exception info before the next try..except.
      exi = sys.exc_info()
      # Try to cancel swarming tasks. Best effort.
      try:
        yield cancel_swarming_tasks_async()
      except Exception as ex:
        # Emit an error log entry so we can alert on high rate of these errors.
        logging.error('could not clean swarming tasks after creation\n%s', ex)
      raise exi[0], exi[1], exi[2]

  # Validate and return results.
  assert all(results), results
  assert all(build or ex for build, ex in results), results
  assert all(not (build and ex) for build, ex in results), results
  raise ndb.Return(results)


@contextlib.contextmanager
def _with_swarming_api_error_converter():
  """Converts swarming API errors to errors appropriate for the user."""
  try:
    yield
  except net.AuthError as ex:
    raise auth.AuthorizationError(
        'Auth error while calling swarming on behalf of %s: %s' % (
          auth.get_current_identity().to_bytes(), ex
        ))
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
    build_id, lease_expiration_date=None, client_operation_id=None,
    pubsub_callback=None):
  """Adds a build with same bucket, parameters and tags as the given one."""
  build = model.Build.get_by_id(build_id)
  if not build:
    raise errors.BuildNotFoundError('Build %s not found' % build_id)
  return add(BuildRequest(
      build.bucket,
      tags=build.tags,
      parameters=build.parameters,
      lease_expiration_date=lease_expiration_date,
      client_operation_id=client_operation_id,
      pubsub_callback=pubsub_callback,
      retry_of=build_id,
  ))


def get(build_id):
  """Gets a build by |build_id|.

  Requires the current user to have permissions to view the build.
  """
  build = model.Build.get_by_id(build_id)
  if not build:
    return None
  if not acl.can_view_build(build):
    raise acl.current_identity_cannot('view build %s', build.key.id())
  return build


def _fetch_page(query, page_size, start_cursor, predicate=None):
  assert query
  assert isinstance(page_size, int)
  assert start_cursor is None or isinstance(start_cursor, basestring)

  curs = None
  if start_cursor:
    try:
      curs = ndb.Cursor(urlsafe=start_cursor)
    except db.BadValueError as ex:
      msg = 'Bad cursor "%s": %s' % (start_cursor, ex)
      logging.warning(msg)
      raise errors.InvalidInputError(msg)

  entities = []
  while len(entities) < page_size:
    page, curs, more = query.fetch_page(page_size, start_cursor=curs)
    for entity in page:
      if predicate is None or predicate(entity):  # pragma: no branch
        entities.append(entity)
        if len(entities) >= page_size:
          break
    if not more:
      break

  curs_str = None
  if more:
    curs_str = curs.urlsafe()
  return entities, curs_str


def _check_search_acls(buckets):
  if not buckets:
    raise errors.InvalidInputError('No buckets specified')
  for bucket in buckets:
    validate_bucket_name(bucket)

  for bucket in buckets:
    if not acl.can_search_builds(bucket):
      raise acl.current_identity_cannot('search builds in bucket %s', bucket)


def search(
    buckets=None, tags=None,
    status=None, result=None, failure_reason=None, cancelation_reason=None,
    created_by=None, max_builds=None, start_cursor=None,
    retry_of=None):
  """Searches for builds.

  Args:
    buckets (list of str): a list of buckets to search in.
      A build must be in one of the buckets.
    tags (list of str): a list of tags that a build must have.
      All of the |tags| must be present in a build.
    status (model.BuildStatus): build status.
    result (model.BuildResult): build result.
    failure_reason (model.FailureReason): failure reason.
    cancelation_reason (model.CancelationReason): build cancelation reason.
    created_by (str): identity who created a build.
    max_builds (int): maximum number of builds to return.
    start_cursor (string): a value of "next" cursor returned by previous
      search_by_tags call. If not None, return next builds in the query.
    retry_of (int): value of retry_of attribute.

  Returns:
    A tuple:
      builds (list of Build): query result.
      next_cursor (string): cursor for the next page.
        None if there are no more builds.
  """
  if buckets is not None and not isinstance(buckets, list):
    raise errors.InvalidInputError('Buckets must be a list or None')
  validate_tags(tags)
  tags = tags or []
  max_builds = fix_max_builds(max_builds)
  created_by = parse_identity(created_by)

  if not buckets and retry_of is not None:
    retry_of_build = model.Build.get_by_id(retry_of)
    if retry_of_build:
      buckets = [retry_of_build.bucket]
  if buckets:
    _check_search_acls(buckets)
  else:
    buckets = acl.get_available_buckets()
    if buckets is not None and len(buckets) == 0:
      return [], None
  if buckets:
    buckets = set(buckets)
  assert buckets is None or buckets

  check_buckets_locally = retry_of is not None
  q = model.Build.query()
  for t in tags:
    if t.startswith('buildset:'):
      check_buckets_locally = True
    q = q.filter(model.Build.tags == t)
  filter_if = lambda p, v: q if v is None else q.filter(p == v)
  q = filter_if(model.Build.status, status)
  q = filter_if(model.Build.result, result)
  q = filter_if(model.Build.failure_reason, failure_reason)
  q = filter_if(model.Build.cancelation_reason, cancelation_reason)
  q = filter_if(model.Build.created_by, created_by)
  q = filter_if(model.Build.retry_of, retry_of)
  # buckets is None if the current identity has access to ALL buckets.
  if buckets and not check_buckets_locally:
    q = q.filter(model.Build.bucket.IN(buckets))
  q = q.order(model.Build.key)

  local_predicate = None

  def local_status_and_bucket_check(build):
    if status is not None and build.status != status:  # pragma: no coverage
      return False
    if buckets and build.bucket not in buckets:
      return False
    return True

  if status is not None or (buckets and check_buckets_locally):
    local_predicate = local_status_and_bucket_check

  return _fetch_page(
      q, max_builds, start_cursor, predicate=local_predicate)


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
  buckets = sorted(set(buckets))
  _check_search_acls(buckets)
  max_builds = fix_max_builds(max_builds)

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
    return (b.status == model.BuildStatus.SCHEDULED and
            not b.is_leased and
            b.bucket in active_buckets)

  return _fetch_page(
      q, max_builds, start_cursor, predicate=local_predicate)


def _get_leasable_build(build_id):
  build = model.Build.get_by_id(build_id)
  if build is None:
    raise errors.BuildNotFoundError()
  if not acl.can_lease_build(build):
    raise acl.current_identity_cannot('lease build %s', build.key.id())
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

  leased, build = try_lease()
  if leased:
    logging.info(
        'Build %s was leased by %s', build.key.id(), build.leasee.to_bytes())
    metrics.increment(metrics.LEASE_COUNT, build)
  return leased, build


def _check_lease(build, lease_key):
  if lease_key != build.lease_key:
    raise errors.LeaseExpiredError(
        'lease_key for build %s is incorrect. Your lease might be expired.' %
        build.key.id())


@ndb.transactional
def reset(build_id):
  """Forcibly unleases the build and resets its state. Idempotent.

  Resets status, url and lease_key.

  Returns:
    The reset Build.
  """
  build = _get_leasable_build(build_id)
  if not acl.can_reset_build(build):
    raise acl.current_identity_cannot('reset build %s', build.key.id())
  if build.status == model.BuildStatus.COMPLETED:
    raise errors.BuildIsCompletedError('Cannot reset a completed build')
  build.status = model.BuildStatus.SCHEDULED
  build.status_changed_time = utils.utcnow()
  build.clear_lease()
  build.url = None
  build.put()
  notifications.enqueue_callback_task_if_needed(build)
  logging.info(
      'Build %s was reset by %s',
      build.key.id(), auth.get_current_identity().to_bytes())
  return build


def start(build_id, lease_key, url=None):
  """Marks build as STARTED. Idempotent.

  Args:
    build_id: id of the started build.
    lease_key: current lease key.
    url (str): a URL to a build-system-specific build, viewable by a human.

  Returns:
    The updated Build.
  """
  validate_lease_key(lease_key)
  validate_url(url)

  @ndb.transactional
  def txn():
    build = _get_leasable_build(build_id)

    if build.status == model.BuildStatus.STARTED:
      if build.url != url:
        build.url = url
        build.put()
      return build
    elif build.status == model.BuildStatus.COMPLETED:
      raise errors.BuildIsCompletedError('Cannot start a completed build')
    assert build.status == model.BuildStatus.SCHEDULED
    _check_lease(build, lease_key)

    build.status = model.BuildStatus.STARTED
    build.status_changed_time = utils.utcnow()
    build.url = url
    build.put()
    notifications.enqueue_callback_task_if_needed(build)
    return build

  build = txn()
  logging.info('Build %s was started. URL: %s', build.key.id(), url)
  metrics.increment(metrics.START_COUNT, build)
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
      raise errors.BuildIsCompletedError()
    _check_lease(build, lease_key)
    build.lease_expiration_date = lease_expiration_date
    yield build.put_async()
    raise ndb.Return(build)

  build = None
  try:
    build = yield txn()
  except Exception as ex:
    logging.warning('Heartbeat for build %s failed: %s', build_id, ex)
    metrics.increment(metrics.HEARTBEAT_COUNT, build, status='FAILURE')
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
    build_id, lease_key, result, result_details, failure_reason=None,
    url=None, new_tags=None):
  """Marks a build as completed. Used by succeed and fail methods."""
  validate_lease_key(lease_key)
  validate_url(url)
  validate_tags(new_tags)
  assert result in (model.BuildResult.SUCCESS, model.BuildResult.FAILURE)

  @ndb.transactional
  def txn():
    build = _get_leasable_build(build_id)

    if build.status == model.BuildStatus.COMPLETED:
      if (build.result == result and
          build.failure_reason == failure_reason and
          build.result_details == result_details and
          build.url == url):
        return build
      raise errors.BuildIsCompletedError(
          'Build %s has already completed' % build_id)
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
    build.put()
    notifications.enqueue_callback_task_if_needed(build)
    return build

  build = txn()
  logging.info(
      'Build %s was completed. Status: %s. Result: %s',
      build.key.id(), build.status, build.result)
  metrics.increment_complete_count(build)
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
      build_id, lease_key, model.BuildResult.SUCCESS, result_details, url=url,
      new_tags=new_tags)


def fail(
    build_id, lease_key, result_details=None, failure_reason=None,
    url=None, new_tags=None):
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
      build_id, lease_key, model.BuildResult.FAILURE, result_details,
      failure_reason, url=url, new_tags=new_tags)


def cancel(build_id):
  """Cancels build. Does not require a lease key.

  The current user has to have a permission to cancel a build in the
  bucket.

  Returns:
    Canceled Build.
  """

  @ndb.transactional
  def txn():
    build = model.Build.get_by_id(build_id)
    if build is None:
      raise errors.BuildNotFoundError()
    if not acl.can_cancel_build(build):
      raise acl.current_identity_cannot('cancel build %s', build.key.id())
    if build.status == model.BuildStatus.COMPLETED:
      if build.result == model.BuildResult.CANCELED:
        return build
      raise errors.BuildIsCompletedError('Cannot cancel a completed build')
    now = utils.utcnow()
    build.status = model.BuildStatus.COMPLETED
    build.status_changed_time = now
    build.result = model.BuildResult.CANCELED
    build.cancelation_reason = model.CancelationReason.CANCELED_EXPLICITLY
    build.complete_time = now
    build.clear_lease()
    build.put()
    notifications.enqueue_callback_task_if_needed(build)
    if build.swarming_hostname and build.swarming_task_id is not None:
      deferred.defer(
          swarming.cancel_task,
          None,
          build.swarming_hostname,
          build.swarming_task_id,
          _transactional=True)
    return build

  build = txn()
  logging.info(
      'Build %s was cancelled by %s', build.key.id(),
      auth.get_current_identity().to_bytes())
  metrics.increment_complete_count(build)
  return build


@ndb.tasklet
def _reset_expired_build_async(build_id):
  @ndb.transactional_tasklet
  def txn():
    build = yield model.Build.get_by_id_async(build_id)
    if not build or build.lease_expiration_date is None:  # pragma: no cover
      return
    is_expired = build.lease_expiration_date <= utils.utcnow()
    if not is_expired:  # pragma: no cover
      return

    assert build.status != model.BuildStatus.COMPLETED, (
      'Completed build is leased')
    build.clear_lease()
    build.status = model.BuildStatus.SCHEDULED
    build.status_changed_time = utils.utcnow()
    build.url = None
    yield build.put_async()
    raise ndb.Return(build)

  build = yield txn()
  logging.info('Expired build %s was reset', build_id)
  metrics.increment(metrics.LEASE_EXPIRATION_COUNT, build)


@ndb.transactional_tasklet
def _timeout_async(build_id):
  build = yield model.Build.get_by_id_async(build_id)
  if not build or build.status == model.BuildStatus.COMPLETED:
    return  # pragma: no cover

  build.clear_lease()
  build.status = model.BuildStatus.COMPLETED
  build.status_changed_time = utils.utcnow()
  build.result = model.BuildResult.CANCELED
  build.cancelation_reason = model.CancelationReason.TIMEOUT
  yield build.put_async()
  logging.info('Build %s: timeout', build_id)
  yield notifications.enqueue_callback_task_if_needed_async(build)
  metrics.increment_complete_count(build)


def reset_expired_builds():
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
      model.Build.status.IN(
          [model.BuildStatus.SCHEDULED, model.BuildStatus.STARTED]),
  )
  for key in q.iter(keys_only=True):
    futures.append(_timeout_async(key.id()))

  ndb.Future.wait_all(futures)


def delete_many_builds(bucket, status, tags=None, created_by=None):
  if status not in (model.BuildStatus.SCHEDULED, model.BuildStatus.STARTED):
    raise errors.InvalidInputError(
        'status can be STARTED or SCHEDULED, not %s' % status)
  if not acl.can_delete_scheduled_builds(bucket):
    raise acl.current_identity_cannot('delete scheduled builds of %s', bucket)
  # Validate created_by prior scheduled a push task.
  created_by = parse_identity(created_by)
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
  def del_if_unchanged(key):
    build = yield key.get_async()
    if build and build.status == status:  # pragma: no branch
      yield key.delete_async()
      logging.debug('Deleted %s', key.id())

  assert status in (model.BuildStatus.SCHEDULED, model.BuildStatus.STARTED)
  tags = tags or []
  created_by = parse_identity(created_by)
  q = model.Build.query(
      model.Build.bucket == bucket,
      model.Build.status == status)
  for t in tags:
    q = q.filter(model.Build.tags == t)
  if created_by:
    q = q.filter(model.Build.created_by == created_by)
  q.map(del_if_unchanged, keys_only=True)


def pause(bucket, is_paused):
  if not acl.can_pause_buckets(bucket):
    raise acl.current_identity_cannot('pause bucket of %s', bucket)

  validate_bucket_name(bucket)
  _, cfg = config.get_bucket(bucket)
  if not cfg:
    raise errors.InvalidInputError('Invalid bucket: %s' % (bucket,))
  if config.is_swarming_config(cfg):
    raise errors.InvalidInputError('Cannot pause a Swarming bucket')

  @ndb.transactional
  def try_set_pause():
    state = (model.BucketState.get_by_id(id=bucket) or
             model.BucketState(id=bucket))
    if state.is_paused != is_paused:
      state.is_paused = is_paused
      state.put()

  try_set_pause()


def parse_identity(identity):
  if isinstance(identity, basestring):
    if not identity:  # pragma: no cover
      return None
    if ':' not in identity:  # pragma: no branch
      identity = 'user:%s' % identity
    try:
      identity = auth.Identity.from_bytes(identity)
    except ValueError as ex:
      raise errors.InvalidInputError('Invalid identity identity: %s' % ex)
  return identity


def longest_pending_time(bucket, builder):
  """Returns longest waiting time among SCHEDULED builds of a builder.

  |builder| is a value of "builder" tag.

  Returns a datetime.timedelta.
  """
  if not bucket:
    raise errors.InvalidInputError('no bucket')
  if not acl.can_access_bucket(bucket):
    raise acl.current_identity_cannot('access bucket %s', bucket)
  if not builder:
    raise errors.InvalidInputError('no builder')

  # Find the oldest, still SCHEDULED build in this builder.
  q = model.Build.query(
      model.Build.bucket == bucket,
      model.Build.tags == ('builder:%s' % builder),
      model.Build.status == model.BuildStatus.SCHEDULED,
      projection=[model.Build.create_time])
  q = q.order(model.Build.create_time)
  result = q.fetch(1)
  if not result:
    return datetime.timedelta(0)
  return utils.utcnow() - result[0].create_time


def _add_to_tag_index_async(tag, new_entries):
  """Adds index entries to the tag index."""
  if not new_entries:  # pragma: no cover
    return
  new_entries.sort(key=lambda e: e.build_id, reverse=True)

  @ndb.transactional_tasklet
  def txn_async():
    idx = (yield model.TagIndex.get_by_id_async(tag)) or model.TagIndex(id=tag)
    if idx.permanently_incomplete:
      return

    # Avoid going beyond 1Mb entity size limit by limiting the number of entries
    new_size = len(idx.entries) + len(new_entries)
    if new_size > model.TagIndex.MAX_ENTRY_COUNT:
      idx.permanently_incomplete = True
      idx.entries = []
    else:
      # idx.entries is sorted by descending.
      # Build ids are monotonically decreasing, so most probably new entries
      # will be added to the end.
      fast_path = (
        not idx.entries or
        idx.entries[-1].build_id > new_entries[0].build_id)
      idx.entries.extend(new_entries)
      if not fast_path:
        # Atypical case
        logging.warning('hitting slow path in maintaining tag index')
        idx.entries.sort(key=lambda e: e.build_id, reverse=True)
    yield idx.put_async()

  return txn_async()


def _indexed_tags(tags):
  """Returns a list of tags that must be indexed."""
  if not tags:
    return []
  return sorted(set(
      t for t in tags
      if t.startswith(('buildset:', 'build_address:'))
  ))
