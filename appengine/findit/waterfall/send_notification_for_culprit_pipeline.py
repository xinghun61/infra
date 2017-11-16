# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.pipelines import SynchronousPipeline
from services import gerrit
from services.parameters import SendNotificationForCulpritParameters


class SendNotificationForCulpritPipeline(SynchronousPipeline):
  input_type = SendNotificationForCulpritParameters
  output_type = bool

  def RunImpl(self, pipeline_input):
    return gerrit.SendNotificationForCulprit(pipeline_input)
