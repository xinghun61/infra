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
from proto import step_pb2
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

    self.queue = taskqueue.Queue('bq-export-prod')
    self.dataset = 'builds'

  @mock.patch('bq.enqueue_pull_task_async', autospec=True)
  def test_enqueue_bq_export_async(self, enqueue_pull_task_async):
    enqueue_pull_task_async.return_value = test_util.future(None)

    build = test_util.build(id=1, status=common_pb2.SUCCESS)

    ndb.transactional(  # pylint: disable=no-value-for-parameter
        lambda: bq.enqueue_bq_export_async(build).get_result())()

    enqueue_pull_task_async.assert_called_once_with(
        'bq-export-prod', json.dumps({'id': 1})
    )

  def test_cron_export_builds_to_bq(self):
    builds = [
        test_util.build(id=1, status=common_pb2.SUCCESS),
        test_util.build(id=2, status=common_pb2.FAILURE),
        test_util.build(id=3, status=common_pb2.SCHEDULED),
        test_util.build(id=4, status=common_pb2.STARTED),
    ]
    ndb.put_multi(builds)

    model.BuildSteps(
        key=model.BuildSteps.key_for(builds[0].key),
        step_container=build_pb2.Build(
            steps=[
                step_pb2.Step(name='bot_update', status=common_pb2.SUCCESS),
            ],
        ),
    ).put()
    self.queue.add([
        taskqueue.Task(method='PULL', payload=json.dumps({'id': b.key.id()}))
        for b in builds
    ])

    bq._process_pull_task_batch(self.queue.name, 'builds')
    net.json_request.assert_called_once_with(
        url=(
            'https://www.googleapis.com/bigquery/v2/'
            'projects/testbed-test/datasets/builds/tables/'
            'completed_BETA/insertAll'
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

  @mock.patch('v2.build_to_v2', autospec=True)
  @mock.patch(
      'google.appengine.api.taskqueue.Queue.delete_tasks', autospec=True
  )
  def test_cron_export_builds_to_bq_exception(self, delete_tasks, build_to_v2):
    builds = [
        test_util.build(id=i + 1, status=common_pb2.SUCCESS) for i in xrange(3)
    ]
    ndb.put_multi(builds)

    tasks = [
        taskqueue.Task(method='PULL', payload=json.dumps({'id': b.key.id()}))
        for b in builds
    ]
    self.queue.add(tasks)

    def build_to_v2_mock(build, *_, **__):
      if build is builds[1]:
        raise Exception()
      return build_pb2.Build()

    build_to_v2.side_effect = build_to_v2_mock

    bq._process_pull_task_batch(self.queue.name, 'builds')

    self.assertTrue(net.json_request.called)
    actual_payload = net.json_request.call_args[1]['payload']
    self.assertEqual(len(actual_payload['rows']), 2)

    # assert second task is not deleted
    deleted = delete_tasks.call_args[0][1]
    self.assertEqual(
        [t.payload for t in deleted],
        [tasks[0].payload, tasks[2].payload],
    )

  def test_cron_export_builds_to_bq_not_found(self):
    self.queue.add([
        taskqueue.Task(method='PULL', payload=json.dumps({'id': 1}))
    ])
    bq._process_pull_task_batch(self.queue.name, 'builds')
    self.assertFalse(net.json_request.called)

  def test_cron_export_builds_to_bq_no_tasks(self):
    bq._process_pull_task_batch(self.queue.name, 'builds')
    self.assertFalse(net.json_request.called)

  @mock.patch(
      'google.appengine.api.taskqueue.Queue.delete_tasks', autospec=True
  )
  def test_cron_export_builds_to_bq_insert_errors(self, delete_tasks):
    builds = [
        test_util.build(id=i + 1, status=common_pb2.SUCCESS) for i in xrange(3)
    ]
    ndb.put_multi(builds)
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

    bq._process_pull_task_batch(self.queue.name, 'builds')
    self.assertTrue(net.json_request.called)

    # assert second task is not deleted
    deleted = delete_tasks.call_args[0][1]
    self.assertEqual(
        [t.payload for t in deleted],
        [tasks[0].payload, tasks[2].payload],
    )
