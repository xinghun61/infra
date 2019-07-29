# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Special logic of pre compile analysis.

Build with compile failures will be pre-processed to determine if a new compile
analysis is needed or not.
"""

from findit_v2.model import luci_build
from findit_v2.model.compile_failure import CompileFailure
from findit_v2.model.compile_failure import CompileFailureAnalysis
from findit_v2.model.compile_failure import CompileFailureInRerunBuild
from findit_v2.model.compile_failure import CompileFailureGroup
from findit_v2.services import projects
from findit_v2.services.analysis.analysis_api import AnalysisAPI
from findit_v2.services.failure_type import StepTypeEnum


class CompileAnalysisAPI(AnalysisAPI):

  @property
  def step_type(self):
    return StepTypeEnum.COMPILE

  def GetMergedFailureKey(self, failure_entities, referred_build_id,
                          step_ui_name, atomic_failure):
    """Gets the key to the entity that a failure should merge into.

    Args:
      failure_entities(dict of list of failure entities): Contains failure
      entities that the current failure could potentially merge into. This dict
      could potentially be modified, if the referred build was not included
      before.
      referred_build_id(int): Id of current failure's first failed build or
        failure group.
      step_ui_name(str): Step name of current failure.
      atomic_failure(frozenset): Failed output_targets.
    """
    return CompileFailure.GetMergedFailureKey(
        failure_entities, referred_build_id, step_ui_name, atomic_failure)

  def GetFailuresInBuild(self, project_api, build, failed_steps):
    """Gets detailed failure information from a build.

    Args:
      project_api (ProjectAPI): API for project specific logic.
      build (buildbucket build.proto): ALL info about the build.
      failed_steps (list of step proto): Info about failed steps in the build.
    """
    return project_api.GetCompileFailures(build, failed_steps)

  def GetFailuresWithMatchingFailureGroups(self, context, build,
                                           first_failures_in_current_build):
    """Gets reusable failure groups for given failure(s).

    Args:
      context (findit_v2.services.context.Context): Scope of the analysis.
      build (buildbucket build.proto): ALL info about the build.
      first_failures_in_current_build (dict): A dict for failures that happened
        the first time in current build.
      {
        'failures': {
          'step': {
            'atomic_failures': [
              frozenset(['target4'])
            ],
            'last_passed_build': {
              'id': 8765432109,
              'number': 122,
              'commit_id': 'git_sha1'
            },
          },
        },
        'last_passed_build': {
          # In this build all the failures that happened in the build being
          # analyzed passed.
          'id': 8765432108,
          'number': 121,
          'commit_id': 'git_sha0'
        }
      }
    """
    luci_project = context.luci_project_name
    project_api = projects.GetProjectAPI(luci_project)
    assert project_api, 'Unsupported project {}'.format(luci_project)

    return project_api.GetFailuresWithMatchingCompileFailureGroups(
        context, build, first_failures_in_current_build)

  def CreateFailure(self, failed_build_key, step_ui_name, first_failed_build_id,
                    last_passed_build_id, merged_failure_key, atomic_failure,
                    properties):
    """Creates a CompileFailure entity.

    Args:
      failed_build_key (LuciFailedBuild Key)
      step_ui_name (str): Name of the failed compile step.
      first_failed_build_id (int): Id of the build that such failure first time
        happened.
      last_passed_build_id (int): Id of the build that such target passed.
      merged_failure_key (CompileFailure Key): Key to the CompileFailure this
        failure entity should merge into.
      atomic_failure (frozenset): Set of the failed output targets.
      properties (dict): Arbitrary properties about the failure.
    """
    return CompileFailure.Create(
        failed_build_key=failed_build_key,
        step_ui_name=step_ui_name,
        output_targets=list(atomic_failure or []),
        rule=(properties or {}).get('rule'),
        first_failed_build_id=first_failed_build_id,
        last_passed_build_id=last_passed_build_id,
        # Default to first_failed_build_id, will be updated later if matching
        # group exists.
        failure_group_build_id=first_failed_build_id,
        merged_failure_key=merged_failure_key)

  def GetFailureEntitiesForABuild(self, build):
    build_entity = luci_build.LuciFailedBuild.get_by_id(build.id)
    assert build_entity, 'No LuciFailedBuild entity for build {}'.format(
        build.id)

    compile_failure_entities = CompileFailure.query(
        ancestor=build_entity.key).fetch()
    assert compile_failure_entities, (
        'No compile failure saved in datastore for build {}'.format(build.id))
    return compile_failure_entities

  def CreateAndSaveFailureGroup(
      self, context, build, compile_failure_keys, last_passed_gitiles_id,
      last_passed_commit_position, first_failed_commit_position):
    group_entity = CompileFailureGroup.Create(
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
        compile_failure_keys=compile_failure_keys)
    group_entity.put()

  def CreateAndSaveFailureAnalysis(
      self, luci_project, context, build, last_passed_gitiles_id,
      last_passed_commit_position, first_failed_commit_position,
      rerun_builder_id, compile_failure_keys):
    analysis = CompileFailureAnalysis.Create(
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
        compile_failure_keys=compile_failure_keys)
    analysis.Save()
    return analysis

  def SaveRerunBuildResults(self, rerun_build_entity, status,
                            detailed_compile_failures):
    """Saves the results of the rerun build.

    Args:
      status (int): status of the build. See common_pb2 for available values.
      detailed_compile_failures (dict): Compile failures in the rerun build.
      Format is like:
      {
        'step_name': {
          'failures': {
            frozenset(['target1', 'target2']): {
              'first_failed_build': {
                'id': 8765432109,
                'number': 123,
                'commit_id': 654321
              },
              'last_passed_build': None,
              'properties': {
                # Arbitrary information about the failure if exists.
              }
            },
          'first_failed_build': {
            'id': 8765432109,
            'number': 123,
            'commit_id': 654321
          },
          'last_passed_build': None,
          'properties': {
            # Arbitrary information about the failure if exists.
          }
        },
      }
    """
    rerun_build_entity.status = status
    rerun_build_entity.failures = []
    for step_ui_name, step_info in detailed_compile_failures.iteritems():
      for output_targets in step_info['failures']:
        failure_entity = CompileFailureInRerunBuild(
            step_ui_name=step_ui_name, output_targets=output_targets)
        rerun_build_entity.failures.append(failure_entity)
    rerun_build_entity.put()
