# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import itertools
import mock

from google.appengine.ext import ndb

from components import utils

from proto import build_pb2
from test import test_util
from testing_utils import testing
import bulkproc
import main
import model


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
    # create a build a day for 3 days
    proc = {'name': 'foo', 'payload': 'bar'}
    self.post({
        'proc': proc,
    })

    # Expect a segment for each day.
    seg_path_prefix = bulkproc.PATH_PREFIX + 'segment/'
    self.assertEqual(enqueue_tasks.call_count, 24)
    all_tasks = []
    for (queue_name, tasks), _ in enqueue_tasks.call_args_list:
      self.assertEqual(queue_name, 'bulkproc')
      all_tasks.extend(tasks)
    self.assertEqual(len(all_tasks), 2165)
    self.assertEqual(
        all_tasks[0],
        (
            None,
            seg_path_prefix + 'seg:0-percent:0',
            utils.encode_to_json({
                'job_id': 'taskname',
                'iteration': 0,
                'seg_index': 0,
                'seg_start': 8991624996803575808,
                'seg_end': 8991647646045175807,
                'started_ts': utils.datetime_to_timestamp(self.now),
                'proc': proc,
            }),
        ),
    )
    self.assertEqual(
        all_tasks[1],
        (
            None,
            seg_path_prefix + 'seg:1-percent:0',
            utils.encode_to_json({
                'job_id': 'taskname',
                'iteration': 0,
                'seg_index': 1,
                'seg_start': 8991647646045175808,
                'seg_end': 8991670295286775807,
                'started_ts': utils.datetime_to_timestamp(self.now),
                'proc': proc,
            }),
        ),
    )


class SegmentTest(TestBase):
  path_suffix = 'segment/rest'

  def setUp(self):
    super(SegmentTest, self).setUp()
    self.proc = {
        'entity_kind': 'Build',
        'func': lambda builds, _: list(builds),  # process all
        'keys_only': False,
    }
    self.patch('bulkproc._get_proc', side_effect=lambda _: self.proc)

  @mock.patch('bulkproc.enqueue_tasks', autospec=True)
  def test_segment_partial(self, enqueue_tasks):
    ndb.put_multi([test_util.build(id=i) for i in xrange(50, 60)])

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
        'seg_end': 59,
        'started_ts': utils.datetime_to_timestamp(self.now),
        'proc': {'name': 'foo', 'payload': 'bar'},
    })

    expected_next_payload = {
        'job_id': 'jobid',
        'iteration': 1,
        'seg_index': 0,
        'seg_start': 50,
        'seg_end': 59,
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
    ndb.put_multi([test_util.build(id=i) for i in xrange(50, 52)])
    self.post({
        'job_id': 'jobid',
        'iteration': 0,
        'seg_index': 0,
        'seg_start': 50,
        'seg_end': 59,
        'started_ts': utils.datetime_to_timestamp(self.now),
        'proc': {'name': 'foo', 'payload': 'bar'},
    })

    self.assertEqual(enqueue_tasks.call_count, 0)

  @mock.patch('bulkproc.enqueue_tasks', autospec=True)
  def test_segment_attempt_2(self, enqueue_tasks):
    ndb.put_multi([test_util.build(id=i) for i in xrange(50, 60)])

    # process 5 builds
    self.proc['func'] = lambda builds, _: list(itertools.islice(builds, 5))

    self.post(
        {
            'job_id': 'jobid',
            'iteration': 0,
            'seg_index': 0,
            'seg_start': 50,
            'seg_end': 59,
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
                'seg_end': 59,
                'start_from': 55,
                'started_ts': utils.datetime_to_timestamp(self.now),
                'proc': {'name': 'foo', 'payload': 'bar'},
            }),
        )],
    )

  @mock.patch('bulkproc.enqueue_tasks', autospec=True)
  def test_build_steps_keys_only(self, enqueue_tasks):
    build_steps = [
        model.BuildSteps(
            parent=ndb.Key(model.Build, i), step_container_bytes=''
        ) for i in xrange(50, 60)
    ]
    ndb.put_multi(build_steps)

    def processor(results, payload):
      # Take 5
      page = list(itertools.islice(results, 5))
      self.assertEqual(page, [b.key for b in build_steps[:5]])
      self.assertEqual(payload, 'bar')

    self.proc = {
        'entity_kind': 'BuildSteps',
        'func': processor,
        'keys_only': True,
    }

    self.post({
        'job_id': 'jobid',
        'iteration': 0,
        'seg_index': 0,
        'seg_start': 50,
        'seg_end': 59,
        'started_ts': utils.datetime_to_timestamp(self.now),
        'proc': {'name': 'foo', 'payload': 'bar'},
    })

    expected_next_payload = {
        'job_id': 'jobid',
        'iteration': 1,
        'seg_index': 0,
        'seg_start': 50,
        'seg_end': 59,
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
