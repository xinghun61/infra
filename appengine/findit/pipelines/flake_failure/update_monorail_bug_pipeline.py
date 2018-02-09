# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Handles all bug-related calls for flake analysis."""

from gae_libs.pipelines import GeneratorPipeline
from libs.structured_object import StructuredObject


class UpdateMonorailBugInput(StructuredObject):
  # The urlsafe key to the MasterFlakeAnalysis.
  analysis_urlsafe_key = basestring


class UpdateMonorailBugPipeline(GeneratorPipeline):
  """Logs or updates attached bugs with flake analysis results."""
  input_type = UpdateMonorailBugInput

  def RunImpl(self, parameters):
    """Logs or updates attached bugs with flake analysis results."""
    # TODO(crbug.com/807959): Update monorail bug pipeline to handle both
    # creating new bugs and updating existing ones.
    pass
