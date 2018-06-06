# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from libs import gtest_name_util


# TODO(crbug.com/848867): Correctly handles different step names that map to the
# same target/binary.
def _NormalizeStepName(step_name):
  """Removes platform information and with patch postfix from the step_name.

  For example, 'angle_unittests (with patch) on Android' becomes
  'angle_unittests'.
  """
  return step_name.split(' ')[0]


def _NormalizeTestName(test_name):
  """Removes prefixes and parameters from test names if they are gtests.

  For example, 'A/ColorSpaceTest.PRE_PRE_testNullTransform/137' maps to
  'ColorSpaceTest.testNullTransform'.

  Note that this method is no-op for non-gtests.
  """
  return gtest_name_util.RemoveAllPrefixesFromTestName(
      gtest_name_util.RemoveParametersFromTestName(test_name))


class Flake(ndb.Model):
  """Parent flake model which different flake occurrences are grouped under."""

  # Project to which this flake belongs to, for example: chromium, angle. This
  # property matches with LUCI's projects, which is defined in:
  # https://chrome-internal.googlesource.com/infradata/config/+/master/configs/
  # luci-config/projects.cfg
  luci_project = ndb.StringProperty(required=True)

  # step_name may include hardware information and 'with patch' postfix, but
  # normalized step name doesn't.
  step_name = ndb.StringProperty(required=True)
  normalized_step_name = ndb.ComputedProperty(
      lambda self: _NormalizeStepName(self.step_name))

  # normalized_test_name removes the instantiation and parameters parts for
  # parameterized gtests and also remove prefixes if the test name contains
  # 'PRE_'.
  test_name = ndb.StringProperty(required=True)
  normalized_test_name = ndb.ComputedProperty(
      lambda self: _NormalizeTestName(self.test_name))

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
  def Create(cls, luci_project, step_name, test_name):
    """Creates a Flake entity for a flaky test."""
    flake_id = cls.GetId(
        luci_project=luci_project, step_name=step_name, test_name=test_name)

    return cls(
        luci_project=luci_project,
        step_name=step_name,
        test_name=test_name,
        id=flake_id)
