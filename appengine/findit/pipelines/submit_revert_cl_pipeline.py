# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.pipelines import SynchronousPipeline
from libs import analysis_status as status
from model.wf_suspected_cl import WfSuspectedCL
from services import gerrit
from services.parameters import SubmitRevertCLParameters


class SubmitRevertCLPipeline(SynchronousPipeline):
  input_type = SubmitRevertCLParameters
  output_type = bool

  def OnAbort(self, pipeline_input):
    culprit = WfSuspectedCL.Get(pipeline_input.cl_key.repo_name,
                                pipeline_input.cl_key.revision)

    if culprit.submit_revert_pipeline_id == self.pipeline_id:
      if (culprit.revert_submission_status and
          culprit.revert_submission_status != status.COMPLETED):
        culprit.revert_submission_status = status.ERROR
      culprit.submit_revert_pipeline_id = None
      culprit.put()

  # Arguments number differs from overridden method - pylint: disable=W0221
  def RunImpl(self, pipeline_input):
    return gerrit.CommitRevert(pipeline_input, self.pipeline_id)
