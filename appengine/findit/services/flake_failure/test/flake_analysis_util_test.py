# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
from datetime import timedelta
import mock

from google.appengine.ext import ndb

from dto.flake_swarming_task_output import FlakeSwarmingTaskOutput
from dto import swarming_task_error
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs import time_util
from libs.gitiles.change_log import ChangeLog
from model.flake.flake_culprit import FlakeCulprit
from model.flake.master_flake_analysis import MasterFlakeAnalysis
# TODO(crbug.com/809885): Merge flake_analysis_util.py.
from services.flake_failure import flake_analysis_util
from services.flake_failure import flake_constants
from waterfall.flake import flake_analysis_util as flake_util
from waterfall.test.wf_testcase import WaterfallTestCase


class FlakeAnalysisUtilTest(WaterfallTestCase):

  def testCanStartAnalysis(self):
    self.assertTrue(flake_analysis_util.CanStartAnalysis(None, 0, True))
    self.assertTrue(flake_analysis_util.CanStartAnalysis(None, 10, False))
    self.assertFalse(flake_analysis_util.CanStartAnalysis(None, 0, False))

  @mock.patch.object(flake_util, 'BotsAvailableForTask', return_value=True)
  def testCanStartAnalysisBotsAvailable(self, _):
    self.assertTrue(flake_analysis_util.CanStartAnalysis(None, 0, False))

  @mock.patch.object(flake_util, 'BotsAvailableForTask', return_value=False)
  def testCanStartAnalysisNoBotsAvailable(self, _):
    self.assertFalse(flake_analysis_util.CanStartAnalysis(None, 0, False))

  @mock.patch.object(
      flake_analysis_util, 'ShouldThrottleAnalysis', return_value=False)
  @mock.patch.object(flake_analysis_util, 'CanStartAnalysis', return_value=True)
  def testCanStartAnalysisImmediately(self, *_):
    self.assertTrue(
        flake_analysis_util.CanStartAnalysisImmediately(None, 0, False))

  def testCanFailedSwarmingTaskBeSalvaged(self):
    completed_time = datetime(2018, 1, 1)
    started_time = completed_time - timedelta(hours=1)
    error = swarming_task_error.SwarmingTaskError(code=1, message='test')
    tries = 100
    successes = 50
    task_id = 'task'
    task_output = FlakeSwarmingTaskOutput(
        completed_time=completed_time,
        error=error,
        iterations=tries,
        pass_count=successes,
        started_time=started_time,
        task_id=task_id)
    self.assertTrue(
        flake_analysis_util.CanFailedSwarmingTaskBeSalvaged(task_output))

    task_output.iterations = None
    self.assertFalse(
        flake_analysis_util.CanFailedSwarmingTaskBeSalvaged(task_output))

  @mock.patch.object(
      flake_util,
      'GetETAToStartAnalysis',
      return_value=datetime(2017, 12, 10, 0, 0, 0, 0))
  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2017, 12, 10, 0, 0, 0, 0))
  def testCalculateDelaySecondsBetweenRetries(self, *_):
    self.assertEqual(0,
                     flake_analysis_util.CalculateDelaySecondsBetweenRetries(
                         0, False))
    self.assertEqual(120,
                     flake_analysis_util.CalculateDelaySecondsBetweenRetries(
                         1, False))
    self.assertEqual(0,
                     flake_analysis_util.CalculateDelaySecondsBetweenRetries(
                         flake_constants.MAX_RETRY_TIMES + 1, False))

  def testShouldThrottleAnalysis(self):
    self.UpdateUnitTestConfigSettings(
        config_property='check_flake_settings',
        override_data={
            'throttle_flake_analyses': True
        })
    self.assertTrue(flake_analysis_util.ShouldThrottleAnalysis())

  def testShouldThrottleAnalysisNotThrottled(self):
    self.UpdateUnitTestConfigSettings(
        config_property='check_flake_settings',
        override_data={
            'throttle_flake_analyses': False
        })
    self.assertFalse(flake_analysis_util.ShouldThrottleAnalysis())

  @mock.patch.object(CachedGitilesRepository, 'GetChangeLog')
  def testUpdateCulpritNewCulprit(self, mocked_fn):
    revision = 'a1b2c3d4'
    commit_position = 12345
    url = 'url'
    repo_name = 'repo_name'
    change_log = ChangeLog(None, None, revision, commit_position, None, None,
                           url, None)
    mocked_fn.return_value = change_log

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')

    culprit = flake_analysis_util.UpdateCulprit(
        analysis.key.urlsafe(), revision, commit_position, repo_name)

    self.assertIsNotNone(culprit)
    self.assertEqual([analysis.key.urlsafe()],
                     culprit.flake_analysis_urlsafe_keys)
    self.assertEqual(url, culprit.url)
    self.assertEqual(repo_name, culprit.repo_name)
    self.assertEqual(revision, culprit.revision)

  def testUpdateCulpritExistingCulprit(self):
    revision = 'a1b2c3d4'
    commit_position = 12345
    url = 'url'
    repo_name = 'repo_name'
    analysis_urlsafe_key = 'urlsafe_key'

    culprit = FlakeCulprit.Create(repo_name, revision, commit_position)
    culprit.flake_analysis_urlsafe_keys = ['another_analysis_urlsafe_key']
    culprit.url = url
    culprit.put()

    culprit = flake_analysis_util.UpdateCulprit(analysis_urlsafe_key, revision,
                                                commit_position, repo_name)

    self.assertIsNotNone(culprit)
    self.assertEqual(2, len(culprit.flake_analysis_urlsafe_keys))
    self.assertIn(analysis_urlsafe_key, culprit.flake_analysis_urlsafe_keys)
    self.assertEqual(url, culprit.url)
    self.assertEqual(repo_name, culprit.repo_name)
    self.assertEqual(revision, culprit.revision)

  def testUpdateCulpritExistingCulpritAlreadyHasAnalyis(self):
    revision = 'a1b2c3d4'
    commit_position = 12345
    url = 'url'
    repo_name = 'repo_name'
    analysis_urlsafe_key = 'urlsafe_key'
    culprit = FlakeCulprit.Create(repo_name, revision, commit_position)
    culprit.flake_analysis_urlsafe_keys = [analysis_urlsafe_key]
    culprit.url = url
    culprit.put()

    culprit = flake_analysis_util.UpdateCulprit(analysis_urlsafe_key, revision,
                                                commit_position, repo_name)

    self.assertIsNotNone(culprit)
    self.assertEqual(1, len(culprit.flake_analysis_urlsafe_keys))
    self.assertIn(analysis_urlsafe_key, culprit.flake_analysis_urlsafe_keys)
    self.assertEqual(url, culprit.url)
    self.assertEqual(repo_name, culprit.repo_name)
    self.assertEqual(revision, culprit.revision)

  @mock.patch.object(CachedGitilesRepository, 'GetChangeLog', return_value=None)
  def testUpdateCulpritNoLogs(self, _):
    revision = 'a1b2c3d4'
    commit_position = 12345
    repo_name = 'repo_name'
    analysis_urlsafe_key = 'urlsfe_key'
    culprit = flake_analysis_util.UpdateCulprit(analysis_urlsafe_key, revision,
                                                commit_position, repo_name)

    self.assertIn(analysis_urlsafe_key, culprit.flake_analysis_urlsafe_keys)
    self.assertEqual(commit_position, culprit.commit_position)
    self.assertEqual(revision, culprit.revision)
    self.assertIsNone(culprit.url)
    self.assertEqual(repo_name, culprit.repo_name)
