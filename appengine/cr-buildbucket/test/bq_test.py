# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import os

from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from components import auth
from components import net
from testing_utils import testing
import mock

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
    self.patch(
        'components.utils.utcnow', return_value=datetime.datetime(2018, 1, 1))

    self.queue = taskqueue.Queue('bq-export-prod')
    self.dataset = 'builds'

  def test_cron_export_builds_to_bq(self):
    builds = [
      mkbuild(
          id=1,
          status=model.BuildStatus.SCHEDULED),
      mkbuild(
          id=2,
          status=model.BuildStatus.STARTED,
          start_time=datetime.datetime(2018, 1, 1)),
      mkbuild(
          id=3,
          status=model.BuildStatus.COMPLETED,
          result=model.BuildResult.SUCCESS,
          complete_time=datetime.datetime(2018, 1, 1)),
    ]
    ndb.put_multi(builds)
    self.queue.add([
      taskqueue.Task(
          method='PULL',
          payload=json.dumps({'id': b.key.id()}),
      )
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
          'kind': 'bigquery#tableDataInsertAllRequest',
          'skipInvalidRows': False,
          'ignoreUnknownValues': False,
          'rows': [{
            'insertId': '3',
            'json': mock.ANY,
          }],
        },
        scopes=bqh.INSERT_ROWS_SCOPE,
        deadline=5 * 60,
    )
    actual_payload = net.json_request.call_args[1]['payload']
    self.assertEqual(actual_payload['rows'][0]['json']['id'], 3)

  def test_cron_export_builds_to_bq_unsupported(self):
    model.Build(
        id=1,
        bucket='foo',
        status=model.BuildStatus.COMPLETED,
        result=model.BuildResult.SUCCESS,
        create_time=datetime.datetime(2018, 1, 1),
        complete_time=datetime.datetime(2018, 1, 1),
    ).put()
    self.queue.add([taskqueue.Task(
        method='PULL',
        payload=json.dumps({'id': 1}))
    ])
    bq._process_pull_task_batch(self.queue.name, 'builds')
    self.assertFalse(net.json_request.called)

  def test_cron_export_builds_to_bq_not_found(self):
    self.queue.add([taskqueue.Task(
        method='PULL',
        payload=json.dumps({'id': 1}))
    ])
    bq._process_pull_task_batch(self.queue.name, 'builds')
    self.assertFalse(net.json_request.called)

  def test_cron_export_builds_to_bq_no_tasks(self):
    bq._process_pull_task_batch(self.queue.name, 'builds')
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

    bq._process_pull_task_batch(self.queue.name, 'builds')
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
