# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.pipeline_wrapper import BasePipeline


class TriggerFlakeSwarmingTaskPipeline(BasePipeline):

  def run(self):
    raise NotImplementedError(
        'TriggerFlakeSwarmingTaskPipeline is already deprecated.')
