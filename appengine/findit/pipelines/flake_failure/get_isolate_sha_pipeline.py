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
from services import step_util
from services import swarmbot_util
from services import swarming
from services.flake_failure import flake_constants
from services.flake_failure import flake_try_job
from waterfall import build_util
from waterfall import buildbot


class GetIsolateShaForBuildParameters(StructuredObject):
  # The name of the master to query for a pre-determined sha.
  master_name = basestring

  # The name of the builder to query for a pre-determined sha.
  builder_name = basestring

  # The build number whose to query for a pre-detrermined sha.
  build_number = int

  # The url to the build page corresponding to master_name, builder_name
  # build_number.
  url = basestring

  # The name of the step to query for a pre-determined sha.
  step_name = basestring


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

  # The build number corresponding to the build whose artifacts were used,
  # if any. Used to assist in finding nearby builds. TODO (crbug.com/872992):
  # Remove build_number once LUCI migration is complete.
  build_number = int

  # The url to the build whose existing artifacts were used, if any. Should be
  # mutually exclusive with try_job_url.
  build_url = basestring

  # The url to the try job page that produced compiled artifacts. Should be
  # mutually exclusive with build_url.
  try_job_url = basestring


class GetIsolateShaForTargetInput(StructuredObject):
  # The urlsafe key to an IsolatedTarget to extract the isolated hash.
  isolated_target_urlsafe_key = basestring


class GetIsolateShaForBuildPipeline(SynchronousPipeline):
  input_type = GetIsolateShaForBuildParameters
  output_type = GetIsolateShaOutput

  def RunImpl(self, parameters):
    isolate_sha = swarming.GetIsolatedShaForStep(
        parameters.master_name, parameters.builder_name,
        parameters.build_number, parameters.step_name, FinditHttpClient())
    return GetIsolateShaOutput(
        isolate_sha=isolate_sha,
        build_number=parameters.build_number,
        build_url=parameters.url,
        try_job_url=None)


class GetIsolateShaForTargetPipeline(SynchronousPipeline):
  input_type = GetIsolateShaForTargetInput
  output_type = GetIsolateShaOutput

  def RunImpl(self, parameters):
    isolated_target = ndb.Key(
        urlsafe=parameters.isolated_target_urlsafe_key).get()
    assert isolated_target, 'IsolatedTarget is missing unexpectedly!'

    return GetIsolateShaOutput(
        isolate_sha=isolated_target.GetIsolatedHash(),
        build_number=None,
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
        build_number=None,
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
    step_name = analysis.step_name
    isolate_target_name = parameters.step_metadata.isolate_target_name

    reference_build_info = build_util.GetBuildInfo(master_name, builder_name,
                                                   analysis.build_number)
    parent_mastername = (reference_build_info.parent_mastername or master_name)
    parent_buildername = (
        reference_build_info.parent_buildername or builder_name)

    targets = (
        IsolatedTarget.FindIsolateAtOrAfterCommitPositionByMaster(
            parent_mastername, parent_buildername, constants.GITILES_HOST,
            constants.GITILES_PROJECT, constants.GITILES_REF,
            isolate_target_name, commit_position))

    # TODO(crbug.com/872992): Remove this entire branch's fallback logic once
    # LUCI migration is complete.
    if not targets:
      analysis.LogInfo(
          ('No IsolatedTargets found for {}/{} with minimum commit position '
           '{}. Falling back to searching buildbot').format(
               master_name, builder_name, commit_position))
      _, earliest_containing_build = step_util.GetValidBoundingBuildsForStep(
          master_name, builder_name, step_name, None,
          parameters.upper_bound_build_number, commit_position)

      assert earliest_containing_build, (
          'Unable to find nearest build cycle with minimum commit position '
          '{}'.format(commit_position))

      build_commit_position = earliest_containing_build.commit_position
      assert build_commit_position >= commit_position, (
          'Upper bound build commit position {} is before {}'.format(
              build_commit_position, commit_position))

      if build_commit_position == commit_position:  # pragma: no branch
        get_build_sha_parameters = self.CreateInputObjectInstance(
            GetIsolateShaForBuildParameters,
            master_name=master_name,
            builder_name=builder_name,
            build_number=earliest_containing_build.build_number,
            step_name=step_name,
            url=buildbot.CreateBuildUrl(master_name, builder_name,
                                        earliest_containing_build.build_number))
        yield GetIsolateShaForBuildPipeline(get_build_sha_parameters)
        return

    if targets:
      upper_bound_target = targets[0]
      if upper_bound_target.commit_position == commit_position:
        # The requested commit position is that of a found IsolatedTarget.
        get_target_input = GetIsolateShaForTargetInput(
            isolated_target_urlsafe_key=upper_bound_target.key.urlsafe())
        yield GetIsolateShaForTargetPipeline(get_target_input)
        return

    # The requested commit position needs to be compiled.
    cache_name = swarmbot_util.GetCacheName(
        parent_mastername,
        parent_buildername,
        suffix=flake_constants.FLAKE_CACHE_SUFFIX)
    test_name = analysis.test_name

    try_job = flake_try_job.GetTryJob(master_name, builder_name, step_name,
                                      test_name, parameters.revision)
    run_flake_try_job_parameters = self.CreateInputObjectInstance(
        RunFlakeTryJobParameters,
        analysis_urlsafe_key=parameters.analysis_urlsafe_key,
        revision=parameters.revision,
        flake_cache_name=cache_name,
        dimensions=parameters.dimensions,
        isolate_target_name=isolate_target_name,
        urlsafe_try_job_key=try_job.key.urlsafe())

    with pipeline.InOrder():
      try_job_result = yield RunFlakeTryJobPipeline(
          run_flake_try_job_parameters)
      get_isolate_sha_from_try_job_input = self.CreateInputObjectInstance(
          GetIsolateShaForTryJobParameters,
          try_job_result=try_job_result,
          step_name=step_name)
      yield GetIsolateShaForTryJobPipeline(get_isolate_sha_from_try_job_input)
