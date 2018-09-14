# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Utility functions for processing test names."""

import re

# Used to identify the prefix in gtests.
_GTEST_PREFIXES = ['PRE_', '*']

# Regular expressions to identify parameterized gtests. Note that instantiation
# names can be empty. For example: ColorSpaceTest.testNullTransform/1.
_VALUE_PARAMETEREZED_GTESTS_REGEX = re.compile(r'^(.+/)?(.+\..+)/[\d+\*]$')
_TYPE_PARAMETERIZED_GTESTS_REGEX = re.compile(r'^(.+/)?(.+)/[\d+\*]\.(.+)$')

# Regular expression for a webkit_layout_test name.
_LAYOUT_TEST_NAME_PATTERN = re.compile(r'^(([^/]+/)+[^/]+\.[a-zA-Z]+).*$')
_VIRTUAL_LAYOUT_TEST_NAME_PATTERN = re.compile(r'^virtual/[^/]+/(.*)$')


def RemoveParametersFromGTestName(test_name):
  """Removes parameters from parameterized gtest names.

  There are two types of parameterized gtest: value-parameterized tests and
  type-paramerized tests, and for example:
  value-parameterized:
    'A/ColorSpaceTest.testNullTransform/11'
  type-parameterized:
    '1/GLES2DecoderPassthroughFixedCommandTest/5.InvalidCommand'

  After removing the parameters, the examples become
  'ColorSpaceTest.testNullTransform' and
  'GLES2DecoderPassthroughFixedCommandTest.InvalidCommand' respectively.

  For more information of parameterized gtests, please refer to:
  https://github.com/google/googletest/blob/master/googletest/docs/
  AdvancedGuide.md
  """
  value_match = _VALUE_PARAMETEREZED_GTESTS_REGEX.match(test_name)
  if value_match:
    return value_match.group(2)

  type_match = _TYPE_PARAMETERIZED_GTESTS_REGEX.match(test_name)
  if type_match:
    return type_match.group(2) + '.' + type_match.group(3)

  return test_name


def ReplaceParametersFromGtestNameWithMask(test_name):
  """Replaces the parameters parts of gtest names with mask: '*'.

  This method works the same way as |RemoveParametersFromGTestName| except that
  the parameters parts are replaced with '*' instead of being removed. For
  example, 'A/suite.test/8' -> '*/suite.test/*'.

  Args:
    test_name: Original test names, may contain parameters.

  Returns:
    A test name with parameters being replaced with '*'.
  """
  value_match = _VALUE_PARAMETEREZED_GTESTS_REGEX.match(test_name)
  if value_match:
    suite_test = value_match.group(2)
    prefix_mask = '*/' if value_match.group(1) else ''
    return '%s%s/*' % (prefix_mask, suite_test)

  type_match = _TYPE_PARAMETERIZED_GTESTS_REGEX.match(test_name)
  if type_match:
    suite = type_match.group(2)
    test = type_match.group(3)
    prefix_mask = '*/' if type_match.group(1) else ''
    return '%s%s/*.%s' % (prefix_mask, suite, test)

  return test_name


def RemoveAllPrefixesFromGTestName(test):
  """Removes prefixes from test names.

  Args:
    test (str): A test's name, eg: 'suite1.PRE_test1'.

  Returns:
    base_test (str): A base test name, eg: 'suite1.test1'.
  """
  test_name_start = max(test.find('.'), 0)
  if test_name_start == 0:
    return test

  test_suite = test[:test_name_start]
  test_name = test[test_name_start + 1:]

  for prefix in _GTEST_PREFIXES:
    while test_name.startswith(prefix):
      test_name = test_name[len(prefix):]

  base_test = '%s.%s' % (test_suite, test_name)
  return base_test


def ReplaceAllPrefixesFromGtestNameWithMask(test_name):
  """Replaces the prefixes parts of gtest names with mask: '*'.

  This method works the same way as |RemoveAllPrefixesFromGTestName| except that
  the prefixes parts are replaced with '*' instead of being removed. For
  example, 'suite.PRE_PRE_test' -> 'suite.*test'.

  Args:
    test_name: Original test names, may contain parameters.

  Returns:
    A test name with prefixes being replaced with '*'.
  """
  test_name_without_prefixes = RemoveAllPrefixesFromGTestName(test_name)
  if test_name_without_prefixes == test_name:
    return test_name

  suite = test_name_without_prefixes.split('.')[0]
  test = test_name_without_prefixes.split('.')[1]
  return '%s.*%s' % (suite, test)


def RemoveSuffixFromWebkitLayoutTestName(test_name):
  """Removes suffix part from webkit_layout_test names if applicable.

  For example, 'external/wpt/editing/run/delete.html?1001-2000' should become
  'external/wpt/editing/run/delete.html' after removing the queries.

  Args:
    test_name: Name of the test to be processed.

  Returns:
    A string representing the name after removing suffix.
  """
  match = _LAYOUT_TEST_NAME_PATTERN.match(test_name)
  if match:
    return match.group(1)

  return test_name


def ReplaceSuffixFromWebkitLayoutTestNameWithMask(test_name):
  """Replaces the suffix parts of webkit_layout_test names with mask: '*'.

  This method works the same way as |RemoveSuffixFromWebkitLayoutTestName|
  except that the suffix parts are replaced with '*' instead of being removed.
  For example, 'external/delete.html?1001-2000' -> 'external/delete.html?*'.

  Args:
    test_name: Original test names, may contain suffixes.

  Returns:
    A test name with suffixes being replaced with '*'.
  """
  test_name_without_suffixes = RemoveSuffixFromWebkitLayoutTestName(test_name)
  if test_name_without_suffixes == test_name:
    return test_name

  return '%s?*' % test_name_without_suffixes


def RemoveVirtualLayersFromWebkitLayoutTestName(test_name):
  """Removes virtual layers from webkit_layout_test names if applicable.

  For example, 'virtual/abc/def/g.html' should become 'def/g.html' after
  removing the layers.

  Args:
    test_name: Name of the test to be processed.

  Returns:
    A string representing the name after removing virtual layers.
  """
  match = _VIRTUAL_LAYOUT_TEST_NAME_PATTERN.match(test_name)
  if match:
    return match.group(1)

  return test_name
