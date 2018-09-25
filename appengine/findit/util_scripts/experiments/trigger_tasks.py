#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Flakiness Swarming Task Experiment - Task Triggering Script

Triggers the needed tasks to run the experiment described by the input file.

Expects as an argument a path to a json file with the following structure:
{
  "experiment_id": "experiment-20180926-30331",
  "experiment_start": 1536000000,
  "dimensions": "os:Windows-7-SP1,pool:Chrome",
  "additional_args_template": "--gtest_repeat=%d <...more args...>",
  "task_count": 100,
  "repeats_per_task": 1,
  "rows": [
    {
      "isolate_hash": "fd4454258e116e999f16ccd6de5faca7b737fbf4",
    },
    {
      "isolate_hash": "ca8c6b3c106f5fd03df487ab062479ff315ee9a4"
    },
    {
      "isolate_hash": "4ff8e831b038aa18c40715eccf45eda7820484a5"
    },
    {
      "isolate_hash": "d18714f2fe36f603836b8592fbfdc486fe661de5"
    }
  ]
}

This script will read the file, trigger the swarming tasks tagging them with
the experiment name. If there are tasks already with the given experiment name,
only trigger the needed amount to reach the specified task count, so as to
increment the task count if necessary without losing the previous ones.

A separate script will read this file and get the results from swarming server
and aggregate them.

see
https://docs.google.com/document/d/1zHGwa2bcCY8galQmWMc0fiogCj_p3aiC3KUBgXMUQTg/edit?usp=sharing
"""
import os
import sys
import subprocess
import json

REQUIRED_EXPERIMENT_PARAMETERS = ('dimensions', 'additional_args_template',
                                  'task_count', 'repeats_per_task', 'rows')


class NoSwarmingTaskIdException(Exception):
  pass


def ParseSwarmingCommandResult(output):
  """Gets the task id from the trigger command output"""
  for line in output.splitlines():
    if line.strip().startswith('swarming.py collect'):
      result = line.strip().split()[-1]
      print 'Triggered swarming task:', result
      return result
  raise NoSwarmingTaskIdException(output)


def ComposeSwarmingTaskTriggerCommand(experiment_id, dimensions, isolate_hash,
                                      repeat_count, additional_args_template):
  """Composes the command line invocation for swarming.py .

  Note that the environment variable SWARMING_PY is expected to have been set to
  local checkout path of the following file:
    https://cs.chromium.org/chromium/infra/luci/client/swarming.py

  Args:
    experiment_id (str): The value of the tag to use to identify the task runs
        as part of a given experiment.
    dimensions (str): A string like "os:Mac,pool:Chrome" specifying the
        dimensions needed to serve the request.
    isolate_hash (str): Input isolate for the task.
    repeat_count (int): Number of times the test needs to be repeated. This is
        used to populate the template containing additional args.
    additional_args_template (str): A template containing the additional
        arguments to pass to the command line. It is expected to contain %d in
        place of the repeat count.
  Returns:
    A list of strings representing the command parts, suitable for passing to
    subprocess lib.
  """

  def DimensionFlags(dimensions):
    """E.g. convert `os:Mac,pool:Chrome` to `-d os Mac -d pool Chrome`."""
    result = []
    for d in dimensions.split(','):
      k, v = d.split(':')
      result.append('-d {0} {1}'.format(k, v))
    return ' '.join(result)

  command_template = ' '.join([
      'python {swarming_py} trigger',
      '-I isolateserver.appspot.com',
      '-S chromium-swarm.appspot.com',
      '{dimension_flags}',
      '-s {isolate_hash}',
      '--priority=190',
      '--expiration=86399',  # 23:59:59
      '--tags=experiment_id:{experiment_id}',
      '-- {additional_args}',
  ])
  command = command_template.format(
      experiment_id=experiment_id + isolate_hash[:4],
      swarming_py=os.environ.get('SWARMING_PY', 'swarming.py'),
      dimension_flags=DimensionFlags(dimensions),
      isolate_hash=isolate_hash,
      additional_args=additional_args_template % repeat_count,
  )
  return command.split()


def GetTaskCount(experiment_id, isolate_hash, experiment_start):
  """Determines number of swarming tasks with experiment name."""
  query_command = [
      'python',
      os.environ.get('SWARMING_PY', 'swarming.py'), 'query', '-S',
      'chromium-swarm.appspot.com',
      'tasks/count?tags=experiment_id%%3A%s&start=%d' %
      (experiment_id + isolate_hash[:4], experiment_start)
  ]
  return int(json.loads(subprocess.check_output(query_command))['count'])


def main(experiment_path):
  experiment = json.load(open(experiment_path))
  for parameter in REQUIRED_EXPERIMENT_PARAMETERS:
    assert parameter in experiment, \
        '"%s" is a required parameter, and missing from %s' % (
            parameter, experiment_path)
  dimensions = experiment['dimensions']
  additional_args_template = experiment['additional_args_template']
  task_count = experiment['task_count']
  repeats_per_task = experiment['repeats_per_task']
  rows = experiment['rows']
  experiment_id = experiment['experiment_id']
  experiment_start = experiment['experiment_start']
  for row in rows:
    current_task_count = GetTaskCount(experiment_id, row['isolate_hash'],
                                      experiment_start)
    if current_task_count < task_count:
      remaining_tasks = task_count - current_task_count
      for _ in range(remaining_tasks):
        subprocess.check_output(
            ComposeSwarmingTaskTriggerCommand(
                experiment_id, dimensions, row['isolate_hash'],
                repeats_per_task, additional_args_template))
  return 0


if __name__ == '__main__':
  assert len(sys.argv) == 2, 'Path to a json file expected as first argument'
  sys.exit(main(sys.argv[1]))
