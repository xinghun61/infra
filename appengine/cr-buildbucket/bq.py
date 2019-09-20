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

from proto import build_pb2
import model
import tq


def enqueue_bq_export_async(build):
  """Enqueues a pull task to export a completed build to BigQuery."""
  assert ndb.in_transaction()
  assert build
  assert build.is_ended

  task_def = {
      'method': 'PULL',
      'payload': {'id': build.key.id()},
  }
  return tq.enqueue_async('bq-export', [task_def])


class CronExportBuilds(webapp2.RequestHandler):  # pragma: no cover
  """Exports builds to a BigQuery table."""

  @decorators.require_cronjob
  def get(self):
    deadline = utils.utcnow() + datetime.timedelta(minutes=9)
    while utils.utcnow() < deadline:
      inserted, total = _process_pull_task_batch(
          'bq-export', 'raw', 'completed_builds'
      )
      if total > 0 and inserted == 0:
        logging.error('Failed to insert a single row out of %d', total)
        self.abort(500)
      if total < 100:
        # Too few for a tight loop.
        return


def _process_pull_task_batch(queue_name, dataset, table_name):
  """Exports up to 300 builds to BigQuery.

  Leases pull tasks, fetches build entities and inserts them into BigQuery.

  If the build is not finalized and it has been 20m or more since the build was
  completed, the following strategies apply:
  - if the build infra-failed with BOT_DIED or TIMED_OUT task status,
    saves build as is.
  - if the build infra-failed with BOOTSTRAPPER_ERROR and there are no steps,
    assumes the build failed to register LogDog prefix and saves it as is.
  - otherwise logs a warning/error, does not save to BigQuery and retries the
    task later.

  Returns: (inserted_count, total_count) tuple.
  """
  now = utils.utcnow()

  # Lease tasks.
  lease_duration = datetime.timedelta(minutes=5)
  lease_deadline = now + lease_duration
  q = taskqueue.Queue(queue_name)
  # https://cloud.google.com/bigquery/quotas#streaming_inserts
  # says "We recommend using about 500 rows per request".
  # We are using less because otherwise we tend to hit the 10 MB per request
  # limit.
  tasks = q.lease_tasks(lease_duration.total_seconds(), 300)
  if not tasks:
    return 0, 0

  build_ids = [json.loads(t.payload)['id'] for t in tasks]

  # IDs of builds that we could not save and want to retry later.
  ids_to_retry = set()
  # model.Build objects to insert to BigQuery.
  to_insert = []

  builds = ndb.get_multi(ndb.Key(model.Build, bid) for bid in build_ids)
  for bid, b in zip(build_ids, builds):
    if not b:
      logging.error('skipping build %d: not found', bid)
    elif not b.is_ended:
      logging.error('will retry build: not complete\n%d', bid)
      ids_to_retry.add(bid)
    else:
      to_insert.append(b)

  row_count = 0
  if to_insert:
    not_inserted_ids = _export_builds(
        dataset, table_name, to_insert, lease_deadline
    )
    row_count = len(to_insert) - len(not_inserted_ids)
    ids_to_retry.update(not_inserted_ids)

  if ids_to_retry:
    logging.warning('will retry builds %r later', sorted(ids_to_retry))

  done_tasks = [
      t for bid, t in zip(build_ids, tasks) if bid not in ids_to_retry
  ]
  q.delete_tasks(done_tasks)
  logging.info(
      'inserted %d rows, processed %d tasks', row_count, len(done_tasks)
  )
  return len(done_tasks), len(tasks)


def _export_builds(dataset, table_name, builds, deadline):
  """Saves builds to BigQuery.

  Logs insert errors and returns a list of ids of builds that could not be
  inserted.
  """
  # BigQuery API doc:
  # https://cloud.google.com/bigquery/docs/reference/rest/v2/tabledata/insertAll
  logging.info('sending %d rows', len(builds))

  pairs = [(b, build_pb2.Build()) for b in builds]
  model.builds_to_protos_async(
      pairs,
      load_tags=True,
      load_input_properties=True,
      load_output_properties=True,
      load_steps=True,
      load_infra=True,
  ).get_result()

  # Clear fields that we don't want in BigQuery.
  for _, proto in pairs:
    for s in proto.steps:
      s.summary_markdown = ''
      s.ClearField('logs')

  res = net.json_request(
      url=((
          'https://www.googleapis.com/bigquery/v2/'
          'projects/%s/datasets/%s/tables/%s/insertAll'
      ) % (app_identity.get_application_id(), dataset, table_name)),
      method='POST',
      payload={
          'kind':
              'bigquery#tableDataInsertAllRequest',
          # Do not fail entire request because of one bad build.
          # We handle invalid rows below.
          'skipInvalidRows':
              True,
          'ignoreUnknownValues':
              False,
          'rows': [{
              'insertId': str(p.id),
              'json': bqh.message_to_dict(p),
          } for _, p in pairs],
      },
      scopes=bqh.INSERT_ROWS_SCOPE,
      # deadline parameter here is duration in seconds.
      deadline=(deadline - utils.utcnow()).total_seconds(),
  )

  failed_ids = []
  for err in res.get('insertErrors', []):
    _, bp = pairs[err['index']]
    failed_ids.append(bp.id)
    logging.error('failed to insert row for build %d: %r', bp.id, err['errors'])
  return failed_ids
