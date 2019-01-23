# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Build bulk processing of builds, a miniature map-reduce."""

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

import model

QUEUE_NAME = 'bulkproc'
PATH_PREFIX = '/internal/task/bulkproc/'
_MAX_BUILD_ID = 2L**63 - 1

# See register().
PROCESSOR_REGISTRY = {}

# Chunk all builds into segments each worth of 6h
SEGMENT_SIZE = model.ONE_MS_BUILD_ID_RANGE * 1000 * 60 * 60 * 6


def register(name, processor, entity_kind='Build', keys_only=False):
  """Registers a processor.

  Args:
    name: identifies the processor.
    entity_kind: kind of the entity to process, a string. Must be "Build"
      or its descendant.
    processor: functiton (results, payload),
      where results is an iterable of entities or their keys
      and payload is the payload specified in start().
      Entities not read from the iterable will be rescheduled for processing in
      a separate job.
      processor is eventually executed on all entities of the kind that exist in
      the datastore.
    keys_only: whether the results passed to processor are only a ndb key, not
      entire entity.
  """

  assert name not in PROCESSOR_REGISTRY
  PROCESSOR_REGISTRY[name] = {
      'func': processor,
      'entity_kind': entity_kind,
      'keys_only': keys_only,
  }


def start(name, payload=None):  # pragma: no cover
  """Starts a processor by name. See register docstring for params.

  It should be called by a module that calls register().
  """
  assert name in PROCESSOR_REGISTRY
  task = (
      None,
      PATH_PREFIX + 'start',
      utils.encode_to_json({
          'proc': {
              'name': name,
              'payload': payload,
          },
      }),
  )
  enqueue_tasks(QUEUE_NAME, [task])


def _get_proc(name):  # pragma: no cover
  return PROCESSOR_REGISTRY[name]


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

  Payload properties:
    proc: processor to run, see TaskSegment docstring.
  """

  def do(self, payload):
    proc = payload['proc']

    now = utils.utcnow()
    space_start, space_end = model.build_id_range(
        now - model.BUILD_STORAGE_DURATION,
        now + datetime.timedelta(days=1),
    )
    assert space_end <= _MAX_BUILD_ID
    space_size = space_end - space_start + 1

    logging.info(
        'build space [%d..%d], size %d, %d shards',
        space_start,
        space_end,
        space_size,
        int(math.ceil(float(space_size) / SEGMENT_SIZE)),
    )

    next_seg_start = space_start
    tasks = []
    while next_seg_start <= space_end:
      seg_start = next_seg_start
      seg_end = min(_MAX_BUILD_ID, seg_start + SEGMENT_SIZE - 1)
      next_seg_start = seg_end + 1
      tasks.append((
          None,
          'segment/seg:{seg_index}-percent:0',
          {
              'job_id': self.request.headers['X-AppEngine-TaskName'],
              'iteration': 0,
              'seg_index': len(tasks),
              'seg_start': seg_start,
              'seg_end': seg_end,
              'started_ts': utils.datetime_to_timestamp(utils.utcnow()),
              'proc': proc,
          },
      ))
    self._recurse(tasks)
    logging.info('enqueued %d segment tasks with proc %r', len(tasks), proc)


class TaskSegment(TaskBase):
  """Processes a chunk of entities in a segment.

  If didn't finish processing entire segment, enqueues itself with a
  new query cursor.

  Payload properties:
    job_id: id of this backfill job. Required.
    iteration: segment task iteration. Required.
    seg_index: index of this shard. Required.
    seg_start: id of the first build in this segment. Required.
    seg_end: id of the last build in this segment. Required.
    start_from: start from this build towards seg_end. Defaults to seg_start.
    started_ts: timestamp when we started to process this segment.
    proc: processor to run on the segment. A JSON object with two properties:
      name: name of the processor, see register()
      payload: processor payload, see register() and start().
  """

  # Maximum number of entities to process in a single iteration.
  # Value 1000 is derived from experimentation on the dev server.
  # It prevents "Exceeded soft private memory limit" and "RequestTooLargeError"
  # errors.
  ENTITY_LIMIT = 1000

  def do(self, payload):
    attempt = int(self.request.headers.get('X-AppEngine-TaskExecutionCount', 0))
    seg_start = payload['seg_start']
    # Check _MAX_BUILD_ID again in case the task was already scheduled.
    seg_end = min(_MAX_BUILD_ID, payload['seg_end'])
    start_from = payload.get('start_from', seg_start)
    proc = payload['proc']
    proc_def = _get_proc(proc['name'])

    logging.info('range %d-%d', seg_start, seg_end)
    logging.info('starting from %s', start_from)

    if attempt > 0:
      logging.warning('attempt %d', attempt)

    q = ndb.Query(
        kind=proc_def['entity_kind'],
        filters=ndb.ConjunctionNode(
            ndb.FilterNode('__key__', '>=', ndb.Key(model.Build, start_from)),
            ndb.FilterNode('__key__', '<=', ndb.Key(model.Build, seg_end)),
        ),
    )
    iterator = q.iter(keys_only=proc_def['keys_only'])

    entity_count = [0]

    def iterate_segment():
      # Datastore query timeout is 60 sec. Limit it to 50 sec.
      deadline = utils.utcnow() + datetime.timedelta(seconds=50)
      while (utils.utcnow() < deadline and
             entity_count[0] < self.ENTITY_LIMIT and iterator.has_next()):
        yield iterator.next()
        entity_count[0] += 1

    proc_def['func'](iterate_segment(), proc['payload'])
    logging.info('processed %d entities', entity_count[0])

    if iterator.has_next():
      logging.info('enqueuing a task for the next iteration...')

      build_key = (
          iterator.next() if proc_def['keys_only'] else iterator.next().key
      )
      while build_key.parent() is not None:
        build_key = build_key.parent()

      p = payload.copy()
      p['iteration'] += 1
      p['start_from'] = build_key.id()

      seg_len = seg_end - seg_start + 1
      percent = 100 * (p['start_from'] - seg_start) / seg_len

      try:
        self._recurse([(
            '{job_id}-{seg_index}-{iteration}',
            'segment/seg:{seg_index}-percent:%d' % percent,
            p,
        )])
      except (taskqueue.TaskAlreadyExistsError,
              taskqueue.TombstonedTaskError):  # pragma: no cover
        pass
      return

    started_time = utils.timestamp_to_datetime(payload['started_ts'])
    logging.info(
        'segment %d is done in %s',
        payload['seg_index'],
        utils.utcnow() - started_time,
    )


# mocked in tests.
def enqueue_tasks(queue_name, tasks):  # pragma: no cover
  """Adds tasks to the queue.

  tasks must be a list of tuples (name, url, payload).
  """
  if tasks:
    taskqueue.Queue(queue_name).add([
        taskqueue.Task(name=name, url=url, payload=payload)
        for name, url, payload in tasks
    ])


def get_routes():  # pragma: no cover
  """Returns webapp2 routes provided by this module."""
  return [
      webapp2.Route(PATH_PREFIX + r'start', TaskStart),
      webapp2.Route(PATH_PREFIX + r'segment/<rest>', TaskSegment),
  ]
