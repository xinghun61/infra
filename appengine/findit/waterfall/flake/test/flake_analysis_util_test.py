# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
from datetime import datetime
import mock

from infra_api_clients.swarming import swarming_util
from infra_api_clients.swarming.swarming_bot_counts import SwarmingBotCounts
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall.flake import flake_analysis_util
from waterfall.test import wf_testcase
from waterfall.test.wf_testcase import DEFAULT_CONFIG_DATA


class FlakeAnalysisUtilTest(wf_testcase.WaterfallTestCase):

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

  def testEstimateSwarmingIterationTimeout(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 100, 's', 't')
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.data_points = [
        DataPoint.Create(
            build_number=100, iterations=10, elapsed_seconds=100, pass_rate=1),
        DataPoint.Create(
            build_number=111, iterations=10, elapsed_seconds=200, pass_rate=1),
        DataPoint.Create(
            build_number=123, iterations=10, elapsed_seconds=1000, pass_rate=1),
        DataPoint.Create(
            build_number=133, iterations=10, elapsed_seconds=300, pass_rate=1),
        DataPoint.Create(
            build_number=144, iterations=10, elapsed_seconds=400, pass_rate=1)
    ]
    analysis.put()

    timeout = flake_analysis_util.EstimateSwarmingIterationTimeout(
        analysis, 123)

    self.assertEqual(200, timeout)

  def testEstimateSwarmingIterationTimeoutWithMissingData(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 100, 's', 't')
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])

    analysis.data_points = [
        DataPoint.Create(build_number=123, iterations=10, pass_rate=1)
    ]
    analysis.put()
    with self.assertRaises(AssertionError):  # Without elapsed_seconds.
      flake_analysis_util.EstimateSwarmingIterationTimeout(analysis, 123)

    analysis.data_points = [
        DataPoint.Create(build_number=123, elapsed_seconds=100, pass_rate=1)
    ]
    analysis.put()
    with self.assertRaises(AssertionError):  # Without iterations.
      flake_analysis_util.EstimateSwarmingIterationTimeout(analysis, 123)

    analysis.data_points = [
        DataPoint.Create(build_number=123, elapsed_seconds=100, iterations=10)
    ]
    analysis.put()
    with self.assertRaises(AssertionError):  # Without pass rate.
      flake_analysis_util.EstimateSwarmingIterationTimeout(analysis, 123)

  def testEstimateSwarmingIterationTimeoutWithBadPassRate(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 100, 's', 't')
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])

    analysis.data_points = [
        DataPoint.Create(
            build_number=123, iterations=10, elapsed_seconds=400, pass_rate=-1)
    ]
    analysis.put()
    with self.assertRaises(AssertionError):
      flake_analysis_util.EstimateSwarmingIterationTimeout(analysis, 123)

  def testEstimateSwarmingIterationTimeoutWithAnalysisWithNoDataForBuild(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 100, 's', 't')
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.data_points = []
    analysis.put()

    timeout = flake_analysis_util.EstimateSwarmingIterationTimeout(
        analysis, 123)

    self.assertEqual(timeout, 120)

  def testCalculateNumberOfIterationsToRunWithinTimeout(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.data_points = []
    analysis.put()

    timeout_per_test = 60
    self.assertEqual(
        flake_analysis_util.CalculateNumberOfIterationsToRunWithinTimeout(
            analysis, timeout_per_test), 60)

  def testCalculateNumberOfIterationsToRunWithinTimeoutWithZero(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.data_points = []
    analysis.put()

    timeout_per_test = 10000
    self.assertEqual(
        flake_analysis_util.CalculateNumberOfIterationsToRunWithinTimeout(
            analysis, timeout_per_test), 1)

  def testGetETAToStartAnalysisWhenManuallyTriggered(self):
    mocked_utcnow = datetime.utcnow()
    self.MockUTCNow(mocked_utcnow)
    self.assertEqual(mocked_utcnow,
                     flake_analysis_util.GetETAToStartAnalysis(True))

  def testGetETAToStartAnalysisWhenTriggeredOnPSTWeekend(self):
    # Sunday 1pm in PST, and Sunday 8pm in UTC.
    mocked_pst_now = datetime(2016, 9, 04, 13, 0, 0, 0)
    mocked_utc_now = datetime(2016, 9, 04, 20, 0, 0, 0)
    self.MockUTCNow(mocked_utc_now)
    with mock.patch('libs.time_util.GetPSTNow') as timezone_func:
      timezone_func.side_effect = [mocked_pst_now, None]
      self.assertEqual(mocked_utc_now,
                       flake_analysis_util.GetETAToStartAnalysis(False))

  def testGetETAToStartAnalysisWhenTriggeredOffPeakHoursOnPSTWeekday(self):
    # Tuesday 1am in PST, and Tuesday 8am in UTC.
    mocked_pst_now = datetime(2016, 9, 20, 1, 0, 0, 0)
    mocked_utc_now = datetime(2016, 9, 20, 8, 0, 0, 0)
    self.MockUTCNow(mocked_utc_now)
    with mock.patch('libs.time_util.GetPSTNow') as timezone_func:
      timezone_func.side_effect = [mocked_pst_now, None]
      self.assertEqual(mocked_utc_now,
                       flake_analysis_util.GetETAToStartAnalysis(False))

  def testGetETAToStartAnalysisWhenTriggeredInPeakHoursOnPSTWeekday(self):
    # Tuesday 12pm in PST, and Tuesday 8pm in UTC.
    seconds_delay = 10
    mocked_utc_now = datetime(2016, 9, 21, 20, 0, 0, 0)
    mocked_pst_now = datetime(2016, 9, 21, 12, 0, 0, 0)
    mocked_utc_eta = datetime(2016, 9, 22, 2, 0, seconds_delay)
    self.MockUTCNow(mocked_utc_now)
    with mock.patch('libs.time_util.GetPSTNow') as (
        timezone_func), mock.patch('random.randint') as random_func:
      timezone_func.side_effect = [mocked_pst_now, mocked_utc_eta]
      random_func.side_effect = [seconds_delay, None]
      self.assertEqual(mocked_utc_eta,
                       flake_analysis_util.GetETAToStartAnalysis(False))

  @mock.patch.object(swarming_util, 'GetBotCounts')
  def testCheckBotsAvailability(self, mock_fn):
    step_metadata = {'dimensions': {'os': 'OS'}}

    mock_fn.return_value = SwarmingBotCounts({
        'count': 20,
        'dead': 1,
        'quarantined': 0,
        'busy': 5
    })

    self.assertFalse(flake_analysis_util.BotsAvailableForTask(None))
    self.assertTrue(flake_analysis_util.BotsAvailableForTask(step_metadata))