# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Implements export of builds from datastore to BigQuery."""

import datetime
import json
import logging

from google.appengine.api import app_identity
from google.appengine.api import taskqueue
from google.appengine.ext import ndb
import webapp2

from components import decorators
from components import net
from components import utils
import bqh

import model
import v2


# Mocked in tests.
@ndb.tasklet
def enqueue_pull_task_async(queue, payload):  # pragma: no cover
  task = taskqueue.Task(
      payload=payload,
      method='PULL')
  # Cannot just return add_async's return value because it is
  # a non-Future object and does not play nice with `yield fut1, fut2` construct
  yield task.add_async(queue_name=queue, transactional=True)


def enqueue_bq_export_async(build):  # pragma: no cover
  """Enqueues a pull task to export a completed build to BigQuery."""
  assert ndb.in_transaction()
  assert build
  assert build.status == model.BuildStatus.COMPLETED

  return enqueue_pull_task_async(
      'bq-export-experimental' if build.experimental else 'bq-export-prod',
      json.dumps({'id': build.key.id()}))


class CronExportBuilds(webapp2.RequestHandler):  # pragma: no cover
  """Exports builds to a BigQuery table."""

  queue_name = None
  dataset = None

  @decorators.require_cronjob
  def get(self):
    assert self.queue_name
    assert self.dataset
    _process_pull_task_batch(self.queue_name, self.dataset)


class CronExportBuildsProd(CronExportBuilds):
  queue_name = 'bq-export-prod'
  dataset = 'builds'


class CronExportBuildsExperimental(CronExportBuilds):
  queue_name = 'bq-export-experimental'
  dataset = 'builds_experimental'


def _process_pull_task_batch(queue_name, dataset):
  # Lease tasks.
  lease_duration = datetime.timedelta(minutes=5)
  lease_deadline = utils.utcnow() + lease_duration
  q = taskqueue.Queue(queue_name)
  tasks = q.lease_tasks(lease_duration.total_seconds(), 1000)
  if not tasks:
    return

  # Fetch builds for the tasks and convert to v2 format.
  build_ids = [json.loads(t.payload)['id'] for t in tasks]
  builds = ndb.get_multi([ndb.Key(model.Build, bid) for bid in build_ids])
  to_export_builds = []
  to_export_tasks = []
  for t, bid, b in zip(tasks, build_ids, builds):
    if not b:
      logging.error('build %d not found', bid)
    elif b.status != model.BuildStatus.COMPLETED:
      logging.error('build %d is not complete', bid)
    else:
      try:
        to_export_builds.append(v2.build_to_v2(b))
        to_export_tasks.append(t)
      except v2.UnsupportedBuild as ex:
        logging.warning(
            'skipping build %d: not supported by v2 conversion: %s',
            bid, ex)

  row_count = 0
  done_tasks = tasks
  if to_export_builds:
    failed_indexes = _export_builds(dataset, to_export_builds, lease_deadline)
    failed_tasks = set(to_export_tasks[i] for i in failed_indexes)
    done_tasks = [t for t in tasks if t not in failed_tasks]
    row_count = len(to_export_builds) - len(failed_indexes)

  q.delete_tasks(done_tasks)
  logging.info('inserted %d rows, processed %d tasks', row_count, len(tasks))


def _export_builds(dataset, v2_builds, deadline):
  """Saves v2 builds to BigQuery.

  Logs insert errors and returns a list of indexes of builds that could not
  be saved.
  """
  table_name = 'completed_BETA'  # TODO(nodir): remove beta suffix.
  # BigQuery API doc:
  # https://cloud.google.com/bigquery/docs/reference/rest/v2/tabledata/insertAll
  logging.info('sending %d rows', len(v2_builds))
  res = net.json_request(
      url=(
        ('https://www.googleapis.com/bigquery/v2/'
          'projects/%s/datasets/%s/tables/%s/insertAll') % (
          app_identity.get_application_id(), dataset, table_name)
        ),
      method='POST',
      payload={
        'kind': 'bigquery#tableDataInsertAllRequest',
        'skipInvalidRows': False,
        'ignoreUnknownValues': False,
        'rows': [
          {
            'insertId': str(b.id),
            'json': bqh.message_to_dict(b),
          }
          for b in v2_builds
        ],
      },
      scopes=bqh.INSERT_ROWS_SCOPE,
      # deadline parameter here is duration in seconds.
      deadline=(deadline - utils.utcnow()).total_seconds(),
  )

  failed_indexes = []
  for err in res.get('insertErrors', []):
    i = err['index']
    failed_indexes.append(i)
    logging.error(
        'failed to insert row for build %d: %r',
        v2_builds[i].id, err['errors'])
  return failed_indexes
