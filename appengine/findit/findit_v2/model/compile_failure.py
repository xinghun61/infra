# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict

from google.appengine.ext import ndb

from findit_v2.model.atomic_failure import AtomicFailure
from findit_v2.model.base_failure_analysis import BaseFailureAnalysis
from findit_v2.model.failure_group import BaseFailureGroup
from findit_v2.model.gitiles_commit import GitilesCommit
from findit_v2.model.luci_build import LuciBuild
from gae_libs.model.versioned_model import VersionedModel


def GetFailedTargets(compile_failures):
  """Gets failed compile targets of each compile step."""
  failed_targets = defaultdict(list)
  for compile_failure in compile_failures or []:
    failed_targets[compile_failure.step_ui_name].extend(
        compile_failure.output_targets)
  return {
      step_ui_name: list(set(failed_targets_in_step))
      for step_ui_name, failed_targets_in_step in failed_targets.iteritems()
  }


class CompileFailure(AtomicFailure):
  """Atom failure inside a compile failure - a failed compile target."""
  # The list of targets the build edge will produce if it succeeds.
  output_targets = ndb.StringProperty(repeated=True)

  # Compile rule, e.g. ACTION, CXX, etc.
  # For chromium builds, it can be found in json.output[ninja_info] log of
  # compile step.
  # For chromeos builds, it can be found in build_compile_failure_output of
  # build.
  rule = ndb.StringProperty()

  # The checked-in source files in the code base that the build edge takes as
  # inputs. Only for CXX or CC failures.
  dependencies = ndb.StringProperty(repeated=True)

  # Key to the failure that this failure merges into.
  # No analysis on current failure, instead use the results of merged_failure.
  merged_failure_key = ndb.KeyProperty(kind='CompileFailure')

  # Arguments number differs from overridden method - pylint: disable=W0221
  @classmethod
  def Create(cls,
             failed_build_key,
             step_ui_name,
             output_targets,
             rule=None,
             first_failed_build_id=None,
             last_passed_build_id=None,
             failure_group_build_id=None,
             files=None,
             dependencies=None,
             merged_failure_key=None,
             properties=None):
    instance = super(CompileFailure, cls).Create(
        failed_build_key, step_ui_name, first_failed_build_id,
        last_passed_build_id, failure_group_build_id, files, properties)
    instance.output_targets = output_targets or []
    instance.rule = rule
    instance.dependencies = dependencies or []
    instance.merged_failure_key = merged_failure_key
    return instance

  def GetFailureIdentifier(self):
    """Gets the identifier to differentiate a compile failure in the compile
      step."""
    return frozenset(self.output_targets or [])

  def GetMergedFailure(self):
    """Gets the most up-to-date merged_failure for the current failure."""
    if self.merged_failure_key:
      return self.merged_failure_key.get()

    if (self.first_failed_build_id == self.build_id and
        self.failure_group_build_id == self.build_id):
      # First failure without being merged into any other failure group.
      return self

    # In a special case that a non-first failure was processed before the first
    # failure, it's possible that the merged_failure_key is not stored in the
    # non-first failure.
    merged_failure_key = self.GetMergedFailureKey(
        {}, self.first_failed_build_id, self.step_ui_name,
        self.GetFailureIdentifier())

    if merged_failure_key:
      self.merged_failure_key = merged_failure_key
      self.put()
      return merged_failure_key.get()

    return None


class CompileFailureGroup(BaseFailureGroup):
  """Class for group of compile failures."""

  # Keys to the failed targets in the first build of the group, remain
  # unchanged after the group is created.
  # These targets are used to compare to failed targets other builds and decide
  # if those targets can be added to the group.
  # If they can, add the targets to the group by setting their
  # failure_group_build_id this group's id.
  compile_failure_keys = ndb.KeyProperty(CompileFailure, repeated=True)

  @property
  def failed_targets(self):
    """Gets failed compile targets of each compile step that are included in the
      group."""
    failed_target_objects = ndb.get_multi(self.compile_failure_keys)
    return GetFailedTargets(failed_target_objects)

  # Arguments number differs from overridden method - pylint: disable=W0221
  @classmethod
  def Create(cls, luci_project, luci_bucket, build_id, gitiles_host,
             gitiles_project, gitiles_ref, last_passed_gitiles_id,
             last_passed_commit_position, first_failed_gitiles_id,
             first_failed_commit_position, compile_failure_keys):
    assert compile_failure_keys, (
        'no failed_targets when creating CompileFailureGroup for {}'.format(
            build_id))

    instance = super(CompileFailureGroup, cls).Create(
        luci_project, luci_bucket, build_id, gitiles_host, gitiles_project,
        gitiles_ref, last_passed_gitiles_id, last_passed_commit_position,
        first_failed_gitiles_id, first_failed_commit_position)

    instance.compile_failure_keys = compile_failure_keys
    return instance


class CompileFailureAnalysis(BaseFailureAnalysis, VersionedModel):
  """Class for a compile analysis.

  This class stores information that is needed during the analysis, and also
  some metadata for the analysis.

  The objects are versioned, so when rerun, Findit will create an entity with
  newer version, instead of deleting the existing analysis.
  """
  # Key to the failed targets this analysis analyzes.
  compile_failure_keys = ndb.KeyProperty(CompileFailure, repeated=True)

  @property
  def failed_targets(self):
    """Gets a list of failed compile targets of each compile step that are
      analyzed in the analysis."""
    failed_target_objects = ndb.get_multi(self.compile_failure_keys)
    return GetFailedTargets(failed_target_objects)

  # Arguments number differs from overridden method - pylint: disable=W0221
  @classmethod
  def Create(cls, luci_project, luci_bucket, luci_builder, build_id,
             gitiles_host, gitiles_project, gitiles_ref, last_passed_gitiles_id,
             last_passed_commit_position, first_failed_gitiles_id,
             first_failed_commit_position, rerun_builder_id,
             compile_failure_keys):
    instance = super(CompileFailureAnalysis, cls).Create(build_id)

    last_passed_commit = GitilesCommit(
        gitiles_host=gitiles_host,
        gitiles_project=gitiles_project,
        gitiles_ref=gitiles_ref,
        gitiles_id=last_passed_gitiles_id,
        commit_position=last_passed_commit_position)

    first_failed_commit = GitilesCommit(
        gitiles_host=gitiles_host,
        gitiles_project=gitiles_project,
        gitiles_ref=gitiles_ref,
        gitiles_id=first_failed_gitiles_id,
        commit_position=first_failed_commit_position)

    instance.builder_id = '{}/{}/{}'.format(luci_project, luci_bucket,
                                            luci_builder)
    instance.build_id = build_id
    instance.last_passed_commit = last_passed_commit
    instance.first_failed_commit = first_failed_commit
    instance.rerun_builder_id = rerun_builder_id
    instance.compile_failure_keys = compile_failure_keys

    return instance

  def Update(self, end_time=None, status=None, error=None):
    # pylint: disable=attribute-defined-outside-init
    self.end_time = self.end_time or end_time
    self.status = status if status is not None else self.status
    self.error = error if error else self.error
    self.put()


class CompileFailureInRerunBuild(ndb.Model):
  """Atomic compile failure in a rerun build.

  Since we only need to keep a simple record on what's failed in rerun build,
  it's no need to reuse CompileFailure.
  """
  # Full step name.
  step_ui_name = ndb.StringProperty()

  # Output targets of one failed compile edge that the rerun build tested.
  output_targets = ndb.StringProperty(repeated=True)


class CompileRerunBuild(LuciBuild):
  """Class for a rerun build for a compile failure analysis."""

  # Compile failures in the rerun build.
  failures = ndb.LocalStructuredProperty(
      CompileFailureInRerunBuild, repeated=True)

  def GetFailedTargets(self):
    """Gets a list of failed compile targets of each compile step that failed
      in the rerun build."""
    return GetFailedTargets(self.failures)

  def SaveRerunBuildResults(self, status, detailed_compile_failures):
    """Saves the results of this rerun build.

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
    self.status = status  # pylint: disable=attribute-defined-outside-init
    self.failures = []
    for step_ui_name, step_info in detailed_compile_failures.iteritems():
      for output_targets in step_info['failures']:
        failure_entity = CompileFailureInRerunBuild(
            step_ui_name=step_ui_name, output_targets=output_targets)
        self.failures.append(failure_entity)
    self.put()

  @classmethod
  def SearchBuildOnCommit(cls, analysis_key, commit):
    return cls.query(ancestor=analysis_key).filter(
        cls.gitiles_commit.gitiles_id == commit.gitiles_id).fetch()
