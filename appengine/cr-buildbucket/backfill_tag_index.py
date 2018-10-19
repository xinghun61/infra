# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tag index backfilling."""

import collections
import logging

from google.appengine.ext import deferred
from google.appengine.ext import ndb

import buildtags
import bulkproc
import search

# Maximum number of entries to collect in a single iteration. This helps
# avoiding hitting the limit of task size and caps the number of transactions we
# need to do in a flush task.
ENTRY_LIMIT = 1000

PROC_NAME = 'backfill_tag_index'

bulkproc.register(
    PROC_NAME,
    lambda builds, payload: _process_builds(
        builds, payload['tag_key'], ENTRY_LIMIT)
)


def launch(tag_key):  # pragma: no cover
  assert tag_key
  assert ':' not in tag_key
  assert isinstance(tag_key, basestring)
  bulkproc.start(PROC_NAME, {'tag_key': tag_key})


def _process_builds(builds, tag_key, entry_limit):
  entry_count = 0
  new_entries = collections.defaultdict(list)

  for b in builds:  # pragma: no branch
    for t in b.tags:
      k, v = buildtags.parse(t)
      if k == tag_key:
        new_entries[v].append([b.bucket_id, b.key.id()])
        entry_count += 1
        if entry_count >= entry_limit:
          break
    if entry_count >= entry_limit:
      break

  logging.info('collected %d entries', entry_count)
  _enqueue_flush_entries(tag_key, new_entries)


def _enqueue_flush_entries(tag_key, new_entries):  # pragma: no cover
  if new_entries:
    deferred.defer(
        _flush_entries,
        tag_key,
        new_entries,
        _queue=bulkproc.QUEUE_NAME,
    )


def _flush_entries(tag_key, new_entries):
  """Adds new entries to TagIndex entities.

  new_entries is {tag_value: [[bucket_id, build_id]]}.
  """
  logging.info(
      'flushing %d tag entries in %d TagIndex entities for tag key %s',
      sum(len(es) for es in new_entries.itervalues()),
      len(new_entries),
      tag_key,
  )

  new_entry_items = new_entries.items()
  futs = [
      _add_index_entries_async(buildtags.unparse(tag_key, tag_value), entries)
      for tag_value, entries in new_entry_items
  ]
  retry_entries = {}
  updated = 0
  for (tag_value, entries), f in zip(new_entry_items, futs):
    ex = f.get_exception()
    if ex:
      logging.warning('failed to update TagIndex for "%s" %s', tag_value, ex)
      retry_entries[tag_value] = entries
    elif f.get_result():
      updated += 1
  logging.info('updated %d TagIndex entities', updated)
  if retry_entries:
    logging.warning(
        'failed to update %d TagIndex entities, retrying...',
        len(retry_entries),
    )
    _enqueue_flush_entries(tag_key, retry_entries)


@ndb.transactional_tasklet
def _add_index_entries_async(tag, entries):
  """Adds TagIndexEntries to one TagIndex.

  entries is [[bucket_id, build_id]].

  Returns True if made changes.
  """
  idx_key = search.TagIndex.random_shard_key(tag)
  idx = (yield idx_key.get_async()) or search.TagIndex(key=idx_key)
  if idx.permanently_incomplete:
    # no point in adding entries to an incomplete index.
    raise ndb.Return(False)

  existing = {e.build_id for e in idx.entries}
  added = False
  for bucket_id, build_id in entries:
    if build_id not in existing:
      if len(idx.entries) >= search.TagIndex.MAX_ENTRY_COUNT:
        logging.warning((
            'refusing to store more than %d entries in TagIndex(%s); '
            'marking as incomplete.'
        ), search.TagIndex.MAX_ENTRY_COUNT, idx_key.id())
        idx.permanently_incomplete = True
        idx.entries = []
        yield idx.put_async()
        raise ndb.Return(True)

      idx.entries.append(
          search.TagIndexEntry(bucket_id=bucket_id, build_id=build_id)
      )
      added = True
  if not added:
    raise ndb.Return(False)
  yield idx.put_async()
  raise ndb.Return(True)
