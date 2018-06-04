# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from model.flake.detection.flake import Flake


class BuildConfiguration(ndb.Model):
  """Tracks the build configuration of a flake occurrence."""

  # Used to identify a build configuration.
  luci_project = ndb.StringProperty(required=True)
  luci_bucket = ndb.StringProperty(required=True)
  luci_builder = ndb.StringProperty(required=True)

  # Required by Flake Analyzer to trigger flake analysis. This should be
  # removed once Flake Analyzer doesn't depend on them anymore.
  legacy_master_name = ndb.StringProperty(indexed=False, required=True)


class CQFalseRejectionFlakeOccurrence(ndb.Model):
  """Tracks a flake occurrence that caused CQ false rejections.

  For how this type of flake occurence is detected, please refer to:
  services/flake_detection/flaky_tests.cq_false_rejection.sql
  """

  # Used to identify the flaky build.
  build_id = ndb.IntegerProperty(indexed=False, required=True)

  # Used to identify the build configuration.
  build_configuration = ndb.StructuredProperty(
      BuildConfiguration, required=True)

  # Id of a build that succeeded and has no code change (exclude rebase)
  # comparing to this build. This reference build is used as evidence on why the
  # flaky build is deemed as flaky.
  reference_succeeded_build_id = ndb.IntegerProperty(
      indexed=False, required=True)

  # The time the flake occurence happened (test start time).
  time_happened = ndb.DateTimeProperty(required=True)

  # The time the flake occurrence was detected, used to track the delay of flake
  # detection for this occurrence.
  time_detected = ndb.DateTimeProperty(required=True, auto_now_add=True)

  @classmethod
  def Create(cls, build_id, luci_project, luci_bucket, luci_builder,
             legacy_master_name, reference_succeeded_build_id, time_happened,
             parent_flake_key):
    """Creates a cq false rejection flake occurrence.

    NOTE: This method assumes that the parent Flake entity exists.
    """
    build_configuration = BuildConfiguration(
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder=luci_builder,
        legacy_master_name=legacy_master_name)

    return cls(
        build_id=build_id,
        build_configuration=build_configuration,
        reference_succeeded_build_id=reference_succeeded_build_id,
        time_happened=time_happened,
        parent=parent_flake_key,
        id=build_id)
