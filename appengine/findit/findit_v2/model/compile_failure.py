# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from findit_v2.model.atomic_failure import AtomicFailure
from findit_v2.model.base_failure_analysis import BaseFailureAnalysis
from findit_v2.model.failure_group import BaseFailureGroup
from findit_v2.model.gitiles_commit import GitlesCommit
from gae_libs.model.versioned_model import VersionedModel


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
             dependencies=None):
    instance = super(CompileFailure, cls).Create(
        failed_build_key, step_ui_name, first_failed_build_id,
        last_passed_build_id, failure_group_build_id, files)
    instance.output_targets = output_targets or []
    instance.rule = rule
    instance.dependencies = dependencies or []
    return instance


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
    """Gets a list of failed compile targets that are included in the group."""
    failed_target_objects = ndb.get_multi(self.compile_failure_keys)
    targets = []
    for target_obj in failed_target_objects:
      targets.extend(target_obj.output_targets)
    return list(set(targets))

  # Arguments number differs from overridden method - pylint: disable=W0221
  @classmethod
  def Create(cls, luci_project, luci_bucket, build_id, gitiles_host,
             gitiles_project, gitiles_ref, last_pass_gitiles_id, last_pass_cp,
             first_failed_gitiles_id, first_failed_cp, compile_failure_keys):
    assert compile_failure_keys, (
        'no failed_targets when creating CompileFailureGroup for {}'.format(
            build_id))

    instance = super(CompileFailureGroup, cls).Create(
        luci_project, luci_bucket, build_id, gitiles_host, gitiles_project,
        gitiles_ref, last_pass_gitiles_id, last_pass_cp,
        first_failed_gitiles_id, first_failed_cp)

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

  # Arguments number differs from overridden method - pylint: disable=W0221
  @classmethod
  def Create(cls, luci_project, luci_bucket, luci_builder, build_id,
             gitiles_host, gitiles_project, gitiles_ref, last_pass_gitiles_id,
             last_pass_cp, first_failed_gitiles_id, first_failed_cp,
             rerun_builder_id, compile_failure_keys):
    instance = super(CompileFailureAnalysis, cls).Create(build_id)

    last_pass_commit = GitlesCommit(
        gitiles_host=gitiles_host,
        gitiles_project=gitiles_project,
        gitiles_ref=gitiles_ref,
        gitiles_id=last_pass_gitiles_id,
        commit_position=last_pass_cp)

    first_failed_commit = GitlesCommit(
        gitiles_host=gitiles_host,
        gitiles_project=gitiles_project,
        gitiles_ref=gitiles_ref,
        gitiles_id=first_failed_gitiles_id,
        commit_position=first_failed_cp)

    instance.luci_project = luci_project
    instance.bucket_id = '{}/{}'.format(luci_project, luci_bucket)
    instance.builder_id = '{}/{}/{}'.format(luci_project, luci_bucket,
                                            luci_builder)
    instance.build_id = build_id
    instance.last_pass_commit = last_pass_commit
    instance.first_failed_commit = first_failed_commit
    instance.rerun_builder_id = rerun_builder_id
    instance.compile_failure_keys = compile_failure_keys

    return instance
