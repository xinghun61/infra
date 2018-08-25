# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.pipelines import GeneratorPipeline
from pipelines.test_failure.revert_and_notify_test_culprit_pipeline import (
    RevertAndNotifyTestCulpritPipeline)
from services import consistent_failure_culprits
from services.parameters import BuildKey
from services.parameters import CulpritActionParameters
from services.parameters import IdentifyTestTryJobCulpritParameters
from services.test_failure import test_try_job


class IdentifyTestTryJobCulpritPipeline(GeneratorPipeline):
  """A pipeline to identify culprit CL info based on test try job results."""
  input_type = IdentifyTestTryJobCulpritParameters
  output_type = bool

  def RunImpl(self, pipeline_input):
    """Identifies the information for failed revisions.

    Please refer to try_job_result_format.md for format check.
    """
    culprits, heuristic_cls, failure_to_culprit_map = (
        test_try_job.IdentifyTestTryJobCulprits(pipeline_input))
    if not culprits:
      return

    master_name, builder_name, build_number = (
        pipeline_input.build_key.GetParts())
    yield RevertAndNotifyTestCulpritPipeline(
        CulpritActionParameters(
            build_key=BuildKey(
                master_name=master_name,
                builder_name=builder_name,
                build_number=build_number),
            culprits=consistent_failure_culprits.GetWfSuspectedClKeysFromCLInfo(
                culprits),
            heuristic_cls=heuristic_cls,
            failure_to_culprit_map=failure_to_culprit_map))
