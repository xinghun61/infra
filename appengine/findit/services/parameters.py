# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is to save structured objects which can serve as:
    * pipeline inputs and outputs
    * Parameters for service functions."""

from libs.structured_object import StructuredObject, TypedDict, TypedList


class BuildKey(StructuredObject):
  """Key to a build, an analysis or a try job."""

  # Use basestring to make the attribute to accept value of both type
  # str and unicode.
  master_name = basestring
  builder_name = basestring
  build_number = int

  def GetParts(self):
    return self.master_name, self.builder_name, self.build_number


class CLKey(StructuredObject):
  """Key to a CL."""
  repo_name = basestring
  revision = basestring


class BaseCL(StructuredObject):
  repo_name = basestring
  revision = basestring
  commit_position = int
  url = basestring


class DictOfCLKeys(TypedDict):
  _value_type = CLKey


class ListOfCLKeys(TypedList):
  _element_type = CLKey


class CreateRevertCLParameters(StructuredObject):
  """Input for CreateRevertCLPipeline."""
  cl_key = CLKey
  build_id = basestring


class SubmitRevertCLParameters(StructuredObject):
  """Input for SubmitRevertCLPipeline."""
  cl_key = CLKey
  revert_status = int


class SendNotificationToIrcParameters(StructuredObject):
  """Input for SendNotificationToIrcPipeline."""
  cl_key = CLKey
  revert_status = int
  submitted = bool


class SendNotificationForCulpritParameters(StructuredObject):
  cl_key = CLKey
  force_notify = bool
  revert_status = int


class CulpritActionParameters(StructuredObject):
  """Input for RevertAndNotifyCompileCulpritPipeline and
     RevertAndNotifyTestCulpritPipeline."""
  build_key = BuildKey
  culprits = DictOfCLKeys
  heuristic_cls = ListOfCLKeys


class RunTryJobParameters(StructuredObject):
  """Shared parameters of RunCompileTryJobPipeline and
      ScheduleTestTryJobPipeline."""
  build_key = BuildKey
  good_revision = basestring
  bad_revision = basestring
  suspected_revisions = list
  cache_name = basestring
  dimensions = list
  force_buildbot = bool
  urlsafe_try_job_key = basestring


class RunCompileTryJobParameters(RunTryJobParameters):
  """Input for RunTryJobParameters."""
  compile_targets = list


class RunTestTryJobParameters(RunTryJobParameters):
  """Input for ScheduleTestTryJobPipeline."""
  targeted_tests = dict


class TryJobReport(StructuredObject):
  """Common info in reports of waterfall and flake try jobs."""
  last_checked_out_revision = basestring
  previously_checked_out_revision = basestring
  previously_cached_revision = basestring
  metadata = dict


class CompileTryJobReport(TryJobReport):
  """Special information in report of compile try jobs."""
  culprit = basestring
  result = dict


class TryJobResult(StructuredObject):
  """Object represents a try job results saved in wf_try_job entity."""
  url = basestring
  try_job_id = basestring
  culprit = dict


class CompileTryJobResult(TryJobResult):
  """Object represents a compile try job results saved in wf_try_job entity."""
  report = CompileTryJobReport


class PassFailCount(StructuredObject):
  pass_count = int
  fail_count = int


class PassFailCounts(TypedDict):
  _value_type = PassFailCount


class TestTryJobStepResult(StructuredObject):
  status = basestring
  valid = bool
  step_metadata = dict
  pass_fail_counts = PassFailCounts
  failures = list


class TestTryJobAllStepsResult(TypedDict):
  _value_type = TestTryJobStepResult


class TestTryJobAllRevisionsResult(TypedDict):
  _value_type = TestTryJobAllStepsResult


class TestTryJobReport(TryJobReport):
  culprits = dict
  flakes = dict
  result = TestTryJobAllRevisionsResult


class TestTryJobResult(TryJobResult):
  """Object represents a test try job results saved in wf_try_job entity."""
  report = TestTryJobReport


class IdentifyCompileTryJobCulpritParameters(StructuredObject):
  build_key = BuildKey
  result = CompileTryJobResult


class IdentifyTestTryJobCulpritParameters(StructuredObject):
  build_key = BuildKey
  result = TestTryJobResult


class RunFlakeTryJobParameters(StructuredObject):
  """Input for RunFlakeTryJobPipeline to compile and isolate only."""
  analysis_urlsafe_key = basestring
  revision = basestring
  flake_cache_name = basestring
  dimensions = list


# Structured objects related to failure info.
class FailureInfoBuild(StructuredObject):
  blame_list = list
  chromium_revision = basestring


class FailureInfoBuilds(TypedDict):
  _value_type = FailureInfoBuild


class BaseFailureInfo(StructuredObject):
  master_name = basestring
  builder_name = basestring
  build_number = int
  parent_mastername = basestring
  parent_buildername = basestring
  builds = FailureInfoBuilds
  failure_type = int
  failed = bool
  chromium_revision = basestring


class BaseFailedStep(StructuredObject):
  last_pass = int
  current_failure = int
  first_failure = int


class BaseFailedSteps(TypedDict):
  _value_type = BaseFailedStep


class CompileFailureInfo(BaseFailureInfo):
  failed_steps = BaseFailedSteps


class CompileHeuristicAnalysisParameters(StructuredObject):
  failure_info = CompileFailureInfo
  build_completed = bool


# Structured objects related to failure signals.
class BaseFailureSignal(StructuredObject):
  files = dict
  keywords = dict


class FailedEdge(StructuredObject):
  dependencies = list
  output_nodes = list
  rule = basestring


class FailedEdges(TypedList):
  _element_type = FailedEdge


class FailedTarget(StructuredObject):
  source = basestring
  target = basestring


class FailedTargets(TypedList):
  _element_type = FailedTarget


class CompileFailureSignal(BaseFailureSignal):
  failed_edges = FailedEdges
  failed_targets = FailedTargets
  failed_output_nodes = list


class CompileFailureSignals(TypedDict):
  _value_type = CompileFailureSignal


# Structured objects related to heuristic result.
class SuspectedCL(BaseCL):
  hints = dict
  score = int
  build_number = int


class SuspectedCLs(TypedList):
  _element_type = SuspectedCL


class HeuristicResultFailure(StructuredObject):
  suspected_cls = SuspectedCLs
  first_failure = int
  last_pass = int
  supported = bool
  step_name = basestring


class CompileHeuristicResultFailure(HeuristicResultFailure):
  new_compile_suspected_cls = SuspectedCLs
  use_ninja_dependencies = bool


class CompileHeuristicResultFailures(TypedList):
  _element_type = CompileHeuristicResultFailure


class CompileHeuristicResult(TypedDict):
  _value_type = CompileHeuristicResultFailures


class CompileHeuristicAnalysisOutput(StructuredObject):
  failure_info = CompileFailureInfo
  signals = CompileFailureSignals
  heuristic_result = CompileHeuristicResult
