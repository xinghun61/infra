# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from libs import test_name_util
from model.flake.flake_issue import FlakeIssue
from services import ci_failure


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

  # The FlakeIssue entity that this flake is associated with.
  flake_issue_key = ndb.KeyProperty(FlakeIssue)

  # Timestamp of the most recent flake occurrence.
  last_occurred_time = ndb.DateTimeProperty(indexed=True)

  # Statistical fields.
  # Number of false rejection occurrences in the past week.
  false_rejection_count_last_week = ndb.IntegerProperty(default=0, indexed=True)

  # Number of distinct impacted CLs in the past week.
  impacted_cl_count_last_week = ndb.IntegerProperty(default=0, indexed=True)

  @staticmethod
  def GetId(luci_project, normalized_step_name, normalized_test_name):
    return '%s@%s@%s' % (luci_project, normalized_step_name,
                         normalized_test_name)

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
    isolate_target_name = ci_failure.GetIsolateTargetName(
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
    canonical_step_name = ci_failure.GetCanonicalStepName(
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
  def NormalizeTestName(test_name):
    """Normalizes test names by removing parameters and queries.

    Removes prefixes and parameters from test names if they are gtests. For
    example, 'A/ColorSpaceTest.PRE_PRE_testNullTransform/137' maps to
    'ColorSpaceTest.testNullTransform'.

    Removes queries from test names if they are webkit_layout_tests. For
    example, 'external/wpt/editing/run/inserttext.html?2001-last' maps to
    'external/wpt/editing/run/inserttext.html'

    Args:
      test_name: The original test name, and it may contain parameters and
                 prefixes for gtests and queries for webkit_layout_tests.

    Returns:
      Normalized version of the given test name.
    """
    normalized_test_name = test_name_util.RemoveAllPrefixesFromGTestName(
        test_name_util.RemoveParametersFromGTestName(test_name))
    normalized_test_name = test_name_util.RemoveSuffixFromWebkitLayoutTestName(
        normalized_test_name)
    return normalized_test_name
