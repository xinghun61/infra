# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is to save structured objects which can serve as:
    * pipeline inputs and outputs
    * Parameters for service functions."""

from dto.dict_of_basestring import DictOfBasestring
from libs.list_of_basestring import ListOfBasestring
from libs.structured_object import StructuredObject
from libs.structured_object import TypedDict
from libs.structured_object import TypedList

# TODO(crbug.com/821623): Refactor into dto's.


class BuildKey(StructuredObject):
  """Key to a build, an analysis or a try job."""
  # Use basestring to make the attribute to accept value of both type
  # str and unicode.
  master_name = basestring
  builder_name = basestring
  build_number = int

  def GetParts(self):
    return self.master_name, self.builder_name, self.build_number


class BaseCL(StructuredObject):
  repo_name = basestring
  revision = basestring
  commit_position = int
  url = basestring


class CreateRevertCLParameters(StructuredObject):
  """Input for CreateRevertCLPipeline."""
  cl_key = basestring
  build_id = basestring
  failure_type = int


class SubmitRevertCLParameters(StructuredObject):
  """Input for SubmitRevertCLPipeline."""
  cl_key = basestring
  revert_status = int
  failure_type = int


class SendNotificationToIrcParameters(StructuredObject):
  """Input for SendNotificationToIrcPipeline."""
  cl_key = basestring
  revert_status = int
  commit_status = int
  failure_type = int


class SendNotificationForCulpritParameters(StructuredObject):
  cl_key = basestring
  force_notify = bool
  revert_status = int
  failure_type = int


class FailureToCulpritMap(TypedDict):
  _value_type = DictOfBasestring

  @property
  def failed_steps(self):
    return self.keys()

  @property
  def failed_steps_and_tests(self):
    failures = {}
    for step, test_culprit_map in self.iteritems():
      failures[step] = test_culprit_map.keys()
    return failures


class CulpritActionParameters(StructuredObject):
  """Input for RevertAndNotifyCompileCulpritPipeline and
     RevertAndNotifyTestCulpritPipeline."""
  build_key = BuildKey
  culprits = DictOfBasestring
  heuristic_cls = ListOfBasestring
  failure_to_culprit_map = FailureToCulpritMap


class RunTryJobParameters(StructuredObject):
  """Shared parameters of RunCompileTryJobPipeline and
      ScheduleTestTryJobPipeline."""
  build_key = BuildKey
  good_revision = basestring
  bad_revision = basestring
  suspected_revisions = list
  cache_name = basestring
  dimensions = list
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
  # TODO(crbug.com/796646): Convert url to
  # master/builder/build_number/buildbucket_build_id record.
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
  is_luci = bool
  buildbucket_bucket = basestring
  buildbucket_id = basestring


class BaseSubFailure(StructuredObject):
  last_pass = int
  current_failure = int
  first_failure = int


class BaseFailedStep(BaseSubFailure):
  supported = bool


class BaseFailedSteps(TypedDict):
  _value_type = BaseFailedStep


# Structured objects related to compile failure info.
class CompileFailureInfo(BaseFailureInfo):
  failed_steps = BaseFailedSteps


class CompileHeuristicAnalysisParameters(StructuredObject):
  failure_info = CompileFailureInfo
  build_completed = bool


# Structured objects related to test failure info.
class FailedTest(BaseSubFailure):
  base_test_name = basestring


class FailedTests(TypedDict):
  _value_type = FailedTest


class IsolatedData(StructuredObject):
  isolatedserver = basestring
  namespace = basestring
  digest = basestring


class IsolatedDataList(TypedList):
  _element_type = IsolatedData


class TestFailedStep(BaseFailedStep):
  tests = FailedTests
  list_isolated_data = IsolatedDataList


class TestFailedSteps(TypedDict):
  _value_type = TestFailedStep


class TestFailureInfo(BaseFailureInfo):
  failed_steps = TestFailedSteps


class TestHeuristicAnalysisParameters(StructuredObject):
  failure_info = TestFailureInfo
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


# Structured objects related to compile failure signals.
class CompileFailureSignal(BaseFailureSignal):
  failed_edges = FailedEdges
  failed_targets = FailedTargets
  failed_output_nodes = list


class CompileFailureSignals(TypedDict):
  _value_type = CompileFailureSignal


# Structured objects related to test failure signals.
class TestFailureSignalsForOneStep(TypedDict):
  _value_type = BaseFailureSignal


class TestFailureSignal(BaseFailureSignal):
  tests = TestFailureSignalsForOneStep


class TestFailureSignals(TypedDict):
  _value_type = TestFailureSignal


# Structured objects related to heuristic result.
class SuspectedCL(BaseCL):
  hints = dict
  score = int
  build_number = int


class SuspectedCLs(TypedList):
  _element_type = SuspectedCL


class HeuristicResultSubFailure(StructuredObject):
  suspected_cls = SuspectedCLs
  first_failure = int
  last_pass = int


class HeuristicResultFailure(HeuristicResultSubFailure):
  supported = bool
  step_name = basestring


# Structured objects related to heuristic result for compile failures.
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


class TestHeuristicResultForOneTest(HeuristicResultSubFailure):
  test_name = basestring


# Structured objects related to heuristic result for test failures.
class TestHeuristicResultFailureTestsInOneStep(TypedList):
  _element_type = TestHeuristicResultForOneTest


class TestHeuristicResultFailure(HeuristicResultFailure):
  tests = TestHeuristicResultFailureTestsInOneStep


class TestHeuristicResultFailures(TypedList):
  _element_type = TestHeuristicResultFailure


class TestHeuristicResult(TypedDict):
  _value_type = TestHeuristicResultFailures


class TestHeuristicAnalysisOutput(StructuredObject):
  failure_info = TestFailureInfo
  heuristic_result = TestHeuristicResult
