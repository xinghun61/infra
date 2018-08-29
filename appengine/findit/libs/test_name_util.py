# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Utility functions for processing test names."""

import re

# Used to identify the prefix in gtests.
_PRE_TEST_PREFIX = 'PRE_'

# Regular expressions to identify parameterized gtests. Note that instantiation
# names can be empty. For example: ColorSpaceTest.testNullTransform/1.
_VALUE_PARAMETEREZED_GTESTS_REGEX = re.compile(r'(.+/)?(.+\..+)/\d+')
_TYPE_PARAMETERIZED_GTESTS_REGEX = re.compile(r'(.+/)?(.+)/\d+\.(.+)')

# Regular expressions to identify webkit_layout_tests with queries.
_QUERY_WEBKIT_LAYOUT_TESTS_REGEXT = re.compile(r'(.+\.html)\?.+')


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
  while test_name.startswith(_PRE_TEST_PREFIX):
    test_name = test_name[len(_PRE_TEST_PREFIX):]
  base_test = '%s.%s' % (test_suite, test_name)
  return base_test


def RemoveQueriesFromWebkitLayoutTestName(test_name):
  """Removes queries part from webkit_layout_test names if applicable.

  For example, 'external/wpt/editing/run/delete.html?1001-2000' should become
  'external/wpt/editing/run/delete.html' after removing the queries.

  Args:
    test_name: Name of the test to be processed.

  Returns:
    A string representing the name after removing queries.
  """
  match = _QUERY_WEBKIT_LAYOUT_TESTS_REGEXT.match(test_name)
  if match:
    return match.group(1)

  return test_name
