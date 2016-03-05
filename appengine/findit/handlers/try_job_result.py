# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from base_handler import BaseHandler
from base_handler import Permission
from model.wf_analysis import WfAnalysis
from model import wf_analysis_status
from model.wf_swarming_task import WfSwarmingTask
from model.wf_try_job import WfTryJob
from waterfall import buildbot


FLAKY = 'Flaky'


def _GetTryJobBuildNumber(url):
  build_keys = buildbot.ParseBuildUrl(url)
  return build_keys[2]


def _GetCulpritInfoForTryJobResult(try_job_key, culprits_info):
  referred_build_keys = try_job_key.split('/')
  try_job = WfTryJob.Get(*referred_build_keys)
  if not try_job:
    return

  if try_job.compile_results:
    try_job_result = try_job.compile_results[-1]
  elif try_job.test_results:
    try_job_result = try_job.test_results[-1]
  else:
    try_job_result = None

  for culprit_info in culprits_info.values():
    if culprit_info['try_job_key'] != try_job_key:
      continue

    # Only include try job result for reliable tests.
    # Flaky tests have been marked as 'Flaky'.
    culprit_info['status'] = (
        wf_analysis_status.TRY_JOB_STATUS_TO_DESCRIPTION[try_job.status]
        if not culprit_info.get('status') else culprit_info['status'])

    if try_job_result and culprit_info['status'] != FLAKY:
      if try_job_result.get('url'):
        culprit_info['try_job_url'] = try_job_result['url']
        culprit_info['try_job_build_number'] = (
            _GetTryJobBuildNumber(try_job_result['url']))
      if try_job_result.get('culprit'):
        try_job_culprits = try_job_result['culprit']
        step = culprit_info['step']
        test = culprit_info['test']
        if not try_job_culprits.get(step, {}).get('tests'):  # Only step level
          # For historical culprit found by try job for compile,
          # step name is not recorded.
          culprit = try_job_culprits.get(step) or try_job_culprits
        elif test in try_job_culprits.get(step, {}).get('tests'):
          culprit = try_job_culprits[step]['tests'][test]
        else:   # pragma: no cover
          continue  # No culprit for test found.

        culprit_info['revision'] = culprit.get('revision')
        culprit_info['commit_position'] = culprit.get('commit_position')
        culprit_info['review_url'] = culprit.get('review_url')


def _UpdateFlakiness(step_name, failure_key_set, culprits_info):
  for failure_key in failure_key_set:
    build_keys = failure_key.split('/')
    task = WfSwarmingTask.Get(*build_keys, step_name=step_name)
    classified_tests = task.classified_tests
    for culprit_info in culprits_info.values():
      if (culprit_info['try_job_key'] == failure_key and
          culprit_info['test'] in classified_tests.get('flaky_tests', [])):
        culprit_info['status'] = 'Flaky'


def _GetAllTryJobResults(master_name, builder_name, build_number):
  culprits_info = {}
  try_job_keys = set()

  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  if not analysis:
    return culprits_info

  failure_result_map = analysis.failure_result_map
  if failure_result_map:
    # failure_result_map uses step_names as keys and saves referred try_job_keys
    # If non-swarming, step_name and referred_try_job_key match directly as:
    # step_name: try_job_key
    # If swarming, add one more layer of tests, so the format would be:
    # step_name: {
    #     test_name1: try_job_key1,
    #     test_name2: try_job_key2,
    #     ...
    # }
    for step_name, step_failure_result_map in failure_result_map.iteritems():
      if isinstance(step_failure_result_map, dict):
        step_refering_keys = set()
        for failed_test, try_job_key in step_failure_result_map.iteritems():
          step_test_key = '%s-%s' % (step_name, failed_test)
          culprits_info[step_test_key] = {
              'step': step_name,
              'test': failed_test,
              'try_job_key': try_job_key
          }
          step_refering_keys.add(try_job_key)

        _UpdateFlakiness(step_name, step_refering_keys, culprits_info)
        try_job_keys.update(step_refering_keys)
      else:
        culprits_info[step_name] = {
            'step': step_name,
            'test': 'N/A',
            'try_job_key': step_failure_result_map
        }
        try_job_keys.add(step_failure_result_map)

    for try_job_key in try_job_keys:
      _GetCulpritInfoForTryJobResult(try_job_key, culprits_info)

  return culprits_info


class TryJobResult(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    """Get the latest try job result if it's compile failure."""
    url = self.request.get('url').strip()
    build_keys = buildbot.ParseBuildUrl(url)

    if not build_keys:  # pragma: no cover
      return {'data': {}}

    data = _GetAllTryJobResults(*build_keys)

    return {'data': data}

  def HandlePost(self):  # pragma: no cover
    return self.HandleGet()
