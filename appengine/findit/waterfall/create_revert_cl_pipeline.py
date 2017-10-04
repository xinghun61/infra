# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.pipeline_wrapper import BasePipeline
from libs import analysis_status as status
from model.wf_suspected_cl import WfSuspectedCL
from services import revert


class CreateRevertCLPipeline(BasePipeline):

  def __init__(self, repo_name, revision):
    super(CreateRevertCLPipeline, self).__init__(repo_name, revision)
    self.repo_name = repo_name
    self.revision = revision

  def _LogUnexpectedAborting(self, was_aborted):
    if not was_aborted:  # pragma: no cover
      return

    culprit = WfSuspectedCL.Get(self.repo_name, self.revision)

    if culprit.revert_pipeline_id == self.pipeline_id:
      if culprit.revert_status and culprit.revert_status != status.COMPLETED:
        culprit.revert_status = status.ERROR
      culprit.revert_pipeline_id = None
      culprit.put()

  def finalized(self):  # pragma: no cover
    self._LogUnexpectedAborting(self.was_aborted)

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, repo_name, revision):
    if revert.ShouldRevert(repo_name, revision, self.pipeline_id):
      return revert.RevertCulprit(repo_name, revision)
    return revert.SKIPPED
