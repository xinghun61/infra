# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from common.pipeline_wrapper import BasePipeline
from model.flake.master_flake_analysis import DataPoint


class ProcessFlakeTryJobResultPipeline(BasePipeline):
  """A pipeline for processing a flake try job result."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, revision, commit_position, try_job_result, urlsafe_try_job_key,
          urlsafe_flake_analysis_key):
    """Extracts pass rate information and updates flake analysis.

    Args:
      revision (str): The git hash the try job was run against.
      commit_position (int): The commit position corresponding to |revision|.
      try_job_result (dict): The result dict reported by buildbucket.
          Example:
          {
            'report': {
                'metadata': {},
                'result': {
                    'cafed52c5f3313646b8e04e05601b5cb98f305b3': {
                        'browser_tests': {
                            'status': 'failed',
                            'failures': ['TabCaptureApiTest.FullscreenEvents'],
                            'valid': True,
                            'pass_fail_counts': {
                                'TabCaptureApiTest.FullscreenEvents': {
                                    'pass_count': 28,
                                    'fail_count': 72
                                }
                            }
                        }
                    }
                }
            }
      urlsafe_try_job_key (str): The urlsafe key to the corresponding try job
          entity.
      urlsafe_flake_analysis_key (str): The urlsafe key for the master flake
          analysis entity to be updated.
    """
    flake_analysis = ndb.Key(urlsafe=urlsafe_flake_analysis_key).get()
    try_job = ndb.Key(urlsafe=urlsafe_try_job_key).get()
    assert flake_analysis
    assert try_job

    step_name = flake_analysis.step_name
    test_name = flake_analysis.test_name
    result = try_job_result['report']['result']
    pass_fail_counts = result[revision][step_name].get('pass_fail_counts', {})

    if pass_fail_counts:
      test_results = pass_fail_counts[test_name]
      pass_count = test_results['pass_count']
      fail_count = test_results['fail_count']
      tries = pass_count + fail_count
      pass_rate = float(pass_count) / tries
    else:  # Test does not exist.
      pass_rate = -1

    data_point = DataPoint()
    data_point.commit_position = commit_position
    data_point.git_hash = revision
    data_point.pass_rate = pass_rate
    data_point.try_job_url = try_job.flake_results[-1].get('url')
    # TODO(chanli): Add swarming task data.
    flake_analysis.data_points.append(data_point)
    flake_analysis.put()
