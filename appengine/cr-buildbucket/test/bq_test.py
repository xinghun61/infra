# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import os

from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from components import auth
from components import net
from test import test_util
from testing_utils import testing
import mock

from proto import build_pb2
from proto import service_config_pb2
from test import test_util
import bq
import bqh
import model
import v2

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
APP_ROOT_DIR = os.path.dirname(THIS_DIR)


class BigQueryExportTest(testing.AppengineTestCase):
  taskqueue_stub_root_path = APP_ROOT_DIR

  def setUp(self):
    super(BigQueryExportTest, self).setUp()
    self.patch('components.net.json_request', autospec=True, return_value={})
    self.now = datetime.datetime(2018, 1, 1)
    self.patch(
        'components.utils.utcnow', autospec=True, side_effect=lambda: self.now)

    self.queue = taskqueue.Queue('bq-export-prod')
    self.dataset = 'builds'

    self.patch(
        'v2.steps.fetch_steps_async', autospec=True,
        return_value=test_util.future(([], True)))

    self.settings = service_config_pb2.BigQueryExport()

  @mock.patch('bq.enqueue_pull_task_async', autospec=True)
  def test_enqueue_bq_export_async(self, enqueue_pull_task_async):
    enqueue_pull_task_async.return_value = test_util.future(None)

    build = model.Build(
        id=1,
        bucket='luci.chromium.try',
        status=model.BuildStatus.COMPLETED)

    ndb.transactional(  # pylint: disable=no-value-for-parameter
        lambda: bq.enqueue_bq_export_async(build).get_result())()

    enqueue_pull_task_async.assert_called_once_with(
        'bq-export-prod', json.dumps({'id': 1}))

  def test_cron_export_builds_to_bq(self):
    builds = [
      mkbuild(
          id=1,
          status=model.BuildStatus.COMPLETED,
          result=model.BuildResult.SUCCESS,
          complete_time=datetime.datetime(2018, 1, 1)),
      mkbuild(
          id=2,
          status=model.BuildStatus.SCHEDULED),
      mkbuild(
          id=3,
          status=model.BuildStatus.STARTED,
          start_time=datetime.datetime(2018, 1, 1)),
    ]
    ndb.put_multi(builds)
    self.queue.add([
      taskqueue.Task(
          method='PULL',
          payload=json.dumps({'id': b.key.id()}))
      for b in builds
    ])

    bq._process_pull_task_batch(self.queue.name, 'builds', self.settings)
    net.json_request.assert_called_once_with(
        url=(
            'https://www.googleapis.com/bigquery/v2/'
            'projects/testbed-test/datasets/builds/tables/'
            'completed_BETA/insertAll'
        ),
        method='POST',
        payload={
          'kind': 'bigquery#tableDataInsertAllRequest',
          'skipInvalidRows': False,
          'ignoreUnknownValues': False,
          'rows': [{
            'insertId': '1',
            'json': mock.ANY,
          }],
        },
        scopes=bqh.INSERT_ROWS_SCOPE,
        deadline=5 * 60,
    )
    actual_payload = net.json_request.call_args[1]['payload']
    self.assertEqual(actual_payload['rows'][0]['json']['id'], 1)

  @mock.patch('v2.build_to_v2_async', autospec=True)
  @mock.patch(
      'google.appengine.api.taskqueue.Queue.delete_tasks', autospec=True)
  def test_cron_export_builds_to_bq_not_finalized(self,
      delete_tasks, build_to_v2_async):
    self.now = datetime.datetime(2018, 1, 10)
    builds = [
      mkbuild(
          id=1,
          status=model.BuildStatus.COMPLETED,
          result=model.BuildResult.SUCCESS,
          complete_time=datetime.datetime(2018, 1, 1)),
      mkbuild(
          id=2,
          status=model.BuildStatus.COMPLETED,
          result=model.BuildResult.SUCCESS,
          complete_time=datetime.datetime(2018, 1, 1)),
      mkbuild(
          id=3,
          status=model.BuildStatus.COMPLETED,
          result=model.BuildResult.SUCCESS,
          complete_time=datetime.datetime(2018, 1, 1),
          result_details={
            'swarming': {
              'task_result': {
                'state': 'BOT_DIED',
              },
            },
          }),
      mkbuild(
          id=4,
          status=model.BuildStatus.COMPLETED,
          result=model.BuildResult.SUCCESS,
          complete_time=datetime.datetime(2018, 1, 1),
          result_details={
            'build_run_result': {
              'infraFailure': {
                'type': 'BOOTSTRAPPER_ERROR',
              },
            },
          }),
    ]
    ndb.put_multi(builds)
    tasks = [
      taskqueue.Task(
          method='PULL',
          payload=json.dumps({'id': b.key.id()}))
      for b in builds
    ]
    self.queue.add(tasks)

    def build_to_v2_async_mock(build, *_, **__):
      return test_util.future((
          build_pb2.Build(id=build.key.id()),
          build is builds[0]
      ))

    build_to_v2_async.side_effect = build_to_v2_async_mock

    bq._process_pull_task_batch(self.queue.name, 'builds', self.settings)

    expected_processed_ids = [1, 3, 4]

    actual_payload = net.json_request.call_args[1]['payload']
    self.assertEqual(
        [r['json']['id'] for r in actual_payload['rows']],
        expected_processed_ids,
    )

    deleted = delete_tasks.call_args[0][1]
    self.assertEqual(
        [json.loads(t.payload)['id'] for t in deleted],
        expected_processed_ids,
    )

  def test_cron_export_builds_to_bq_unsupported(self):
    model.Build(
        id=1,
        bucket='luci.foo',
        status=model.BuildStatus.COMPLETED,
        result=model.BuildResult.SUCCESS,
        create_time=datetime.datetime(2018, 1, 1),
        complete_time=datetime.datetime(2018, 1, 1),
    ).put()
    self.queue.add([taskqueue.Task(
        method='PULL',
        payload=json.dumps({'id': 1}))
    ])
    bq._process_pull_task_batch(self.queue.name, 'builds', self.settings)
    self.assertFalse(net.json_request.called)

  @mock.patch('v2.build_to_v2_async', autospec=True)
  @mock.patch(
      'google.appengine.api.taskqueue.Queue.delete_tasks', autospec=True)
  def test_cron_export_builds_to_bq_exception(
      self, delete_tasks, build_to_v2_async):
    builds = [
      mkbuild(
          id=i+1,
          status=model.BuildStatus.COMPLETED,
          result=model.BuildResult.SUCCESS,
          complete_time=datetime.datetime(2018, 1, 1))
      for i in xrange(3)
    ]
    ndb.put_multi(builds)

    tasks = [
      taskqueue.Task(
          method='PULL',
          payload=json.dumps({'id': b.key.id()}))
      for b in builds
    ]
    self.queue.add(tasks)

    def build_to_v2_async_mock(build, *_, **__):
      if build is builds[1]:
        return test_util.future_exception(Exception())
      return test_util.future((build_pb2.Build(), True))

    build_to_v2_async.side_effect = build_to_v2_async_mock

    bq._process_pull_task_batch(self.queue.name, 'builds', self.settings)

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
    self.queue.add([taskqueue.Task(
        method='PULL',
        payload=json.dumps({'id': 1}))
    ])
    bq._process_pull_task_batch(self.queue.name, 'builds', self.settings)
    self.assertFalse(net.json_request.called)

  def test_cron_export_builds_to_bq_no_tasks(self):
    bq._process_pull_task_batch(self.queue.name, 'builds', self.settings)
    self.assertFalse(net.json_request.called)

  @mock.patch(
      'google.appengine.api.taskqueue.Queue.delete_tasks', autospec=True)
  def test_cron_export_builds_to_bq_insert_errors(self, delete_tasks):
    builds = [
      mkbuild(
          id=i + 1,
          status=model.BuildStatus.COMPLETED,
          result=model.BuildResult.SUCCESS,
          complete_time=datetime.datetime(2018, 1, 1))
      for i in xrange(3)
    ]
    ndb.put_multi(builds)
    tasks = [
      taskqueue.Task(
          method='PULL',
          payload=json.dumps({'id': b.key.id()}))
      for b in builds
    ]
    self.queue.add(tasks)

    net.json_request.return_value = {
      'insertErrors': [{
        'index': 1,
        'errors': [{'reason': 'bad', 'message': ':('}],
      }]
    }

    bq._process_pull_task_batch(self.queue.name, 'builds', self.settings)
    self.assertTrue(net.json_request.called)

    # assert second task is not deleted
    deleted = delete_tasks.call_args[0][1]
    self.assertEqual(
      [t.payload for t in deleted],
      [tasks[0].payload, tasks[2].payload],
    )


def mkbuild(**kwargs):
  args = dict(
      id=1,
      project='chromium',
      bucket='luci.chromium.try',
      parameters={v2.BUILDER_PARAMETER: 'linux-rel'},
      created_by=auth.Identity('user', 'john@example.com'),
      create_time=datetime.datetime(2018, 1, 1),
  )
  args['parameters'].update(kwargs.pop('parameters', {}))
  args.update(kwargs)
  return model.Build(**args)
