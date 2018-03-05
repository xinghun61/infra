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

  build_ids = [json.loads(t.payload)['id'] for t in tasks]
  # IDs of builds that we could not save and want to retry later.
  ids_to_retry = set()

  # Fetch builds for the tasks and convert to v2 format.
  builds = ndb.get_multi([ndb.Key(model.Build, bid) for bid in build_ids])
  v2_builds = []
  for bid, b in zip(build_ids, builds):
    if not b:
      logging.error('build %d not found', bid)
    elif b.status != model.BuildStatus.COMPLETED:
      logging.error('build %d is not complete', bid)
    else:
      try:
        v2_builds.append(v2.build_to_v2(b))
      except v2.UnsupportedBuild as ex:
        logging.warning(
            'skipping build %d: not supported by v2 conversion: %s',
            bid, ex)
      except Exception:
        ids_to_retry.add(bid)
        logging.exception('failed to convert build to v2\nBuild id: %d', bid)

  row_count = 0
  if v2_builds:
    not_inserted_ids = _export_builds(dataset, v2_builds, lease_deadline)
    row_count = len(v2_builds) - len(not_inserted_ids)
    ids_to_retry.update(not_inserted_ids)

  if ids_to_retry:
    logging.error('will retry builds %r later', sorted(build_ids))

  done_tasks = [
    t
    for bid, t in zip(build_ids, tasks)
    if bid not in ids_to_retry
  ]
  q.delete_tasks(done_tasks)
  logging.info(
      'inserted %d rows, processed %d tasks', row_count, len(done_tasks))


def _export_builds(dataset, v2_builds, deadline):
  """Saves v2 builds to BigQuery.

  Logs insert errors and returns a list of ids of builds that could not be
  inserted.
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

  failed_ids = []
  for err in res.get('insertErrors', []):
    b = v2_builds[err['index']]
    failed_ids.append(b.id)
    logging.error(
        'failed to insert row for build %d: %r',
        b.id, err['errors'])
  return failed_ids
