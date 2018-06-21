# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Build indexing and search."""

import heapq
import logging
import random
import re

from google.appengine.ext import db
from google.appengine.ext import ndb
from protorpc import messages

from components import utils

from proto import common_pb2
import buildtags
import errors
import metrics
import model
import user

MAX_RETURN_BUILDS = 100
RE_TAG_INDEX_SEARCH_CURSOR = re.compile('^id>\d+$')


def fix_max_builds(max_builds):
  """Fixes a page size."""
  max_builds = max_builds or 10
  if not isinstance(max_builds, int):
    raise errors.InvalidInputError('max_builds must be an integer')
  if max_builds < 0:
    raise errors.InvalidInputError('max_builds must be positive')
  return min(MAX_RETURN_BUILDS, max_builds)


def fetch_page(query, page_size, start_cursor, predicate=None):
  """Fetches a page of Build entities."""
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
  skipped = 0
  pages = 0
  started = utils.utcnow()
  while len(entities) < page_size:
    # It is important not to request more than needed in query.fetch_page,
    # otherwise the cursor we return to the user skips fetched, but not returned
    # entities, and the user will never see them.
    to_fetch = page_size - len(entities)

    page, curs, more = query.fetch_page(to_fetch, start_cursor=curs)
    pages += 1
    for entity in page:
      if predicate and not predicate(entity):  # pragma: no cover
        skipped += 1
        continue
      entities.append(entity)
      if len(entities) >= page_size:
        break
    if not more:
      break
  logging.debug(
      'fetch_page: fetched %d pages in %dms, skipped %d entities', pages,
      (utils.utcnow() - started).total_seconds() * 1000, skipped
  )

  curs_str = None
  if more:
    curs_str = curs.urlsafe()
  return entities, curs_str


def check_acls(buckets, inc_metric=None):
  """Checks access to the buckets.

  Raises an error if the current identity doesn't have access to any of the
  buckets.
  """
  assert buckets
  for bucket in buckets:
    errors.validate_bucket_name(bucket)

  for bucket in buckets:
    if not user.can_search_builds(bucket):
      if inc_metric:  # pragma: no cover
        inc_metric.increment(fields={'bucket': bucket})
      raise user.current_identity_cannot('search builds in bucket %s', bucket)


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


class Query(object):
  """Argument for search. Mutable."""

  def __init__(
      self,
      buckets=None,
      tags=None,
      status=None,
      result=None,
      failure_reason=None,
      cancelation_reason=None,
      created_by=None,
      max_builds=None,
      start_cursor=None,
      retry_of=None,
      canary=None,
      create_time_low=None,
      create_time_high=None,
      include_experimental=None
  ):
    """Initializes Query.

    Args:
      buckets (list of str): a list of buckets to search in.
        A build must be in one of the buckets.
      tags (list of str): a list of tags that a build must have.
        All of the |tags| must be present in a build.
      status (StatusFilter or common_pb2.Status): build status.
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
      include_experimental (bool): if true, search results will include
        experimental builds. Otherwise, experimental builds will be excluded.
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
    self.include_experimental = include_experimental

  def copy(self):
    return Query(**self.__dict__)

  def __eq__(self, other):  # pragma: no cover
    # "pragma: no cover" because this code is executed
    # by mock module, not service_test
    # pylint: disable=unidiomatic-typecheck
    return type(self) == type(other) and self.__dict__ == other.__dict__

  def __ne__(self, other):  # pragma: no cover
    # "pragma: no cover" because this code is executed
    # by mock module, not service_test
    return not self.__eq__(other)

  def __repr__(self):
    return repr(self.__dict__)

  @property
  def status_is_v2(self):
    return isinstance(self.status, int)


def search(q):
  """Searches for builds.

  Args:
    q (Query): the query.

  Returns:
    A tuple:
      builds (list of Build): query result.
      next_cursor (string): cursor for the next page.
        None if there are no more builds.
  """
  assert isinstance(q.status, (type(None), StatusFilter, int)), q.status
  if q.buckets is not None and not isinstance(q.buckets, list):
    raise errors.InvalidInputError('Buckets must be a list or None')
  buildtags.validate_tags(q.tags, 'search')

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
  q.created_by = user.parse_identity(q.created_by)
  q.status = q.status if q.status != common_pb2.STATUS_UNSPECIFIED else None

  if not q.buckets and q.retry_of is not None:
    retry_of_build = model.Build.get_by_id(q.retry_of)
    if retry_of_build:
      q.buckets = [retry_of_build.bucket]
  if q.buckets:
    check_acls(q.buckets)
    q.buckets = set(q.buckets)

  is_tag_index_cursor = (
      q.start_cursor and RE_TAG_INDEX_SEARCH_CURSOR.match(q.start_cursor)
  )
  can_use_tag_index = (
      indexed_tags(q.tags) and (not q.start_cursor or is_tag_index_cursor)
  )
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
          (utils.utcnow() - search_start_time).total_seconds() * 1000
      )
      return results
    except errors.TagIndexIncomplete:
      if not can_use_query_search:
        raise
      logging.info('falling back to querying')

  # Searching using datastore query.
  assert can_use_query_search
  search_start_time = utils.utcnow()
  results = _query_search(q)
  logging.info(
      'query search took %dms',
      (utils.utcnow() - search_start_time).total_seconds() * 1000
  )
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
    q.buckets = user.get_acessible_buckets_async().get_result()
    if q.buckets is not None and len(q.buckets) == 0:
      return [], None
  # (buckets is None) means the requester has access to all buckets.
  assert q.buckets is None or q.buckets

  check_buckets_locally = q.retry_of is not None
  dq = model.Build.query()
  for t in q.tags:
    dq = dq.filter(model.Build.tags == t)
  filter_if = lambda p, v: dq if v is None else dq.filter(p == v)

  expected_statuses_v1 = None
  if q.status_is_v2:
    dq = dq.filter(model.Build.status_v2 == q.status)
  elif q.status == StatusFilter.INCOMPLETE:
    expected_statuses_v1 = (
        model.BuildStatus.SCHEDULED, model.BuildStatus.STARTED
    )
    dq = dq.filter(model.Build.incomplete == True)
  elif q.status is not None:
    s = model.BuildStatus.lookup_by_number(q.status.number)
    expected_statuses_v1 = (s,)
    dq = dq.filter(model.Build.status == s)

  dq = filter_if(model.Build.result, q.result)
  dq = filter_if(model.Build.failure_reason, q.failure_reason)
  dq = filter_if(model.Build.cancelation_reason, q.cancelation_reason)
  dq = filter_if(model.Build.created_by, q.created_by)
  dq = filter_if(model.Build.retry_of, q.retry_of)
  dq = filter_if(model.Build.canary, q.canary)
  if not q.include_experimental:
    dq = dq.filter(model.Build.experimental == False)

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
    if q.status_is_v2:
      if build.status_v2 != q.status:  # pragma: no cover
        return False
    elif expected_statuses_v1 and build.status not in expected_statuses_v1:
      return False  # pragma: no cover
    if q.buckets and build.bucket not in q.buckets:
      return False
    if not _between(build.create_time, q.create_time_low, q.create_time_high):
      return False  # pragma: no cover
    return True

  return fetch_page(dq, q.max_builds, q.start_cursor, predicate=local_predicate)


def _tag_index_search(q):
  """Searches for builds using TagIndex entities. For args doc, see search().

  Assumes:
  - arguments are valid
  - if bool(buckets), permissions are checked.

  Raises:
    errors.TagIndexIncomplete if the tag index is complete and cannot be used.
  """
  assert q.tags
  assert not q.buckets or isinstance(q.buckets, set)

  # Choose a tag to search by.
  all_indexed_tags = indexed_tags(q.tags)
  assert all_indexed_tags
  indexed_tag = all_indexed_tags[0]  # choose the most selective tag.
  indexed_tag_key = buildtags.parse(indexed_tag)[0]

  # Exclude the indexed tag from the tag filter.
  q = q.copy()
  q.tags = q.tags[:]
  q.tags.remove(indexed_tag)

  # Determine build id range we are considering.
  # id_low is inclusive, id_high is exclusive.
  id_low, id_high = model.build_id_range(q.create_time_low, q.create_time_high)
  id_low = 0 if id_low is None else id_low
  id_high = (1 << 64) - 1 if id_high is None else id_high
  if q.start_cursor:
    # The cursor is a minimum build id, exclusive. Such cursor is resilient
    # to duplicates and additions of index entries to beginning or end.
    assert RE_TAG_INDEX_SEARCH_CURSOR.match(q.start_cursor)
    min_id_exclusive = int(q.start_cursor[len('id>'):])
    id_low = max(id_low, min_id_exclusive + 1)
  if id_low >= id_high:
    return [], None

  # Load index entries and put them to a min-heap, sorted by build_id.
  entry_heap = []  # tuples (build_id, TagIndexEntry).
  for idx in ndb.get_multi(TagIndex.all_shard_keys(indexed_tag)):
    if not idx:
      continue
    if idx.permanently_incomplete:
      raise errors.TagIndexIncomplete(
          'TagIndex(%s) is incomplete' % idx.key.id()
      )
    for e in idx.entries:
      if id_low <= e.build_id < id_high:
        entry_heap.append((e.build_id, e))
  if not entry_heap:
    return [], None
  heapq.heapify(entry_heap)

  # If buckets were not specified explicitly, permissions were not checked
  # earlier. In this case, check permissions for each build.
  check_permissions = not q.buckets
  has_access_cache = {}

  def has_access(bucket):
    has = has_access_cache.get(bucket)
    if has is None:
      has = user.can_search_builds(bucket)
      has_access_cache[bucket] = has
    return has

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
  if q.status_is_v2:
    scalar_filters.append(('status_v2', q.status))
  elif q.status == StatusFilter.INCOMPLETE:
    scalar_filters.append(('incomplete', True))
  elif q.status is not None:
    scalar_filters.append(
        ('status', model.BuildStatus.lookup_by_number(q.status.number))
    )

  # Find the builds.
  result = []  # ordered by build id by ascending.
  last_considered_entry = None
  skipped_entries = 0
  inconsistent_entries = 0
  eof = False
  while len(result) < q.max_builds:
    fetch_count = q.max_builds - len(result)
    entries_to_fetch = []  # ordered by build id by ascending.
    while entry_heap:
      _, e = heapq.heappop(entry_heap)
      prev = last_considered_entry
      last_considered_entry = e
      if prev and prev.build_id == e.build_id:
        # Tolerate duplicates.
        continue
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
      if not (b and b.bucket == e.bucket and indexed_tag in b.tags):
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
      if b.experimental and not q.include_experimental:
        continue
      result.append(b)

  metrics.TAG_INDEX_SEARCH_SKIPPED_BUILDS.add(
      skipped_entries, fields={'tag': indexed_tag_key}
  )
  metrics.TAG_INDEX_INCONSISTENT_ENTRIES.add(
      inconsistent_entries, fields={'tag': indexed_tag_key}
  )

  # Return the results.
  next_cursor = None
  if not eof and last_considered_entry:
    next_cursor = 'id>%d' % last_considered_entry.build_id
  return result, next_cursor


def indexed_tags(tags):
  """Returns a list of tags that must be indexed.

  The order of returned tags is from more selective to less selective.
  """
  if not tags:
    return []
  return sorted(
      set(t for t in tags if t.startswith(('buildset:', 'build_address:')))
  )


def update_tag_indexes_async(builds):
  """Updates tag indexes for the builds.

  For each new build, for each indexed tag, add an entry to a tag index.
  """
  index_entries = {}
  for b in builds:
    for t in set(indexed_tags(b.tags)):
      index_entries.setdefault(t, []).append(
          TagIndexEntry(build_id=b.key.id(), bucket=b.bucket)
      )
  return [
      add_to_tag_index_async(tag, entries)
      for tag, entries in index_entries.iteritems()
  ]


def add_to_tag_index_async(tag, new_entries):
  """Adds index entries to the tag index.

  new_entries must be a list of TagIndexEntry and not have duplicate builds ids.
  """
  if not new_entries:  # pragma: no cover
    return
  build_ids = {e.build_id for e in new_entries}
  assert len(build_ids) == len(new_entries), new_entries

  @ndb.transactional_tasklet
  def txn_async():
    idx_key = TagIndex.random_shard_key(tag)
    idx = (yield idx_key.get_async()) or TagIndex(key=idx_key)
    if idx.permanently_incomplete:
      return

    # Avoid going beyond 1Mb entity size limit by limiting the number of entries
    new_size = len(idx.entries) + len(new_entries)
    if new_size > TagIndex.MAX_ENTRY_COUNT:
      idx.permanently_incomplete = True
      idx.entries = []
    else:
      logging.debug(
          'adding %d entries to TagIndex(%s)', len(new_entries), idx_key.id()
      )
      idx.entries.extend(new_entries)
    yield idx.put_async()

  return txn_async()


class TagIndexEntry(ndb.Model):
  """A single entry in a TagIndex, references a build."""
  created_time = ndb.DateTimeProperty(auto_now_add=True)
  # ID of the build.
  build_id = ndb.IntegerProperty(indexed=False)
  # Bucket of the build.
  bucket = ndb.StringProperty(indexed=False)


class TagIndex(ndb.Model):
  """A custom index of builds by a tag.

  Entity key:
    Entity id has format "<tag_key>:<tag_value>" or
    ":<shard_index>:<tag_key>:<tag_value>" for positive values of shard_index.
    TagIndex has no parent.
  """

  MAX_ENTRY_COUNT = 1000
  SHARD_COUNT = 16  # This value MUST NOT decrease.

  # if incomplete, this TagIndex should not be used in search.
  # It is set to True if there are more than MAX_ENTRY_COUNT builds
  # for this tag.
  permanently_incomplete = ndb.BooleanProperty()

  # entries is a superset of all builds that have the tag equal to the id of
  # this entity. It may contain references to non-existent builds or builds that
  # do not actually have this tag; such builds must be ignored.
  entries = ndb.LocalStructuredProperty(
      TagIndexEntry, repeated=True, indexed=False
  )

  @classmethod
  def make_key(cls, shard_index, tag):
    """Returns a TagIndex entity key."""
    assert shard_index >= 0
    assert not tag.startswith(':')
    iid = tag if shard_index == 0 else ':%d:%s' % (shard_index, tag)
    return ndb.Key(TagIndex, iid)

  @classmethod
  def all_shard_keys(cls, tag):  # pragma: no cover
    return [cls.make_key(i, tag) for i in xrange(cls.SHARD_COUNT)]

  @classmethod
  def random_shard_key(cls, tag):
    """Returns a TagIndex entity key of a random shard."""
    return cls.make_key(cls.random_shard_index(), tag)

  @classmethod
  def random_shard_index(cls):  # pragma: no cover
    return random.randint(0, cls.SHARD_COUNT - 1)
