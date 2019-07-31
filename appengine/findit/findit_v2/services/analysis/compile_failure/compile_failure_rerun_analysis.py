# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""The core logic of compile analysis."""

import logging

from buildbucket_proto import common_pb2
from google.appengine.ext import ndb

from common.waterfall import buildbucket_client
from findit_v2.model import compile_failure
from findit_v2.model import luci_build
from findit_v2.model.compile_failure import CompileFailureAnalysis
from findit_v2.model.compile_failure import CompileRerunBuild
from findit_v2.model.gitiles_commit import Culprit
from findit_v2.services import projects
from findit_v2.services import constants
from findit_v2.services.analysis import analysis_util
from libs import analysis_status
from libs import time_util
from services import git


def _GetRegressionRangesForCompileFailures(analysis):
  """Gets updated regression ranges and failures having that range.

    Uses completed rerun builds in this analysis to narrow down regression
    ranges for each failures.

    For example, if initially the regression range for the analysis is (r0, r10]
    and compile failures in the analysis have output_targets ['a.o', 'b.o']
    and ['c.o'] respectively (below use output_targets to identify a compile
    failure).
    1. When there's no rerun build, all targets have the same range (r0, r10]
    2. 1st rerun build on r5, all passed. Then all failures have a smaller
      range (r5, r10]
    3. 2nd rerun build on r7, ['a.o', 'b.o'] failed, ['c.o'] passed. So now the
      regression range for ['a.o', 'b.o'] is (r5, r7], and for ['c.o'] is
      (r7, r10].
    4. 3rd rerun build on r6, and it only compiles ['a.o', 'b.o']. and both of
     them failed. The regression range is updated to (r5, r6].
    6. 4th rerun build on r8 and it only compiles 'c.o', and it failed. So the
     regression range is updated to (r7, r8].

    Returns:
    (list of dict): Failures with the same regression range and the range.
    [
      {
        'failures': [CompileFailure(output_targets=['a.o', 'b.o'])],
        'last_passed_commit': GitilesCommit(gitiles_id=r5),
        'first_failed_commit': GitilesCommit(gitiles_id=r6)
      },
      {
        'failures': [CompileFailure(output_targets=['c.o'])],
        'last_passed_commit': GitilesCommit(gitiles_id=r7),
        'first_failed_commit': GitilesCommit(gitiles_id=r8)
      },
    ]
    """
  compile_failures = ndb.get_multi(analysis.compile_failure_keys)
  rerun_builds = CompileRerunBuild.query(ancestor=analysis.key).order(
      CompileRerunBuild.gitiles_commit.commit_position).fetch()
  if not rerun_builds:
    return [{
        'failures': compile_failures,
        'last_passed_commit': analysis.last_passed_commit,
        'first_failed_commit': analysis.first_failed_commit
    }]

  # Gets rerun builds results.
  # Specifically, if a rerun build failed, gets its failed targets.
  # Otherwise just keep an empty failed targets indicating a successful build.
  rerun_builds_info = [
      (rerun_build.gitiles_commit, rerun_build.GetFailedTargets())
      for rerun_build in rerun_builds
      if rerun_build.status in [common_pb2.FAILURE, common_pb2.SUCCESS]
  ]

  # A list for regression ranges of each failure.
  # Initially all failures have the same (and the widest) range. By checking
  # rerun build results, each failure's regression range could be narrower and
  # different from others.
  failures_with_range = []
  for failure in compile_failures:
    if failure.culprit_commit_key:
      # Skips the failures if it already found the culprit.
      continue
    failures_with_range.append({
        'failure': failure,
        'last_passed_commit': analysis.last_passed_commit,
        'first_failed_commit': analysis.first_failed_commit
    })

  # Updates regression range for each failed targets.
  analysis_util.UpdateFailureRegressionRanges(rerun_builds_info,
                                              failures_with_range)
  # Groups failed targets with the same regression range, and returns these
  # groups along with their regression range.
  return analysis_util.GroupFailuresByRegerssionRange(failures_with_range)


def _GetRerunBuildInputProperties(context, targets):
  luci_project = context.luci_project_name
  project_api = projects.GetProjectAPI(luci_project)
  assert project_api, 'Unsupported project {}'.format(luci_project)

  return project_api.GetCompileRerunBuildInputProperties(targets)


def _GetRerunBuildTags(analyzed_build_id):
  return [{
      'key': constants.RERUN_BUILD_PURPOSE_TAG_KEY,
      'value': constants.COMPILE_RERUN_BUILD_PURPOSE
  },
          {
              'key': constants.ANALYZED_BUILD_ID_TAG_KEY,
              'value': str(analyzed_build_id)
          }]


# pylint: disable=E1120
@ndb.transactional(xg=True)
def TriggerRerunBuild(context, analyzed_build_id, analysis_key, rerun_builder,
                      rerun_commit, output_targets):
  """Triggers a rerun build if there's no existing one.

  Creates and saves a CompileRerunBuild entity if a new build is triggered.

  Checking for existing build and saving new build are in one transaction to
  make sure no duplicated rerun builds can be triggered.

  Args:
    context (findit_v2.services.context.Context): Scope of the analysis.
    analyzed_build_id (int): Build id of the build that's being analyzed.
    analysis_key (Key to CompileFailureAnalysis): Key to the running analysis.
    rerun_builder (BuilderId): Builder to rerun the build.
    rerun_commit (GitilesCommit): Gitiles commit the build runs on.
    output_targets (dict): A dict of targets the rerun build should re-compile.
    {
      'compile': ['target1.o', ...]
    }
  """
  # Check if there's a running build on that commit already.
  existing_builds = CompileRerunBuild.SearchBuildOnCommit(
      analysis_key, rerun_commit)
  if existing_builds:
    # TODO(crbug/957760): Re-trigger the build if the existing one(s) ended with
    # unexpected failures.
    logging.debug('Found existing rerun build for analysis %s on commit %d.',
                  analysis_key.urlsafe(), rerun_commit.commit_position)
    return

  rerun_tags = _GetRerunBuildTags(analyzed_build_id)
  input_properties = _GetRerunBuildInputProperties(context, output_targets)
  if not input_properties:
    logging.error(
        'Failed to get input properties to trigger rerun build'
        'for build %d.', analyzed_build_id)
    return

  gitiles_commit_pb = common_pb2.GitilesCommit(
      project=rerun_commit.gitiles_project,
      host=rerun_commit.gitiles_host,
      ref=rerun_commit.gitiles_ref,
      id=rerun_commit.gitiles_id)
  new_build = buildbucket_client.TriggerV2Build(
      rerun_builder, gitiles_commit_pb, input_properties, tags=rerun_tags)

  if not new_build:
    logging.error(
        'Failed to trigger rerun build for %s in build %d,'
        'on commit %s', output_targets, analyzed_build_id,
        rerun_commit.gitiles_id)
    return

  CompileRerunBuild.Create(
      luci_project=rerun_builder.project,
      luci_bucket=rerun_builder.bucket,
      luci_builder=rerun_builder.builder,
      build_id=new_build.id,
      legacy_build_number=new_build.number,
      gitiles_host=rerun_commit.gitiles_host,
      gitiles_project=rerun_commit.gitiles_project,
      gitiles_ref=rerun_commit.gitiles_ref,
      gitiles_id=rerun_commit.gitiles_id,
      commit_position=rerun_commit.commit_position,
      status=new_build.status,
      create_time=new_build.create_time.ToDatetime(),
      parent_key=analysis_key).put()


def _SaveCulpritInCompileFailures(compile_failures, culprit_commit):
  """Saves the culprit to compile failures.

  Args:
    compile_failures (list of CompileFailure): CompileFailures that are caused
      by the culprit_commit.
    culprit_commit (GitilesCommit): The commit that caused compile failure(s).
  """
  culprit_entity = Culprit.GetOrCreate(
      gitiles_host=culprit_commit.gitiles_host,
      gitiles_project=culprit_commit.gitiles_project,
      gitiles_ref=culprit_commit.gitiles_ref,
      gitiles_id=culprit_commit.gitiles_id,
      commit_position=culprit_commit.commit_position,
      failure_urlsafe_keys=[cf.key.urlsafe() for cf in compile_failures])

  for failure in compile_failures:
    failure.culprit_commit_key = culprit_entity.key
  ndb.put_multi(compile_failures)


def RerunBasedAnalysis(context, analyzed_build_id):
  """Checks rerun build results and looks for either the culprit or the next
    commit to compile. Then wraps up the analysis with culprit or continues the
     analysis by triggering the next rerun build.

    Args:
      context (findit_v2.services.context.Context): Scope of the analysis.
      analyzed_build_id (int): Build id of the build that's being analyzed.
  """
  analysis = CompileFailureAnalysis.GetVersion(analyzed_build_id)
  assert analysis, 'Failed to get CompileFailureAnalysis for build {}'.format(
      analyzed_build_id)

  rerun_builder = luci_build.ParseBuilderId(analysis.rerun_builder_id)

  # Gets a map from commit_position to gitiles_ids (git_hash/ revision) for the
  # commits between lass_passed_commit and first_failed_commit, bounds are
  # included.
  commit_position_to_git_hash_map = git.MapCommitPositionsToGitHashes(
      analysis.first_failed_commit.gitiles_id,
      analysis.first_failed_commit.commit_position,
      analysis.last_passed_commit.commit_position,
      repo_url=git.GetRepoUrlFromContext(context),
      ref=context.gitiles_ref)
  analysis_completed = True
  analysis_error = None

  # Gets updated regression range for the targets based on rerun build
  # results. The format is like:
  # [
  #   {
  #     'failures': {'compile': ['target1', 'target2']},
  #     'last_passed_commit': left_bound_commit,
  #     'first_failed_commit': right_bound_commit},
  #   {
  #     'failures': {'compile': ['target3']},
  #     'last_passed_commit': other_left_bound_commit,
  #     'first_failed_commit': other_right_bound_commit},
  # ]
  # It's possible that failures have different regression range so that multiple
  # rerun builds got triggered for different failures on different commit.
  # Though this case should be rare.
  updated_ranges = _GetRegressionRangesForCompileFailures(analysis)
  for failures_with_range in updated_ranges:
    last_passed_commit = failures_with_range['last_passed_commit']
    first_failed_commit = failures_with_range['first_failed_commit']
    failures = failures_with_range['failures']

    rerun_commit, culprit_commit = analysis_util.BisectGitilesCommit(
        context, last_passed_commit, first_failed_commit,
        commit_position_to_git_hash_map)
    if culprit_commit:
      # Analysis for these failures has run to the end.
      _SaveCulpritInCompileFailures(failures, culprit_commit)
      continue

    # No culprit found for these failures, analysis continues.
    analysis_completed = False
    if not rerun_commit:
      # TODO (crbug.com/957760): Properly recover failed analysis.
      analysis_error = (
          'Failed to find the next commit to run from the range {}..{}'.format(
              last_passed_commit.commit_position,
              first_failed_commit.commit_position))
      continue

    # Triggers a rerun build unless there's an existing one.
    # It's possible if the existing one is still running so that Findit doesn't
    # know that build's result.
    TriggerRerunBuild(context, analyzed_build_id, analysis.key, rerun_builder,
                      rerun_commit, compile_failure.GetFailedTargets(failures))

  analysis.end_time = time_util.GetUTCNow()
  analysis.status = (
      analysis_status.COMPLETED
      if analysis_completed else analysis_status.RUNNING)
  analysis.error = analysis_error if analysis_error else analysis.error
  analysis.put()
