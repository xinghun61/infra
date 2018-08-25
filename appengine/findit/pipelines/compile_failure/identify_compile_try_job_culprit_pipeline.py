# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.pipelines import GeneratorPipeline
from pipelines.compile_failure import (
    revert_and_notify_compile_culprit_pipeline as revert_pipeline)
from services import consistent_failure_culprits
from services.compile_failure import compile_try_job
from services.parameters import BuildKey
from services.parameters import CulpritActionParameters
from services.parameters import IdentifyCompileTryJobCulpritParameters


class IdentifyCompileTryJobCulpritPipeline(GeneratorPipeline):
  """A pipeline to identify culprit CL info based on try job compile results."""
  input_type = IdentifyCompileTryJobCulpritParameters
  output_type = bool

  def RunImpl(self, pipeline_input):
    """Identifies the information for failed revisions.

    Please refer to try_job_result_format.md for format check.
    """
    culprits, heuristic_cls = compile_try_job.IdentifyCompileTryJobCulprit(
        pipeline_input)

    if not culprits:
      return

    master_name, builder_name, build_number = (
        pipeline_input.build_key.GetParts())
    yield revert_pipeline.RevertAndNotifyCompileCulpritPipeline(
        CulpritActionParameters(
            build_key=BuildKey(
                master_name=master_name,
                builder_name=builder_name,
                build_number=build_number),
            culprits=consistent_failure_culprits.GetWfSuspectedClKeysFromCLInfo(
                culprits),
            heuristic_cls=heuristic_cls,
            failure_to_culprit_map=None))
