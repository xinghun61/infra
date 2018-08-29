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


def OnIssueChange(operation, category):
  monitoring.issues.increment({'category': category, 'operation': operation})


def OnFlakeCulprit(result, action_taken, reason):
  monitoring.flake_analyses.increment({
      'result': result,
      'action_taken': action_taken,
      'reason': reason,
  })


def OnWaterfallAnalysisStateChange(master_name, builder_name, failure_type,
                                   canonical_step_name, isolate_target_name,
                                   status, analysis_type):
  monitoring.waterfall_analysis_statuses.increment({
      'master_name': master_name,
      'builder_name': builder_name,
      'failure_type': failure_type,
      'canonical_step_name': canonical_step_name,
      'isolate_target_name': isolate_target_name,
      'status': status,
      'analysis_type': analysis_type,
  })


def OnFlakeAnalysisTriggered(source, operation, trigger, canonical_step_name,
                             isolate_target_name):
  monitoring.flakes.increment({
      'source': source,
      'operation': operation,
      'trigger': trigger,
      'canonical_step_name': canonical_step_name,
      'isolate_target_name': isolate_target_name
  })


def OnFlakeIdentified(canonical_step_name, isolate_target_name, operation,
                      count):
  monitoring.flakes_identified_by_waterfall_analyses.increment_by(
      count,
      {
          'canonical_step_name': canonical_step_name,
          'isolate_target_name': isolate_target_name,
          # analyzed, throttled or error.
          'operation': operation
      })


def OnFlakeDetectionQueryFailed(flake_type):
  """Used to monitor failed Flake Detection query execution.

  Args:
    flake_type: Type of the flake, such as 'cq false rejection' and
                'cq hidden flake'.
  """
  monitoring.flake_detection_query_failures.increment({
      'flake_type': flake_type
  })


def OnFlakeDetectionDetectNewOccurrences(flake_type, num_occurrences):
  """Used to monitor new occurrences detected by Flake Detection.

  Args:
    flake_type: Type of the flake, such as 'cq false rejection' and
                'cq hidden flake'.
    num_occurrences: Number of newly detected flake occurrences.
  """
  monitoring.flake_detection_flake_occurrences.increment_by(
      num_occurrences, {'flake_type': flake_type})


def OnFlakeDetectionCreateOrUpdateIssues(operation):
  """Used to monitor issues created or updated by Flake Detection.

  Args:
    operation: Type of the operation: create and update.
  """
  monitoring.flake_detection_issues.increment({'operation': operation})
