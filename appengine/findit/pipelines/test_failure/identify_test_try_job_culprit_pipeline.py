# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.pipeline_wrapper import BasePipeline
from pipelines.test_failure.revert_and_notify_test_culprit_pipeline import (
    RevertAndNotifyTestCulpritPipeline)
from services import git
from services.parameters import BuildKey
from services.parameters import CulpritActionParameters
from services.test_failure import test_try_job


class IdentifyTestTryJobCulpritPipeline(BasePipeline):
  """A pipeline to identify culprit CL info based on try job results."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number, try_job_id, result):
    """Identifies the information for failed revisions.

    Please refer to try_job_result_format.md for format check.
    """
    culprits, heuristic_cls = test_try_job.IdentifyTestTryJobCulprits(
        master_name, builder_name, build_number, try_job_id, result)
    if not culprits:
      return

    yield RevertAndNotifyTestCulpritPipeline(
        CulpritActionParameters(
            build_key=BuildKey(
                master_name=master_name,
                builder_name=builder_name,
                build_number=build_number),
            culprits=git.GetCLKeysFromCLInfo(culprits),
            heuristic_cls=heuristic_cls))
