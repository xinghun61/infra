# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from gae_libs.http.http_client_appengine import HttpClientAppengine
from gae_libs.pipeline_wrapper import BasePipeline
from waterfall import swarming_util


class GetTestLocationPipeline(BasePipeline):
  """Gets the location of the flaky test to be used for heuristic analysis."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, analysis_urlsafe_key):
    """Extracts the location of the flaky test from swarming."""
    analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
    assert analysis

    suspected_build_point = analysis.GetDataPointOfSuspectedBuild()
    task_id = suspected_build_point.task_id
    task_output = swarming_util.GetIsolatedOutputForTask(
        task_id, HttpClientAppengine())

    tests_locations = task_output.get('tests_locations')

    if tests_locations is None:
      logging.warning(
          ('Failed to get test locations from isolated output for task %s for '
           '%s/%s/%s/%s on suspected build %s'), task_id, analysis.master_name,
          analysis.builder_name, analysis.step_name, analysis.test_name,
          suspected_build_point.build_number)
      return None

    test_location = tests_locations.get(analysis.test_name)

    if test_location is None:
      logging.warning(
          'Failed to get test location for test %s', analysis.test_name)
      return None

    return test_location
