# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from google.appengine.ext import ndb

from dto.flake_swarming_task_output import FlakeSwarmingTaskOutput
from dto.swarming_task_error import SwarmingTaskError
from dto.update_flake_analysis_data_points_input import (
    UpdateFlakeAnalysisDataPointsInput)
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from services.flake_failure import data_point_util
from waterfall.build_info import BuildInfo
from waterfall.flake import flake_constants
from waterfall.test import wf_testcase


class DataPointUtilTest(wf_testcase.WaterfallTestCase):

  def testGetMaximumIterationsToRunPerDataPoint(self):
    self.assertEqual(flake_constants.DEFAULT_MAX_ITERATIONS_TO_RERUN,
                     data_point_util.GetMaximumIterationsToRunPerDataPoint())

  def testGetMaximumSwarmingTaskRetriesPerDataPoint(self):
    self.assertEqual(
        flake_constants.DEFAULT_MAX_SWARMING_TASK_RETRIES_PER_DATA_POINT,
        data_point_util.GetMaximumSwarmingTaskRetriesPerDataPoint())

  def testHasSeriesOfFullyStablePointsPrecedingCommitPosition(self):
    self.assertFalse(  # Not enough data points.
        data_point_util.HasSeriesOfFullyStablePointsPrecedingCommitPosition(
            [], 100, 1))
    self.assertFalse(  # Not enough data points in a row.
        data_point_util.HasSeriesOfFullyStablePointsPrecedingCommitPosition([
            DataPoint.Create(pass_rate=1.0, commit_position=10),
            DataPoint.Create(pass_rate=1.0, commit_position=11),
            DataPoint.Create(pass_rate=0.4, commit_position=12),
        ], 12, 3))
    self.assertFalse(  # Not all data points fully stable.
        data_point_util.HasSeriesOfFullyStablePointsPrecedingCommitPosition([
            DataPoint.Create(pass_rate=1.0, commit_position=10),
            DataPoint.Create(pass_rate=0.99, commit_position=11),
            DataPoint.Create(pass_rate=1.0, commit_position=12),
            DataPoint.Create(pass_rate=0.4, commit_position=13),
        ], 13, 3))
    self.assertFalse(  # Preceding data points must be of the same stable type.
        data_point_util.HasSeriesOfFullyStablePointsPrecedingCommitPosition([
            DataPoint.Create(pass_rate=1.0, commit_position=10),
            DataPoint.Create(pass_rate=0.0, commit_position=11),
            DataPoint.Create(pass_rate=1.0, commit_position=12),
            DataPoint.Create(pass_rate=0.4, commit_position=13),
        ], 13, 3))
    self.assertTrue(  # All stable passing.
        data_point_util.HasSeriesOfFullyStablePointsPrecedingCommitPosition([
            DataPoint.Create(pass_rate=1.0, commit_position=10),
            DataPoint.Create(pass_rate=1.0, commit_position=11),
            DataPoint.Create(pass_rate=1.0, commit_position=12),
            DataPoint.Create(pass_rate=0.4, commit_position=13),
        ], 13, 3))
    self.assertTrue(  # All stable failing.
        data_point_util.HasSeriesOfFullyStablePointsPrecedingCommitPosition([
            DataPoint.Create(pass_rate=0.0, commit_position=10),
            DataPoint.Create(pass_rate=0.0, commit_position=11),
            DataPoint.Create(pass_rate=0.0, commit_position=12),
            DataPoint.Create(pass_rate=0.4, commit_position=13),
        ], 13, 3))
    self.assertTrue(  # Stable failing, stable passing, stable failing.
        data_point_util.HasSeriesOfFullyStablePointsPrecedingCommitPosition([
            DataPoint.Create(pass_rate=0.0, commit_position=10),
            DataPoint.Create(pass_rate=1.0, commit_position=11),
            DataPoint.Create(pass_rate=0.0, commit_position=12),
            DataPoint.Create(pass_rate=0.0, commit_position=13),
            DataPoint.Create(pass_rate=0.0, commit_position=14),
            DataPoint.Create(pass_rate=0.0, commit_position=15),
        ], 15, 3))
    self.assertTrue(
        data_point_util.HasSeriesOfFullyStablePointsPrecedingCommitPosition([
            DataPoint.Create(pass_rate=0.0, commit_position=10),
            DataPoint.Create(pass_rate=0.0, commit_position=11),
            DataPoint.Create(pass_rate=0.0, commit_position=12),
        ], 13, 3))

  @mock.patch.object(
      data_point_util,
      'GetMaximumSwarmingTaskRetriesPerDataPoint',
      return_value=3)
  def testMaximumSwarmingTaskRetriesReached(self, _):
    data_point = DataPoint.Create(failed_swarming_task_attempts=4)
    self.assertTrue(
        data_point_util.MaximumSwarmingTaskRetriesReached(data_point))

  @mock.patch.object(
      data_point_util,
      'GetMaximumIterationsToRunPerDataPoint',
      return_value=100)
  def testMaximumIterationsPerDataPointReached(self, _):
    self.assertTrue(data_point_util.MaximumIterationsPerDataPointReached(150))

  def testUpdateFailedSwarmingTaskAttempts(self):
    data_point = DataPoint.Create(failed_swarming_task_attempts=1)
    data_point_util.UpdateFailedSwarmingTaskAttempts(data_point)
    self.assertEqual(2, data_point.failed_swarming_task_attempts)

  def testUpdateAnalysisDataPointsNewDataPointWithError(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.Save()

    commit_position = 1000
    completed_time = datetime(2018, 1, 1, 1, 0, 0)
    error = SwarmingTaskError(code=1, message='message')
    iterations = None
    pass_count = None
    revision = 'r1000'
    started_time = datetime(2018, 1, 1, 0, 0, 0)
    task_id = 'task_id'
    build_url = 'url'
    try_job_url = None

    swarming_task_output = FlakeSwarmingTaskOutput(
        completed_time=completed_time,
        error=error,
        iterations=iterations,
        pass_count=pass_count,
        started_time=started_time,
        task_id=task_id)

    update_data_points_input = UpdateFlakeAnalysisDataPointsInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=commit_position,
        build_url=build_url,
        revision=revision,
        swarming_task_output=swarming_task_output,
        try_job_url=try_job_url)

    data_point_util.UpdateAnalysisDataPoints(update_data_points_input)

    analysis = ndb.Key(urlsafe=analysis.key.urlsafe()).get()
    data_points = analysis.data_points
    data_point = data_points[0]

    self.assertEqual(1, len(data_points))
    self.assertEqual(commit_position, data_point.commit_position)
    self.assertEqual(revision, data_point.git_hash)
    self.assertIsNone(data_point.pass_rate)
    self.assertIsNone(data_point.elapsed_seconds)
    self.assertEqual(1, data_point.failed_swarming_task_attempts)
    self.assertEqual([task_id], data_point.task_ids)

  def testUpdateAnalysisDataPointsNewDataPointWithErrorButSalvagable(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.Save()

    commit_position = 1000
    completed_time = datetime(2018, 1, 1, 0, 1, 0)
    error = SwarmingTaskError(code=1, message='message')
    iterations = 100
    pass_count = 50
    revision = 'r1000'
    started_time = datetime(2018, 1, 1, 0, 0, 0)
    task_id = 'task_id'
    build_url = None
    try_job_url = 'url'

    lower_bound_build = BuildInfo('m', 'b', 122)
    lower_bound_build.commit_position = 998
    lower_bound_build.chromium_revision = 'r998'
    upper_bound_build = BuildInfo('m', 'b', 123)
    upper_bound_build.commit_position = 1000
    upper_bound_build.chromium_revision = 'r1000'

    swarming_task_output = FlakeSwarmingTaskOutput(
        completed_time=completed_time,
        error=error,
        iterations=iterations,
        pass_count=pass_count,
        started_time=started_time,
        task_id=task_id)

    update_data_points_input = UpdateFlakeAnalysisDataPointsInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=commit_position,
        build_url=build_url,
        revision=revision,
        swarming_task_output=swarming_task_output,
        try_job_url=try_job_url)

    data_point_util.UpdateAnalysisDataPoints(update_data_points_input)

    analysis = ndb.Key(urlsafe=analysis.key.urlsafe()).get()
    data_points = analysis.data_points
    data_point = data_points[0]

    self.assertEqual(1, len(data_points))
    self.assertEqual(commit_position, data_point.commit_position)
    self.assertEqual(revision, data_point.git_hash)
    self.assertEqual(.5, data_point.pass_rate)
    self.assertEqual(60, data_point.elapsed_seconds)
    self.assertEqual(0, data_point.failed_swarming_task_attempts)
    self.assertEqual([task_id], data_point.task_ids)

  def testUpdateAnalysisDataPointsNewDataPointNoError(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.Save()

    commit_position = 1000
    completed_time = datetime(2018, 1, 1, 1, 0, 0)
    error = None
    iterations = 100
    pass_count = 60
    revision = 'r1000'
    started_time = datetime(2018, 1, 1, 0, 0, 0)
    task_id = 'task_id'
    build_url = 'url'
    try_job_url = 'try_job_url'

    swarming_task_output = FlakeSwarmingTaskOutput(
        completed_time=completed_time,
        error=error,
        iterations=iterations,
        pass_count=pass_count,
        started_time=started_time,
        task_id=task_id)

    update_data_points_input = UpdateFlakeAnalysisDataPointsInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=commit_position,
        build_url=build_url,
        revision=revision,
        swarming_task_output=swarming_task_output,
        try_job_url=try_job_url)

    data_point_util.UpdateAnalysisDataPoints(update_data_points_input)

    analysis = ndb.Key(urlsafe=analysis.key.urlsafe()).get()
    data_points = analysis.data_points
    data_point = data_points[0]

    self.assertEqual(1, len(data_points))
    self.assertEqual(commit_position, data_point.commit_position)
    self.assertEqual(revision, data_point.git_hash)
    self.assertEqual(0.6, data_point.pass_rate)
    self.assertEqual(3600, data_point.elapsed_seconds)
    self.assertEqual(0, data_point.failed_swarming_task_attempts)
    self.assertEqual([task_id], data_point.task_ids)

  def testUpdateAnalysisDataPointsExistingDataPointWithError(self):
    commit_position = 1000
    revision = 'r1000'
    iterations = 100
    pass_count = None
    failed_swarming_task_attempts = 2
    completed_time = datetime(2018, 1, 1, 1, 0, 0)
    error = SwarmingTaskError(code=1, message='m')
    started_time = datetime(2018, 1, 1, 0, 0, 0)
    task_id = 'task_2'
    build_url = 'url'
    try_job_url = None

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(
            commit_position=commit_position,
            git_hash=revision,
            pass_rate=0.5,
            iterations=iterations,
            elapsed_seconds=1800,
            failed_swarming_task_attempts=failed_swarming_task_attempts,
            task_ids=['task_1'])
    ]
    analysis.Save()

    swarming_task_output = FlakeSwarmingTaskOutput(
        completed_time=completed_time,
        error=error,
        iterations=iterations,
        pass_count=pass_count,
        started_time=started_time,
        task_id=task_id)

    update_data_points_input = UpdateFlakeAnalysisDataPointsInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=commit_position,
        build_url=build_url,
        revision=revision,
        swarming_task_output=swarming_task_output,
        try_job_url=try_job_url)

    data_point_util.UpdateAnalysisDataPoints(update_data_points_input)

    analysis = ndb.Key(urlsafe=analysis.key.urlsafe()).get()
    data_points = analysis.data_points
    data_point = data_points[0]

    self.assertEqual(1, len(data_points))
    self.assertEqual(commit_position, data_point.commit_position)
    self.assertEqual(revision, data_point.git_hash)
    self.assertEqual(0.5, data_point.pass_rate)
    self.assertEqual(1800, data_point.elapsed_seconds)
    self.assertEqual(3, data_point.failed_swarming_task_attempts)
    self.assertEqual(['task_1', 'task_2'], data_point.task_ids)

  def testUpdateAnalysisDataPointsExistingDataPointWithErrorSalvagable(self):
    commit_position = 1000
    revision = 'r1000'
    iterations = 100
    pass_count = 50
    completed_time = datetime(2018, 1, 1, 1, 0, 0)
    error = SwarmingTaskError(code=1, message='m')
    started_time = datetime(2018, 1, 1, 0, 0, 0)
    task_id = 'task_2'
    build_url = None
    try_job_url = 'url'

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(
            commit_position=commit_position,
            git_hash=revision,
            pass_rate=0,
            iterations=0,
            elapsed_seconds=0,
            failed_swarming_task_attempts=0,
            task_ids=['task_1'])
    ]
    analysis.Save()

    swarming_task_output = FlakeSwarmingTaskOutput(
        completed_time=completed_time,
        error=error,
        iterations=iterations,
        pass_count=pass_count,
        started_time=started_time,
        task_id=task_id)

    update_data_points_input = UpdateFlakeAnalysisDataPointsInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=commit_position,
        build_url=build_url,
        revision=revision,
        swarming_task_output=swarming_task_output,
        try_job_url=try_job_url)

    data_point_util.UpdateAnalysisDataPoints(update_data_points_input)

    analysis = ndb.Key(urlsafe=analysis.key.urlsafe()).get()
    data_points = analysis.data_points
    data_point = data_points[0]

    self.assertEqual(1, len(data_points))
    self.assertEqual(commit_position, data_point.commit_position)
    self.assertEqual(revision, data_point.git_hash)
    self.assertEqual(0.5, data_point.pass_rate)
    self.assertEqual(3600, data_point.elapsed_seconds)
    self.assertEqual(0, data_point.failed_swarming_task_attempts)
    self.assertEqual(['task_1', 'task_2'], data_point.task_ids)

  def testUpdateAnalysisDataPointsExistingDataPointWithErrorNoTaskId(self):
    commit_position = 1000
    revision = 'r1000'
    iterations = 100
    pass_count = 60
    failed_swarming_task_attempts = 2
    completed_time = datetime(2018, 1, 1, 1, 0, 0)
    error = SwarmingTaskError(code=1, message='m')
    started_time = datetime(2018, 1, 1, 0, 0, 0)
    task_id = None
    build_url = 'url'
    try_job_url = None

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(
            commit_position=commit_position,
            git_hash=revision,
            pass_rate=0.5,
            iterations=iterations,
            elapsed_seconds=1800,
            failed_swarming_task_attempts=failed_swarming_task_attempts,
            task_ids=['task_1'])
    ]
    analysis.Save()

    swarming_task_output = FlakeSwarmingTaskOutput(
        completed_time=completed_time,
        error=error,
        iterations=iterations,
        pass_count=pass_count,
        started_time=started_time,
        task_id=task_id)

    update_data_points_input = UpdateFlakeAnalysisDataPointsInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=commit_position,
        build_url=build_url,
        revision=revision,
        swarming_task_output=swarming_task_output,
        try_job_url=try_job_url)

    data_point_util.UpdateAnalysisDataPoints(update_data_points_input)

    analysis = ndb.Key(urlsafe=analysis.key.urlsafe()).get()
    data_points = analysis.data_points
    data_point = data_points[0]

    self.assertEqual(1, len(data_points))
    self.assertEqual(commit_position, data_point.commit_position)
    self.assertEqual(revision, data_point.git_hash)
    self.assertEqual(0.5, data_point.pass_rate)
    self.assertEqual(1800, data_point.elapsed_seconds)
    self.assertEqual(3, data_point.failed_swarming_task_attempts)
    self.assertEqual(['task_1'], data_point.task_ids)

  def testUpdateAnalysisDataPointsExistingDataPointNoError(self):
    commit_position = 1000
    revision = 'r1000'
    iterations = 100
    pass_count = 60
    failed_swarming_task_attempts = 2
    completed_time = datetime(2018, 1, 1, 1, 0, 0)
    error = None
    started_time = datetime(2018, 1, 1, 0, 0, 0)
    task_id = 'task_2'
    build_url = None
    try_job_url = 'url'

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(
            commit_position=commit_position,
            git_hash=revision,
            pass_rate=0.5,
            iterations=iterations,
            elapsed_seconds=1800,
            failed_swarming_task_attempts=failed_swarming_task_attempts,
            task_ids=['task_1'])
    ]
    analysis.Save()

    swarming_task_output = FlakeSwarmingTaskOutput(
        completed_time=completed_time,
        error=error,
        iterations=iterations,
        pass_count=pass_count,
        started_time=started_time,
        task_id=task_id)

    update_data_points_input = UpdateFlakeAnalysisDataPointsInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=commit_position,
        build_url=build_url,
        revision=revision,
        swarming_task_output=swarming_task_output,
        try_job_url=try_job_url)

    data_point_util.UpdateAnalysisDataPoints(update_data_points_input)

    analysis = ndb.Key(urlsafe=analysis.key.urlsafe()).get()
    data_points = analysis.data_points
    data_point = data_points[0]

    self.assertEqual(1, len(data_points))
    self.assertEqual(commit_position, data_point.commit_position)
    self.assertEqual(revision, data_point.git_hash)
    self.assertEqual(0.55, data_point.pass_rate)
    self.assertEqual(5400, data_point.elapsed_seconds)
    self.assertEqual(failed_swarming_task_attempts,
                     data_point.failed_swarming_task_attempts)
    self.assertEqual(['task_1', 'task_2'], data_point.task_ids)
