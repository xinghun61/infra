# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.pipelines import SynchronousPipeline
from pipelines.pipeline_inputs_and_outputs import (
    SendNotificationForCulpritPipelineInput)
from services import gerrit


class SendNotificationForCulpritPipeline(SynchronousPipeline):
  input_type = SendNotificationForCulpritPipelineInput
  output_type = bool

  def RunImpl(self, pipeline_input):
    return gerrit.SendNotificationForCulprit(pipeline_input)
