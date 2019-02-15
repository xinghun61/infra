# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict

from google.appengine.ext import ndb

from libs import time_util
from model.base_build_model import BaseBuildModel
from model.base_swarming_task import BaseSwarmingTask


class _ResultCount(ndb.Model):
  """Represent one result status and the count."""
  status = ndb.StringProperty(indexed=False)
  count = ndb.IntegerProperty(indexed=False)


class _ClassifiedTestResult(ndb.Model):
  """Represents classified result of one test."""
  test_name = ndb.StringProperty(indexed=False)

  # Total runs of the test in a rerun.
  total_run = ndb.IntegerProperty(indexed=False)

  # Number of runs with expected result.
  num_expected_results = ndb.IntegerProperty(indexed=False)
  # Number of runs with unexpected result.
  num_unexpected_results = ndb.IntegerProperty(indexed=False)

  # All the passing status and their counts.
  passes = ndb.LocalStructuredProperty(
      _ResultCount, repeated=True, compressed=True)
  # All the failing status and their counts.
  failures = ndb.LocalStructuredProperty(
      _ResultCount, repeated=True, compressed=True)
  # All the skipping status and their counts.
  skips = ndb.LocalStructuredProperty(
      _ResultCount, repeated=True, compressed=True)
  # All the unknown status and their counts.
  unknowns = ndb.LocalStructuredProperty(
      _ResultCount, repeated=True, compressed=True)
  # All the unknown status and their counts.
  notruns = ndb.LocalStructuredProperty(
      _ResultCount, repeated=True, compressed=True)

  @staticmethod
  def _GetResultList(results):
    return [
        _ResultCount(status=status, count=count)
        for status, count in results.iteritems()
    ]

  @classmethod
  def FromClassifiedTestResultObject(cls, test_name, classified_results):
    result = cls()
    result.test_name = test_name
    result.total_run = classified_results.total_run
    result.num_expected_results = classified_results.num_expected_results
    result.num_unexpected_results = classified_results.num_unexpected_results
    result.passes = cls._GetResultList(classified_results.results.passes)
    result.failures = cls._GetResultList(classified_results.results.failures)
    result.skips = cls._GetResultList(classified_results.results.skips)
    result.unknowns = cls._GetResultList(classified_results.results.unknowns)
    result.notruns = cls._GetResultList(classified_results.results.notruns)
    return result


class WfSwarmingTask(BaseBuildModel, BaseSwarmingTask):
  """Represents a swarming task for a failed step.

  'Wf' is short for waterfall.
  """

  def _GetClassifiedTestsFromLegacyTestStatuses(self):
    """Classifies tests into lists of reliable and flaky tests from
      legacy test statuses.

    example legacy test statuses:
        {
        'test1': {
            'total_run': 2,
            'SUCCESS': 2
        },
        'test2': {
            'total_run': 4,
            'SUCCESS': 2,
            'FAILURE': 2
        },
        'test3': {
            'total_run': 6,
            'FAILURE': 6
        },
        'test4': {
            'total_run': 6,
            'SKIPPED': 6
        },
        'test5': {
            'total_run': 6,
            'UNKNOWN': 6
        }
    }

    example classified tests:
    {
        'flaky_tests': ['test1', 'test2'],
        'reliable_tests': ['test3', 'test4'],
        'unknown_tests': ['test5']
    }
    """
    tests = defaultdict(list)
    for test_name, test_statuses in self.tests_statuses.iteritems():
      if test_statuses.get('SUCCESS'):  # Test passed for some runs, flaky.
        tests['flaky_tests'].append(test_name)
      elif test_statuses.get('UNKNOWN'):
        tests['unknown_tests'].append(test_name)
      else:
        # Here we consider a 'non-flaky' test to be 'reliable'.
        # If the test is 'SKIPPED', there should be failure in its dependency,
        # considers it to be failed as well.
        # TODO(chanli): Check more test statuses.
        tests['reliable_tests'].append(test_name)
    return tests

  @property
  def classified_tests(self):
    """Classifies tests into lists of reliable and flaky tests.

    The swarming task is for deflake purpose, meaning Findit runs the task on
    failed tests that it finds on waterfall.

    So the classification should be:
      * Flaky failure: Any test run succeeded or resulted in an expected status.
      * Unknown failure: Test is not flaky, and any test run ended with an
        unknown status.
      * Reliable failure: All test runs failed or skipped unexpectedly.

    example classified tests:
    {
        'flaky_tests': ['test1'],
        'reliable_tests': ['test3'],
        'unknown_tests': ['test2']
    }
    """
    if not self.classified_test_results:
      return self._GetClassifiedTestsFromLegacyTestStatuses()

    tests = defaultdict(list)
    for classified_test_result in self.classified_test_results:
      test_name = classified_test_result.test_name
      if (classified_test_result.num_expected_results > 0 or
          classified_test_result.passes):
        # There are expected or successful runs for a test that failed on
        # waterfall, classifies the test as a flake.
        tests['flaky_tests'].append(test_name)
      elif classified_test_result.unknowns or classified_test_result.notruns:
        tests['unknown_tests'].append(test_name)
      else:
        # Here we consider a 'non-flaky' test to be 'reliable'.
        # If the test has skipping results, there should be failure in its
        # dependency, considers it to be failed as well.
        tests['reliable_tests'].append(test_name)
    return tests

  @property
  def reliable_tests(self):
    return self.classified_tests.get('reliable_tests', [])

  @property
  def flaky_tests(self):
    return self.classified_tests.get('flaky_tests', [])

  @property
  def reproducible_flaky_tests(self):
    tests = []
    if not self.classified_test_results:
      # For Legacy data.
      for test_name, test_statuses in self.tests_statuses.iteritems():
        if (test_statuses.get('SUCCESS') and
            test_statuses['SUCCESS'] < test_statuses['total_run']):
          # Test has passed and not passed runs, confirmed to be flaky.
          tests.append(test_name)
      return tests

    for classified_test_result in self.classified_test_results:
      test_name = classified_test_result.test_name
      if (classified_test_result.num_expected_results > 0 and
          classified_test_result.num_unexpected_results > 0):
        # Test has expected and unexpected runs, confirmed to be flaky.
        tests.append(test_name)
    return tests

  @ndb.ComputedProperty
  def step_name(self):
    return self.key.pairs()[1][1]

  @staticmethod
  def _CreateKey(master_name, builder_name, build_number,
                 step_name):  # pragma: no cover
    build_key = BaseBuildModel.CreateBuildKey(master_name, builder_name,
                                              build_number)
    return ndb.Key('WfBuild', build_key, 'WfSwarmingTask', step_name)

  @staticmethod
  def Create(master_name, builder_name, build_number,
             step_name):  # pragma: no cover
    task = WfSwarmingTask(
        key=WfSwarmingTask._CreateKey(master_name, builder_name, build_number,
                                      step_name))
    task.parameters = task.parameters or {}
    task.tests_statuses = task.tests_statuses or {}
    task.requested_time = time_util.GetUTCNow()
    return task

  @staticmethod
  def Get(master_name, builder_name, build_number,
          step_name):  # pragma: no cover
    return WfSwarmingTask._CreateKey(master_name, builder_name, build_number,
                                     step_name).get()

  @staticmethod
  def GetClassifiedTestResults(results):
    """Gets classified test results and populates data to
      _ClassifiedTestResults.

    Args:
      results(ClassifiedTestResults): A plain dict-like object for classified
        test results.
    """
    return [
        _ClassifiedTestResult.FromClassifiedTestResultObject(test_name, result)
        for test_name, result in results.iteritems()
    ]

  # Classified test results.
  classified_test_results = ndb.LocalStructuredProperty(
      _ClassifiedTestResult, repeated=True, compressed=True)
