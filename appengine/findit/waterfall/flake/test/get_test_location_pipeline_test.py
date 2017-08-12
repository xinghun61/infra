# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall import swarming_util
from waterfall.flake.get_test_location_pipeline import GetTestLocationPipeline
from waterfall.test import wf_testcase


class GetTestLocationPipelineTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(swarming_util, 'GetIsolatedOutputForTask', return_value={})
  def testGetTestLocationPipelineNoTestLocations(self, _):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(build_number=123, pass_rate=0.5, task_id='task_id')
    ]
    analysis.suspected_flake_build_number = 123
    analysis.put()

    pipeline_job = GetTestLocationPipeline()
    test_location = pipeline_job.run(analysis.key.urlsafe())
    self.assertIsNone(test_location)

  @mock.patch.object(
      swarming_util,
      'GetIsolatedOutputForTask',
      return_value={'test_locations': {}})
  def testGetTestLocationPipelineNoTestLocation(self, _):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(build_number=123, pass_rate=0.5, task_id='task_id')
    ]
    analysis.suspected_flake_build_number = 123
    analysis.put()

    pipeline_job = GetTestLocationPipeline()
    test_location = pipeline_job.run(analysis.key.urlsafe())
    self.assertIsNone(test_location)

  @mock.patch.object(swarming_util, 'GetIsolatedOutputForTask')
  def testGetTestLocationPipeline(self, mocked_get_isolated_output):
    test_name = 'test_name'
    expected_test_location = {
        'line': 123,
        'file': '/path/to/test_file.cc',
    }
    mocked_get_isolated_output.return_value = {
        'test_locations': {
            test_name: expected_test_location,
        }
    }
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', test_name)
    analysis.data_points = [
        DataPoint.Create(build_number=123, pass_rate=0.5, task_id='task_id')
    ]
    analysis.suspected_flake_build_number = 123
    analysis.put()

    pipeline_job = GetTestLocationPipeline()
    test_location = pipeline_job.run(analysis.key.urlsafe())
    self.assertEqual(expected_test_location, test_location)
