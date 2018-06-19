# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Functions for operating on test results from swarming reruns for flaky tests.
"""

from libs.test_results import test_results_util


def GetCountsFromSwarmingRerun(test_results_json):
  """Gets the total number of runs and passes from the test result of a swarming
    rerun determining pass_rate.

  Assumption: only one test is run.

  When getting pass counts for a swarming rerun for a flaky test to
  determine pass rate, always assume the test is expected to pass,
  regardless what's currently expected for the test in test results.

  So counts results based on pass/fail only, rather than expected/unexpected.

  Args:
    test_results_json(dict): Test results log.

  Returns:
    (int, int) total number of tries and number of successful runs.
  """
  test_results_obj = test_results_util.GetTestResultObject(test_results_json)
  if not test_results_obj:
    return None, None

  classified_test_results = test_results_obj.GetClassifiedTestResults()

  num_tests = len(classified_test_results)
  if num_tests == 0:  # The test doesn't exist yet, i.e. newly-added tests.
    return 0, 0

  # There should be exactly 1 test that was run.
  assert num_tests == 1, 'Expecting 1 test in results, but got {}'.format(
      num_tests)

  test_result = classified_test_results.values()[0]

  tries = test_result.total_run

  passes = test_result.results.passes
  successes = sum(passes.values())

  return tries, successes
