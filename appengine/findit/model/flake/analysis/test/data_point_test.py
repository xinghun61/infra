# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from datetime import datetime
from model.flake.analysis.data_point import DataPoint
from waterfall.test import wf_testcase


class DataPointTest(wf_testcase.WaterfallTestCase):

  def testGetPassCount(self):
    self.assertEqual(
        0,
        DataPoint.Create(pass_rate=0.0, iterations=100).GetPassCount())
    self.assertEqual(
        10,
        DataPoint.Create(pass_rate=0.5, iterations=20).GetPassCount())
    self.assertEqual(
        429,
        DataPoint.Create(pass_rate=0.9976744186046511,
                         iterations=430).GetPassCount())

  def testGetSwarmingTaskId(self):
    task_ids = ['a', 'b', 'c']
    data_point = DataPoint.Create(task_ids=task_ids)
    self.assertEqual(data_point.GetSwarmingTaskId(), 'c')

  def testCreateAndSave(self):
    gitiles_project = 'chromium/src'
    bucket = 'ci'
    builder_name = 'b'
    step_name = 's'
    test_name = 't'
    git_hash = 'a1b2c3'
    legacy_master_name = 'm'
    build_number = 123
    build_url = 'build_url'
    pass_rate = 0.5
    task_ids = ['task']
    commit_position = 1000
    try_job_url = 'try_job_url'
    iterations = 100
    elapsed_seconds = 300
    error = None
    commit_timestamp = datetime(2018, 12, 4)
    failed_swarming_task_attempts = 0

    data_point = DataPoint.CreateAndSave(
        gitiles_project,
        bucket,
        builder_name,
        step_name,
        test_name,
        git_hash,
        legacy_master_name=legacy_master_name,
        build_number=build_number,
        build_url=build_url,
        pass_rate=pass_rate,
        task_ids=task_ids,
        commit_position=commit_position,
        try_job_url=try_job_url,
        iterations=iterations,
        elapsed_seconds=elapsed_seconds,
        error=error,
        commit_timestamp=commit_timestamp,
        failed_swarming_task_attempts=failed_swarming_task_attempts)

    self.assertEqual(
        data_point,
        DataPoint.Get(gitiles_project, bucket, builder_name, step_name,
                      test_name, git_hash))
    self.assertEqual(legacy_master_name, data_point.legacy_master_name)
    self.assertEqual(build_number, data_point.build_number)
    self.assertEqual(build_url, data_point.build_url)
    self.assertEqual(pass_rate, data_point.pass_rate)
    self.assertEqual(task_ids, data_point.task_ids)
    self.assertEqual(commit_position, data_point.commit_position)
    self.assertEqual(try_job_url, data_point.try_job_url)
    self.assertEqual(iterations, data_point.iterations)
    self.assertEqual(elapsed_seconds, data_point.elapsed_seconds)
    self.assertEqual(error, data_point.error)
    self.assertEqual(commit_timestamp, data_point.commit_timestamp)
    self.assertEqual(failed_swarming_task_attempts,
                     data_point.failed_swarming_task_attempts)

  def testGet(self):
    gitiles_project = 'chromium/src'
    bucket = 'ci'
    builder_name = 'b'
    step_name = 's'
    test_name = 't'
    git_hash = 'a1b2c3'
    data_point = DataPoint(
        key=DataPoint._CreateKey(gitiles_project, bucket, builder_name,
                                 step_name, test_name, git_hash))
    data_point.put()

    self.assertIsNone(
        DataPoint.Get(gitiles_project, bucket, builder_name, step_name,
                      test_name, 'wrong_hash'))
    self.assertEqual(
        data_point,
        DataPoint.Get(gitiles_project, bucket, builder_name, step_name,
                      test_name, git_hash))
