# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dto.create_and_submit_revert_input import CreateAndSubmitRevertInput
from gae_libs import pipelines
from services.flake_failure import culprit_util


class CreateAndSubmitRevertPipeline(pipelines.SynchronousPipeline):
  """Creates and submits a revert for a test flake."""

  input_type = CreateAndSubmitRevertInput
  output_type = bool

  def OnAbort(self, parameters):
    culprit_util.AbortCreateAndSubmitRevert(parameters, self.pipeline_id)

  def RunImpl(self, parameters):
    return culprit_util.CreateAndSubmitRevert(parameters, self.pipeline_id)
