# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module is to save structured pipeline inputs and outputs."""

from libs.structured_object import StructuredObject


class CLKey(StructuredObject):
  """Key to a CL."""
  repo_name = unicode
  revision = unicode


class CreateRevertCLPipelineInput(StructuredObject):
  """Input for CreateRevertCLPipeline."""
  cl_key = CLKey
  build_id = unicode