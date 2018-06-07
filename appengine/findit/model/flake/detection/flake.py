# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from libs import gtest_name_util


class Flake(ndb.Model):
  """Parent flake model which different flake occurrences are grouped under."""

  # Project to which this flake belongs to, for example: chromium, angle. This
  # property matches with LUCI's projects, which is defined in:
  # https://chrome-internal.googlesource.com/infradata/config/+/master/configs/
  # luci-config/projects.cfg
  luci_project = ndb.StringProperty(required=True)

  # normalized_step_name is step_name without hardware information, 'with patch'
  # and 'without patch' postfix.
  # For example: 'angle_unittests (with patch) on Android' -> 'angle_unittests'.
  normalized_step_name = ndb.StringProperty(required=True)

  # normalized_test_name is test_name without 'PRE_' prefixes and parameters.
  # For example: 'A/ColorSpaceTest.PRE_PRE_testNullTransform/137 maps' ->
  # 'ColorSpaceTest.testNullTransform'.
  normalized_test_name = ndb.StringProperty(required=True)

  @staticmethod
  def GetId(luci_project, normalized_step_name, normalized_test_name):
    return '%s@%s@%s' % (luci_project, normalized_step_name,
                         normalized_test_name)

  @classmethod
  def Get(cls, luci_project, normalized_step_name, normalized_test_name):
    """Gets a Flake entity for a flaky test if it exists."""
    return cls.get_by_id(
        cls.GetId(
            luci_project=luci_project,
            normalized_step_name=normalized_step_name,
            normalized_test_name=normalized_test_name))

  @classmethod
  def Create(cls, luci_project, normalized_step_name, normalized_test_name):
    """Creates a Flake entity for a flaky test."""
    flake_id = cls.GetId(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name)

    return cls(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name,
        id=flake_id)

  # TODO(crbug.com/848867): Correctly handles different step names that map to
  # the same target/binary.
  @staticmethod
  def NormalizeStepName(step_name):
    """Removes platform information, 'with patch' and 'without patch' postfix
    from the step_name.

    For example, 'angle_unittests (with patch) on Android' becomes
    'angle_unittests'.
    """
    return step_name.split(' ')[0]

  @staticmethod
  def NormalizeTestName(test_name):
    """Removes prefixes and parameters from test names if they are gtests.

    For example, 'A/ColorSpaceTest.PRE_PRE_testNullTransform/137' maps to
    'ColorSpaceTest.testNullTransform'.

    Note that this method is a no-op for non-gtests.
    """
    return gtest_name_util.RemoveAllPrefixesFromTestName(
        gtest_name_util.RemoveParametersFromTestName(test_name))
