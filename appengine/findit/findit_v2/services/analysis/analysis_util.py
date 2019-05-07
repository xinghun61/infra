# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Shared logic of all types of analysis."""

from collections import defaultdict


def UpdateFailureRegressionRanges(rerun_builds_info, failures_with_range):
  """Updates regression ranges for each failure based on rerun build results.

  Args:
    rerun_builds_info(list of (GitilesCommit, dict)): Gitiles commit each rerun
      build runs on and failures in each rerun build ({} if no failures).
      Format is like:
      [
        (GitilesCommit,
        {
          'compile': [a.o', 'b.o'],  # If the rerun build is for compile.
          'browser_tests': ['t1, 't2'],  # If the rerun build is for test.
          ...
        })
      ]
    failures_with_range (list): A dict for regression ranges of each
      failure. All failures have the same range, which is
      (analysis.last_passed_commit, analysis.first_failed_commit].
      Format is like:
      [
        {
          'failure': AtomicFailure,
          'last_passed_commit': GitilesCommit,
          'first_failed_commit': GitilesCommit
        },
        {
          'failure': AtomicFailure,
          'last_passed_commit': GitilesCommit,
          'first_failed_commit': GitilesCommit
        },
      ]
    After processing, each failure will have their own updated regression
    range.
  """
  for commit, failures_in_rerun_build in rerun_builds_info:
    for failure_with_range in failures_with_range:
      failure = failure_with_range['failure']
      if (commit.commit_position <
          failure_with_range['last_passed_commit'].commit_position or
          commit.commit_position >
          failure_with_range['first_failed_commit'].commit_position):
        # Commit is outside of this failure's regression range, so the rerun
        # build must be irrelevant to this failure.
        continue

      if (not failures_in_rerun_build.get(failure.step_ui_name) or
          not set(failure.GetFailureIdentifier()).issubset(
              set(failures_in_rerun_build[failure.step_ui_name]))):
        # Target/test passes in the rerun build, updates its last_pass.
        failure_with_range['last_passed_commit'] = max(
            failure_with_range['last_passed_commit'],
            commit,
            key=lambda c: c.commit_position)
      else:
        # Target/test fails in the rerun build, updates its first_failure.
        failure_with_range['first_failed_commit'] = min(
            failure_with_range['first_failed_commit'],
            commit,
            key=lambda c: c.commit_position)


def GroupFailuresByRegerssionRange(failures_with_range):
  """Gets groups of failures with the same regression range.

  Args:
    failures_with_range(list): A list for regression ranges of each
      failure. It has been updated by UpdateFailureRegressionRanges so each
      failure has their own updated regression range.
      Format is like:
      [
        {
          'failure': AtomicFailure,
          'last_passed_commit': GitilesCommit,
          'first_failed_commit': GitilesCommit
        },
        {
          'failure': AtomicFailure,
          'last_passed_commit': GitilesCommit,
          'first_failed_commit': GitilesCommit
        },
      ]

  Returns:
    (list of dict): Failures with the same regression range and the range.
    [
      {
        'failures': [AtomicFailure, ...],
        'last_passed_commit': GitilesCommit,
        'first_failed_commit': GitilesCommit
      },
      ...
    ]
  """

  def range_info():
    # Returns a template for range_to_failures values.
    return {
        'failures': [],
        'last_passed_commit': None,
        'first_failed_commit': None
    }

  # Groups failures with the same range. After processing it should look like:
  # {
  #   (600123, 600134): {
  #     'failures': [AtomicFailure, ...],
  #     'last_passed_commit': GitilesCommit for 600123
  #     'first_failed_commit': GitilesCommit for 600134
  #   },
  #   ...
  # }
  range_to_failures = defaultdict(range_info)
  for failure_with_range in failures_with_range:
    failure = failure_with_range['failure']
    last_passed_commit = failure_with_range['last_passed_commit']
    first_failed_commit = failure_with_range['first_failed_commit']
    commit_position_range = (last_passed_commit.commit_position,
                             first_failed_commit.commit_position)
    range_to_failures[commit_position_range]['failures'].append(failure)
    range_to_failures[commit_position_range][
        'last_passed_commit'] = last_passed_commit
    range_to_failures[commit_position_range][
        'first_failed_commit'] = first_failed_commit

  return range_to_failures.values()
