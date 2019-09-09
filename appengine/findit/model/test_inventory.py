# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from model.flake.flake_issue import FlakeIssue


class DisabledTestVariantsProperty(ndb.JsonProperty):
  """App Engine NDB datastore Property for disabled_test_variants.

    Utility property that allows easy storage and retrieval of
    LuciTest.disabled_test_variants
  """

  def _validate(self, disabled_test_variants):
    """Validates implementation of disabled_test_variants.

    Args:
      disabled_test_variants:  collection of disabled test variants to be set
        on the property.
        Should be a either a list containing string tuples
        or a set containing string tuples.

    Raises:
      TypeError if disabled_test_variants is not a set containing string tuples
        or a list containing tuples of strings.
    """
    if not isinstance(disabled_test_variants, (list, set)):
      raise TypeError(
          'expected a list or a set, got %r' % disabled_test_variants)

    for test_variant in disabled_test_variants:
      if not isinstance(test_variant, tuple):
        raise TypeError('expected a tuple, got %r' % test_variant)

      if not test_variant:
        raise TypeError('tuple cannot be empty')

      for configuration in test_variant:
        if not isinstance(configuration, (str, unicode)):
          raise TypeError('expected a string, got %r' % configuration)

  def _to_base_type(self, disabled_test_variants):
    """Converts to a list of string tuples for serialization."""
    return list(disabled_test_variants)

  def _from_base_type(self, disabled_test_variants):
    """Reads disabled_test_variants as a set containing string tuples."""
    return {tuple(variant) for variant in disabled_test_variants}


class LuciTest(ndb.Model):
  """Stores static test information including disabled test variants.

  No parent entity. Storage of the model is keyed through LuciTest._GetId as:
    '{luci_project}@{normalized_step_name}@{normalized_test_name}'.

    luci_project: Project to which this test belongs to,
      for example: chromium, angle. This property matches with LUCI's
      projects, which is defined in:
      https://luci-config.appspot.com

    normalized_step_name: The base test target name of a step where tests are
      actually defined.

      Be more specific on base_test_target. For GTest-based tests that run
      the binaries as it is, base_test_target equals the test target name.

      For example, 'base_unittests (with patch) on Android' ->
      'base_unittests'.

      For gtest targets that run the binaries with command line arguments to
      enable specific features, base_test_target equals the name of the
      underlying test target actually compiles the binary. For example,
      'viz_browser_tests (with patch) on Android' -> 'browser_tests'.

    normalized_test_name: The test_name without 'PRE_' prefixes and
      parameters. For example:
      'A/ColorSpaceTest.PRE_PRE_testNullTransform/137 maps' ->
      'ColorSpaceTest.testNullTransform'.
  """

  # Python set of tuples, each tuple corresponds to a disabled test variant
  # Each tuple is a tuple of strings.
  # The tuple of strings contains the collection of key-value pairs which
  # define the test variant.
  # ie set([('os:Mac', 'msan:True'), ('os:Linux', 'msan:False')])
  disabled_test_variants = DisabledTestVariantsProperty()

  # Time of the most recent update.
  last_updated_time = ndb.DateTimeProperty()

  # Keys to the FlakeIssue entities being used to track the test's disablement.
  # If a test already has FlakeIssue entities associated with it because it was
  # previously a Flake, then the same FlakeIssue entity should be used to track
  # its disablement.
  issue_keys = ndb.KeyProperty(kind=FlakeIssue, repeated=True)

  # Tags that specify the category of the test, e.g. directory, component,
  # step, test_type.
  tags = ndb.StringProperty(repeated=True)

  @ndb.ComputedProperty
  def disabled(self):
    return bool(self.disabled_test_variants)

  @ndb.ComputedProperty
  def luci_project(self):
    return self.key.id().split('@')[0]

  @ndb.ComputedProperty
  def normalized_step_name(self):
    return self.key.id().split('@')[1]

  @ndb.ComputedProperty
  def normalized_test_name(self):
    return self.key.id().split('@')[2]

  @staticmethod
  def _GetId(luci_project, normalized_step_name, normalized_test_name):
    """Returns an ID for a LuciTest entity."""
    return '%s@%s@%s' % (luci_project, normalized_step_name,
                         normalized_test_name)

  @classmethod
  def CreateKey(cls, luci_project, normalized_step_name, normalized_test_name):
    """Returns a key for a LuciTest entity."""
    return ndb.Key(
        cls, cls._GetId(luci_project, normalized_step_name,
                        normalized_test_name))
