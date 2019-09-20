# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import os

from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from components import net
from test import test_util
from testing_utils import testing
import mock

from proto import build_pb2
from proto import common_pb2
from test import test_util
import bq
import bqh
import model

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
APP_ROOT_DIR = os.path.dirname(THIS_DIR)


class BigQueryExportTest(testing.AppengineTestCase):
  taskqueue_stub_root_path = APP_ROOT_DIR

  def setUp(self):
    super(BigQueryExportTest, self).setUp()
    self.patch('components.net.json_request', autospec=True, return_value={})
    self.now = datetime.datetime(2018, 1, 1)
    self.patch(
        'components.utils.utcnow', autospec=True, side_effect=lambda: self.now
    )

    self.queue = taskqueue.Queue('bq-export')
    self.dataset = 'builds'

  @mock.patch('tq.enqueue_async', autospec=True)
  def test_enqueue_bq_export_async(self, enqueue_async):
    enqueue_async.return_value = test_util.future(None)

    build = test_util.build(id=1, status=common_pb2.SUCCESS)

    ndb.transactional(  # pylint: disable=no-value-for-parameter
        lambda: bq.enqueue_bq_export_async(build).get_result())()

    task_def = {
        'method': 'PULL',
        'payload': {'id': 1},
    }
    enqueue_async.assert_any_call('bq-export', [task_def])

  def test_cron_export_builds_to_bq(self):
    bundles = [
        test_util.build_bundle(
            id=1,
            status=common_pb2.SUCCESS,
            infra=dict(
                swarming=dict(
                    task_dimensions=[
                        dict(key='a', value='1', expiration=dict(seconds=1)),
                    ],
                    caches=[
                        dict(
                            path='a',
                            name='1',
                            wait_for_warm_cache=dict(seconds=1),
                        ),
                    ],
                ),
            ),
        ),
        test_util.build_bundle(id=2, status=common_pb2.FAILURE),
        test_util.build_bundle(id=3, status=common_pb2.SCHEDULED),
        test_util.build_bundle(id=4, status=common_pb2.STARTED),
    ]
    for b in bundles:
      b.put()

    builds = [b.build for b in bundles]
    build_steps = model.BuildSteps(key=model.BuildSteps.key_for(builds[0].key))
    build_steps.write_steps(
        build_pb2.Build(
            steps=[
                dict(
                    name='bot_update',
                    status=common_pb2.SUCCESS,
                    summary_markdown='summary_markdown',
                    logs=[dict(name='stdout')],
                ),
            ],
        )
    )
    build_steps.put()
    self.queue.add([
        taskqueue.Task(method='PULL', payload=json.dumps({'id': b.key.id()}))
        for b in builds
    ])

    bq._process_pull_task_batch(self.queue.name, 'raw', 'completed_builds')
    net.json_request.assert_called_once_with(
        url=(
            'https://www.googleapis.com/bigquery/v2/'
            'projects/testbed-test/datasets/raw/tables/'
            'completed_builds/insertAll'
        ),
        method='POST',
        payload={
            'kind':
                'bigquery#tableDataInsertAllRequest',
            'skipInvalidRows':
                True,
            'ignoreUnknownValues':
                False,
            'rows': [
                {'insertId': '1', 'json': mock.ANY},
                {'insertId': '2', 'json': mock.ANY},
            ],
        },
        scopes=bqh.INSERT_ROWS_SCOPE,
        deadline=5 * 60,
    )
    actual_payload = net.json_request.call_args[1]['payload']
    self.assertEqual(
        [r['json']['id'] for r in actual_payload['rows']],
        [1, 2],
    )

    step = actual_payload['rows'][0]['json']['steps'][0]
    self.assertEqual(step['name'], 'bot_update')
    self.assertEqual(step['summary_markdown'], '')
    self.assertNotIn('logs', step)

  def test_cron_export_builds_to_bq_not_found(self):
    self.queue.add([
        taskqueue.Task(method='PULL', payload=json.dumps({'id': 1}))
    ])
    bq._process_pull_task_batch(self.queue.name, 'raw', 'completed_builds')
    self.assertFalse(net.json_request.called)

  def test_cron_export_builds_to_bq_no_tasks(self):
    bq._process_pull_task_batch(self.queue.name, 'raw', 'completed_builds')
    self.assertFalse(net.json_request.called)

  @mock.patch(
      'google.appengine.api.taskqueue.Queue.delete_tasks', autospec=True
  )
  def test_cron_export_builds_to_bq_insert_errors(self, delete_tasks):
    bundles = [
        test_util.build_bundle(id=i + 1, status=common_pb2.SUCCESS)
        for i in xrange(3)
    ]
    for b in bundles:
      b.put()
    builds = [b.build for b in bundles]
    tasks = [
        taskqueue.Task(method='PULL', payload=json.dumps({'id': b.key.id()}))
        for b in builds
    ]
    self.queue.add(tasks)

    net.json_request.return_value = {
        'insertErrors': [{
            'index': 1,
            'errors': [{'reason': 'bad', 'message': ':('}],
        }]
    }

    bq._process_pull_task_batch(self.queue.name, 'raw', 'completed_builds')
    self.assertTrue(net.json_request.called)

    # assert second task is not deleted
    deleted = delete_tasks.call_args[0][1]
    self.assertEqual(
        [t.payload for t in deleted],
        [tasks[0].payload, tasks[2].payload],
    )
