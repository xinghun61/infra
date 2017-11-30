# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb
from common.findit_http_client import FinditHttpClient
from gae_libs.pipelines import GeneratorPipeline
from gae_libs.pipelines import SynchronousPipeline
from libs.structured_object import StructuredObject
from pipelines.flake_failure.run_flake_try_job_pipeline import (
    RunFlakeTryJobPipeline)
from services.parameters import RunFlakeTryJobParameters
from waterfall import build_util
from waterfall import swarming_util


class GetIsolateShaForCommitPositionParameters(StructuredObject):
  # The urlsafe key to the MasterFlakeAnalysis this pipeline is assisting in
  # analyyzing.
  analysis_urlsafe_key = basestring

  # The exact commit position being requested for analysis.
  commit_position = int

  # The exact revision corresponding to commit_position being requested.
  revision = basestring


class GetIsolateShaForBuildParameters(StructuredObject):
  # The name of the master to query for a pre-determined sha.
  master_name = basestring

  # The name of the builder to query for a pre-determined sha.
  builder_name = basestring

  # The build number whose to query for a pre-detrermined sha.
  build_number = int

  # The name of the step to query for a pre-determined sha.
  step_name = basestring


class GetIsolateShaForBuildPipeline(SynchronousPipeline):
  input_type = GetIsolateShaForBuildParameters
  output_type = basestring

  def RunImpl(self, parameters):
    return swarming_util.GetIsolatedShaForStep(
        parameters.master_name, parameters.builder_name,
        parameters.build_number, parameters.step_name, FinditHttpClient())


class GetIsolateShaForCommitPositionPipeline(GeneratorPipeline):

  input_type = GetIsolateShaForCommitPositionParameters
  output_type = basestring

  def RunImpl(self, parameters):
    """Determines the Isolated sha to run in swarming given a commit position.

    If the requested commit position maps directly to a  build, simply get that
    existing build's isolated sha. Otherwise, trigger a try job to compile and
    isolate at that revision and return the resulting sha.
    """
    analysis = ndb.Key(urlsafe=parameters.analysis_urlsafe_key).get()
    assert analysis

    master_name = analysis.master_name
    builder_name = analysis.builder_name
    step_name = analysis.step_name
    commit_position = parameters.commit_position

    earliest_containing_build = build_util.GetEarliestContainingBuild(
        master_name, builder_name, None, None, commit_position)

    assert earliest_containing_build
    assert earliest_containing_build.commit_position >= commit_position

    if earliest_containing_build.commit_position == commit_position:
      # The requested commit position is that of an existing build.
      get_build_sha_parameters = self.CreateInputObjectInstance(
          GetIsolateShaForBuildParameters,
          master_name=master_name,
          builder_name=builder_name,
          build_number=earliest_containing_build.build_number,
          step_name=step_name)
      yield GetIsolateShaForBuildPipeline(get_build_sha_parameters)
    else:
      # The requested commit position needs to be compiled.
      run_flake_try_job_parameters = self.CreateInputObjectInstance(
          RunFlakeTryJobParameters,
          analysis_urlsafe_key=parameters.analysis_urlsafe_key,
          revision=parameters.revision,
          flake_cache_name=None,
          dimensions=[])
      yield RunFlakeTryJobPipeline(run_flake_try_job_parameters)
