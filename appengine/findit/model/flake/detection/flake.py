# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from libs import gtest_name_util

# Used to identify a step that has the with patch postfix.
_WITH_PATCH_POSTFIX = ' (with patch)'


def _RemoveTestTypeWithPatchPostfix(test_type):
  """Removes the (with patch) postfix from the test_type.

  Note that the test_type is assumed to have removed hardware/platform
  information, otherwise this method is no-op.
  """
  if test_type.endswith(_WITH_PATCH_POSTFIX):
    return test_type[:test_type.rfind(_WITH_PATCH_POSTFIX)]

  return test_type


class Flake(ndb.Model):
  """Parent flake model which different flake occurrences are grouped under."""

  # Project to which this flake belongs to, for example: chromium, angle. This
  # property matches with LUCI's projects, which is defined in:
  # https://chrome-internal.googlesource.com/infradata/config/+/master/configs/
  # luci-config/projects.cfg
  luci_project = ndb.StringProperty(required=True)

  # step_name may include hardware information and 'with patch' postfix, but
  # normalized step name doesn't. For example:
  # step name 'angle_unittests (with patch) on Android' and
  # 'angle_unittests (with patch) on Windows-10-15063' have the same normalized
  # step name: 'angle_unittests'.
  # TODO(crbug.com/848867): Correctly handle different step names that map to
  # the same target/binary.
  step_name = ndb.StringProperty(required=True)
  normalized_step_name = ndb.StringProperty(required=True)

  # normalized_test_name removes the instantiation and parameters parts for
  # parameterized gtests and also remove prefixes if the test name contains
  # 'PRE_'. For example: A/ColorSpaceTest.PRE_PRE_testNullTransform/137 maps to
  # ColorSpaceTest.testNullTransform.
  test_name = ndb.StringProperty(required=True)
  normalized_test_name = ndb.StringProperty(required=True)

  # TODO(crbug.com/849462): Re-evaluate the choice of id.
  @staticmethod
  def GetId(luci_project, step_name, test_name):
    return '%s/%s/%s' % (luci_project, step_name, test_name)

  @classmethod
  def Get(cls, luci_project, step_name, test_name):
    """Gets a Flake entity for a flaky test if it exists."""
    return cls.get_by_id(
        cls.GetId(
            luci_project=luci_project, step_name=step_name,
            test_name=test_name))

  @classmethod
  def Create(cls, luci_project, step_name, test_name, test_type):
    """Creates a Flake entity for a flaky test.

    Note that the test_type is assumed to have removed hardware/platform
    information.
    """
    flake_id = cls.GetId(
        luci_project=luci_project, step_name=step_name, test_name=test_name)
    normalized_step_name = _RemoveTestTypeWithPatchPostfix(test_type)
    normalized_test_name = gtest_name_util.RemoveAllPrefixesFromTestName(
        gtest_name_util.RemoveParametersFromTestName(test_name))

    return cls(
        luci_project=luci_project,
        step_name=step_name,
        normalized_step_name=normalized_step_name,
        test_name=test_name,
        normalized_test_name=normalized_test_name,
        id=flake_id)
