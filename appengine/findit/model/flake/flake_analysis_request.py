# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from model.flake.master_flake_analysis import MasterFlakeAnalysis
from model.versioned_model import VersionedModel


class BuildStep(ndb.Model):
  """Represents a build step on Waterfall or Commit Queue.

  For a build step on Commit Queue, the matching Waterfall build step could be
  added if found.
  """

  # The build step in which a flake actually occurred.
  master_name = ndb.StringProperty(indexed=False)
  builder_name = ndb.StringProperty(indexed=False)
  build_number = ndb.IntegerProperty(indexed=False)
  step_name = ndb.StringProperty(indexed=False)

  # When the flake was reported on this step.
  reported_time = ndb.DateTimeProperty(indexed=False)

  # The matching build step on the Waterfall of the matching test configuration.
  wf_master_name = ndb.StringProperty(indexed=False)
  wf_builder_name = ndb.StringProperty(indexed=False)
  wf_build_number = ndb.IntegerProperty(indexed=False)
  wf_step_name = ndb.StringProperty(indexed=False)

  # Indicate whether the flake is run on Swarming.
  swarmed = ndb.BooleanProperty(indexed=False, default=False)

  # Indicate whether analysis on the step is supported.
  supported = ndb.BooleanProperty(indexed=False, default=False)

  # Indicate whether the flake on this configuration is analyzed.
  analyzed = ndb.BooleanProperty(indexed=False, default=False)

  @staticmethod
  def _StripMasterPrefix(name):
    master_prefix = 'master.'
    if name.startswith(master_prefix):
      return name[len(master_prefix):]
    return name

  @staticmethod
  def Create(master_name, builder_name, build_number, step_name, reported_time):
    return BuildStep(
        master_name=BuildStep._StripMasterPrefix(master_name),
        builder_name=builder_name,
        build_number=build_number,
        step_name=step_name,
        reported_time=reported_time)


class FlakeAnalysisRequest(VersionedModel):
  """Represents a request to analyze a flake.

  The name of the flake will be the key, and the model is versioned.
  """

  # Name of the flake. Could be a step name, or a test name.
  # Assume there are no step and test with the same name.
  name = ndb.StringProperty(indexed=True)

  # Indicate whether the flake is a step or a test.
  is_step = ndb.BooleanProperty(indexed=True, default=True)

  # Indicate whether the flake is run on Swarming for some configuration.
  swarmed = ndb.BooleanProperty(indexed=False, default=False)

  # Indicate whether analysis on this flake is supported.
  supported = ndb.BooleanProperty(indexed=False, default=False)

  # The bug id for this flake on Monorail.
  bug_id = ndb.IntegerProperty(indexed=False)

  # The emails of users who request analysis of this flake.
  user_emails = ndb.StringProperty(indexed=False, repeated=True)

  # The build steps in which the flake occurred.
  build_steps = ndb.LocalStructuredProperty(
      BuildStep, compressed=True, repeated=True)

  # Executed analyses on different test configurations.
  analyses = ndb.KeyProperty(MasterFlakeAnalysis, repeated=True)

  # Arguments number differs from overridden method - pylint: disable=W0221
  @classmethod
  def Create(cls, name, is_step, bug_id):
    instance = super(cls, FlakeAnalysisRequest).Create(key=name)
    instance.name = name
    instance.is_step = is_step
    instance.bug_id = bug_id
    return instance

  def AddBuildStep(
      self, master_name, builder_name, build_number, step_name, reported_time):
    """Adds a build step in which the flake is found."""
    for s in self.build_steps:
      if s.master_name == master_name and s.builder_name == builder_name:
        # For the same builder/tester, only analyze the earliest build.
        # TODO: re-evaluate cases that flakes might be re-introduced in between.
        if s.build_number <= build_number:
          return False
        s.build_number = build_number
        s.reported_time = reported_time
        return True

    self.build_steps.append(
        BuildStep.Create(
            master_name, builder_name, build_number, step_name, reported_time))
    return True
