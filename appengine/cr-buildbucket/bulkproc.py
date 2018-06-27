# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Bulk processing of Build entities."""

import collections
import datetime
import json
import logging
import math
import posixpath

from google.appengine.api import taskqueue
from google.appengine.ext import ndb
import webapp2

from components import utils

import webapp2

from v2 import api as v2_api
import config
import model
import search

PATH_PREFIX = '/internal/task/backfill-tag-index/'


class TaskBase(webapp2.RequestHandler):

  def _recurse(self, jobs):
    queue_name = self.request.headers['X-AppEngine-QueueName']
    tasks = []
    for name_fmt, path_suffix_fmt, payload in jobs:
      name = name_fmt and name_fmt.format(**payload)
      path_suffix = path_suffix_fmt.format(**payload)
      tasks.append((
          name,
          posixpath.join(PATH_PREFIX, path_suffix),
          utils.encode_to_json(payload),
      ))
      if len(tasks) > 90:
        # enqueue_tasks accepts up to 100
        enqueue_tasks(queue_name, tasks)
        tasks = []
    if tasks:  # pragma: no branch
      enqueue_tasks(queue_name, tasks)

  def post(self, **_rest):
    if 'X-AppEngine-QueueName' not in self.request.headers:  # pragma: no cover
      self.abort(403)
    self.do(json.loads(self.request.body))

  def do(self, payload):
    raise NotImplementedError()


class TaskStart(TaskBase):
  """Splits build space into segments and enqueues TaskSegment for each.

  Assumes that build creation rate was about the same forever.

  Payload properties:
    tag: tag to reindex. Required.
    shards: number of workers to create. Must be positive. Required.
  """

  def do(self, payload):
    tag = payload['tag']
    shards = payload['shards']
    assert isinstance(tag, basestring), tag
    assert tag
    assert isinstance(shards, int)
    assert shards > 0

    first, = model.Build.query().fetch(1, keys_only=True) or [None]
    if not first:  # pragma: no cover
      logging.warning('no builds to backfill')
      return
    # Do not require -key index by using created_time index.
    last, = (
        model.Build.query().order(model.Build.create_time
                                 ).fetch(1, keys_only=True)
    )
    space_start, space_end = first.id(), last.id() + 1
    space_size = space_end - space_start
    seg_size = max(1, int(math.ceil(space_size / shards)))

    logging.info(
        'build space [%d..%d), size %d, %d shards, segment size %d',
        space_start, space_end, space_size, shards, seg_size
    )

    next_seg_start = space_start
    tasks = []
    while next_seg_start < space_end:
      seg_start = next_seg_start
      seg_end = min(space_end, seg_start + seg_size)
      next_seg_start = seg_end
      tasks.append((
          None,
          'segment/seg:{seg_index}-percent:0',
          {
              'tag': tag,
              'job_id': self.request.headers['X-AppEngine-TaskName'],
              'iteration': 0,
              'seg_index': len(tasks),
              'seg_start': seg_start,
              'seg_end': seg_end,
              'started_ts': utils.datetime_to_timestamp(utils.utcnow()),
          },
      ))
    self._recurse(tasks)
    logging.info('enqueued %d segment tasks for tag %s', len(tasks), tag)


class TaskSegment(TaskBase):
  """Processes a chunk of builds in a segment.

  When finished, enqueues a flush task to persist new tag index entries.
  If there are more builds in the segment to process, enqueues itself with a
  new query cursor.

  Payload properties:
    tag: tag to reindex. Required.
    job_id: id of this backfill job. Required.
    iteration: segment task iteration. Required.
    seg_index: index of this shard. Required.
    seg_start: id of the first build in this segment. Required.
    seg_end: id of the first build in the next segment. Required.
    start_from: start from this build towards seg_end. Defaults to seg_start.
    started_ts: timestamp when we started to process this segment.
  """

  # Maximum number of entries to collect in a single iteration.
  # This helps avoiding hitting the limit of task size and caps the number of
  # transactions we need to do in a flush task.
  ENTRY_LIMIT = 500
  # Maximum number of builds to process in a single iteration.
  # Value 3000 is derived from experimentation on the dev server.
  # It prevents "Exceeded soft private memory limit" error.
  BUILD_LIMIT = 3000

  def do(self, payload):
    attempt = int(self.request.headers.get('X-AppEngine-TaskExecutionCount', 0))

    seg_start = payload['seg_start']
    seg_end = payload['seg_end']
    start_from = payload.get('start_from', seg_start)

    logging.info('range %d-%d', seg_start, seg_end)
    logging.info('starting from %s', start_from)

    if attempt > 0:
      logging.warning('attempt %d', attempt)

    q = model.Build.query(
        model.Build.key >= ndb.Key(model.Build, start_from),
        model.Build.key < ndb.Key(model.Build, seg_end)
    )
    iterator = q.iter()

    entry_count = 0
    build_count = 0
    new_entries = collections.defaultdict(list)

    # Datastore query timeout is 60 sec. Limit it to 50 sec.
    deadline = utils.utcnow() + datetime.timedelta(seconds=50)
    while (utils.utcnow() < deadline and entry_count < self.ENTRY_LIMIT and
           build_count < self.BUILD_LIMIT and iterator.has_next()):
      b = iterator.next()
      build_count += 1
      for t in b.tags:
        k, v = t.split(':', 1)
        if k == payload['tag']:
          new_entries[v].append([b.bucket, b.key.id()])
          entry_count += 1
    logging.info(
        'collected %d entries from %d builds', entry_count, build_count
    )

    if new_entries:  # pragma: no branch
      logging.info(
          'enqueuing a task to flush %d tag entries in %d TagIndex entities...',
          entry_count, len(new_entries)
      )
      flush_payload = {
          'tag': payload['tag'],
          'new_entries': new_entries,
      }
      self._recurse([(None, 'flush', flush_payload)])
    if iterator.has_next():
      logging.info('enqueuing a task for the next iteration...')

      p = payload.copy()
      p['iteration'] += 1
      p['start_from'] = iterator.next().key.id()

      seg_len = seg_end - seg_start
      percent = 100 * (p['start_from'] - seg_start) / seg_len

      try:
        self._recurse([(
            '{job_id}-{seg_index}-{iteration}',
            'segment/seg:{seg_index}-percent:%d' % percent,
            p,
        )])
      except taskqueue.TaskAlreadyExistsError:  # pragma: no cover
        pass
      return

    started_time = utils.timestamp_to_datetime(payload['started_ts'])
    logging.info(
        'segment %d is done in %s',
        payload['seg_index'],
        utils.utcnow() - started_time,
    )


class TaskFlushTagIndexEntries(TaskBase):
  """Saves new tag index entries.

  Payload properties:
    tag: tag to reindex. Required.
    new_entries: a dict {tag_value: [[bucket, id}]]} of new index entries to
      add. Required.
  """

  def do(self, payload):
    new_entries = payload['new_entries']
    logging.info(
        'flushing %d tag entries in %d TagIndex entities',
        sum(len(es) for es in new_entries.itervalues()), len(new_entries)
    )

    futs = [
        self._add_index_entries_async(
            payload['tag'] + ':' + tag_value, entries
        ) for tag_value, entries in new_entries.iteritems()
    ]
    ndb.Future.wait_all(futs)

    retry_entries = {}
    updated = 0
    for (tag, entries), f in zip(new_entries.iteritems(), futs):
      ex = f.get_exception()
      if ex:
        logging.warning('failed to update TagIndex for %r: %s', tag, ex)
        retry_entries[tag] = entries
      elif f.get_result():
        updated += 1
    logging.info('updated %d TagIndex entities', updated)
    if retry_entries:
      logging.warning(
          'failed to update %d TagIndex entities, retrying...',
          len(retry_entries)
      )
      p = payload.copy()
      p['new_entries'] = retry_entries
      self._recurse([(None, 'flush', p)])

  @staticmethod
  @ndb.transactional_tasklet
  def _add_index_entries_async(tag, entries):
    idx_key = search.TagIndex.random_shard_key(tag)
    idx = (yield idx_key.get_async()) or search.TagIndex(key=idx_key)
    if idx.permanently_incomplete:
      # no point in adding entries to an incomplete index.
      raise ndb.Return(False)
    existing = {e.build_id for e in idx.entries}
    added = False
    for bucket, build_id in entries:
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
            search.TagIndexEntry(bucket=bucket, build_id=build_id)
        )
        added = True
    if not added:
      raise ndb.Return(False)
    yield idx.put_async()
    raise ndb.Return(True)


# mocked in tests.
def enqueue_tasks(queue_name, tasks):  # pragma: no cover
  """Adds tasks to the queue.

  tasks must be a list of tuples (name, url, payload).
  """
  taskqueue.Queue(queue_name).add([
      taskqueue.Task(name=name, url=url, payload=payload)
      for name, url, payload in tasks
  ])


def get_routes():  # pragma: no cover
  """Returns webapp2 routes provided by this module."""
  return [
      webapp2.Route(PATH_PREFIX + r'start', TaskStart),
      webapp2.Route(PATH_PREFIX + r'segment/<rest>', TaskSegment),
      webapp2.Route(PATH_PREFIX + r'flush', TaskFlushTagIndexEntries),
  ]
