# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Special logic of pre test analysis.

Build with test failures will be pre-processed to determine if a new analysis is
needed or not.
"""

from google.appengine.ext import ndb

from findit_v2.model import luci_build
from findit_v2.model.test_failure import TestFailure
from findit_v2.model.test_failure import TestFailureAnalysis
from findit_v2.model.test_failure import TestFailureGroup
from findit_v2.services.analysis.analysis_api import AnalysisAPI
from findit_v2.services.failure_type import StepTypeEnum


class TestAnalysisAPI(AnalysisAPI):

  @property
  def step_type(self):
    return StepTypeEnum.TEST

  def _GetMergedFailureKey(self, failure_entities, referred_build_id,
                           step_ui_name, atomic_failure):
    return TestFailure.GetMergedFailureKey(failure_entities, referred_build_id,
                                           step_ui_name, atomic_failure)

  def _GetFailuresInBuild(self, project_api, build, failed_steps):
    return project_api.GetTestFailures(build, failed_steps)

  def _GetFailuresWithMatchingFailureGroups(self, project_api, context, build,
                                            first_failures_in_current_build):
    return project_api.GetFailuresWithMatchingTestFailureGroups(
        context, build, first_failures_in_current_build)

  def _CreateFailure(self, failed_build_key, step_ui_name,
                     first_failed_build_id, last_passed_build_id,
                     merged_failure_key, atomic_failure, properties):
    """Creates a TestFailure entity."""
    assert (not atomic_failure or len(atomic_failure) == 1), (
        'Atomic test failure should be a frozenset of a single element.')
    return TestFailure.Create(
        failed_build_key=failed_build_key,
        step_ui_name=step_ui_name,
        test=next(iter(atomic_failure)) if atomic_failure else None,
        first_failed_build_id=first_failed_build_id,
        last_passed_build_id=last_passed_build_id,
        # Default to first_failed_build_id, will be updated later if matching
        # group exists.
        failure_group_build_id=first_failed_build_id,
        merged_failure_key=merged_failure_key,
        properties=properties)

  def _GetFailureEntitiesForABuild(self, build):
    more = True
    cursor = None
    test_failure_entities = []
    while more:
      entities, cursor, more = TestFailure.query(
          ancestor=ndb.Key(luci_build.LuciFailedBuild, build.id)).fetch_page(
              500, start_cursor=cursor)
      test_failure_entities.extend(entities)

    assert test_failure_entities, (
        'No test failure saved in datastore for build {}'.format(build.id))
    return test_failure_entities

  def _CreateFailureGroup(self, context, build, test_failure_keys,
                          last_passed_gitiles_id, last_passed_commit_position,
                          first_failed_commit_position):
    group_entity = TestFailureGroup.Create(
        luci_project=context.luci_project_name,
        luci_bucket=build.builder.bucket,
        build_id=build.id,
        gitiles_host=context.gitiles_host,
        gitiles_project=context.gitiles_project,
        gitiles_ref=context.gitiles_ref,
        last_passed_gitiles_id=last_passed_gitiles_id,
        last_passed_commit_position=last_passed_commit_position,
        first_failed_gitiles_id=context.gitiles_id,
        first_failed_commit_position=first_failed_commit_position,
        test_failure_keys=test_failure_keys)
    return group_entity

  def _CreateFailureAnalysis(
      self, luci_project, context, build, last_passed_gitiles_id,
      last_passed_commit_position, first_failed_commit_position,
      rerun_builder_id, test_failure_keys):
    analysis = TestFailureAnalysis.Create(
        luci_project=luci_project,
        luci_bucket=build.builder.bucket,
        luci_builder=build.builder.builder,
        build_id=build.id,
        gitiles_host=context.gitiles_host,
        gitiles_project=context.gitiles_project,
        gitiles_ref=context.gitiles_ref,
        last_passed_gitiles_id=last_passed_gitiles_id,
        last_passed_commit_position=last_passed_commit_position,
        first_failed_gitiles_id=context.gitiles_id,
        first_failed_commit_position=first_failed_commit_position,
        rerun_builder_id=rerun_builder_id,
        test_failure_keys=test_failure_keys)
    return analysis
