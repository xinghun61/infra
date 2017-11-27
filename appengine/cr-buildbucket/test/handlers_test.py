# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import datetime
import mock

from google.appengine.ext import ndb

from components import utils

from test.test_util import future_exception
from testing_utils import testing
import handlers
import main
import model


class HandlerTest(testing.AppengineTestCase):
  @property
  def app_module(self):
    return main.create_backend_app()


class BuildBucketBackendHandlersTest(HandlerTest):
  @mock.patch('service.reset_expired_builds', autospec=True)
  def test_reset_expired_builds(self, reset_expired_builds):
    path = '/internal/cron/buildbucket/reset_expired_builds'
    response = self.test_app.get(path, headers={'X-AppEngine-Cron': 'true'})
    self.assertEquals(200, response.status_int)
    reset_expired_builds.assert_called_once_with()


class TaskBackfillTagIndexTest(HandlerTest):
  task_url = '/internal/task/buildbucket/backfill-tag-index/'

  def setUp(self):
    super(TaskBackfillTagIndexTest, self).setUp()
    self.now = datetime.datetime(2017, 1, 1)
    self.patch('components.utils.utcnow', side_effect=lambda: self.now)

  def post(self, payload, headers=None):
    headers = headers or {}
    headers['X-AppEngine-QueueName'] = 'backfill-tag-index'
    headers['X-AppEngine-TaskName'] = 'taskname'
    return self.test_app.post(
        self.task_url + 'rest',
        utils.encode_to_json(payload),
        headers=headers)

  @mock.patch('handlers.enqueue_tasks')
  def test_start(self, enqueue_tasks):
    ndb.put_multi([
      model.Build(
          id=i,
          bucket='chromium',
          create_time=self.now - datetime.timedelta(minutes=i))
      for i in xrange(1, 11)
    ])
    self.post({
      'action': 'start',
      'tag': 'buildset',
      'shards': 3,
    })

    enqueue_tasks.assert_called_with('backfill-tag-index', [
      (
        None,
        self.task_url + 'tag:buildset-seg:0-percent:0',
        utils.encode_to_json({
          'action': 'segment',
          'tag': 'buildset',
          'job_id': 'taskname',
          'iteration': 0,
          'seg_index': 0,
          'seg_start': 1,
          'seg_end': 4,
          'started_ts': utils.datetime_to_timestamp(self.now),
        }),
      ),
      (
        None,
        self.task_url + 'tag:buildset-seg:1-percent:0',
        utils.encode_to_json({
          'action': 'segment',
          'tag': 'buildset',
          'job_id': 'taskname',
          'iteration': 0,
          'seg_index': 1,
          'seg_start': 4,
          'seg_end': 7,
          'started_ts': utils.datetime_to_timestamp(self.now),
        }),
      ),
      (
        None,
        self.task_url + 'tag:buildset-seg:2-percent:0',
        utils.encode_to_json({
          'action': 'segment',
          'tag': 'buildset',
          'job_id': 'taskname',
          'iteration': 0,
          'seg_index': 2,
          'seg_start': 7,
          'seg_end': 10,
          'started_ts': utils.datetime_to_timestamp(self.now),
        }),
      ),
      (
        None,
        self.task_url + 'tag:buildset-seg:3-percent:0',
        utils.encode_to_json({
          'action': 'segment',
          'tag': 'buildset',
          'job_id': 'taskname',
          'iteration': 0,
          'seg_index': 3,
          'seg_start': 10,
          'seg_end': 11,
          'started_ts': utils.datetime_to_timestamp(self.now),
        }),
      ),
    ])

  @mock.patch('handlers.enqueue_tasks')
  def test_start_many_shards(self, enqueue_tasks):
    ndb.put_multi([
      model.Build(
          id=i,
          bucket='chromium',
          create_time=self.now - datetime.timedelta(minutes=i))
      for i in xrange(1, 150)
    ])
    self.post({
      'action': 'start',
      'tag': 'buildset',
      'shards': 100,
    })

    self.assertEqual(enqueue_tasks.call_count, 2)

  @contextlib.contextmanager
  def entry_limit(self, limit):
    orig_entry_limit = handlers.TaskBackfillTagIndex.ENTRY_LIMIT
    handlers.TaskBackfillTagIndex.ENTRY_LIMIT = limit
    try:
      yield
    finally:
      handlers.TaskBackfillTagIndex.ENTRY_LIMIT = orig_entry_limit

  @mock.patch('handlers.enqueue_tasks')
  def test_segment_partial(self, enqueue_tasks):
    ndb.put_multi([
      model.Build(
          id=i,
          bucket='chromium',
          tags=[
            'buildset:%d' % (i % 3),
            'a:b',
          ])
      for i in xrange(50, 60)
    ])

    with self.entry_limit(5):
      self.post({
        'action': 'segment',
        'tag': 'buildset',
        'job_id': 'jobid',
        'iteration': 0,
        'seg_index': 0,
        'seg_start': 50,
        'seg_end': 60,
        'started_ts': utils.datetime_to_timestamp(self.now),
      })

    enqueue_tasks.assert_any_call('backfill-tag-index', [(
      None,
      self.task_url + 'tag:buildset-flush',
      utils.encode_to_json({
        'action': 'flush',
        'tag': 'buildset',
        'new_entries': {
          '0': [
            ['chromium', 51],
            ['chromium', 54],
          ],
          '1': [
            ['chromium', 52],
          ],
          '2': [
            ['chromium', 50],
            ['chromium', 53],
          ],
        },
      }),
    )])

    expected_next_payload = {
      'action': 'segment',
      'tag': 'buildset',
      'job_id': 'jobid',
      'iteration': 1,
      'seg_index': 0,
      'seg_start': 50,
      'seg_end': 60,
      'start_from': 55,
      'started_ts': utils.datetime_to_timestamp(self.now),
    }
    enqueue_tasks.assert_any_call('backfill-tag-index', [(
      'jobid-0-1',
      self.task_url + 'tag:buildset-seg:0-percent:50',
      utils.encode_to_json(expected_next_payload)
    )])

    self.post(expected_next_payload)

  @mock.patch('handlers.enqueue_tasks')
  def test_segment_full(self, enqueue_tasks):
    ndb.put_multi([
      model.Build(id=i, bucket='chromium', tags=['buildset:%d' % (i % 3)])
      for i in xrange(50, 52)
    ])
    self.post({
      'action': 'segment',
      'tag': 'buildset',
      'seg_index': 0,
      'seg_start': 50,
      'seg_end': 60,
      'started_ts': utils.datetime_to_timestamp(self.now),
    })

    self.assertEqual(enqueue_tasks.call_count, 1)
    enqueue_tasks.assert_called_with('backfill-tag-index', [(
      None,
      self.task_url + 'tag:buildset-flush',
      utils.encode_to_json({
        'action': 'flush',
        'tag': 'buildset',
        'new_entries': {
          '0': [['chromium', 51]],
          '2': [['chromium', 50]],
        },
      }),
    )])

  @mock.patch('handlers.enqueue_tasks')
  def test_segment_attempt_2(self, enqueue_tasks):
    ndb.put_multi([
      model.Build(id=i, bucket='chromium', tags=['buildset:%d' % (i % 3)])
      for i in xrange(50, 60)
    ])

    with self.entry_limit(1):
      headers = {
        'X-AppEngine-TaskExecutionCount': '1',
      }
      self.post({
        'action': 'segment',
        'tag': 'buildset',
        'job_id': 'jobid',
        'iteration': 0,
        'seg_index': 0,
        'seg_start': 50,
        'seg_end': 60,
        'started_ts': utils.datetime_to_timestamp(self.now),
      }, headers=headers)

    enqueue_tasks.assert_any_call('backfill-tag-index', [(
      'jobid-0-1',
      self.task_url + 'tag:buildset-seg:0-percent:10',
      utils.encode_to_json({
        'action': 'segment',
        'tag': 'buildset',
        'job_id': 'jobid',
        'iteration': 1,
        'seg_index': 0,
        'seg_start': 50,
        'seg_end': 60,
        'start_from': 51,
        'started_ts': utils.datetime_to_timestamp(self.now),
      }),
    )])

  def test_flush(self):
    model.TagIndex(id='buildset:0', entries=[
      model.TagIndexEntry(bucket='chormium', build_id=51),
    ]).put()
    model.TagIndex(id='buildset:2', entries=[
      model.TagIndexEntry(bucket='chormium', build_id=1),
      model.TagIndexEntry(bucket='chormium', build_id=100),
    ]).put()
    self.post({
      'action': 'flush',
      'tag': 'buildset',
      'new_entries': {
        '0': [['chromium', 51]],
        '1': [['chromium', 52]],
        '2': [['chromium', 50]],
      },
    })

    idx0 = model.TagIndex.get_by_id('buildset:0')
    self.assertIsNotNone(idx0)
    self.assertEqual(len(idx0.entries), 1)
    self.assertEqual(idx0.entries[0].build_id, 51)

    idx1 = model.TagIndex.get_by_id('buildset:1')
    self.assertIsNotNone(idx1)
    self.assertEqual(len(idx1.entries), 1)
    self.assertEqual(idx1.entries[0].build_id, 52)

    idx2 = model.TagIndex.get_by_id('buildset:2')
    self.assertIsNotNone(idx2)
    self.assertEqual(len(idx2.entries), 3)
    self.assertEqual(idx2.entries[0].build_id, 100)
    self.assertEqual(idx2.entries[1].build_id, 50)
    self.assertEqual(idx2.entries[2].build_id, 1)

  @mock.patch('handlers.enqueue_tasks')
  def test_flush_retry(self, enqueue_tasks):
    orig_add = handlers.TaskBackfillTagIndex._add_index_entries_async

    def add(tag, entries):
      if tag == 'buildset:1':
        return future_exception(Exception('transient error'))
      return orig_add(tag, entries)

    with mock.patch(
        'handlers.TaskBackfillTagIndex._add_index_entries_async',
        side_effect=add):
      self.post({
        'action': 'flush',
        'tag': 'buildset',
        'new_entries': {
          '0': [['chromium', 51]],
          '1': [['chromium', 52]],
          '2': [['chromium', 50]],
        },
      })

    idx0 = model.TagIndex.get_by_id('buildset:0')
    self.assertIsNotNone(idx0)
    self.assertEqual(len(idx0.entries), 1)
    self.assertEqual(idx0.entries[0].build_id, 51)

    idx2 = model.TagIndex.get_by_id('buildset:2')
    self.assertIsNotNone(idx2)
    self.assertEqual(len(idx2.entries), 1)
    self.assertEqual(idx2.entries[0].build_id, 50)

    enqueue_tasks.assert_called_with('backfill-tag-index', [(
      None,
      self.task_url + 'tag:buildset-flush',
      utils.encode_to_json({
        'action': 'flush',
        'tag': 'buildset',
        'new_entries': {
          '1': [['chromium', 52]],
        },
      }),
    )])

  def test_flush_too_many(self):
    self.post({
      'action': 'flush',
      'tag': 'buildset',
      'new_entries': {
        '0': [['chromium', i] for i in xrange(1, 2001)],
      },
    })

    idx0 = model.TagIndex.get_by_id('buildset:0')
    self.assertIsNotNone(idx0)
    self.assertTrue(idx0.permanently_incomplete)
    self.assertEqual(len(idx0.entries), 0)

    # Again, for code coverage.
    self.post({
      'action': 'flush',
      'tag': 'buildset',
      'new_entries': {
        '0': [['chromium', 1]],
      },
    })
