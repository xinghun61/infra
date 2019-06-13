# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Shared logic of all types of analysis."""

from collections import defaultdict
import logging

from findit_v2.model.gitiles_commit import GitilesCommit
from findit_v2.model.messages.findit_result import Culprit
from findit_v2.model.messages.findit_result import (GitilesCommit as
                                                    GitilesCommitPb)


def BisectGitilesCommit(context, left_bound_commit, right_bound_commit,
                        commit_position_to_git_hash_map):
  """Uses bisection to get the gitiles to check.

  Args:
    context (findit_v2.services.context.Context): Scope of the analysis.
    left_bound_commit (GitilesCommit): left bound of the regression range, not
    included. It should be the last passed commit found so far.
    right_bound_commit (GitilesCommit): right bound of the regression range,
      included. It should be the first failed commit found so far.
    commit_position_to_git_hash_map (dict): A map of commit_positions to
      git_hashes.

  Return:
    (GitilesCommit, GitilesCommit): Commit to bisect next, or the culprit
      commit. If the next commit is identified, there will be no culprit
        commit and vice versa.
  """
  assert left_bound_commit and right_bound_commit, (
      'Requiring two bounds to determine a bisecting commit')

  left_commit_position = left_bound_commit.commit_position
  right_commit_position = right_bound_commit.commit_position
  assert left_commit_position <= right_commit_position, (
      'left bound commit is after right.')

  if right_commit_position == left_commit_position + 1:
    # Cannot further divide the regression range, culprit is the
    #  ight_bound_commit.
    return None, right_bound_commit

  bisect_commit_position = left_commit_position + (
      right_commit_position - left_commit_position) / 2

  bisect_commit_gitiles_id = commit_position_to_git_hash_map.get(
      bisect_commit_position) if commit_position_to_git_hash_map else None

  if not bisect_commit_gitiles_id:
    logging.error('Failed to get git_hash for change %s/%s/%s/%d',
                  context.gitiles_host, context.gitiles_project,
                  context.gitiles_ref, bisect_commit_position)
    return None, None

  return GitilesCommit(
      gitiles_host=context.gitiles_host,
      gitiles_project=context.gitiles_project,
      gitiles_ref=context.gitiles_ref,
      gitiles_id=bisect_commit_gitiles_id,
      commit_position=bisect_commit_position), None


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


def GetCulpritsForFailures(failures):
  """Gets culprits for the requested failures.

  Args:
    failures (list of AtomicFailures)

  Returns:
    (list of findit_result.Culprit)
  """
  culprit_keys = set([
      failure.culprit_commit_key
      for failure in failures
      if failure and failure.culprit_commit_key
  ])
  culprits = []
  for culprit_key in culprit_keys:
    culprit_entity = culprit_key.get()
    culprit_message = Culprit(
        commit=GitilesCommitPb(
            host=culprit_entity.gitiles_host,
            project=culprit_entity.gitiles_project,
            ref=culprit_entity.gitiles_ref,
            id=culprit_entity.gitiles_id,
            commit_position=culprit_entity.commit_position))
    culprits.append(culprit_message)
  return culprits
