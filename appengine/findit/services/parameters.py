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


class ScheduleTryJobParameters(StructuredObject):
  """Shared parameters of ScheduleCompileTryJobPipeline and
      ScheduleTestTryJobPipeline."""
  build_key = BuildKey
  good_revision = basestring
  bad_revision = basestring
  suspected_revisions = list
  cache_name = basestring
  dimensions = list
  force_buildbot = bool


class ScheduleCompileTryJobParameters(ScheduleTryJobParameters):
  """Input for ScheduleTryJobParameters."""
  compile_targets = list


class ScheduleTestTryJobParameters(ScheduleTryJobParameters):
  """Input for ScheduleTestTryJobPipeline."""
  targeted_tests = dict


class RunFlakeTryJobParameters(StructuredObject):
  """Input for RunFlakeTryJobPipeline to compile and isolate only."""
  analysis_urlsafe_key = basestring
  revision = basestring
  flake_cache_name = basestring
  dimensions = list
