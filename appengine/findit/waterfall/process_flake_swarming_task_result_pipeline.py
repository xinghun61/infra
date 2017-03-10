# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from gae_libs.http.http_client_appengine import HttpClientAppengine
from model.flake.flake_swarming_task import FlakeSwarmingTask
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall import build_util
from waterfall.process_base_swarming_task_result_pipeline import (
    ProcessBaseSwarmingTaskResultPipeline)


_CHROMIUM_REPO_URL = 'https://chromium.googlesource.com/chromium/src.git'


def _GetCommitsBetweenRevisions(start_revision, end_revision):
  """Gets the revisions between start_revision and end_revision.

  Args:
    start_revision (str): The revision for which to get changes after. This
        revision is not included in the returned list.
    end_revision (str): The last revision in the range to return.

  Returns:
    A list of revisions sorted in order by oldest to newest.
  """
  repo = CachedGitilesRepository(HttpClientAppengine(), _CHROMIUM_REPO_URL)
  commits = repo.GetCommitsBetweenRevisions(start_revision, end_revision)
  commits.reverse()
  return commits


class ProcessFlakeSwarmingTaskResultPipeline(
    ProcessBaseSwarmingTaskResultPipeline):
  """A pipeline for monitoring swarming task and processing task result.

  This pipeline waits for result for a swarming task and processes the result to
  generate a dict for statuses for each test run.
  """

  def _UpdateMasterFlakeAnalysis(
      self, master_name, builder_name, build_number, step_name,
      master_build_number, test_name, version_number, pass_rate,
      flake_swarming_task):
    """Update MasterFlakeAnalysis to include result of the swarming task."""
    master_flake_analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, master_build_number, step_name, test_name,
        version=version_number)
    logging.info(
        'Updating MasterFlakeAnalysis data %s/%s/%s/%s/%s',
        master_name, builder_name, master_build_number, step_name, test_name)

    logging.info('MasterFlakeAnalysis %s version %s',
                 master_flake_analysis, master_flake_analysis.version_number)

    data_point = DataPoint()
    data_point.build_number = build_number
    data_point.pass_rate = pass_rate
    data_point.task_id = flake_swarming_task.task_id

    # Include git information about each build that was run.
    build_info = build_util.GetBuildInfo(
        master_name, builder_name, build_number)
    data_point.commit_position = build_info.commit_position
    data_point.git_hash = build_info.chromium_revision

    if build_number > 0:
      previous_build = build_util.GetBuildInfo(
          master_name, builder_name, build_number - 1)
      data_point.previous_build_commit_position = previous_build.commit_position
      data_point.previous_build_git_hash = previous_build.chromium_revision
      data_point.blame_list = _GetCommitsBetweenRevisions(
          previous_build.chromium_revision, build_info.chromium_revision)
    else:
      data_point.blame_list = build_info.blame_list

    master_flake_analysis.data_points.append(data_point)

    results = flake_swarming_task.GetFlakeSwarmingTaskData()
    # TODO(lijeffrey): Determine whether or not this flake swarming task
    # was a cache hit (already ran results for more iterations than were
    # requested) and update results['cache_hit'] accordingly.
    master_flake_analysis.swarming_rerun_results.append(results)
    master_flake_analysis.put()

  # Arguments number differs from overridden method - pylint: disable=W0221
  def _CheckTestsRunStatuses(self, output_json, master_name,
                             builder_name, build_number, step_name,
                             master_build_number, test_name, version_number):
    """Checks result status for each test run and saves the numbers accordingly.

    Args:
      output_json (dict): A dict of all test results in the swarming task.
      master_name (string): Name of master of swarming rerun.
      builder_name (dict): Name of builder of swarming rerun.
      build_number (int): Build Number of swarming rerun.
      step_name (dict): Name of step of swarming rerun.
      master_build_number (int): Build number of corresponding mfa.
      test_name (string): Name of test of swarming rerun.
      version_number (int): The version to save analysis results and ` to.

    Returns:
      tests_statuses (dict): A dict of different statuses for each test.

    Currently for each test, we are saving number of total runs,
    number of succeeded runs and number of failed runs.
    """

    # Should query by test name, because some test has dependencies which
    # are also run, like TEST and PRE_TEST in browser_tests.
    tests_statuses = super(ProcessFlakeSwarmingTaskResultPipeline,
                           self)._CheckTestsRunStatuses(output_json)

    tries = tests_statuses.get(test_name, {}).get('total_run', 0)
    successes = tests_statuses.get(test_name, {}).get('SUCCESS', 0)

    if tries > 0:
      pass_rate = successes * 1.0 / tries
    else:
      pass_rate = -1  # Special value to indicate test is not existing.

    flake_swarming_task = FlakeSwarmingTask.Get(
        master_name, builder_name, build_number, step_name, test_name)
    flake_swarming_task.tries = tries
    flake_swarming_task.successes = successes
    flake_swarming_task.put()

    self._UpdateMasterFlakeAnalysis(
        master_name, builder_name, build_number, step_name, master_build_number,
        test_name, version_number, pass_rate, flake_swarming_task)

    return tests_statuses

  def _GetArgs(self, master_name, builder_name, build_number,
               step_name, *args):
    master_build_number = args[0]
    test_name = args[1]
    version_number = args[2]
    return (master_name, builder_name, build_number, step_name,
            master_build_number, test_name, version_number)

  # Unused Argument - pylint: disable=W0612,W0613
  # Arguments number differs from overridden method - pylint: disable=W0221
  def _GetSwarmingTask(self, master_name, builder_name, build_number,
                       step_name, master_build_number, test_name, _):
    # Gets the appropriate kind of swarming task (FlakeSwarmingTask).
    return FlakeSwarmingTask.Get(master_name, builder_name, build_number,
                                 step_name, test_name)
