# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dto.flakiness import Flakiness
from libs.list_of_basestring import ListOfBasestring
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from services.flake_failure import data_point_util
from waterfall.test import wf_testcase


class DataPointUtilTest(wf_testcase.WaterfallTestCase):

  def testConvertFlakinessAndAppendToAnalysis(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.Save()

    build_url = 'url'
    commit_position = 1000
    total_test_run_seconds = 60
    failed_swarming_task_attempts = 0
    iterations = 10
    pass_rate = 0.3
    revision = 'r1000'
    try_job_url = None
    task_id = 'task_id'

    flakiness = Flakiness(
        build_url=build_url,
        commit_position=commit_position,
        total_test_run_seconds=total_test_run_seconds,
        error=None,
        failed_swarming_task_attempts=failed_swarming_task_attempts,
        iterations=iterations,
        pass_rate=pass_rate,
        revision=revision,
        try_job_url=try_job_url,
        task_ids=ListOfBasestring.FromSerializable([task_id]))

    expected_data_point = DataPoint.Create(
        build_url=build_url,
        commit_position=commit_position,
        elapsed_seconds=total_test_run_seconds,
        failed_swarming_task_attempts=failed_swarming_task_attempts,
        iterations=iterations,
        pass_rate=pass_rate,
        git_hash=revision,
        try_job_url=try_job_url,
        task_ids=[task_id])

    data_point_util.ConvertFlakinessAndAppendToAnalysis(analysis.key.urlsafe(),
                                                        flakiness)

    data_point = analysis.data_points[0]
    self.assertEqual(1, len(analysis.data_points))
    self.assertEqual(expected_data_point, data_point)

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
