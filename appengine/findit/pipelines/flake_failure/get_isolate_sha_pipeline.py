# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from common.findit_http_client import FinditHttpClient
from dto.flake_try_job_result import FlakeTryJobResult
from dto.step_metadata import StepMetadata
from gae_libs.pipelines import GeneratorPipeline
from gae_libs.pipelines import pipeline
from gae_libs.pipelines import SynchronousPipeline
from libs.list_of_basestring import ListOfBasestring
from libs.structured_object import StructuredObject
from model.isolated_target import IsolatedTarget
from pipelines.flake_failure.run_flake_try_job_pipeline import (
    RunFlakeTryJobParameters)
from pipelines.flake_failure.run_flake_try_job_pipeline import (
    RunFlakeTryJobPipeline)
from services import constants
from services import swarmbot_util
from services import swarming
from services.flake_failure import flake_constants
from services.flake_failure import flake_try_job
from waterfall import build_util
from waterfall import buildbot


class GetIsolateShaForCommitPositionParameters(StructuredObject):
  # The urlsafe key to the MasterFlakeAnalysis this pipeline is assisting in
  # analyyzing.
  analysis_urlsafe_key = basestring

  # The exact commit position being requested for analysis.
  commit_position = int

  # Dimensions of the bot that will be used to trigger try jobs.
  dimensions = ListOfBasestring

  # The exact revision corresponding to commit_position being requested.
  revision = basestring

  # Information about the test used to determine isolated targets.
  step_metadata = StepMetadata

  # A late build number on the builder to assist in finding nearby builds.
  upper_bound_build_number = int


class GetIsolateShaForTryJobParameters(StructuredObject):
  try_job_result = FlakeTryJobResult
  step_name = basestring


class GetIsolateShaOutput(StructuredObject):
  # The isolate sha of the build artifacts.
  isolate_sha = basestring

  # The url to the build whose existing artifacts were used, if any. Should be
  # mutually exclusive with try_job_url.
  build_url = basestring

  # The url to the try job page that produced compiled artifacts. Should be
  # mutually exclusive with build_url.
  try_job_url = basestring


class GetIsolateShaForTargetInput(StructuredObject):
  # The urlsafe key to an IsolatedTarget to extract the isolated hash.
  isolated_target_urlsafe_key = basestring


class GetIsolateShaForTargetPipeline(SynchronousPipeline):
  input_type = GetIsolateShaForTargetInput
  output_type = GetIsolateShaOutput

  def RunImpl(self, parameters):
    isolated_target = ndb.Key(
        urlsafe=parameters.isolated_target_urlsafe_key).get()
    assert isolated_target, 'IsolatedTarget is missing unexpectedly!'

    return GetIsolateShaOutput(
        isolate_sha=isolated_target.isolated_hash,
        build_url=isolated_target.build_url,
        try_job_url=None)


class GetIsolateShaForTryJobPipeline(SynchronousPipeline):
  input_type = GetIsolateShaForTryJobParameters
  output_type = GetIsolateShaOutput

  def RunImpl(self, parameters):
    isolated_tests = parameters.try_job_result.report.isolated_tests
    assert len(isolated_tests) == 1, (
        'Expecting only one isolate target, but got {}'.format(
            len(isolated_tests)))
    return GetIsolateShaOutput(
        isolate_sha=isolated_tests.values()[0],
        build_url=None,
        try_job_url=parameters.try_job_result.url)


class GetIsolateShaForCommitPositionPipeline(GeneratorPipeline):

  input_type = GetIsolateShaForCommitPositionParameters

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
    commit_position = parameters.commit_position
    target_name = parameters.step_metadata.isolate_target_name

    targets = (
        IsolatedTarget.FindIsolateAtOrAfterCommitPositionByMaster(
            master_name, builder_name, constants.GITILES_HOST,
            constants.GITILES_PROJECT, constants.GITILES_REF, target_name,
            commit_position))

    assert targets, ((
        'No IsolatedTargets found for {}/{} with minimum commit position '
        '{}').format(master_name, builder_name, commit_position))

    upper_bound_target = targets[0]

    if upper_bound_target.commit_position == commit_position:
      # The requested commit position is that of a found IsolatedTarget.
      get_target_input = GetIsolateShaForTargetInput(
          isolated_target_urlsafe_key=upper_bound_target.key.urlsafe())
      yield GetIsolateShaForTargetPipeline(get_target_input)
    else:
      # The requested commit position needs to be compiled.
      _, reference_build_info = build_util.GetBuildInfo(
          master_name, builder_name, analysis.build_number)
      parent_mastername = (
          reference_build_info.parent_mastername or master_name)
      parent_buildername = (
          reference_build_info.parent_buildername or builder_name)
      cache_name = swarmbot_util.GetCacheName(
          parent_mastername,
          parent_buildername,
          suffix=flake_constants.FLAKE_CACHE_SUFFIX)
      step_name = analysis.step_name
      test_name = analysis.test_name

      try_job = flake_try_job.GetTryJob(master_name, builder_name, step_name,
                                        test_name, parameters.revision)
      run_flake_try_job_parameters = self.CreateInputObjectInstance(
          RunFlakeTryJobParameters,
          analysis_urlsafe_key=parameters.analysis_urlsafe_key,
          revision=parameters.revision,
          flake_cache_name=cache_name,
          dimensions=parameters.dimensions,
          urlsafe_try_job_key=try_job.key.urlsafe())

      with pipeline.InOrder():
        try_job_result = yield RunFlakeTryJobPipeline(
            run_flake_try_job_parameters)
        get_isolate_sha_from_try_job_input = self.CreateInputObjectInstance(
            GetIsolateShaForTryJobParameters,
            try_job_result=try_job_result,
            step_name=step_name)
        yield GetIsolateShaForTryJobPipeline(get_isolate_sha_from_try_job_input)
