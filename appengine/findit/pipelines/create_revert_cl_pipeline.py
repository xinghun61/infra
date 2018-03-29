# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from gae_libs.pipelines import SynchronousPipeline
from libs import analysis_status as status
from model import entity_util
from model.wf_suspected_cl import WfSuspectedCL
from services import culprit_action
from services.parameters import CreateRevertCLParameters


class CreateRevertCLPipeline(SynchronousPipeline):
  input_type = CreateRevertCLParameters
  output_type = int

  def OnAbort(self, pipeline_input):
    culprit = entity_util.GetEntityFromUrlsafeKey(pipeline_input.cl_key)
    assert culprit

    if culprit.revert_pipeline_id == self.pipeline_id:
      if culprit.revert_status and culprit.revert_status != status.COMPLETED:
        culprit.revert_status = status.ERROR
      culprit.revert_pipeline_id = None
      culprit.put()

  # Arguments number differs from overridden method - pylint: disable=W0221
  def RunImpl(self, pipeline_input):
    return culprit_action.RevertCulprit(pipeline_input, self.pipeline_id)
