# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for monitoring operations.

It provides functions to:
  * Monitor when try job is triggered.
"""

from common import monitoring


def OnTryJobTriggered(try_job_type, master_name, builder_name):
  """Records when a try job is triggered."""
  monitoring.try_jobs.increment({
      'operation': 'trigger',
      'type': try_job_type,
      'master_name': master_name,
      'builder_name': builder_name,
  })


def OnCulpritAction(failure_type, action):
  """Records when Findit take action on a culprit.

  Args:
    failure_type (str): 'compile', 'test' or 'flake'.
    action (str): revert_created, revert_committed, revert_confirmed,
      revert_status_error, revert_commit_error, culprit_notified,
      culprit_notified_error, irc_notified, irc_notified_error.
  """
  monitoring.culprit_found.increment({
      'type': failure_type,
      'action_taken': action
  })


def OnTryJobError(try_job_type, error_dict, master_name, builder_name):
  monitoring.try_job_errors.increment({
      'type': try_job_type,
      'error': error_dict.get('message') or 'unknown',
      'master_name': master_name,
      'builder_name': builder_name
  })


def OnSwarmingTaskStatusChange(operation, category):
  monitoring.swarming_tasks.increment({
      'operation': operation,
      'category': category
  })
