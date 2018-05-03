# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE f
"""Pipeline input for UpdateFlakeAnalysisDataPointPipeline."""
from dto.flake_swarming_task_output import FlakeSwarmingTaskOutput
from libs.structured_object import StructuredObject


class UpdateFlakeAnalysisDataPointsInput(StructuredObject):
  # The urlsafe-key to the analysis to update.
  analysis_urlsafe_key = basestring

  # The url to the build whose artifacts were used to create the data point.
  # Can be None if existing build artifacts were not used (compile was needed).
  build_url = basestring

  # The data point with matching commit position to update.
  commit_position = int

  # The revision corresponding to the data point.
  revision = basestring

  # The url to the try job that generated the build artifacts to generate the
  # data point. Can be None if existing build artifacts were used (commit
  # position mapped to a nearby valid build).
  try_job_url = basestring

  # The results of the flake swarming task to update data points with.
  swarming_task_output = FlakeSwarmingTaskOutput
