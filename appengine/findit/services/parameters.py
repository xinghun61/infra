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
  culprit = dict
  result = TestTryJobAllRevisionsResult


class TestTryJobResult(TryJobResult):
  """Object represents a test try job results saved in wf_try_job entity."""
  report = TestTryJobReport


class IdentifyCompileTryJobCulpritParameters(StructuredObject):
  build_key = BuildKey
  result = CompileTryJobResult


class RunFlakeTryJobParameters(StructuredObject):
  """Input for RunFlakeTryJobPipeline to compile and isolate only."""
  analysis_urlsafe_key = basestring
  revision = basestring
  flake_cache_name = basestring
  dimensions = list
