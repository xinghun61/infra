# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is to save structured pipeline inputs and outputs."""

from libs.structured_object import StructuredObject
from libs.structured_object import TypedDict
from libs.structured_object import TypedList


class BuildKey(StructuredObject):
  """Key to a build, an analysis or a try job."""

  # Use basestring to make the attribute to accept value of both type
  # str and unicode.
  master_name = basestring
  builder_name = basestring
  build_number = int


class CLKey(StructuredObject):
  """Key to a CL."""
  repo_name = basestring
  revision = basestring


class CreateRevertCLPipelineInput(StructuredObject):
  """Input for CreateRevertCLPipeline."""
  cl_key = CLKey
  build_id = basestring


class SubmitRevertCLPipelineInput(StructuredObject):
  """Input for SubmitRevertCLPipeline."""
  cl_key = CLKey
  revert_status = int


class SendNotificationToIrcPipelineInput(StructuredObject):
  """Input for SendNotificationToIrcPipeline."""
  cl_key = CLKey
  revert_status = int
  submitted = bool


class SendNotificationForCulpritPipelineInput(StructuredObject):
  cl_key = CLKey
  force_notify = bool
  revert_status = int


class DictOfCLKeys(TypedDict):
  _value_type = CLKey


class ListOfCLKeys(TypedList):
  _element_type = CLKey


class RevertAndNotifyCulpritPipelineInput(StructuredObject):
  """Input for RevertAndNotifyCompileCulpritPipeline and
     RevertAndNotifyTestCulpritPipeline."""
  build_key = BuildKey
  culprits = DictOfCLKeys
  heuristic_cls = ListOfCLKeys