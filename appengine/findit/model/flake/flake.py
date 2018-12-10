# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb
from google.appengine.ext.ndb import msgprop

from libs import test_name_util
from model.flake.flake_issue import FlakeIssue
from model.flake.flake_type import FlakeType
from services import step_util


class FlakeCountsByType(ndb.Model):
  """Counts for a specific flake type."""
  flake_type = msgprop.EnumProperty(FlakeType, required=True)
  occurrence_count = ndb.IntegerProperty(default=0)
  impacted_cl_count = ndb.IntegerProperty(default=0)


class TestLocation(ndb.Model):
  """The location of a test in the source tree"""
  file_path = ndb.StringProperty(required=True)
  line_number = ndb.IntegerProperty(required=True)


class Flake(ndb.Model):
  """Parent flake model which different flake occurrences are grouped under."""

  # Project to which this flake belongs to, for example: chromium, angle. This
  # property matches with LUCI's projects, which is defined in:
  # https://chrome-internal.googlesource.com/infradata/config/+/master/configs/
  # luci-config/projects.cfg
  luci_project = ndb.StringProperty(required=True)

  # normalized_step_name is the base test target name of a step where tests are
  # actually defined.
  #
  # Be more specific on base_test_target. For GTest-based tests that run the
  # binaries as it is, base_test_target equals the test target name.
  # For example, 'base_unittests (with patch) on Android' -> 'base_unittests'.
  #
  # For gtest targets that run the binaries with command line arguments to
  # enable specific features, base_test_target equals the name of the underlying
  # test target actually compiles the binary. For example,
  # 'viz_browser_tests (with patch) on Android' -> 'browser_tests'.
  #
  # For script Tests, base_test_target equals the test target name with one
  # exception: '.*_webkit_layout_tests' maps to 'webkit_layout_tests'.
  # For example,
  # 'site_per_process_webkit_layout_tests (with patch)' -> 'webkit_layout_tests'
  # and 'chromedriver_py_tests (with patch)' -> 'chromedriver_py_tests'.
  normalized_step_name = ndb.StringProperty(required=True)

  # normalized_test_name is test_name without 'PRE_' prefixes and parameters.
  # For example: 'A/ColorSpaceTest.PRE_PRE_testNullTransform/137 maps' ->
  # 'ColorSpaceTest.testNullTransform'.
  normalized_test_name = ndb.StringProperty(required=True)

  # test_label_name is the same as a normalized_test_name except that the
  # variable parts are replaced with '*', it is only for display purpose and the
  # intention is to clarify that this name may refer to a group of tests instead
  # of always a spcific one.
  test_label_name = ndb.StringProperty(required=True)

  # The FlakeIssue entity that this flake is associated with.
  flake_issue_key = ndb.KeyProperty(FlakeIssue)

  # Timestamp of the most recent flake occurrence.
  last_occurred_time = ndb.DateTimeProperty(indexed=True)

  # Statistical fields.
  # TODO(crbug/896006): remove false_rejection_count_last_week and
  # impacted_cl_count_last_week when it's stable to use new count fields.
  # Number of false rejection occurrences in the past week.
  false_rejection_count_last_week = ndb.IntegerProperty(default=0, indexed=True)

  # Number of distinct impacted CLs in the past week.
  impacted_cl_count_last_week = ndb.IntegerProperty(default=0, indexed=True)

  # Numbers of flake occurrences and distinct impacted CLs in the past week for
  # each flake type.
  flake_counts_last_week = ndb.StructuredProperty(
      FlakeCountsByType, repeated=True)

  # Score of the flake for ranking.
  # The score is calculated by the number of distinct impacted CLs in each flake
  # type and weights of each flake type.
  flake_score_last_week = ndb.IntegerProperty(indexed=True, default=0)

  # A string like 'Blink>NFC' based on the tags of the OWNERS file applicable to
  # the test location.
  component = ndb.StringProperty(indexed=True)

  # The source file location where the test is defined.
  test_location = ndb.StructuredProperty(TestLocation)

  # Tags that specify the category of the flake occurrence, e.g. builder name,
  # master name, step name, etc.
  tags = ndb.StringProperty(repeated=True)

  # When was the last update of tags based on the test location. Used to
  # determine when to update again since WATCHLIST or dir-component mapping
  # could change along the time.
  last_test_location_based_tag_update_time = ndb.DateTimeProperty()

  @classmethod
  def _CreateKey(cls, luci_project, step_name, test_name):
    return ndb.Key(cls, cls.GetId(luci_project, step_name, test_name))

  @staticmethod
  def GetId(luci_project, normalized_step_name, normalized_test_name):
    return '%s@%s@%s' % (luci_project, normalized_step_name,
                         normalized_test_name)

  @classmethod
  def Create(cls, luci_project, normalized_step_name, normalized_test_name,
             test_label_name):
    """Creates a Flake entity for a flaky test."""
    flake_id = cls.GetId(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name)

    return cls(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name,
        test_label_name=test_label_name,
        id=flake_id)

  @classmethod
  def Get(cls, luci_project, step_name, test_name):
    return cls._CreateKey(luci_project, step_name, test_name).get()

  # TODO(crbug.com/873256): Switch to use base_test_target and refactor this out
  # to services/step.py (with a better name) for reuse by other code once the
  # base_test_target field is in place.
  @staticmethod
  def NormalizeStepName(step_name, master_name, builder_name, build_number):
    """Normalizes step name according to the above mentioned definitions.

    The most reliable solution to obtain base test target names is to add a
    base_test_target field in the GN templates that define the tests and expose
    them through step_metadata, but unfortunately, it doesn't exist yet.

    The closest thing that exists is isolate_target_name in the step_metadata.
    Though the isolate_target_name may go away eventually, it will be kept as it
    is until base_test_target is in place, so it is safe to use
    isolate_target_name as a temporary workaround.

    Args:
      step_name: The original step name, and it may contain hardware information
                 and 'with(out) patch' suffixes.
      master_name: Master name of the build of the step.
      builder_name: Builder name of the build of the step.
      build_number: Build number of the build of the step.

    Returns:
      Normalized version of the given step name.
    """
    isolate_target_name = step_util.GetIsolateTargetName(
        master_name=master_name,
        builder_name=builder_name,
        build_number=build_number,
        step_name=step_name)
    if isolate_target_name:
      if 'webkit_layout_tests' in isolate_target_name:
        return 'webkit_layout_tests'

      return isolate_target_name

    # In case isolate_target_name doesn't exist, fall back to
    # canonical_step_name or step_name.split()[0].
    logging.error((
        'Failed to obtain isolate_target_name for step: %s in build: %s/%s/%s. '
        'Fall back to use canonical_step_name.') % (step_name, master_name,
                                                    builder_name, build_number))
    canonical_step_name = step_util.GetCanonicalStepName(
        master_name=master_name,
        builder_name=builder_name,
        build_number=build_number,
        step_name=step_name)
    if canonical_step_name:
      return canonical_step_name

    logging.error((
        'Failed to obtain canonical_step_name for step: %s in build: %s/%s/%s. '
        'Fall back to use step_name.split()[0].') %
                  (step_name, master_name, builder_name, build_number))
    return step_name.split()[0]

  @staticmethod
  def NormalizeTestName(test_name, step_name=None):
    """Normalizes test names by removing parameters and queries.

    Removes prefixes and parameters from test names if they are gtests. For
    example, 'A/ColorSpaceTest.PRE_PRE_testNullTransform/137' maps to
    'ColorSpaceTest.testNullTransform'.

    Removes queries from test names if they are webkit_layout_tests. For
    example, 'external/wpt/editing/run/inserttext.html?2001-last' maps to
    'external/wpt/editing/run/inserttext.html'

    step_name is an optional argument to help identify the type of the tests.
    If not given, goes through all normalizers for different types of tests.
    Note that without step name, this function is not perfect, for example,
    a/suite/c.html can be both a type parameterized version of suite.html gtest
    or a webkit_layout_tests.

    Args:
      test_name: Any test name, and it can be original test name containing
                 parameters, normalized test name (no-op) or a test label name
                 with masks.
      step_name: The original step name, needed to identify the type of the
                 test, such as webkit_layout_tests, gtests.

    Returns:
      Normalized version of the given test name.
    """
    if step_name and 'webkit_layout_tests' in step_name:
      return test_name_util.RemoveSuffixFromWebkitLayoutTestName(
          test_name_util.RemoveVirtualLayersFromWebkitLayoutTestName(test_name))

    test_name = test_name_util.RemoveAllPrefixesFromGTestName(
        test_name_util.RemoveParametersFromGTestName(test_name))

    return test_name_util.RemoveSuffixFromWebkitLayoutTestName(
        test_name_util.RemoveVirtualLayersFromWebkitLayoutTestName(test_name))

  @staticmethod
  def GetTestLabelName(test_name, step_name):
    """Gets a label name for the normalized step name for display purpose.

    This method works the same way as |NormalizeTestName| except that the
    variable parts are replaced with mask '*' instead of being removed.

    Args:
      test_name: The original test name, and it may contain parameters and
                 prefixes for gtests and queries for webkit_layout_tests.
      step_name: The original step name, needed to identify the type of the
                 test, such as webkit_layout_tests, gtests.

    Returns:
      A test name with the variable parts being replaced with mask '*'.
    """
    if 'webkit_layout_tests' in step_name:
      return test_name_util.ReplaceSuffixFromWebkitLayoutTestNameWithMask(
          test_name)

    return test_name_util.ReplaceAllPrefixesFromGtestNameWithMask(
        test_name_util.ReplaceParametersFromGtestNameWithMask(test_name))

  def GetTestSuiteName(self):
    """Gets suite name of the test from tags."""
    for tag in (self.tags or []):
      if tag.startswith('suite::'):
        return tag.split('::')[1]

    return None

  def GetIssue(self, up_to_date=False, key_only=False):
    """Returns the associated FlakeIssue.

    Args:
      up_to_date (bool): True if want to get the most up-to-date FlakeIssue,
        otherwise False.
      key_only (bool): True if just need the key to the destination issue, False
        if need the entity.
    """
    if not self.flake_issue_key:
      return None

    flake_issue = self.flake_issue_key.get()
    if not flake_issue:
      # Data is inconsistent, reset the key to allow a new FlakeIssue to be
      # attached later.
      self.flake_issue_key = None
      self.put()
      return None

    if flake_issue and up_to_date:
      return flake_issue.GetMostUpdatedIssue(key_only)
    return self.flake_issue_key if key_only else flake_issue
