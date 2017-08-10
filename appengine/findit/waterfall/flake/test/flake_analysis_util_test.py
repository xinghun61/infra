# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis

from waterfall.flake import flake_analysis_util
from waterfall.test import wf_testcase
from waterfall.test.wf_testcase import DEFAULT_CONFIG_DATA


class FlakeAnalysisUtilTest(wf_testcase.WaterfallTestCase):

  def testUpdateIterationsToRerunNoIterationsToUpdate(self):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    step_name = 's'
    test_name = 't'
    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.algorithm_parameters = DEFAULT_CONFIG_DATA['check_flake_settings']
    analysis.Save()

    flake_analysis_util.UpdateIterationsToRerun(analysis, None)
    self.assertEqual(analysis.algorithm_parameters,
                     DEFAULT_CONFIG_DATA['check_flake_settings'])

  def testUpdateIterationsToRerun(self):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    step_name = 's'
    test_name = 't'
    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.algorithm_parameters = DEFAULT_CONFIG_DATA['check_flake_settings']
    analysis.Save()

    iterations_to_rerun = 100

    flake_analysis_util.UpdateIterationsToRerun(analysis, iterations_to_rerun)
    self.assertEqual(
        analysis.algorithm_parameters['swarming_rerun']['iterations_to_rerun'],
        iterations_to_rerun)
    self.assertEqual(
        analysis.algorithm_parameters['try_job_rerun']['iterations_to_rerun'],
        iterations_to_rerun)

  def testGetIterationsToRerun(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 100, 's', 't')
    analysis.algorithm_parameters = {
        'swarming_rerun': {
            'iterations_to_rerun': 1
        }
    }
    self.assertEqual(1, flake_analysis_util.GetIterationsToRerun(
        None, analysis))
    self.assertEqual(2, flake_analysis_util.GetIterationsToRerun(2, analysis))

  def testNormalizeDataPoints(self):
    data_points = [
        DataPoint.Create(pass_rate=0.9, build_number=2),
        DataPoint.Create(pass_rate=0.8, build_number=1),
        DataPoint.Create(pass_rate=1.0, build_number=3)
    ]
    normalized_data_points = (
        flake_analysis_util.NormalizeDataPointsByBuildNumber(data_points))
    self.assertEqual(normalized_data_points[0].run_point_number, 3)
    self.assertEqual(normalized_data_points[1].run_point_number, 2)
    self.assertEqual(normalized_data_points[2].run_point_number, 1)
    self.assertEqual(normalized_data_points[0].pass_rate, 1.0)
    self.assertEqual(normalized_data_points[1].pass_rate, 0.9)
    self.assertEqual(normalized_data_points[2].pass_rate, 0.8)
