# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Calculates detection rate on reliable failures at step level.

The criteria would be:
1. failure type: compile or test.
2. result type: suspects/culprits, flakiness, not_found, not_support, error.

To deduplicate, we should only check analysis of first failures.

I will not group the same steps/tests because we are not always have enough
information to do that. For example, Findit doesn't support webkit_tests and
doesn't have failed tests info for this step, so if group by step name, we will
only get one unsupported failures in metrics but in fact there should be plenty.
"""

import datetime
import json
import os
import sys

_REMOTE_API_DIR = os.path.join(os.path.dirname(__file__), os.path.pardir)
sys.path.insert(1, _REMOTE_API_DIR)

import remote_api

from google.appengine.ext import ndb

from model.wf_analysis import WfAnalysis
from model.wf_swarming_task import WfSwarmingTask
from model.wf_try_job import WfTryJob
from waterfall import build_util


class Result(object):

  def __init__(self, step, name_test):
    self.step_name = step
    self.test_name = name_test
    self.failure_type = None
    self.culprits = None
    self.is_flaky = False
    self.is_supported = True
    self.error = False
    self.build_keys = None
    self.culprits = []
    self.build_keys = []

  def ToDict(self):
    return {
        'step_name': self.step_name,
        'test_name': self.test_name,
        'failure_type': self.failure_type,
        'culprits': self.culprits,
        'is_flaky': self.is_flaky,
        'is_supported': self.is_supported,
        'error': self.error,
        'build_keys': self.build_keys
    }


def _CheckIfTestFlaky(
    master, builder, build, step, checked_test_name):
  task = WfSwarmingTask.Get(master, builder, build, step)
  if task and task.classified_tests:
    return checked_test_name in task.classified_tests.get('flaky_tests', [])
  return False


def _CreateResult(step, checked_test_name, culprit):
  new_result = Result(step, checked_test_name)
  new_result.culprits.append({
    'repo_name': culprit.get('repo_name'),
    'revision': culprit.get('revision')
  })
  return new_result


def _GetCompileTryJobCulprit(compile_try_job):
  compile_culprits = None

  if not compile_try_job:
    return compile_culprits

  try_job_result = (compile_try_job.compile_results[-1] if
                    compile_try_job.compile_results else {})

  compile_culprits = try_job_result.get('culprit', {}).get('compile')
  if not compile_culprits:
    return culprits

  return _CreateResult('compile', None, compile_culprits)


def _GetTestTryJobCulprit(test_try_job, step):
  test_try_job_culprits = {}

  if not test_try_job:
    return culprits

  try_job_result = (
    test_try_job.test_results[-1] if test_try_job.test_results else {})

  step_culprit = try_job_result.get('culprit', {}).get(step)
  if not step_culprit:
    return step_culprit

  if step_culprit.get('tests'):
    for checked_test_name, test_culprit in step_culprit.iteritems():
      test_try_job_culprits[checked_test_name] = _CreateResult(
          step, checked_test_name, test_culprit)

  return test_try_job_culprits


def _AddSuspectedCLs(updated_result, suspected_cls):
  for cl in suspected_cls:
    updated_result.culprits.append({
      'repo_name': cl['repo_name'],
      'revision': cl['revision']
    })


def _PrintResults(results):
  for res in results:
    print json.dumps(res.ToDict(), indent=2)


def _ResultPercentage(num, total):
  return float(num) * 100 / total if total else -1


def _CalculateDetectionRate(results):
  with_culprits = []
  flaky = []
  not_support = []
  errored_out = []
  not_found = []

  for res in results:
    if not res.is_supported:
      not_support.append(res)
    elif res.is_flaky:
      flaky.append(res)
    elif res.culprits:
      with_culprits.append(res)
    elif res.error:
      errored_out.append(res)
    else:
      not_found.append(res)

  num_total = len(results)
  num_with_culprit = len(with_culprits)
  num_flaky = len(flaky)
  num_not_support = len(not_support)
  num_errored_out = len(errored_out)
  num_not_found = len(not_found)

  print '----------------Total failures:', num_total
  print '----------------Findit found suspects or culprits:', num_with_culprit
  print 'percentage: %.2f%%' % _ResultPercentage(num_with_culprit, num_total)
  _PrintResults(with_culprits)

  print '\n----------------Findit identified flaky failures:', num_flaky
  print 'percentage: %.2f%%' % _ResultPercentage(num_flaky, num_total)
  _PrintResults(flaky)

  print '\n----------------Not supported by Findit:', num_not_support
  print 'percentage: %.2f%%' % _ResultPercentage(num_not_support, num_total)
  _PrintResults(not_support)

  print '\n----------------Findit encountered an error:', num_errored_out
  print 'percentage: %.2f%%' % _ResultPercentage(num_errored_out, num_total)
  _PrintResults(errored_out)

  print '\n----------------Findit couldn\'t provide any info:', num_not_found
  print 'percentage: %.2f%%' % _ResultPercentage(num_not_found, num_total)
  _PrintResults(not_found)


if __name__ == '__main__':
  # Set up the Remote API to use services on the live App Engine.
  remote_api.EnableRemoteApi(app_id='findit-for-me')

  start = datetime.datetime(2017, 4, 25, 0, 0, 0)
  end = datetime.datetime(2017, 4, 27, 0, 0, 0)
  cursor = None
  more = True

  test_results = []
  compile_results = []

  while more:
    analyses, cursor, more = WfAnalysis.query(ndb.AND(
        WfAnalysis.build_start_time >= start,
        WfAnalysis.build_start_time < end)).fetch_page(
            100, start_cursor=cursor)

    for analysis in analyses:
      if not analysis.completed or not analysis.result:
        continue

      build_key = analysis.key.pairs()[0][1]
      master_name, builder_name, build_number = build_util.GetBuildInfoFromId(
          build_key)
      build_number = int(build_number)

      try_job = WfTryJob.Get(master_name, builder_name, build_number)

      for failure in analysis.result.get('failures', {}):

        result = None
        step_name = failure['step_name']
        culprits = _GetTestTryJobCulprit(try_job, step_name)
        if failure.get('tests'):
          for test in failure['tests']:
            if test['first_failure'] != build_number:
              # Not first time failure.
              continue

            test_name = test['test_name']

            result = Result(step_name, test_name)
            result.is_supported = failure.get('supported', True)
            result.error = analysis.failed
            result.build_keys.append(build_key)
            test_results.append(result)

            result.is_flaky = _CheckIfTestFlaky(
                master_name, builder_name, build_number, step_name, test_name)
            if result.is_flaky:
              continue

            # Adds suspected CLs found by heuristic analysis.
            _AddSuspectedCLs(result, test['suspected_cls'])

            # Adds culprits found by try job.
            if culprits and culprits.get(test_name):
              result.culprits.extend(culprits[test_name].culprits)

        else:
          if failure['first_failure'] != build_number:
            # Not first time failure.
            continue
          if step_name.lower() == 'compile':
            result = _GetCompileTryJobCulprit(try_job)
          if not result:
            result = Result(step_name, None)
            result.is_supported = failure.get('supported', True)
          result.build_keys.append(build_key)
          result.error = analysis.failed
          _AddSuspectedCLs(result, failure['suspected_cls'])
          if step_name.lower() == 'compile':
            compile_results.append(result)
          else:
            test_results.append(result)


  print '************* Compile ****************'
  _CalculateDetectionRate(compile_results)
  print
  print '************* Test ****************'
  _CalculateDetectionRate(test_results)
