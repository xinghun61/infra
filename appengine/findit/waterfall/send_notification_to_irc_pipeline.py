# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.pipelines import SynchronousPipeline
from pipelines.pipeline_inputs_and_outputs import (
    SendNotificationToIrcPipelineInput)
from services import irc


class SendNotificationToIrcPipeline(SynchronousPipeline):
  input_type = SendNotificationToIrcPipelineInput
  output_type = bool

  def RunImpl(self, pipeline_input):
    return irc.SendMessageToIrc(pipeline_input)
