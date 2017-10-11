# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from common.findit_http_client import FinditHttpClient
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from gae_libs.pipeline_wrapper import BasePipeline
from gae_libs.pipeline_wrapper import pipeline
from libs import analysis_status
from model.flake.flake_swarming_task import FlakeSwarmingTask
from model.flake.master_flake_analysis import DataPoint
from waterfall import build_util
from waterfall.flake import flake_constants

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
  repo = CachedGitilesRepository(FinditHttpClient(), _CHROMIUM_REPO_URL)
  commits = repo.GetCommitsBetweenRevisions(start_revision, end_revision)
  commits.reverse()
  return commits


def _GetPassRate(flake_swarming_task):
  if flake_swarming_task.tries > 0:
    return float(flake_swarming_task.successes) / flake_swarming_task.tries
  return flake_constants.PASS_RATE_TEST_NOT_FOUND


def _CreateDataPoint(flake_swarming_task):
  """Creates a DataPoint object with the fields from a flake swarming task.

  Args:
    flake_swarming_task (FlakeSwarmingTask): A completed flake swarming task
        from which to craft a DataPoint.

  Returns:
    DataPoint: A data point populated with the results of flake_swarming_task.
  """
  master_name = flake_swarming_task.master_name
  builder_name = flake_swarming_task.builder_name
  build_number = flake_swarming_task.build_number

  assert flake_swarming_task.completed_time
  assert flake_swarming_task.started_time
  assert flake_swarming_task.tries is not None

  data_point = DataPoint()
  data_point.build_number = build_number
  data_point.pass_rate = _GetPassRate(flake_swarming_task)
  data_point.task_id = flake_swarming_task.task_id
  data_point.has_valid_artifact = flake_swarming_task.has_valid_artifact
  data_point.iterations = flake_swarming_task.tries

  data_point.elapsed_seconds = int(
      (flake_swarming_task.completed_time -
       flake_swarming_task.started_time).total_seconds())

  # Include git information about each build that was run.
  build_info = build_util.GetBuildInfo(master_name, builder_name, build_number)

  if not build_info:
    raise pipeline.Retry('Failed to get build info for %s/%s/%s' %
                         (master_name, builder_name, build_number))

  data_point.commit_position = build_info.commit_position
  data_point.git_hash = build_info.chromium_revision

  if build_number > 0:
    previous_build_info = build_util.GetBuildInfo(master_name, builder_name,
                                                  build_number - 1)
    if not previous_build_info:
      raise pipeline.Retry('Failed to get build info for %s/%s/%s' %
                           (master_name, builder_name, build_number - 1))

    data_point.previous_build_commit_position = (
        previous_build_info.commit_position)
    data_point.previous_build_git_hash = previous_build_info.chromium_revision
    data_point.blame_list = _GetCommitsBetweenRevisions(
        previous_build_info.chromium_revision, build_info.chromium_revision)
  else:
    data_point.blame_list = build_info.blame_list

  return data_point


class UpdateFlakeAnalysisDataPointsPipeline(BasePipeline):
  """Updates a MasterFlakeAnalysis with results of a swarming task."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, urlsafe_analysis_key, swarming_task_build_number):
    """Updates a MasterFlakeAnalysis with results of a swarming task.

    Args:
      urlsafe_analysis_key (string): The url-safe key to the MasterFlakeAnalysis
          to update.
      swarming_task_build_number (int): The build number of the completed flake
          swarming task to update the analysis' data points with.
    """
    flake_analysis = ndb.Key(urlsafe=urlsafe_analysis_key).get()
    assert flake_analysis

    master_name = flake_analysis.master_name
    builder_name = flake_analysis.builder_name
    master_build_number = flake_analysis.build_number
    step_name = flake_analysis.step_name
    test_name = flake_analysis.test_name

    flake_swarming_task = FlakeSwarmingTask.Get(master_name, builder_name,
                                                swarming_task_build_number,
                                                step_name, test_name)
    assert flake_swarming_task

    if flake_swarming_task.status == analysis_status.ERROR:
      flake_analysis.LogWarning(
          'Swarming task failed, will not update data points')
      return

    logging.info(
        'Updating MasterFlakeAnalysis swarming task data %s/%s/%s/%s/%s',
        master_name, builder_name, master_build_number, step_name, test_name)

    data_point = _CreateDataPoint(flake_swarming_task)
    flake_analysis.AppendOrMergeDataPoint(data_point)

    results = flake_swarming_task.GetFlakeSwarmingTaskData()
    flake_analysis.swarming_rerun_results.append(results)
    flake_analysis.put()
