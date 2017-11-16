# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.pipelines import SynchronousPipeline
from services import irc
from services.parameters import SendNotificationToIrcParameters


class SendNotificationToIrcPipeline(SynchronousPipeline):
  input_type = SendNotificationToIrcParameters
  output_type = bool

  def RunImpl(self, pipeline_input):
    return irc.SendMessageToIrc(pipeline_input)
