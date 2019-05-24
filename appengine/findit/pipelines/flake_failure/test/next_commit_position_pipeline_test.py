# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from dto.commit_id_range import CommitID
from dto.int_range import IntRange
from dto.step_metadata import StepMetadata
from gae_libs import pipelines
from gae_libs.pipeline_wrapper import pipeline_handlers
from model.flake.analysis.flake_culprit import FlakeCulprit
from model.flake.analysis.data_point import DataPoint
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from model.isolated_target import IsolatedTarget
from pipelines.flake_failure.next_commit_position_pipeline import (
    NextCommitPositionInput)
from pipelines.flake_failure.next_commit_position_pipeline import (
    NextCommitPositionPipeline)
from services import step_util
from services.flake_failure import heuristic_analysis
from services.flake_failure import lookback_algorithm
from services.flake_failure import next_commit_position_utils
from waterfall import build_util
from waterfall.build_info import BuildInfo
from waterfall.test.wf_testcase import WaterfallTestCase


class NextCommitPositionPipelineTest(WaterfallTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(lookback_algorithm, 'GetNextCommitId')
  def testNextCommitPositionPipelineFoundCulprit(self, mock_next_commit):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    start_commit_position = 1000

    culprit_commit_id = CommitID(commit_position=1000, revision='r1000')
    mock_next_commit.return_value = (None, culprit_commit_id)

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    next_commit_position_input = NextCommitPositionInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position_range=IntRange(lower=None, upper=start_commit_position),
        step_metadata=None)

    pipeline_job = NextCommitPositionPipeline(next_commit_position_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    pipeline_job = pipelines.pipeline.Pipeline.from_id(pipeline_job.pipeline_id)
    next_commit_position_output = pipeline_job.outputs.default.value

    self.assertFalse(pipeline_job.was_aborted)
    self.assertEqual(culprit_commit_id.ToSerializable(),
                     next_commit_position_output['culprit_commit_id'])
    self.assertIsNone(next_commit_position_output['next_commit_id'])

  @mock.patch.object(lookback_algorithm, 'GetNextCommitId')
  def testNextCommitPositionPipelineNotReproducible(self, mock_next_commit):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    start_commit_position = 1000

    mock_next_commit.return_value = (None, None)

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    next_commit_position_input = NextCommitPositionInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position_range=IntRange(lower=None, upper=start_commit_position),
        step_metadata=None)

    pipeline_job = NextCommitPositionPipeline(next_commit_position_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    pipeline_job = pipelines.pipeline.Pipeline.from_id(pipeline_job.pipeline_id)
    next_commit_position_output = pipeline_job.outputs.default.value

    self.assertFalse(pipeline_job.was_aborted)
    self.assertIsNone(next_commit_position_output['culprit_commit_id'])
    self.assertIsNone(next_commit_position_output['next_commit_id'])

  @mock.patch.object(lookback_algorithm, 'GetNextCommitId')
  @mock.patch.object(MasterFlakeAnalysis, 'CanRunHeuristicAnalysis')
  @mock.patch.object(next_commit_position_utils,
                     'GetNextCommitIdFromHeuristicResults')
  def testNextCommitPositionPipelineWithHeuristicResults(
      self, mock_heuristic_result, mock_run_heuristic, mock_next_commit):
    master_name = 'm'
    builder_name = 'b'
    build_number = 105
    step_name = 's'
    test_name = 't'
    start_commit_position = 1000
    suspect_commit_position = 95
    expected_next_commit_id = CommitID(commit_position=94, revision='r94')

    suspect = FlakeCulprit.Create('repo', 'revision', suspect_commit_position)
    suspect.commit_position = suspect_commit_position
    suspect.put()

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.suspect_urlsafe_keys.append(suspect.key.urlsafe())
    analysis.put()

    mock_run_heuristic.return_value = False
    mock_heuristic_result.return_value = expected_next_commit_id

    calculated_next_commit_id = CommitID(commit_position=999, revision='r999')
    mock_next_commit.return_value = (calculated_next_commit_id, None)

    next_commit_position_input = NextCommitPositionInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position_range=IntRange(lower=None, upper=start_commit_position),
        step_metadata=None)

    pipeline_job = NextCommitPositionPipeline(next_commit_position_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    pipeline_job = pipelines.pipeline.Pipeline.from_id(pipeline_job.pipeline_id)
    next_commit_position_output = pipeline_job.outputs.default.value

    self.assertFalse(pipeline_job.was_aborted)
    self.assertIsNone(next_commit_position_output['culprit_commit_id'])
    self.assertEqual(expected_next_commit_id.ToSerializable(),
                     next_commit_position_output['next_commit_id'])
    mock_heuristic_result.assert_called_once_with(analysis.key.urlsafe())

  @mock.patch.object(lookback_algorithm, 'GetNextCommitId')
  @mock.patch.object(MasterFlakeAnalysis, 'CanRunHeuristicAnalysis')
  @mock.patch.object(next_commit_position_utils,
                     'GetNextCommitIdFromHeuristicResults')
  @mock.patch.object(heuristic_analysis, 'RunHeuristicAnalysis')
  def testNextCommitPositionPipelineRunHeuristicResults(
      self, _, mock_heuristic_result, mock_can_run_heuristic, mock_next_commit):
    master_name = 'm'
    builder_name = 'b'
    build_number = 105
    step_name = 's'
    test_name = 't'
    start_commit_position = 1000
    expected_next_commit_id = CommitID(commit_position=94, revision='r94')

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.put()

    mock_can_run_heuristic.return_value = True
    mock_heuristic_result.side_effect = [None, expected_next_commit_id]

    calculated_next_commit_id = CommitID(commit_position=999, revision='r999')
    mock_next_commit.return_value = (calculated_next_commit_id, None)

    next_commit_position_input = NextCommitPositionInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position_range=IntRange(lower=None, upper=start_commit_position),
        step_metadata=None)

    pipeline_job = NextCommitPositionPipeline(next_commit_position_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    pipeline_job = pipelines.pipeline.Pipeline.from_id(pipeline_job.pipeline_id)
    next_commit_position_output = pipeline_job.outputs.default.value

    self.assertFalse(pipeline_job.was_aborted)
    self.assertIsNone(next_commit_position_output['culprit_commit_id'])
    self.assertEqual(expected_next_commit_id.ToSerializable(),
                     next_commit_position_output['next_commit_id'])

  @mock.patch.object(next_commit_position_utils,
                     'GenerateCommitIDsForBoundingTargets')
  @mock.patch.object(build_util, 'GetBuildInfo')
  @mock.patch.object(lookback_algorithm, 'GetNextCommitId')
  @mock.patch.object(MasterFlakeAnalysis, 'CanRunHeuristicAnalysis')
  @mock.patch.object(next_commit_position_utils,
                     'GetNextCommitIdFromHeuristicResults')
  @mock.patch.object(heuristic_analysis, 'RunHeuristicAnalysis')
  def testNextCommitPositionPipelineRunHeuristicResultsNoResults(
      self, _, mock_heuristic_result, mock_can_run_heuristic, mock_next_commit,
      mock_reference_build, mock_bound_commits):
    master_name = 'm'
    builder_name = 'b'
    build_number = 105
    build_id = 10000
    step_name = 's'
    test_name = 't'
    start_commit_position = 1000
    lower_bound_commit_position = 990
    lower_bound_commit_id = CommitID(
        commit_position=lower_bound_commit_position, revision='r990')
    start_revision = 'r1000'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.data_points = [
        DataPoint.Create(commit_position=start_commit_position)
    ]
    analysis.put()

    mock_can_run_heuristic.return_value = True
    mock_heuristic_result.return_value = None

    calculated_next_commit_id = CommitID(commit_position=999, revision='r999')
    mock_next_commit.return_value = (calculated_next_commit_id, None)

    target_name = 'browser_tests'
    step_metadata = StepMetadata(
        canonical_step_name=None,
        dimensions=None,
        full_step_name=None,
        isolate_target_name=target_name,
        patched=True,
        swarm_task_ids=None,
        waterfall_buildername=None,
        waterfall_mastername=None)

    reference_build = BuildInfo(master_name, builder_name, build_number)
    reference_build.commit_position = start_commit_position
    mock_reference_build.return_value = reference_build

    luci_name = 'chromium'
    bucket_name = 'ci'
    gitiles_host = 'chromium.googlesource.com'
    gitiles_project = 'chromium/src'
    gitiles_ref = 'refs/heads/master'
    gerrit_patch = ''

    lower_bound_target = IsolatedTarget.Create(
        build_id - 1, luci_name, bucket_name, master_name, builder_name,
        gitiles_host, gitiles_project, gitiles_ref, gerrit_patch, target_name,
        'hash_1', lower_bound_commit_position, lower_bound_commit_id.revision)
    lower_bound_target.put()

    upper_bound_target = IsolatedTarget.Create(
        build_id, luci_name, bucket_name, master_name, builder_name,
        gitiles_host, gitiles_project, gitiles_ref, gerrit_patch, target_name,
        'hash_2', start_commit_position, start_revision)
    upper_bound_target.put()
    mock_bound_commits.return_value = (
        lower_bound_commit_id,
        CommitID(commit_position=start_commit_position, revision='r1000'))

    next_commit_position_input = NextCommitPositionInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position_range=IntRange(lower=None, upper=start_commit_position),
        step_metadata=step_metadata)

    pipeline_job = NextCommitPositionPipeline(next_commit_position_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    pipeline_job = pipelines.pipeline.Pipeline.from_id(pipeline_job.pipeline_id)
    next_commit_position_output = pipeline_job.outputs.default.value

    self.assertFalse(pipeline_job.was_aborted)
    self.assertIsNone(next_commit_position_output['culprit_commit_id'])
    self.assertEqual(lower_bound_commit_id.ToSerializable(),
                     next_commit_position_output['next_commit_id'])

  @mock.patch.object(lookback_algorithm, 'GetNextCommitId')
  @mock.patch.object(next_commit_position_utils, 'GetEarliestCommitPosition')
  def testNextCommitPositionPipelineLongStandingFlake(
      self, mock_earliest_commit, mock_next_commit):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    start_commit_position = 1000
    cutoff_commit_position = 500

    mock_earliest_commit.return_value = cutoff_commit_position
    next_commit_id = CommitID(
        commit_position=cutoff_commit_position - 1, revision='r499')
    mock_next_commit.return_value = (next_commit_id, None)

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    next_commit_position_input = NextCommitPositionInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position_range=IntRange(lower=None, upper=start_commit_position),
        step_metadata=None)

    pipeline_job = NextCommitPositionPipeline(next_commit_position_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    pipeline_job = pipelines.pipeline.Pipeline.from_id(pipeline_job.pipeline_id)
    next_commit_position_output = pipeline_job.outputs.default.value

    self.assertFalse(pipeline_job.was_aborted)
    self.assertIsNone(next_commit_position_output['culprit_commit_id'])
    self.assertIsNone(next_commit_position_output['next_commit_id'])

  @mock.patch.object(next_commit_position_utils,
                     'GenerateCommitIDsForBoundingTargets')
  @mock.patch.object(lookback_algorithm, 'GetNextCommitId')
  @mock.patch.object(MasterFlakeAnalysis, 'CanRunHeuristicAnalysis')
  @mock.patch.object(build_util, 'GetBuildInfo')
  def testNextCommitPositionPipelineContinueAnalysis(
      self, mock_reference_build, mock_heuristic, mock_next_commit,
      mock_bound_commits):
    master_name = 'm'
    builder_name = 'b'
    parent_mastername = 'p_m'
    parent_buildername = 'p_b'
    build_number = 100
    build_id = 10000
    step_name = 's'
    test_name = 't'
    start_commit_position = 1000
    expected_next_commit_id = CommitID(commit_position=990, revision='r990')

    reference_build = BuildInfo(master_name, builder_name, build_number)
    reference_build.commit_position = start_commit_position
    reference_build.parent_mastername = parent_mastername
    reference_build.parent_buildername = parent_buildername
    mock_reference_build.return_value = reference_build
    mock_heuristic.return_value = False

    calculated_next_commit_id = CommitID(commit_position=999, revision='r999')
    mock_next_commit.return_value = (calculated_next_commit_id, None)

    target_name = 'browser_tests'
    step_metadata = StepMetadata(
        canonical_step_name=None,
        dimensions=None,
        full_step_name=None,
        isolate_target_name=target_name,
        patched=True,
        swarm_task_ids=None,
        waterfall_buildername=None,
        waterfall_mastername=None)

    luci_name = 'chromium'
    bucket_name = 'ci'
    gitiles_host = 'chromium.googlesource.com'
    gitiles_project = 'chromium/src'
    gitiles_ref = 'refs/heads/master'
    gerrit_patch = ''

    lower_bound_target = IsolatedTarget.Create(
        build_id - 1, luci_name, bucket_name, parent_mastername,
        parent_buildername, gitiles_host, gitiles_project, gitiles_ref,
        gerrit_patch, target_name, 'hash_1',
        expected_next_commit_id.commit_position, None)
    lower_bound_target.put()

    upper_bound_target = IsolatedTarget.Create(
        build_id, luci_name, bucket_name, parent_mastername, parent_buildername,
        gitiles_host, gitiles_project, gitiles_ref, gerrit_patch, target_name,
        'hash_2', start_commit_position, None)
    upper_bound_target.put()
    mock_bound_commits.return_value = (
        expected_next_commit_id,
        CommitID(commit_position=start_commit_position, revision='r1000'))

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.data_points = [
        DataPoint.Create(commit_position=start_commit_position)
    ]
    analysis.Save()

    next_commit_position_input = NextCommitPositionInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position_range=IntRange(lower=None, upper=start_commit_position),
        step_metadata=step_metadata)

    pipeline_job = NextCommitPositionPipeline(next_commit_position_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    pipeline_job = pipelines.pipeline.Pipeline.from_id(pipeline_job.pipeline_id)
    next_commit_position_output = pipeline_job.outputs.default.value

    self.assertFalse(pipeline_job.was_aborted)
    self.assertIsNone(next_commit_position_output['culprit_commit_id'])
    self.assertEqual(expected_next_commit_id.ToSerializable(),
                     next_commit_position_output['next_commit_id'])
    mock_bound_commits.assert_called_once_with(
        analysis.data_points, lower_bound_target, upper_bound_target)

  @mock.patch.object(build_util, 'GetBuildInfo')
  @mock.patch.object(lookback_algorithm, 'GetNextCommitId')
  @mock.patch.object(step_util, 'GetValidBoundingBuildsForStep')
  @mock.patch.object(step_util, 'GetBoundingIsolatedTargets')
  @mock.patch.object(MasterFlakeAnalysis, 'CanRunHeuristicAnalysis')
  @mock.patch.object(MasterFlakeAnalysis, 'UpdateSuspectedBuildUsingBuildInfo')
  def testNextCommitPositionPipelineContinueAnalysisFallbackToBuildInfo(
      self, mock_update, mock_heuristic, mock_targets, mock_bounding_builds,
      mock_next_commit, mock_reference_build):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    start_commit_position = 1000
    expected_next_commit_id = CommitID(commit_position=990, revision='r990')

    mock_heuristic.return_value = False

    calculated_next_commit_id = CommitID(commit_position=999, revision='r999')
    mock_next_commit.return_value = (calculated_next_commit_id, None)

    target_name = 'browser_tests'
    step_metadata = StepMetadata(
        canonical_step_name=None,
        dimensions=None,
        full_step_name=None,
        isolate_target_name=target_name,
        patched=True,
        swarm_task_ids=None,
        waterfall_buildername=None,
        waterfall_mastername=None)

    reference_build = BuildInfo(master_name, builder_name, build_number)
    reference_build.commit_position = start_commit_position
    mock_reference_build.return_value = reference_build

    lower_bound_build = BuildInfo(master_name, builder_name, build_number - 1)
    lower_bound_build.commit_position = expected_next_commit_id.commit_position
    lower_bound_build.chromium_revision = expected_next_commit_id.revision
    upper_bound_build = BuildInfo(master_name, builder_name, build_number)
    upper_bound_build.commit_position = start_commit_position
    mock_bounding_builds.return_value = (lower_bound_build, upper_bound_build)

    mock_targets.side_effect = AssertionError()

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.data_points = [
        DataPoint.Create(commit_position=start_commit_position)
    ]
    analysis.Save()

    next_commit_position_input = NextCommitPositionInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position_range=IntRange(lower=None, upper=start_commit_position),
        step_metadata=step_metadata)

    pipeline_job = NextCommitPositionPipeline(next_commit_position_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    mock_update.assert_called_once_with(lower_bound_build, upper_bound_build)
    pipeline_job = pipelines.pipeline.Pipeline.from_id(pipeline_job.pipeline_id)
    next_commit_position_output = pipeline_job.outputs.default.value

    self.assertFalse(pipeline_job.was_aborted)
    self.assertIsNone(next_commit_position_output['culprit_commit_id'])
    self.assertEqual(expected_next_commit_id.ToSerializable(),
                     next_commit_position_output['next_commit_id'])
