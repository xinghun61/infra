# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import contextlib
import datetime
import logging
import re
import sys
import urlparse

from google.appengine.api import taskqueue
from google.appengine.api import modules
from google.appengine.ext import db
from google.appengine.ext import deferred
from google.appengine.ext import ndb
from protorpc import messages

from components import auth
from components import net
from components import utils

import acl
import config
import errors
import events
import metrics
import model
import swarming

MAX_RETURN_BUILDS = 100
MAX_LEASE_DURATION = datetime.timedelta(hours=2)
DEFAULT_LEASE_DURATION = datetime.timedelta(minutes=1)
MAX_BUILDSET_LENGTH = 1024
RE_TAG_INDEX_SEARCH_CURSOR = re.compile('^id>\d+$')
# Gitiles commit buildset pattern. Example:
# ('commit/gitiles/chromium.googlesource.com/infra/luci/luci-go/+/'
#  'b7a757f457487cd5cfe2dae83f65c5bc10e288b7')
RE_BUILDSET_GITILES_COMMIT = re.compile(
    r'^commit/gitiles/[^/]+/(.+?)/\+/[a-f0-9]{40}$')
# Gerrit CL buildset pattern. Example:
# patch/gerrit/chromium-review.googlesource.com/677784/5
RE_BUILDSET_GERRIT_CL = re.compile(r'^patch/gerrit/[^/]+/\d+/\d+$')

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


def validate_build_set(bs):
  """Validates a buildset."""
  if len('buildset:') + len(bs) > MAX_BUILDSET_LENGTH:
    raise errors.InvalidInputError('too long')

  # Verify that a buildset with a known prefix is well formed.
  if bs.startswith('commit/gitiles/'):
    m = RE_BUILDSET_GITILES_COMMIT.match(bs)
    if not m:
      raise errors.InvalidInputError(
          'does not match regex "%s"' % RE_BUILDSET_GITILES_COMMIT.pattern)
    project = m.group(1)
    if project.startswith('a/'):
      raise errors.InvalidInputError(
          'gitiles project must not start with "a/"')
    if project.endswith('.git'):
      raise errors.InvalidInputError(
          'gitiles project must not end with ".git"')

  elif bs.startswith('patch/gerrit/'):
    if not RE_BUILDSET_GERRIT_CL.match(bs):
      # TODO(nodir): turn into an exception when we verify that
      # cr-buildbucket.appspot.com users do not use invalid format
      logging.warning(
          'does not match regex "%s"', RE_BUILDSET_GERRIT_CL.pattern)


def validate_tags(tags, mode, builder=None):
  """Validates build tags.

  mode must be a string, one of:
    'new': tags are for a new build.
    'append': tags are to be appended to an existing build.
    'search': tags to search by.

  builder is the value of "builder_name" parameter. If specified, tags
  "builder:<v>" must have v equal to the builder.
  """
  assert mode in ('new', 'append', 'search'), mode
  if tags is None:
    return
  if not isinstance(tags, list):
    raise errors.InvalidInputError('tags must be a list')
  builder_tag = None
  for t in tags:
    if not isinstance(t, basestring):
      raise errors.InvalidInputError(
          'Invalid tag "%s": must be a string' % (t, ))
    if ':' not in t:
      raise errors.InvalidInputError(
          'Invalid tag "%s": does not contain ":"' % t)
    if t[0] == ':':
      raise errors.InvalidInputError('Invalid tag "%s": starts with ":"' % t)
    k, v = t.split(':', 1)
    if k == 'buildset':
      try:
        validate_build_set(v)
      except errors.InvalidInputError as ex:
        raise errors.InvalidInputError('Invalid tag "%s": %s' % (t, ex))
    if k == 'build_address' and mode != 'search':
      raise errors.InvalidInputError('Tag "build_address" is reserved')
    if k == 'builder':
      if mode == 'append':
        raise errors.InvalidInputError(
          'Tag "builder" cannot be added to an existing build')
      if mode == 'new':  # pragma: no branch
        if builder is not None and v != builder:
          raise errors.InvalidInputError(
              'Tag "%s" conflicts with builder_name parameter "%s"' %
              (t, builder))
        if builder_tag is None:
          builder_tag = t
        elif t != builder_tag:
          raise errors.InvalidInputError(
              'Tag "%s" conflicts with tag "%s"' % (t, builder_tag))


_BuildRequestBase = collections.namedtuple('_BuildRequestBase', [
  'project', 'bucket', 'tags', 'parameters', 'lease_expiration_date',
  'client_operation_id', 'pubsub_callback', 'retry_of', 'canary_preference',
])


class BuildRequest(_BuildRequestBase):
  """A request to add a new build. Immutable."""

  def __new__(
      cls, project, bucket, tags=None, parameters=None,
      lease_expiration_date=None, client_operation_id=None,
      pubsub_callback=None, retry_of=None,
      canary_preference=model.CanaryPreference.AUTO):
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
    """
    self = super(BuildRequest, cls).__new__(
        cls, project, bucket, tags, parameters, lease_expiration_date,
        client_operation_id, pubsub_callback, retry_of, canary_preference)
    return self

  def normalize(self):
    """Returns a validated and normalized BuildRequest.

    Raises:
      errors.InvalidInputError if arguments are invalid.
    """
    # Validate.
    if not isinstance(self.canary_preference, model.CanaryPreference):
      raise errors.InvalidInputError(
          'invalid canary_preference %r' % self.canary_preference)
    validate_bucket_name(self.bucket)
    validate_tags(
        self.tags, 'new',
        builder=self.parameters.get('builder_name') if self.parameters else None
    )
    if self.parameters is not None and not isinstance(self.parameters, dict):
      raise errors.InvalidInputError('parameters must be a dict or None')
    validate_lease_expiration_date(self.lease_expiration_date)
    if self.client_operation_id is not None:
      if not isinstance(
          self.client_operation_id, basestring):  # pragma: no cover
        raise errors.InvalidInputError('client_operation_id must be string')
      if '/' in self.client_operation_id:  # pragma: no cover
        raise errors.InvalidInputError(
            'client_operation_id must not contain /')

    # Normalize.
    normalized_tags = sorted(set(self.tags or []))
    return BuildRequest(
        self.project, self.bucket, normalized_tags, self.parameters,
        self.lease_expiration_date, self.client_operation_id,
        self.pubsub_callback, self.retry_of, self.canary_preference)

  def _client_op_memcache_key(self, identity=None):
    if self.client_operation_id is None:  # pragma: no cover
      return None
    return (
      'client_op/%s/%s/add_build' % (
        (identity or auth.get_current_identity()).to_bytes(),
        self.client_operation_id))

  def create_build(self, build_id, created_by, now):
    """Converts the request to a build."""
    build = model.Build(
        id=build_id,
        bucket=self.bucket,
        project=self.project,
        initial_tags=self.tags,
        tags=self.tags,
        parameters=self.parameters,
        status=model.BuildStatus.SCHEDULED,
        created_by=created_by,
        create_time=now,
        never_leased=self.lease_expiration_date is None,
        pubsub_callback=self.pubsub_callback,
        retry_of=self.retry_of,
        canary_preference=self.canary_preference,
    )
    if self.lease_expiration_date is not None:
      build.lease_expiration_date = self.lease_expiration_date
      build.leasee = created_by
      build.regenerate_lease_key()

    # Auto-add builder tag.
    # Note that we leave build.initial_tags intact.
    builder = (build.parameters or {}).get('builder_name')
    if builder:
      builder_tag = 'builder:' + builder
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
    now = utils.utcnow()
    for i, r in pending_reqs():
      while True:
        build_id = model.create_build_id(now)
        if build_id not in build_ids:  # pragma: no branch
          break
      build_ids.add(build_id)
      new_builds[i] = r.create_build(build_id, identity, now)

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
      for t in set(_indexed_tags(b.tags)):
        index_entries[t].append(model.TagIndexEntry(
            build_id=b.key.id(), bucket=b.bucket))
    return [
      _add_to_tag_index_async(tag, entries)
      for tag, entries in index_entries.iteritems()
    ]

  @ndb.tasklet
  def put_and_cache_builds_async():
    """Puts new builds, updates metrics and memcache."""
    for b in new_builds.itervalues():
      b.tags = sorted(set(b.tags))
    yield ndb.put_multi_async(new_builds.values())
    memcache_sets = []
    for i, b in new_builds.iteritems():
      events.on_build_created(b)
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
      build.project,
      build.bucket,
      tags=build.initial_tags if build.initial_tags is not None else build.tags,
      parameters=build.parameters,
      lease_expiration_date=lease_expiration_date,
      client_operation_id=client_operation_id,
      pubsub_callback=pubsub_callback,
      retry_of=build_id,
      canary_preference=build.canary_preference or model.CanaryPreference.AUTO,
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


def _log_inconsistent_search_results(error_message):  # pragma: no cover
  logging.error(error_message)


class StatusFilter(messages.Enum):
  # A build must have status model.BuildStatus.SCHEDULED.
  SCHEDULED = model.BuildStatus.SCHEDULED.number
  # A build must have status model.BuildStatus.STARTED.
  STARTED = model.BuildStatus.STARTED.number
  # A build must have status model.BuildStatus.COMPLETED.
  COMPLETED = model.BuildStatus.COMPLETED.number
  # A build must have status model.BuildStatus.SCHEDULED or
  # model.BuildStatus.STARTED.
  INCOMPLETE = 10


class SearchQuery(object):
  """Argument for search. Mutable."""

  def __init__(
      self, buckets=None, tags=None, status=None, result=None,
      failure_reason=None, cancelation_reason=None, created_by=None,
      max_builds=None, start_cursor=None, retry_of=None, canary=None,
      create_time_low=None, create_time_high=None):
    """Initializes SearchQuery.

    Args:
      buckets (list of str): a list of buckets to search in.
        A build must be in one of the buckets.
      tags (list of str): a list of tags that a build must have.
        All of the |tags| must be present in a build.
      status (StatusFilter): build status.
      result (model.BuildResult): build result.
      failure_reason (model.FailureReason): failure reason.
      cancelation_reason (model.CancelationReason): build cancelation reason.
      created_by (str): identity who created a build.
      max_builds (int): maximum number of builds to return.
      start_cursor (string): a value of "next" cursor returned by previous
        search_by_tags call. If not None, return next builds in the query.
      retry_of (int): value of retry_of attribute.
      canary (bool): if not None, value of "canary" field.
        Search by canary_preference is not supported.
      create_time_low (datetime.datetime): if not None, minimum value of
        create_time attribute. Inclusive.
      create_time_high (datetime.datetime): if not None, maximum value of
        create_time attribute. Exclusive.
    """
    self.buckets = buckets
    self.tags = tags
    self.status = status
    self.result = result
    self.failure_reason = failure_reason
    self.cancelation_reason = cancelation_reason
    self.created_by = created_by
    self.retry_of = retry_of
    self.canary = canary
    self.create_time_low = create_time_low
    self.create_time_high = create_time_high
    self.max_builds = max_builds
    self.start_cursor = start_cursor

  def copy(self):
    return SearchQuery(**self.__dict__)

  def __eq__(self, other):  # pragma: no cover
    # "pragma: no cover" because this code is executed
    # by mock module, not service_test
    return type(self) == type(other) and self.__dict__ == other.__dict__

  def __ne__(self, other):  # pragma: no cover
    # "pragma: no cover" because this code is executed
    # by mock module, not service_test
    return not self.__eq__(other)


def search(q):
  """Searches for builds.

  Args:
    q (SearchQuery): the query.

  Returns:
    A tuple:
      builds (list of Build): query result.
      next_cursor (string): cursor for the next page.
        None if there are no more builds.
  """
  if q.buckets is not None and not isinstance(q.buckets, list):
    raise errors.InvalidInputError('Buckets must be a list or None')
  validate_tags(q.tags, 'search')

  q = q.copy()
  if (q.create_time_low is not None and
      q.create_time_low < model.BEGINING_OF_THE_WORLD):
    q.create_time_low = None
  if q.create_time_high is not None:
    if q.create_time_high <= model.BEGINING_OF_THE_WORLD:
      return [], None
    if (q.create_time_low is not None and
        q.create_time_low >= q.create_time_high):
      return [], None

  q.tags = q.tags or []
  q.max_builds = fix_max_builds(q.max_builds)
  q.created_by = parse_identity(q.created_by)

  if not q.buckets and q.retry_of is not None:
    retry_of_build = model.Build.get_by_id(q.retry_of)
    if retry_of_build:
      q.buckets = [retry_of_build.bucket]
  if q.buckets:
    _check_search_acls(q.buckets)
    q.buckets = set(q.buckets)

  is_tag_index_cursor = (
    q.start_cursor and RE_TAG_INDEX_SEARCH_CURSOR.match(q.start_cursor))
  can_use_tag_index = (
    _indexed_tags(q.tags) and (not q.start_cursor or is_tag_index_cursor))
  if is_tag_index_cursor and not can_use_tag_index:
    raise errors.InvalidInputError('invalid cursor')
  can_use_query_search = not q.start_cursor or not is_tag_index_cursor
  assert can_use_tag_index or can_use_query_search

  # Try searching using tag index.
  if can_use_tag_index:
    try:
      search_start_time = utils.utcnow()
      results = _tag_index_search(q)
      logging.info(
          'tag index search took %dms',
          (utils.utcnow() - search_start_time).total_seconds() * 1000)
      return results
    except (errors.InvalidIndexEntryOrder, errors.TagIndexIncomplete) as ex:
      if isinstance(ex, errors.InvalidIndexEntryOrder):
        logging.exception('invalid index entry order')
      if not can_use_query_search:
        raise
      logging.info('falling back to querying')

  # Searching using datastore query.
  assert can_use_query_search
  search_start_time = utils.utcnow()
  results = _query_search(q)
  logging.info(
      'query search took %dms',
      (utils.utcnow() - search_start_time).total_seconds() * 1000)
  return results


def _between(value, low, high):  # pragma: no cover
  # low is inclusive, high is exclusive
  if low is not None and value < low:
    return False
  if high is not None and value >= high:
    return False
  return True


def _query_search(q):
  """Searches for builds using NDB query. For args doc, see search().

  Assumes:
  - arguments are valid
  - if bool(buckets), permissions are checked.
  """
  if not q.buckets:
    q.buckets = acl.get_available_buckets()
    if q.buckets is not None and len(q.buckets) == 0:
      return [], None
  # (buckets is None) means the requester has access to all buckets.
  assert q.buckets is None or q.buckets

  check_buckets_locally = q.retry_of is not None
  dq = model.Build.query()
  for t in q.tags:
    dq = dq.filter(model.Build.tags == t)
  filter_if = lambda p, v: dq if v is None else dq.filter(p == v)

  expected_statuses = None
  if q.status == StatusFilter.INCOMPLETE:
    expected_statuses = (model.BuildStatus.SCHEDULED, model.BuildStatus.STARTED)
    dq = dq.filter(model.Build.incomplete == True)
  elif q.status is not None:
    s = model.BuildStatus.lookup_by_number(q.status.number)
    expected_statuses = (s,)
    if s == model.BuildStatus.COMPLETED:
      # Vast majority of builds in the datastore are COMPLETED b/c
      # that's the ultimate final state of any build.
      # It is very inefficient to filter by status=COMPLETED using datastore
      # because datastore merge-joins indexes for other filtering properties
      # with huge list of completed builds.
      # Omit the status in the query filter and filter in application.
      pass
    else:
      dq = filter_if(model.Build.status, s)
  dq = filter_if(model.Build.result, q.result)
  dq = filter_if(model.Build.failure_reason, q.failure_reason)
  dq = filter_if(model.Build.cancelation_reason, q.cancelation_reason)
  dq = filter_if(model.Build.created_by, q.created_by)
  dq = filter_if(model.Build.retry_of, q.retry_of)
  dq = filter_if(model.Build.canary, q.canary)

  # buckets is None if the current identity has access to ALL buckets.
  if q.buckets and not check_buckets_locally:
    dq = dq.filter(model.Build.bucket.IN(q.buckets))

  id_low, id_high = model.build_id_range(q.create_time_low, q.create_time_high)
  if id_low is not None:
    dq = dq.filter(model.Build.key >= ndb.Key(model.Build, id_low))
  if id_high is not None:
    dq = dq.filter(model.Build.key < ndb.Key(model.Build, id_high))

  dq = dq.order(model.Build.key)

  def local_predicate(build):
    if expected_statuses and build.status not in expected_statuses:
      return False  # pragma: no cover
    if q.buckets and build.bucket not in q.buckets:
      return False
    if not _between(build.create_time, q.create_time_low, q.create_time_high):
      return False  # pragma: no cover
    return True

  return _fetch_page(
      dq, q.max_builds, q.start_cursor, predicate=local_predicate)


def _tag_index_search(q):
  """Searches for builds using TagIndex entities. For args doc, see search().

  Assumes:
  - arguments are valid
  - if bool(buckets), permissions are checked.

  Raises:
    errors.TagIndexIncomplete if the tag index is complete and cannot be used.
    errors.InvalidIndexEntryOrder if raised when the tag index entry order is
      invalid.
  """
  assert q.tags
  assert not q.buckets or isinstance(q.buckets, set)

  # Choose a tag to search by.
  all_indexed_tags = _indexed_tags(q.tags)
  assert all_indexed_tags
  indexed_tag = all_indexed_tags[0] # choose the most selective tag.
  indexed_tag_key = indexed_tag.split(':', 1)[0]
  # Exclude the indexed tag from the tag filter.
  q.tags = q.tags[:]
  q.tags.remove(indexed_tag)

  idx = model.TagIndex.get_by_id(indexed_tag)
  if idx and idx.permanently_incomplete:
    raise errors.TagIndexIncomplete('TagIndex(%s) is incomplete' % indexed_tag)
  if not idx or not idx.entries:
    logging.info('no index/entries for tag %s', indexed_tag)
    return [], None
  logging.info(
      'using TagIndex(%s); last build id = %s',
      indexed_tag, idx.entries[-1].build_id)

  _check_tag_index_entry_order(idx)

  # If buckets were not specified explicitly, permissions were not checked
  # earlier. In this case, check permissions for each build.
  check_permissions = not q.buckets
  has_access_cache = {}

  def has_access(bucket):
    has = has_access_cache.get(bucket)
    if has is None:
      has = acl.can_search_builds(bucket)
      has_access_cache[bucket] = has
    return has

  # The order of index entries is descending, i.e. the newest builds are in the
  # end. Start from the end.
  entry_index = len(idx.entries) - 1

  id_low, id_high = model.build_id_range(q.create_time_low, q.create_time_high)

  # Skip entries with build ids that are less or equal to the id in the cursor.
  if q.start_cursor:
    # The cursor is a minimum build id, exclusive. Such cursor is resilient
    # to duplicates and additions of index entries to beginning or end.
    assert RE_TAG_INDEX_SEARCH_CURSOR.match(q.start_cursor)
    min_id_exclusive = int(q.start_cursor[len('id>'):])
    if id_low is not None and id_low > min_id_exclusive:
      # If the minimum build id requested is greater than the cursor, we need
      # to skip more entries. Subtract 1 because id_low is inclusive.
      min_id_exclusive = id_low - 1
    if id_high is not None and min_id_exclusive >= id_high:
      # If the min id is greater than the requested max, we should give up.
      return [], None
    # TODO(nodir): optimization: use binary search.
    while entry_index >= 0:
      if idx.entries[entry_index].build_id > min_id_exclusive:
        break
      entry_index -= 1
    if entry_index < 0:
      # We've skipped everything.
      return [], None

  # scalar_filters maps a name of a model.Build attribute to a filter value.
  # Applies only to non-repeated fields.
  scalar_filters = [
    ('result', q.result),
    ('failure_reason', q.failure_reason),
    ('cancelation_reason', q.cancelation_reason),
    ('created_by', q.created_by),
    ('retry_of', q.retry_of),
    ('canary', q.canary),
  ]
  scalar_filters = [(a, v) for a, v in scalar_filters if v is not None]
  if q.status == StatusFilter.INCOMPLETE:
    scalar_filters.append(('incomplete', True))
  elif q.status is not None:
    scalar_filters.append(
        ('status', model.BuildStatus.lookup_by_number(q.status.number)))

  # Find the builds.
  result = [] # ordered by build id by ascending.
  last_considered_entry = None
  skipped_entries = 0
  inconsistent_entries = 0
  eof = False
  while len(result) < q.max_builds:
    fetch_count = q.max_builds - len(result)
    entries_to_fetch = [] # ordered by build id by ascending.
    while entry_index >= 0:
      e = idx.entries[entry_index]
      entry_index -= 1
      prev = last_considered_entry
      last_considered_entry = e
      if prev and prev.build_id == e.build_id:
        # Tolerate duplicates.
        continue
      if id_low is not None and e.build_id < id_low:
        # Skip build ids smaller than the ones requested.
        continue
      if id_high is not None and e.build_id >= id_high:
        # Since the index is ordered by ascending build ids, if we exceed
        # build_id_high, we should stop and not return a cursor.
        entry_index = -1
        eof = True
        break
      # If we filter by bucket, check it here without fetching the build.
      # This is not a security check.
      if q.buckets and e.bucket not in q.buckets:
        continue
      if check_permissions and not has_access(e.bucket):
        continue
      entries_to_fetch.append(e)
      if len(entries_to_fetch) >= fetch_count:
        break

    if not entries_to_fetch:
      eof = True
      break

    build_keys = [ndb.Key(model.Build, e.build_id) for e in entries_to_fetch]
    for e, b in zip(entries_to_fetch, ndb.get_multi(build_keys)):
      # Check for inconsistent entries.
      if not (b and b.bucket == e.bucket and idx.key.id() in b.tags):
        logging.warning('entry with build_id %d is inconsistent', e.build_id)
        inconsistent_entries += 1
        continue
      # Check user-supplied filters.
      if any(getattr(b, a) != v for a, v in scalar_filters):
        skipped_entries += 1
        continue
      if not _between(b.create_time, q.create_time_low, q.create_time_high):
        continue  # pragma: no cover
      if any(t not in b.tags for t in q.tags):
        skipped_entries += 1
        continue
      result.append(b)

  metrics.TAG_INDEX_SEARCH_SKIPPED_BUILDS.add(
      skipped_entries, fields={'tag': indexed_tag_key})
  metrics.TAG_INDEX_INCONSISTENT_ENTRIES.add(
      inconsistent_entries, fields={'tag': indexed_tag_key})

  # Return the results.
  next_cursor = None
  if not eof and last_considered_entry:
    next_cursor = 'id>%d' % last_considered_entry.build_id
  return result, next_cursor


def _check_tag_index_entry_order(idx):
  """Raises errors.InvalidIndexEntryOrder if the order is incorrect."""
  # The order must be descending.
  for i in xrange(len(idx.entries) - 1):
    # Tolerate duplicates.
    if idx.entries[i].build_id < idx.entries[i+1].build_id:
      raise errors.InvalidIndexEntryOrder(
          'invalid entry order in TagIndex(%r)' % idx.key.id())


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

  updated, build = try_lease()
  if updated:
    events.on_build_leased(build)
  return updated, build


def _check_lease(build, lease_key):
  if lease_key != build.lease_key:
    raise errors.LeaseExpiredError(
        'lease_key for build %s is incorrect. Your lease might be expired.' %
        build.key.id())


def reset(build_id):
  """Forcibly unleases the build and resets its state.

  Resets status, url and lease_key.

  Returns:
    The reset Build.
  """
  @ndb.transactional
  def txn():
    build = _get_leasable_build(build_id)
    if not acl.can_reset_build(build):
      raise acl.current_identity_cannot('reset build %s', build.key.id())
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
      raise errors.BuildIsCompletedError()
    _check_lease(build, lease_key)
    build.lease_expiration_date = lease_expiration_date
    yield build.put_async()
    raise ndb.Return(build)

  build = None
  try:
    build = yield txn()
  except Exception as ex:
    events.on_heartbeat_failure(build_id, build, ex)
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
  validate_tags(new_tags, 'append')
  assert result in (model.BuildResult.SUCCESS, model.BuildResult.FAILURE)

  @ndb.transactional
  def txn():
    build = _get_leasable_build(build_id)

    if build.status == model.BuildStatus.COMPLETED:
      if (build.result == result and
          build.failure_reason == failure_reason and
          build.result_details == result_details and
          build.url == url):
        return False, build
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
    if not acl.can_cancel_build(build):
      raise acl.current_identity_cannot('cancel build %s', build.key.id())
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
    _fut_results(build.put_async(), events.on_build_completing_async(build))
    if build.swarming_hostname and build.swarming_task_id is not None:
      deferred.defer(
          swarming.cancel_task,
          None,
          build.swarming_hostname,
          build.swarming_task_id,
          _transactional=True)
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
        'Completed build is leased')
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
  if updated :  # pragma: no branch
    events.on_build_completed(build)


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

  _fut_results(*futures)


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
  """Adds index entries to the tag index.

  new_entries must not have duplicates.
  """
  if not new_entries:  # pragma: no cover
    return
  new_entries.sort(key=lambda e: e.build_id, reverse=True)
  for i in xrange(len(new_entries) - 1):
    assert new_entries[i].build_id != new_entries[i+1].build_id, 'Duplicate!'

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
  """Returns a list of tags that must be indexed.

  The order of returned tags is from more selective to less selective.
  """
  if not tags:
    return []
  return sorted(set(
      t for t in tags
      if t.startswith(('buildset:', 'build_address:'))
  ))


def _fut_results(*futures):
  return [f.get_result() for f in futures]
