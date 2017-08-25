# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for gtest-related operations.

It provides functions to:
  * normalize the test names
  * concatenate gtest logs
"""

import base64

_PRE_TEST_PREFIX = 'PRE_'


def RemoveAllPrefixes(test):
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
  pre_position = test_name.find(_PRE_TEST_PREFIX)
  while pre_position == 0:
    test_name = test_name[len(_PRE_TEST_PREFIX):]
    pre_position = test_name.find(_PRE_TEST_PREFIX)
  base_test = '%s.%s' % (test_suite, test_name)
  return base_test


def ConcatenateTestLog(string1, string2):
  """Concatenates the base64 encoded log.

  Tests if one string is a substring of another,
      if yes, returns the longer string,
      otherwise, returns the concatenation.

  Args:
    string1: base64-encoded string.
    string2: base64-encoded string.

  Returns:
    base64-encoded string.
  """
  str1 = base64.b64decode(string1)
  str2 = base64.b64decode(string2)
  if str2 in str1:
    return string1
  elif str1 in str2:
    return string2
  else:
    return base64.b64encode(str1 + str2)
