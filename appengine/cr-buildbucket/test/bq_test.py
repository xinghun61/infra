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

from third_party import annotations_pb2

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
          status=model.BuildStatus.COMPLETED,
          result=model.BuildResult.FAILURE,
          failure_reason=model.FailureReason.BUILD_FAILURE,
          complete_time=datetime.datetime(2018, 1, 1)),
      mkbuild(
          id=3,
          status=model.BuildStatus.SCHEDULED),
      mkbuild(
          id=4,
          status=model.BuildStatus.STARTED,
          start_time=datetime.datetime(2018, 1, 1)),
    ]
    ndb.put_multi(builds)

    ann_step = annotations_pb2.Step(
        substep=[
          annotations_pb2.Step.Substep(
              step=annotations_pb2.Step(
                  name='bot_update',
                  status=annotations_pb2.SUCCESS,
              ),
          ),
        ],
    )
    model.BuildAnnotations(
        key=model.BuildAnnotations.key_for(builds[0].key),
        annotation_binary=ann_step.SerializeToString(),
        annotation_url='logdog://logdog.example.com/project/prefix/+/name',
    ).put()
    self.queue.add([
      taskqueue.Task(
          method='PULL',
          payload=json.dumps({'id': b.key.id()}))
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
          'rows': [
            { 'insertId': '1', 'json': mock.ANY },
            { 'insertId': '2', 'json': mock.ANY },
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
    bq._process_pull_task_batch(self.queue.name, 'builds')
    self.assertFalse(net.json_request.called)

  @mock.patch('v2.build_to_v2_partial', autospec=True)
  @mock.patch(
      'google.appengine.api.taskqueue.Queue.delete_tasks', autospec=True)
  def test_cron_export_builds_to_bq_exception(
      self, delete_tasks, build_to_v2_partial):
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

    def build_to_v2_partial_mock(build, *_, **__):
      if build is builds[1]:
        raise Exception()
      return build_pb2.Build()

    build_to_v2_partial.side_effect = build_to_v2_partial_mock

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


class ParseLogDogURLTest(testing.AppengineTestCase):
 def test_success(self):
    url = (
        'logdog://luci-logdog-dev.appspot.com/'
        'infra/'
        'buildbucket/cr-buildbucket-dev.appspot.com/8952867341410234048/+/'
        'annotations')
    expected = (
      'luci-logdog-dev.appspot.com',
      'infra',
      'buildbucket/cr-buildbucket-dev.appspot.com/8952867341410234048',
      'annotations',
    )
    actual = bq.parse_logdog_url(url)
    self.assertEqual(actual, expected)

 def test_failure(self):
    with self.assertRaises(ValueError):
      bq.parse_logdog_url('logdog://trash')


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
