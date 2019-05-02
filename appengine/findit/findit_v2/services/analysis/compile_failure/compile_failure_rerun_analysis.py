# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""The core logic of compile analysis."""

import logging

from google.appengine.ext import ndb

from common.waterfall import buildbucket_client
from findit_v2.model.compile_failure import CompileRerunBuild
from findit_v2.services import projects
from findit_v2.services import constants


def _GetRerunBuildInputProperties(context, referred_build, targets):
  luci_project = context.luci_project_name
  project_api = projects.GetProjectAPI(luci_project)
  assert project_api, 'Unsupported project {}'.format(luci_project)

  return project_api.GetCompileRerunBuildInputProperties(
      referred_build, targets)


def _GetRerunBuildTags(analyzed_build_id):
  return [{
      'key': constants.RERUN_BUILD_PURPOSE_TAG_KEY,
      'value': constants.COMPILE_RERUN_BUILD_PURPOSE
  }, {
      'key': constants.ANALYZED_BUILD_ID_TAG_KEY,
      'value': analyzed_build_id
  }]


# pylint: disable=E1120
@ndb.transactional(xg=True)
def TriggerRerunBuild(context, analyzed_build_id, referred_build, analysis_key,
                      rerun_builder, rerun_commit, output_targets):
  """Triggers a rerun build if there's no existing one.

  Creates and saves a CompileRerunBuild entity if a new build is triggered.

  Checking for existing build and saving new build are in one transaction to
  make sure no duplicated rerun builds can be triggered.

  Args:
    context (findit_v2.services.context.Context): Scope of the analysis.
    analyzed_build_id (int): Build id of the build that's being analyzed.
    referred_build (buildbucket build.proto): Info about the build being
      referred to trigger new rerun builds. This build could be the analyzed
      build or a previous rerun build in the same analysis.
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
  input_properties = _GetRerunBuildInputProperties(context, referred_build,
                                                   output_targets)
  if not input_properties:
    logging.error(
        'Failed to get input properties to trigger rerun build'
        'for build %d.', analyzed_build_id)
    return

  new_build = buildbucket_client.TriggerV2Build(
      rerun_builder, rerun_commit, input_properties, tags=rerun_tags)

  if not new_build:
    logging.error(
        'Failed to trigger rerun build for %s in build %d,'
        'on commit %s', output_targets, analyzed_build_id,
        rerun_commit.gitiles_id)
    return

  CompileRerunBuild.Create(
      luci_project=rerun_builder.project,
      luci_bucket=rerun_builder.bucket,
      luci_builder=referred_build.builder.builder,
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
