# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from dto.flake_swarming_task_output import FlakeSwarmingTaskOutput
from dto.flakiness import Flakiness
from dto.swarming_task_error import SwarmingTaskError
from libs.list_of_basestring import ListOfBasestring
from services.flake_failure import flake_analysis_util
from services.flake_failure import flake_constants
from services.flake_failure import flakiness_util
from waterfall.test import wf_testcase


class FlakinessUtilTest(wf_testcase.WaterfallTestCase):

  def testGetMaximumIterationsToRun(self):
    self.assertEqual(flake_constants.DEFAULT_MAX_ITERATIONS_TO_RERUN,
                     flakiness_util._GetMaximumIterationsToRun())

  def testGetMaximumSwarmingTaskRetries(self):
    self.assertEqual(
        flake_constants.DEFAULT_MAX_SWARMING_TASK_RETRIES_PER_DATA_POINT,
        flakiness_util._GetMaximumSwarmingTaskRetries())

  @mock.patch.object(
      flakiness_util, '_GetMaximumSwarmingTaskRetries', return_value=3)
  def testMaximumSwarmingTaskRetriesReached(self, _):
    flakiness = Flakiness(failed_swarming_task_attempts=4)
    self.assertTrue(flakiness_util.MaximumSwarmingTaskRetriesReached(flakiness))

  @mock.patch.object(
      flakiness_util, '_GetMaximumIterationsToRun', return_value=100)
  def testMaximumIterationsReached(self, _):
    flakiness = Flakiness(iterations=150)
    self.assertTrue(flakiness_util.MaximumIterationsReached(flakiness))

  def testUpdateFlakiness(self):
    flakiness = Flakiness(
        build_number=None,
        build_url='url',
        commit_position=1000,
        total_test_run_seconds=0,
        error=None,
        failed_swarming_task_attempts=0,
        iterations=0,
        pass_rate=None,
        revision='r1000',
        try_job_url=None,
        task_ids=ListOfBasestring.FromSerializable([]))

    self.assertEqual(flakiness, flakiness_util.UpdateFlakiness(flakiness, None))

  @mock.patch.object(
      flake_analysis_util,
      'CanFailedSwarmingTaskBeSalvaged',
      return_value=False)
  def testUpdateFlakinessWithErrorUnsalvagable(self, _):
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

    flakiness_to_update = Flakiness(
        build_number=None,
        build_url=build_url,
        commit_position=commit_position,
        total_test_run_seconds=0,
        error=None,
        failed_swarming_task_attempts=0,
        iterations=0,
        pass_rate=None,
        revision=revision,
        try_job_url=try_job_url,
        task_ids=ListOfBasestring.FromSerializable([]))

    expected_flakiness = Flakiness(
        build_number=None,
        build_url=build_url,
        commit_position=commit_position,
        total_test_run_seconds=0,
        error=None,
        failed_swarming_task_attempts=1,
        iterations=0,
        pass_rate=None,
        revision=revision,
        try_job_url=try_job_url,
        task_ids=ListOfBasestring.FromSerializable([task_id]))

    resulting_flakiness = flakiness_util.UpdateFlakiness(
        flakiness_to_update, swarming_task_output)

    self.assertEqual(expected_flakiness, resulting_flakiness)

  def testUpdateFlakinessNewFlakinessWithErrorButSalvagable(self):
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

    swarming_task_output = FlakeSwarmingTaskOutput(
        completed_time=completed_time,
        error=error,
        iterations=iterations,
        pass_count=pass_count,
        started_time=started_time,
        task_id=task_id)

    initial_flakiness = Flakiness(
        build_number=None,
        build_url=build_url,
        commit_position=commit_position,
        total_test_run_seconds=None,
        error=None,
        failed_swarming_task_attempts=0,
        iterations=None,
        pass_rate=None,
        revision=revision,
        try_job_url=try_job_url,
        task_ids=ListOfBasestring.FromSerializable([]))

    expected_flakiness = Flakiness(
        build_number=None,
        build_url=build_url,
        commit_position=commit_position,
        total_test_run_seconds=60,
        error=None,
        failed_swarming_task_attempts=0,
        iterations=iterations,
        pass_rate=0.5,
        revision=revision,
        try_job_url=try_job_url,
        task_ids=ListOfBasestring.FromSerializable([task_id]))

    resulting_flakiness = flakiness_util.UpdateFlakiness(
        initial_flakiness, swarming_task_output)

    self.assertEqual(expected_flakiness, resulting_flakiness)

  def testUpdateFlakinessNewFlakinessNoError(self):
    commit_position = 1000
    completed_time = datetime(2018, 1, 1, 0, 1, 0)
    error = None
    iterations = 100
    pass_count = 50
    revision = 'r1000'
    started_time = datetime(2018, 1, 1, 0, 0, 0)
    task_id = 'task_id'
    build_url = None
    try_job_url = 'url'

    swarming_task_output = FlakeSwarmingTaskOutput(
        completed_time=completed_time,
        error=error,
        iterations=iterations,
        pass_count=pass_count,
        started_time=started_time,
        task_id=task_id)

    initial_flakiness = Flakiness(
        build_number=None,
        build_url=build_url,
        commit_position=commit_position,
        total_test_run_seconds=None,
        error=None,
        failed_swarming_task_attempts=0,
        iterations=None,
        pass_rate=None,
        revision=revision,
        try_job_url=try_job_url,
        task_ids=ListOfBasestring.FromSerializable([]))

    expected_flakiness = Flakiness(
        build_number=None,
        build_url=build_url,
        commit_position=commit_position,
        total_test_run_seconds=60,
        error=None,
        failed_swarming_task_attempts=0,
        iterations=iterations,
        pass_rate=0.5,
        revision=revision,
        try_job_url=try_job_url,
        task_ids=ListOfBasestring.FromSerializable([task_id]))

    resulting_flakiness = flakiness_util.UpdateFlakiness(
        initial_flakiness, swarming_task_output)

    self.assertEqual(expected_flakiness, resulting_flakiness)

  @mock.patch.object(
      flake_analysis_util,
      'CanFailedSwarmingTaskBeSalvaged',
      return_value=False)
  def testUpdateExistingFlakinessWithErrorUnsalvagable(self, _):
    commit_position = 1000
    revision = 'r1000'
    iterations = 100
    pass_count = None
    completed_time = datetime(2018, 1, 1, 0, 1, 0)
    error = SwarmingTaskError(code=1, message='m')
    started_time = datetime(2018, 1, 1, 0, 0, 0)
    task_id_1 = 'task_1'
    task_id_2 = 'task_2'
    build_url = 'url'
    try_job_url = None

    swarming_task_output = FlakeSwarmingTaskOutput(
        completed_time=completed_time,
        error=error,
        iterations=iterations,
        pass_count=pass_count,
        started_time=started_time,
        task_id=task_id_2)

    initial_flakiness = Flakiness(
        build_number=None,
        build_url=build_url,
        commit_position=commit_position,
        total_test_run_seconds=60,
        error=None,
        failed_swarming_task_attempts=0,
        iterations=None,
        pass_rate=0.5,
        revision=revision,
        try_job_url=try_job_url,
        task_ids=ListOfBasestring.FromSerializable([task_id_1]))

    expected_flakiness = Flakiness(
        build_number=None,
        build_url=build_url,
        commit_position=commit_position,
        total_test_run_seconds=60,  # No change due to unrecoverable error.
        error=None,  # Only set error if no more retries.
        failed_swarming_task_attempts=1,
        iterations=None,  # No change to iterations.
        pass_rate=0.5,  # No change to pass rate.
        revision=revision,
        try_job_url=try_job_url,
        task_ids=ListOfBasestring.FromSerializable([task_id_1, task_id_2]))

    resulting_flakiness = flakiness_util.UpdateFlakiness(
        initial_flakiness, swarming_task_output)

    self.assertEqual(expected_flakiness, resulting_flakiness)

  @mock.patch.object(
      flake_analysis_util, 'CanFailedSwarmingTaskBeSalvaged', return_value=True)
  def testUpdateExistingFlakinessWithErrorWithSuccessfulRun(self, _):
    commit_position = 1000
    revision = 'r1000'
    iterations = 10
    pass_count = 5
    completed_time = datetime(2018, 1, 1, 0, 1, 0)
    started_time = datetime(2018, 1, 1, 0, 0, 0)
    task_id_1 = 'task_1'
    task_id_2 = 'task_2'
    build_url = 'url'
    try_job_url = None

    swarming_task_output = FlakeSwarmingTaskOutput(
        completed_time=completed_time,
        error=None,
        iterations=iterations,
        pass_count=pass_count,
        started_time=started_time,
        task_id=task_id_2)

    # Simulate first run failing.
    initial_flakiness = Flakiness(
        build_number=None,
        build_url=build_url,
        commit_position=commit_position,
        total_test_run_seconds=60,
        error=None,
        failed_swarming_task_attempts=1,
        iterations=0,
        pass_rate=None,
        revision=revision,
        try_job_url=try_job_url,
        task_ids=ListOfBasestring.FromSerializable([task_id_1]))

    expected_flakiness = Flakiness(
        build_number=None,
        build_url=build_url,
        commit_position=commit_position,
        total_test_run_seconds=120,  # No change due to unrecoverable error.
        error=None,
        failed_swarming_task_attempts=1,
        iterations=10,
        pass_rate=0.5,
        revision=revision,
        try_job_url=try_job_url,
        task_ids=ListOfBasestring.FromSerializable([task_id_1, task_id_2]))

    resulting_flakiness = flakiness_util.UpdateFlakiness(
        initial_flakiness, swarming_task_output)

    self.assertEqual(expected_flakiness, resulting_flakiness)

  @mock.patch.object(
      flake_analysis_util, 'CanFailedSwarmingTaskBeSalvaged', return_value=True)
  def testUpdateAnalysisDataPointsExistingDataPointWithErrorSalvagable(self, _):
    commit_position = 1000
    revision = 'r1000'
    iterations = 100
    pass_count = 50
    completed_time = datetime(2018, 1, 1, 0, 1, 0)
    error = SwarmingTaskError(code=1, message='m')
    started_time = datetime(2018, 1, 1, 0, 0, 0)
    task_id_1 = 'task_1'
    task_id_2 = 'task_2'
    build_url = 'url'
    try_job_url = None

    swarming_task_output = FlakeSwarmingTaskOutput(
        completed_time=completed_time,
        error=error,
        iterations=iterations,
        pass_count=pass_count,
        started_time=started_time,
        task_id=task_id_2)

    initial_flakiness = Flakiness(
        build_number=None,
        build_url=build_url,
        commit_position=commit_position,
        total_test_run_seconds=60,
        error=None,
        failed_swarming_task_attempts=0,
        iterations=50,
        pass_rate=0.5,
        revision=revision,
        try_job_url=try_job_url,
        task_ids=ListOfBasestring.FromSerializable([task_id_1]))

    expected_flakiness = Flakiness(
        build_number=None,
        build_url=build_url,
        commit_position=commit_position,
        total_test_run_seconds=120,
        error=None,  # Only set error if no more retries.
        failed_swarming_task_attempts=0,  # Task was salvaged.
        iterations=150,
        pass_rate=0.5,
        revision=revision,
        try_job_url=try_job_url,
        task_ids=ListOfBasestring.FromSerializable([task_id_1, task_id_2]))

    resulting_flakiness = flakiness_util.UpdateFlakiness(
        initial_flakiness, swarming_task_output)

    self.assertEqual(expected_flakiness, resulting_flakiness)

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

    initial_flakiness = Flakiness(
        build_number=None,
        build_url=build_url,
        commit_position=commit_position,
        total_test_run_seconds=1800,
        error=None,
        failed_swarming_task_attempts=failed_swarming_task_attempts,
        iterations=iterations,
        pass_rate=0.5,
        revision=revision,
        try_job_url=try_job_url,
        task_ids=ListOfBasestring.FromSerializable(['task_1']))

    swarming_task_output = FlakeSwarmingTaskOutput(
        completed_time=completed_time,
        error=error,
        iterations=iterations,
        pass_count=pass_count,
        started_time=started_time,
        task_id=task_id)

    resulting_flakiness = flakiness_util.UpdateFlakiness(
        initial_flakiness, swarming_task_output)

    expected_flakiness = Flakiness(
        build_number=None,
        build_url=build_url,
        commit_position=commit_position,
        total_test_run_seconds=5400,
        error=None,
        failed_swarming_task_attempts=failed_swarming_task_attempts,
        iterations=200,
        pass_rate=0.55,
        revision=revision,
        task_ids=ListOfBasestring.FromSerializable(['task_1', 'task_2']),
        try_job_url=try_job_url)

    self.assertEqual(expected_flakiness, resulting_flakiness)
