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

  # Required for legacy reasons, such as:
  # 1. Flake Analyzer to trigger flake analysis.
  # 2. To obtain isolate_target_name/step_metadata of a step in a build.
  # This should be removed once all builders are migrated to LUCI.
  legacy_master_name = ndb.StringProperty(indexed=False, required=True)
  legacy_build_number = ndb.IntegerProperty(indexed=False, required=True)


class CQFalseRejectionFlakeOccurrence(ndb.Model):
  """Tracks a flake occurrence that caused CQ false rejections.

  For how this type of flake occurence is detected, please refer to:
  services/flake_detection/flaky_tests.cq_false_rejection.sql
  """

  # Used to identify the flaky build.
  build_id = ndb.IntegerProperty(indexed=False, required=True)

  # Used to identify the original name of a step in a given build. step_name may
  # include hardware information, 'with patch' and 'without patch' postfix.
  # For example: 'angle_unittests (with patch) on Android'.
  step_name = ndb.StringProperty(required=True)

  # Used to identify the original name of a test in a given test binary.
  # test_name may include 'PRE_' prefixes and parameters if it's a gtest.
  # For example: 'A/ColorSpaceTest.PRE_PRE_testNullTransform/137'.
  test_name = ndb.StringProperty(required=True)

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

  # The id of the gerrit cl this occurrence is associated with.
  gerrit_cl_id = ndb.IntegerProperty(required=True)

  @staticmethod
  def GetId(build_id, step_name, test_name):
    return '%s@%s@%s' % (build_id, step_name, test_name)

  @classmethod
  def Create(cls, build_id, step_name, test_name, luci_project, luci_bucket,
             luci_builder, legacy_master_name, legacy_build_number,
             reference_succeeded_build_id, time_happened, gerrit_cl_id,
             parent_flake_key):
    """Creates a cq false rejection flake occurrence.

    Args:
      step_name: The original name of a step in a given build.
      test_name: The original name of a test in a give test binary.
      parent_flake_key: parent Flake model this occurrence is grouped under.
                        This method assumes that the parent Flake entity exists.

    For other args, please see model properties.
    """
    flake_occurrence_id = cls.GetId(build_id, step_name, test_name)
    build_configuration = BuildConfiguration(
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder=luci_builder,
        legacy_master_name=legacy_master_name,
        legacy_build_number=legacy_build_number)

    return cls(
        build_id=build_id,
        step_name=step_name,
        test_name=test_name,
        build_configuration=build_configuration,
        reference_succeeded_build_id=reference_succeeded_build_id,
        time_happened=time_happened,
        gerrit_cl_id=gerrit_cl_id,
        id=flake_occurrence_id,
        parent=parent_flake_key)
