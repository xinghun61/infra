# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from dto.flake_swarming_task_output import FlakeSwarmingTaskOutput
from dto.flakiness import Flakiness
from dto.swarming_task_error import SwarmingTaskError
from gae_libs import pipelines
from gae_libs.pipeline_wrapper import pipeline_handlers
from libs.list_of_basestring import ListOfBasestring
from pipelines.flake_failure.determine_approximate_pass_rate_pipeline import (
    AggregateFlakinessInput)
from pipelines.flake_failure.determine_approximate_pass_rate_pipeline import (
    AggregateFlakinessPipeline)
from pipelines.flake_failure.determine_approximate_pass_rate_pipeline import (
    DetermineApproximatePassRateInput)
from pipelines.flake_failure.determine_approximate_pass_rate_pipeline import (
    DetermineApproximatePassRatePipeline)
from pipelines.flake_failure.determine_approximate_pass_rate_pipeline import (
    DetermineApproximatePassRatePipelineWrapper)
from pipelines.flake_failure.get_isolate_sha_pipeline import (
    GetIsolateShaOutput)
from pipelines.flake_failure.run_flake_swarming_task_pipeline import (
    RunFlakeSwarmingTaskInput)
from pipelines.flake_failure.run_flake_swarming_task_pipeline import (
    RunFlakeSwarmingTaskPipeline)
from services.flake_failure import flake_constants
from services.flake_failure import flakiness_util
from services.flake_failure import pass_rate_util
from waterfall.test.wf_testcase import WaterfallTestCase


class DetermineApproximatePassRatePipelineTest(WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def testDetermineApproximatePassRateFirstRun(self):
    master_name = 'm'
    builder_name = 'b'
    reference_build_number = 123
    step_name = 's'
    test_name = 't'
    commit_position = 1000
    incoming_pass_count = 15
    iterations = 20
    isolate_sha = 'sha1'
    timeout_seconds = 3600
    revision = 'r1000'
    started_time = datetime(2018, 1, 1, 0, 0, 0)
    completed_time = datetime(2018, 1, 1, 1, 0, 0)
    build_url = 'url'
    task_id = 'task_id'
    try_job_url = None

    isolate_sha_output = GetIsolateShaOutput(
        build_number=None,
        build_url=build_url,
        isolate_sha=isolate_sha,
        try_job_url=try_job_url)

    determine_approximate_pass_rate_input = DetermineApproximatePassRateInput(
        builder_name=builder_name,
        commit_position=commit_position,
        flakiness_thus_far=None,
        get_isolate_sha_output=isolate_sha_output,
        master_name=master_name,
        previous_swarming_task_output=None,
        reference_build_number=reference_build_number,
        revision=revision,
        step_name=step_name,
        test_name=test_name)

    flake_swarming_task_input = RunFlakeSwarmingTaskInput(
        builder_name=builder_name,
        commit_position=commit_position,
        isolate_sha=isolate_sha,
        iterations=iterations,
        master_name=master_name,
        reference_build_number=reference_build_number,
        step_name=step_name,
        test_name=test_name,
        timeout_seconds=timeout_seconds)

    flake_swarming_task_output = FlakeSwarmingTaskOutput(
        error=None,
        pass_count=incoming_pass_count,
        iterations=iterations,
        completed_time=completed_time,
        started_time=started_time,
        task_id=task_id)

    initial_flakiness = Flakiness(
        build_number=None,
        build_url=build_url,
        commit_position=commit_position,
        total_test_run_seconds=0,
        error=None,
        failed_swarming_task_attempts=0,
        iterations=0,
        pass_rate=None,
        revision=revision,
        task_ids=ListOfBasestring.FromSerializable([]),
        try_job_url=try_job_url)

    expected_aggregate_flakiness_input = AggregateFlakinessInput(
        flakiness_thus_far=initial_flakiness,
        incoming_swarming_task_output=flake_swarming_task_output)

    expected_flakiness_output = Flakiness(
        build_number=None,
        build_url=build_url,
        commit_position=commit_position,
        total_test_run_seconds=3600,
        error=None,
        failed_swarming_task_attempts=0,
        iterations=iterations,
        pass_rate=0.5,
        revision=revision,
        try_job_url=try_job_url,
        task_ids=ListOfBasestring.FromSerializable([task_id]))

    recursive_input = DetermineApproximatePassRateInput(
        builder_name=builder_name,
        commit_position=commit_position,
        flakiness_thus_far=expected_flakiness_output,
        get_isolate_sha_output=isolate_sha_output,
        previous_swarming_task_output=flake_swarming_task_output,
        master_name=master_name,
        reference_build_number=reference_build_number,
        revision=revision,
        step_name=step_name,
        test_name=test_name)

    self.MockAsynchronousPipeline(RunFlakeSwarmingTaskPipeline,
                                  flake_swarming_task_input,
                                  flake_swarming_task_output)
    self.MockSynchronousPipeline(AggregateFlakinessPipeline,
                                 expected_aggregate_flakiness_input,
                                 expected_flakiness_output)
    self.MockGeneratorPipeline(DetermineApproximatePassRatePipelineWrapper,
                               recursive_input, None)

    pipeline_job = DetermineApproximatePassRatePipeline(
        determine_approximate_pass_rate_input)
    pipeline_job.start()
    self.execute_queued_tasks()

  @mock.patch.object(
      flakiness_util, 'MaximumSwarmingTaskRetriesReached', return_value=True)
  def testDetermineApproximatePassRateMaximumRetriesPerSwarmingTaskReached(
      self, _):
    master_name = 'm'
    builder_name = 'b'
    reference_build_number = 123
    step_name = 's'
    test_name = 't'
    commit_position = 1000
    incoming_pass_count = 15
    iterations = 30
    incoming_pass_rate = float(incoming_pass_count / iterations)
    isolate_sha = 'sha1'
    revision = 'r1000'
    task_id = 'task_id_2'
    started_time = datetime(2018, 1, 1, 0, 0, 0)
    completed_time = datetime(2018, 1, 1, 1, 0, 0)
    build_url = 'url'
    try_job_url = None
    swarming_task_error = SwarmingTaskError(code=1, message='error')

    isolate_sha_output = GetIsolateShaOutput(
        build_number=None,
        build_url=build_url,
        isolate_sha=isolate_sha,
        try_job_url=try_job_url)

    flakiness_thus_far = Flakiness(
        build_number=None,
        build_url=build_url,
        commit_position=commit_position,
        total_test_run_seconds=3600,
        error=None,
        failed_swarming_task_attempts=0,
        iterations=iterations,
        pass_rate=incoming_pass_rate,
        revision=revision,
        try_job_url=try_job_url,
        task_ids=ListOfBasestring.FromSerializable(['task_id_1']))

    expected_flakiness_thus_far = Flakiness(
        build_number=None,
        build_url=build_url,
        commit_position=commit_position,
        total_test_run_seconds=3600,
        error=swarming_task_error,
        failed_swarming_task_attempts=0,
        iterations=iterations,
        pass_rate=incoming_pass_rate,
        revision=revision,
        try_job_url=try_job_url,
        task_ids=ListOfBasestring.FromSerializable(['task_id_1']))

    incoming_flake_swarming_task_output = FlakeSwarmingTaskOutput(
        completed_time=completed_time,
        error=swarming_task_error,
        pass_count=incoming_pass_count,
        iterations=iterations,
        started_time=started_time,
        task_id=task_id)

    determine_approximate_pass_rate_input = DetermineApproximatePassRateInput(
        builder_name=builder_name,
        commit_position=commit_position,
        flakiness_thus_far=flakiness_thus_far,
        get_isolate_sha_output=isolate_sha_output,
        master_name=master_name,
        previous_swarming_task_output=incoming_flake_swarming_task_output,
        reference_build_number=reference_build_number,
        revision=revision,
        step_name=step_name,
        test_name=test_name)

    pipeline_job = DetermineApproximatePassRatePipeline(
        determine_approximate_pass_rate_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    pipeline_job = pipelines.pipeline.Pipeline.from_id(pipeline_job.pipeline_id)
    self.assertEqual(expected_flakiness_thus_far.ToSerializable(),
                     pipeline_job.outputs.default.value)

  @mock.patch.object(
      flakiness_util, 'MaximumIterationsReached', return_value=True)
  def testDetermineApproximatePassRateMaximumIterationsReached(self, _):
    master_name = 'm'
    builder_name = 'b'
    reference_build_number = 123
    step_name = 's'
    test_name = 't'
    commit_position = 1000
    incoming_pass_count = 15
    iterations = 30
    incoming_pass_rate = float(incoming_pass_count / iterations)
    isolate_sha = 'sha1'
    revision = 'r1000'
    task_id = 'task_id'
    started_time = datetime(2018, 1, 1, 0, 0, 0)
    completed_time = datetime(2018, 1, 1, 1, 0, 0)
    build_url = None
    try_job_url = 'url'

    isolate_sha_output = GetIsolateShaOutput(
        build_number=None,
        build_url=build_url,
        isolate_sha=isolate_sha,
        try_job_url=try_job_url)

    flakiness_thus_far = Flakiness(
        build_number=None,
        build_url=build_url,
        commit_position=commit_position,
        total_test_run_seconds=3600,
        error=None,
        failed_swarming_task_attempts=0,
        iterations=iterations,
        pass_rate=incoming_pass_rate,
        revision=revision,
        try_job_url=try_job_url,
        task_ids=ListOfBasestring.FromSerializable(['task_id_1']))

    flake_swarming_task_output = FlakeSwarmingTaskOutput(
        error=None,
        pass_count=incoming_pass_count,
        iterations=iterations,
        started_time=started_time,
        completed_time=completed_time,
        task_id=task_id)

    determine_approximate_pass_rate_input = DetermineApproximatePassRateInput(
        builder_name=builder_name,
        commit_position=commit_position,
        flakiness_thus_far=flakiness_thus_far,
        get_isolate_sha_output=isolate_sha_output,
        previous_swarming_task_output=flake_swarming_task_output,
        master_name=master_name,
        reference_build_number=reference_build_number,
        revision=revision,
        step_name=step_name,
        test_name=test_name)

    pipeline_job = DetermineApproximatePassRatePipeline(
        determine_approximate_pass_rate_input)
    pipeline_job.start()
    self.execute_queued_tasks()

  @mock.patch.object(
      flakiness_util, 'MaximumIterationsReached', return_value=False)
  @mock.patch.object(pass_rate_util, 'TestDoesNotExist', return_value=True)
  def testDetermineApproximatePassRateTestDoesNotExist(self, *_):
    master_name = 'm'
    builder_name = 'b'
    reference_build_number = 123
    step_name = 's'
    test_name = 't'
    commit_position = 1000
    incoming_pass_count = 0
    iterations = 10
    incoming_pass_rate = flake_constants.PASS_RATE_TEST_NOT_FOUND
    isolate_sha = 'sha1'
    revision = 'r1000'
    task_id = 'task_id'
    started_time = datetime(2018, 1, 1, 0, 0, 0)
    completed_time = datetime(2018, 1, 1, 1, 0, 0)
    build_url = 'url'
    try_job_url = None

    flakiness_thus_far = Flakiness(
        build_number=None,
        build_url=build_url,
        commit_position=commit_position,
        total_test_run_seconds=3600,
        error=None,
        failed_swarming_task_attempts=0,
        iterations=iterations,
        pass_rate=incoming_pass_rate,
        revision=revision,
        try_job_url=try_job_url,
        task_ids=ListOfBasestring.FromSerializable(['task_id_1']))

    isolate_sha_output = GetIsolateShaOutput(
        build_number=None,
        build_url=build_url,
        isolate_sha=isolate_sha,
        try_job_url=try_job_url)

    flake_swarming_task_output = FlakeSwarmingTaskOutput(
        error=None,
        pass_count=incoming_pass_count,
        iterations=iterations,
        task_id=task_id,
        started_time=started_time,
        completed_time=completed_time)

    determine_approximate_pass_rate_input = DetermineApproximatePassRateInput(
        builder_name=builder_name,
        commit_position=commit_position,
        flakiness_thus_far=flakiness_thus_far,
        get_isolate_sha_output=isolate_sha_output,
        master_name=master_name,
        previous_swarming_task_output=flake_swarming_task_output,
        reference_build_number=reference_build_number,
        revision=revision,
        step_name=step_name,
        test_name=test_name)

    pipeline_job = DetermineApproximatePassRatePipeline(
        determine_approximate_pass_rate_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    pipeline_job = pipelines.pipeline.Pipeline.from_id(pipeline_job.pipeline_id)
    self.assertEqual(flakiness_thus_far.ToSerializable(),
                     pipeline_job.outputs.default.value)

  @mock.patch.object(
      flakiness_util, 'MaximumIterationsReached', return_value=False)
  @mock.patch.object(pass_rate_util, 'TestDoesNotExist', return_value=False)
  @mock.patch.object(
      pass_rate_util, 'HasSufficientInformation', return_value=True)
  def testDetermineApproximatePassRateConverged(self, *_):
    master_name = 'm'
    builder_name = 'b'
    reference_build_number = 123
    step_name = 's'
    test_name = 't'
    commit_position = 1000
    incoming_pass_count = 15
    iterations = 30
    incoming_pass_rate = 0.5
    isolate_sha = 'sha1'
    revision = 'r1000'
    started_time = datetime(2018, 1, 1, 0, 0, 0)
    completed_time = datetime(2018, 1, 1, 1, 0, 0)
    build_url = 'url'
    try_job_url = None

    isolate_sha_output = GetIsolateShaOutput(
        build_number=None,
        build_url=None,
        isolate_sha=isolate_sha,
        try_job_url='url')

    flake_swarming_task_output = FlakeSwarmingTaskOutput(
        error=None,
        pass_count=incoming_pass_count,
        iterations=iterations,
        started_time=started_time,
        completed_time=completed_time,
        task_id='task_id')

    flakiness_thus_far = Flakiness(
        build_number=None,
        build_url=build_url,
        commit_position=commit_position,
        total_test_run_seconds=3600,
        error=None,
        failed_swarming_task_attempts=0,
        iterations=iterations,
        pass_rate=incoming_pass_rate,
        revision=revision,
        try_job_url=try_job_url,
        task_ids=ListOfBasestring.FromSerializable(['task_id_1']))

    determine_approximate_pass_rate_input = DetermineApproximatePassRateInput(
        builder_name=builder_name,
        commit_position=commit_position,
        get_isolate_sha_output=isolate_sha_output,
        flakiness_thus_far=flakiness_thus_far,
        previous_swarming_task_output=flake_swarming_task_output,
        master_name=master_name,
        reference_build_number=reference_build_number,
        revision=revision,
        step_name=step_name,
        test_name=test_name)

    pipeline_job = DetermineApproximatePassRatePipeline(
        determine_approximate_pass_rate_input)
    pipeline_job.start()
    self.execute_queued_tasks()

  @mock.patch.object(
      flakiness_util, 'MaximumIterationsReached', return_value=False)
  @mock.patch.object(pass_rate_util, 'TestDoesNotExist', return_value=False)
  @mock.patch.object(
      pass_rate_util, 'HasSufficientInformation', return_value=False)
  def testDetermineApproximatePassRateNotYetConverged(self, *_):
    master_name = 'm'
    builder_name = 'b'
    reference_build_number = 123
    step_name = 's'
    test_name = 't'
    commit_position = 1000
    incoming_pass_count = 15
    iterations_completed = 30
    expected_iterations = 15
    incoming_pass_rate = 0.5
    isolate_sha = 'sha1'
    revision = 'r1000'
    timeout_seconds = 3600
    started_time = datetime(2018, 1, 1, 0, 0, 0)
    completed_time = datetime(2018, 1, 1, 1, 0, 0)
    build_url = None
    try_job_url = 'url'

    isolate_sha_output = GetIsolateShaOutput(
        build_number=None,
        build_url=build_url,
        isolate_sha=isolate_sha,
        try_job_url=try_job_url)

    flakiness_thus_far = Flakiness(
        build_number=None,
        build_url=build_url,
        commit_position=commit_position,
        total_test_run_seconds=timeout_seconds,
        error=None,
        failed_swarming_task_attempts=0,
        iterations=iterations_completed,
        pass_rate=incoming_pass_rate,
        revision=revision,
        try_job_url=try_job_url,
        task_ids=ListOfBasestring.FromSerializable(['task_id_1']))

    incoming_flake_swarming_task_output = FlakeSwarmingTaskOutput(
        error=None,
        pass_count=incoming_pass_count,
        iterations=iterations_completed,
        started_time=started_time,
        completed_time=completed_time,
        task_id='task_id_2')

    expected_aggregate_flakiness_input = AggregateFlakinessInput(
        flakiness_thus_far=flakiness_thus_far,
        incoming_swarming_task_output=incoming_flake_swarming_task_output)

    expected_aggregate_flakiness_output = Flakiness(
        build_number=None,
        build_url=build_url,
        commit_position=commit_position,
        total_test_run_seconds=timeout_seconds,
        error=None,
        failed_swarming_task_attempts=0,
        iterations=45,
        pass_rate=0.5,
        revision=revision,
        try_job_url=try_job_url,
        task_ids=ListOfBasestring.FromSerializable(['task_id_1']))

    determine_approximate_pass_rate_input = DetermineApproximatePassRateInput(
        builder_name=builder_name,
        commit_position=commit_position,
        flakiness_thus_far=flakiness_thus_far,
        get_isolate_sha_output=isolate_sha_output,
        master_name=master_name,
        previous_swarming_task_output=incoming_flake_swarming_task_output,
        reference_build_number=reference_build_number,
        revision=revision,
        step_name=step_name,
        test_name=test_name)

    flake_swarming_task_input = RunFlakeSwarmingTaskInput(
        builder_name=builder_name,
        commit_position=commit_position,
        isolate_sha=isolate_sha,
        iterations=expected_iterations,
        master_name=master_name,
        reference_build_number=reference_build_number,
        step_name=step_name,
        test_name=test_name,
        timeout_seconds=timeout_seconds)

    recursive_input = DetermineApproximatePassRateInput(
        builder_name=builder_name,
        commit_position=commit_position,
        flakiness_thus_far=expected_aggregate_flakiness_output,
        get_isolate_sha_output=isolate_sha_output,
        master_name=master_name,
        previous_swarming_task_output=incoming_flake_swarming_task_output,
        reference_build_number=reference_build_number,
        revision=revision,
        step_name=step_name,
        test_name=test_name)

    self.MockAsynchronousPipeline(RunFlakeSwarmingTaskPipeline,
                                  flake_swarming_task_input,
                                  incoming_flake_swarming_task_output)
    self.MockSynchronousPipeline(AggregateFlakinessPipeline,
                                 expected_aggregate_flakiness_input,
                                 expected_aggregate_flakiness_output)
    self.MockGeneratorPipeline(DetermineApproximatePassRatePipelineWrapper,
                               recursive_input, None)

    pipeline_job = DetermineApproximatePassRatePipeline(
        determine_approximate_pass_rate_input)
    pipeline_job.start()
    self.execute_queued_tasks()

  def testDetermineApproximatePassRatePipelineWrapper(self):
    master_name = 'm'
    builder_name = 'b'
    reference_build_number = 123
    step_name = 's'
    test_name = 't'
    commit_position = 1000
    incoming_pass_rate = 0.5
    isolate_sha = 'sha1'
    revision = 'r1000'
    build_url = None
    try_job_url = 'url'

    isolate_sha_output = GetIsolateShaOutput(
        build_number=None,
        build_url=build_url,
        isolate_sha=isolate_sha,
        try_job_url=try_job_url)

    flakiness_thus_far = Flakiness(
        build_number=None,
        build_url=build_url,
        commit_position=commit_position,
        total_test_run_seconds=60,
        error=None,
        failed_swarming_task_attempts=0,
        iterations=10,
        pass_rate=incoming_pass_rate,
        revision=revision,
        try_job_url=try_job_url,
        task_ids=ListOfBasestring.FromSerializable(['task_id_1']))

    determine_approximate_pass_rate_input = DetermineApproximatePassRateInput(
        builder_name=builder_name,
        commit_position=commit_position,
        get_isolate_sha_output=isolate_sha_output,
        flakiness_thus_far=flakiness_thus_far,
        master_name=master_name,
        previous_swarming_task_output=None,
        reference_build_number=reference_build_number,
        revision=revision,
        step_name=step_name,
        test_name=test_name)

    self.MockGeneratorPipeline(DetermineApproximatePassRatePipeline,
                               determine_approximate_pass_rate_input, None)

    pipeline_job = DetermineApproximatePassRatePipelineWrapper(
        determine_approximate_pass_rate_input)
    pipeline_job.start()
    self.execute_queued_tasks()
