#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Flakiness Swarming Task Experiment - Result Collection Script

This script operates on the same json file as trigger_tasks.py

It retrieves result for the triggered tasks and saves the result counts to the
json file.
"""
import json
import os
import sys

# Append paths so that dependencies would work.
_FINDIT_DIR = os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)
_THIRD_PARTY_DIR = os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir, 'third_party')
_FIRST_PARTY_DIR = os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir, 'first_party')
sys.path.insert(0, _FINDIT_DIR)
sys.path.insert(0, _THIRD_PARTY_DIR)
sys.path.insert(0, _FIRST_PARTY_DIR)

from local_libs import remote_api
remote_api.EnableRemoteApi(app_id='findit-for-me')

from infra_api_clients.swarming import swarming_util
from common.findit_http_client import FinditHttpClient
from services import constants
from services import swarming
from services.flake_failure import flake_test_results
from services.swarmed_test_util import GetSwarmingTaskDataAndResult


def ListTasks(experiment_id, isolate_hash):
  tag_filter = {'experiment_id': experiment_id + isolate_hash[:4]}
  return [
      i.task_id
      for i in swarming_util.ListTasks(swarming.SwarmingHost(), tag_filter,
                                       FinditHttpClient())
  ]


def ResultsForBatch(experiment_id, batch):
  """Retrieve swarming results for each task and aggregate them.

  This function makes the same assumptions about the swarming task as flake
  analysis reruns.

  Args:
    batch (dict): Entry with an isolate hash, and swarming task ids, as well as,
        possibly, partial results.

  Returns:
    A dict with counts for tries, passes, incomplete, errored and successful
    tasks.
  """
  batch['results'] = batch.get('results', {})
  batch['task_results'] = batch.get('task_results', {})
  total_tries = batch['results'].get('total_tries', 0)
  total_passes = batch['results'].get('total_passes', 0)
  incomplete_tasks = 0
  errored_tasks = batch['results'].get('errored_tasks', 0)
  successful_tasks = batch['results'].get('successful_tasks', 0)
  error_bots = set(batch['results'].get('error_bots', []))
  not_all_pass_bots = set(batch['task_results'].get('not_all_pass_bots', []))
  all_pass_bots = set(batch['task_results'].get('all_pass_bots', []))
  for task_id in ListTasks(experiment_id, batch['isolate_hash']):
    if task_id not in batch['task_results']:
      batch['task_results'][task_id] = {}
    elif 'complete' in batch['task_results'][task_id]:
      continue
    task_data, task_output, error = GetSwarmingTaskDataAndResult(task_id)
    if task_data.get('state') == constants.STATE_COMPLETED:
      batch['task_results'][task_id]['complete'] = True
      batch['task_results'][task_id]['bot'] = task_data.get('bot_id')
      tries, passes = flake_test_results.GetCountsFromSwarmingRerun(task_output)
      if tries is None or passes is None:
        errored_tasks += 1
        error_bots.add(task_data.get('bot_id'))
        batch['task_results'][task_id]['errored'] = True
        print >> sys.stderr, (
            error or 'Tries or passes info missing for ' + task_id)
        continue
      total_tries += tries or 0
      total_passes += passes or 0
      successful_tasks += 1
      if passes == tries:
        all_pass_bots.add(task_data.get('bot_id'))
      else:
        not_all_pass_bots.add(task_data.get('bot_id'))
      batch['task_results'][task_id]['passes'] = passes
      batch['task_results'][task_id]['failures'] = tries - passes
    else:
      incomplete_tasks += 1
  batch['results'].update({
      'total_tries': total_tries,
      'total_passes': total_passes,
      'incomplete_tasks': incomplete_tasks,
      'errored_tasks': errored_tasks,
      'successful_tasks': successful_tasks,
      'total_tasks': len(batch['task_results']),
      'error_bots': list(error_bots),
      'all_pass_bots': list(all_pass_bots),
      'not_all_pass_bots': list(not_all_pass_bots),
  })
  return batch


def main(experiment_path):
  try:
    experiment = json.load(open(experiment_path))
  except:  # pylint: disable bare-except
    print 'Unable to open the json file at', experiment_path
    raise
  try:
    total_incomplete_tasks = 0
    for row in experiment.get('rows'):
      # Fetch results when:
      #   - No results have been fetch
      #   - Some tasks had not finished last time we checked
      #   - More tasks have been triggred than we have results for.
      if (not row.get('results') or row['results'].get('incomplete_tasks') or
          len(row.get('task_results')) != row['results']['total_tasks']):
        row = ResultsForBatch(experiment['experiment_id'], row)
      total_incomplete_tasks += row.get('results', {}).get(
          'incomplete_tasks', 0)
    if total_incomplete_tasks:
      print '%d pending/running tasks' % total_incomplete_tasks
    else:
      print 'All tasks complete'
  finally:
    json.dump(
        experiment,
        open(experiment_path, 'w'),
        indent=4,
        separators=(',', ': '))


if __name__ == '__main__':
  assert len(sys.argv) > 1, 'Path to a json file expected as first argument'
  sys.exit(main(sys.argv[1]))
