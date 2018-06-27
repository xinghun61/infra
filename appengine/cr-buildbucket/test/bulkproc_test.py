# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import datetime
import itertools
import mock

from google.appengine.ext import ndb

from components import utils

from test.test_util import future_exception
from testing_utils import testing
import bulkproc
import main
import model
import search
import v2


class TestBase(testing.AppengineTestCase):
  path_suffix = ''

  @property
  def app_module(self):
    return main.create_backend_app()

  def setUp(self):
    super(TestBase, self).setUp()
    self.now = datetime.datetime(2017, 1, 1)
    self.patch('components.utils.utcnow', side_effect=lambda: self.now)

  def post(self, payload, headers=None):
    assert self.path_suffix
    headers = headers or {}
    headers['X-AppEngine-QueueName'] = bulkproc.QUEUE_NAME
    headers['X-AppEngine-TaskName'] = 'taskname'
    task_url = bulkproc.PATH_PREFIX + self.path_suffix
    return self.test_app.post(
        task_url, utils.encode_to_json(payload), headers=headers
    )


class StartTest(TestBase):
  path_suffix = 'start'

  @mock.patch('bulkproc.enqueue_tasks', autospec=True)
  def test_start(self, enqueue_tasks):
    ndb.put_multi([
        model.Build(
            id=i,
            bucket='chromium',
            create_time=self.now - datetime.timedelta(minutes=i)
        ) for i in xrange(1, 11)
    ])
    proc = {'name': 'foo', 'payload': 'bar'}
    self.post({
        'shards': 3,
        'proc': proc,
    })

    seg_path_prefix = bulkproc.PATH_PREFIX + 'segment/'
    enqueue_tasks.assert_called_with(
        'bulkproc', [
            (
                None,
                seg_path_prefix + 'seg:0-percent:0',
                utils.encode_to_json({
                    'job_id': 'taskname',
                    'iteration': 0,
                    'seg_index': 0,
                    'seg_start': 1,
                    'seg_end': 4,
                    'started_ts': utils.datetime_to_timestamp(self.now),
                    'proc': proc,
                }),
            ),
            (
                None,
                seg_path_prefix + 'seg:1-percent:0',
                utils.encode_to_json({
                    'job_id': 'taskname',
                    'iteration': 0,
                    'seg_index': 1,
                    'seg_start': 4,
                    'seg_end': 7,
                    'started_ts': utils.datetime_to_timestamp(self.now),
                    'proc': proc,
                }),
            ),
            (
                None,
                seg_path_prefix + 'seg:2-percent:0',
                utils.encode_to_json({
                    'job_id': 'taskname',
                    'iteration': 0,
                    'seg_index': 2,
                    'seg_start': 7,
                    'seg_end': 10,
                    'started_ts': utils.datetime_to_timestamp(self.now),
                    'proc': proc,
                }),
            ),
            (
                None,
                seg_path_prefix + 'seg:3-percent:0',
                utils.encode_to_json({
                    'job_id': 'taskname',
                    'iteration': 0,
                    'seg_index': 3,
                    'seg_start': 10,
                    'seg_end': 11,
                    'started_ts': utils.datetime_to_timestamp(self.now),
                    'proc': proc,
                }),
            ),
        ]
    )

  @mock.patch('bulkproc.enqueue_tasks', autospec=True)
  def test_start_many_shards(self, enqueue_tasks):
    ndb.put_multi([
        model.Build(
            id=i,
            bucket='chromium',
            create_time=self.now - datetime.timedelta(minutes=i)
        ) for i in xrange(1, 150)
    ])
    self.post({
        'shards': 100,
        'proc': {'name': 'foo', 'payload': 'bar'},
    })

    self.assertEqual(enqueue_tasks.call_count, 2)


class SegmentTest(TestBase):
  path_suffix = 'segment/rest'

  def setUp(self):
    super(SegmentTest, self).setUp()
    self.proc = {
        'func': lambda builds, _: list(builds),  # process all
        'keys_only': False,
    }
    self.patch('bulkproc._get_proc', return_value=self.proc)

  @mock.patch('bulkproc.enqueue_tasks', autospec=True)
  def test_segment_partial(self, enqueue_tasks):
    ndb.put_multi([
        model.Build(
            id=i, bucket='chromium', tags=[
                'buildset:%d' % (i % 3),
                'a:b',
            ]
        ) for i in xrange(50, 60)
    ])

    def process(builds, payload):
      # process 5 builds
      page = list(itertools.islice(builds, 5))
      self.assertEqual([b.key.id() for b in page], range(50, 55))
      self.assertEqual(payload, 'bar')

    self.proc['func'] = process

    self.post({
        'job_id': 'jobid',
        'iteration': 0,
        'seg_index': 0,
        'seg_start': 50,
        'seg_end': 60,
        'started_ts': utils.datetime_to_timestamp(self.now),
        'proc': {'name': 'foo', 'payload': 'bar'},
    })

    expected_next_payload = {
        'job_id': 'jobid',
        'iteration': 1,
        'seg_index': 0,
        'seg_start': 50,
        'seg_end': 60,
        'start_from': 55,
        'started_ts': utils.datetime_to_timestamp(self.now),
        'proc': {'name': 'foo', 'payload': 'bar'},
    }
    enqueue_tasks.assert_called_with(
        'bulkproc',
        [(
            'jobid-0-1',
            bulkproc.PATH_PREFIX + 'segment/seg:0-percent:50',
            utils.encode_to_json(expected_next_payload),
        )],
    )

  @mock.patch('bulkproc.enqueue_tasks', autospec=True)
  def test_segment_full(self, enqueue_tasks):
    ndb.put_multi([
        model.Build(id=i, bucket='chromium', tags=['buildset:%d' % (i % 3)])
        for i in xrange(50, 52)
    ])
    self.post({
        'job_id': 'jobid',
        'iteration': 0,
        'seg_index': 0,
        'seg_start': 50,
        'seg_end': 60,
        'started_ts': utils.datetime_to_timestamp(self.now),
        'proc': {'name': 'foo', 'payload': 'bar'},
    })

    self.assertEqual(enqueue_tasks.call_count, 0)

  @mock.patch('bulkproc.enqueue_tasks', autospec=True)
  def test_segment_attempt_2(self, enqueue_tasks):
    ndb.put_multi([
        model.Build(id=i, bucket='chromium', tags=['buildset:%d' % (i % 3)])
        for i in xrange(50, 60)
    ])

    # process 5 builds
    self.proc['func'] = lambda builds, _: list(itertools.islice(builds, 5))

    self.post(
        {
            'job_id': 'jobid',
            'iteration': 0,
            'seg_index': 0,
            'seg_start': 50,
            'seg_end': 60,
            'started_ts': utils.datetime_to_timestamp(self.now),
            'proc': {'name': 'foo', 'payload': 'bar'},
        },
        headers={
            'X-AppEngine-TaskExecutionCount': '1',
        },
    )

    enqueue_tasks.assert_called_with(
        'bulkproc',
        [(
            'jobid-0-1',
            bulkproc.PATH_PREFIX + 'segment/seg:0-percent:50',
            utils.encode_to_json({
                'job_id': 'jobid',
                'iteration': 1,
                'seg_index': 0,
                'seg_start': 50,
                'seg_end': 60,
                'start_from': 55,
                'started_ts': utils.datetime_to_timestamp(self.now),
                'proc': {'name': 'foo', 'payload': 'bar'},
            }),
        )],
    )
