# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Provides functions for Findit's special operations on test results."""

import base64


def GetFailedTestsInformationFromTestResult(test_results_object):
  """ Gets logs for failed tests.

  In the case where we have found reliable failed tests but no failure log, use
  test locations as failure log.

  Args:
    test_results_object(BaseTestResults): Test result object.

  Returns:
    An dict of logs for failed tests.
    An dict of consistently failed tests.
  """
  failed_test_log, reliable_failed_tests = (
      test_results_object.GetFailedTestsInformation())

  # Uses test location as test failure log if there is no failure log.
  for test_name in reliable_failed_tests:
    if not failed_test_log.get(test_name):
      # No failure log for this test.
      test_location, _ = test_results_object.GetTestLocation(test_name)
      if not test_location or not test_location.get('file'):
        continue
      failed_test_log[test_name] = base64.b64encode(test_location['file'])

  return failed_test_log, reliable_failed_tests
