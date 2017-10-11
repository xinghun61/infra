# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from common.findit_http_client import FinditHttpClient
from gae_libs.pipeline_wrapper import BasePipeline
from waterfall import swarming_util


class GetTestLocationPipeline(BasePipeline):
  """Gets the location of the flaky test to be used for heuristic analysis."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, analysis_urlsafe_key):
    """Extracts the location of the flaky test from swarming as a dict.

    Args:
      analysis_urlsafe_key (str): The urlsafe key of a MasterFlakeAnalysis.

    Returns:
      test_location (dict): A dict containing the file and line number of the
          test location, or None if either no suspected build point is
          identified or the test location could not be determined. test_location
          should be in the format:
          {
              'file': (str),
              'line': (int),
          }
    """
    analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
    assert analysis

    suspected_build_point = analysis.GetDataPointOfSuspectedBuild()

    if suspected_build_point is None:
      analysis.LogInfo('Cannot get test location due to no suspected flake '
                       'build being identified')
      return None

    task_id = suspected_build_point.task_id
    task_output = swarming_util.GetIsolatedOutputForTask(
        task_id, FinditHttpClient())

    test_locations = task_output.get('test_locations')

    if test_locations is None:
      analysis.LogWarning(
          'Failed to get test locations from isolated output for task %s for '
          'on suspected build %s' % (task_id,
                                     suspected_build_point.build_number))
      return None

    test_location = test_locations.get(analysis.test_name)

    if test_location is None:
      analysis.LogWarning(
          'Failed to get test location for test %s' % analysis.test_name)
      return None

    return test_location
