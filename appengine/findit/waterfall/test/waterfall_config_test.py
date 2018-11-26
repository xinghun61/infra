# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import mock

from waterfall import waterfall_config
from waterfall.test import wf_testcase


class MastersTest(wf_testcase.WaterfallTestCase):

  def testConvertOldMastersFormatToNew(self):
    self.assertEqual({
        'supported_masters': {
            'master1': {
                'unsupported_steps': ['1', '2']
            },
            'master2': {}
        },
        'global': {}
    },
                     waterfall_config._ConvertOldMastersFormatToNew({
                         'master1': ['1', '2'],
                         'master2': {}
                     }))

  def testGetStepsForMastersRulesWithSettingsProvided(self):

    class MockSettings():
      steps_for_masters_rules = {'blabla': 'blabla'}

    self.assertEqual(
        waterfall_config.GetStepsForMastersRules(MockSettings()),
        MockSettings().steps_for_masters_rules)

  def testMasterIsSupported(self):
    self.assertTrue(waterfall_config.MasterIsSupported('master1'))
    self.assertFalse(waterfall_config.MasterIsSupported('blabla'))

  def testStepIsSupportedForMaster(self):
    self.assertFalse(
        waterfall_config.StepIsSupportedForMaster('unsupported_step1',
                                                  'master1'))
    self.assertTrue(
        waterfall_config.StepIsSupportedForMaster('step4', 'master1'))
    self.assertTrue(
        waterfall_config.StepIsSupportedForMaster('step4', 'master2'))
    self.assertFalse(
        waterfall_config.StepIsSupportedForMaster('blabla', 'blabla'))
    self.assertTrue(
        waterfall_config.StepIsSupportedForMaster('step4', 'master2'))
    self.assertTrue(
        waterfall_config.StepIsSupportedForMaster('blabla', 'master3'))
    self.assertTrue(
        waterfall_config.StepIsSupportedForMaster('step5', 'master1'))
    self.assertTrue(
        waterfall_config.StepIsSupportedForMaster('step5', 'master2'))
    self.assertFalse(
        waterfall_config.StepIsSupportedForMaster('unsupported_step7',
                                                  'master2'))
    self.assertTrue(
        waterfall_config.StepIsSupportedForMaster('unsupported_step6',
                                                  'master1'))
    self.assertFalse(
        waterfall_config.StepIsSupportedForMaster('unsupported_step6',
                                                  'master2'))
    self.assertFalse(
        waterfall_config.StepIsSupportedForMaster('unsupported_step6',
                                                  'master3'))
    self.assertFalse(
        waterfall_config.StepIsSupportedForMaster('unsupported_step7',
                                                  'master3'))

  def testGetTryJobSettings(self):
    self.assertEqual({
        'server_query_interval_seconds': 60,
        'job_timeout_hours': 5,
        'allowed_response_error_times': 5,
        'max_seconds_look_back_for_group': 86400
    }, waterfall_config.GetTryJobSettings())

  def testGetSwarmingSettings(self):
    self.assertEqual({
        'server_host': 'chromium-swarm.appspot.com',
        'default_request_priority': 150,
        'request_expiration_hours': 20,
        'server_query_interval_seconds': 60,
        'task_timeout_hours': 23,
        'isolated_server': 'https://isolateserver.appspot.com',
        'isolated_storage_url': 'isolateserver.storage.googleapis.com',
        'iterations_to_rerun': 10,
        'get_swarming_task_id_timeout_seconds': 300,
        'get_swarming_task_id_wait_seconds': 10,
        'server_retry_timeout_hours': 2,
        'maximum_server_contact_retry_interval_seconds': 5 * 60,
        'should_retry_server': False,
        'minimum_number_of_available_bots': 5,
        'minimum_percentage_of_available_bots': 0.1,
    }, waterfall_config.GetSwarmingSettings())

  def testGetDownloadBuildDataSettings(self):
    self.assertEqual({
        'download_interval_seconds': 10,
        'memcache_master_download_expiration_seconds': 3600,
        'use_ninja_output_log': True
    }, waterfall_config.GetDownloadBuildDataSettings())

  def testEnableStrictRegexForCompileLinkFailures(self):
    self.assertFalse(
        waterfall_config.EnableStrictRegexForCompileLinkFailures('m', 'b'))
    self.assertTrue(
        waterfall_config.EnableStrictRegexForCompileLinkFailures(
            'master1', 'builder1'))

  def testShouldSkipTestTryJobs(self):
    self.assertFalse(
        waterfall_config.ShouldSkipTestTryJobs('master1', 'builder1'))
    self.assertFalse(
        waterfall_config.ShouldSkipTestTryJobs('master2', 'builder3'))
    self.assertTrue(
        waterfall_config.ShouldSkipTestTryJobs('master2', 'builder2'))

  def testGetActionSettings(self):
    self.assertEqual({
        'cr_notification_build_threshold':
            2,
        'cr_notification_latency_limit_minutes':
            30,
        'cr_notification_should_notify_flake_culprit':
            True,
        'culprit_commit_limit_hours':
            24,
        'auto_create_revert_compile':
            True,
        'auto_commit_revert_compile':
            True,
        'auto_commit_revert_daily_threshold_compile':
            4,
        'auto_create_revert_daily_threshold_compile':
            10,
        'auto_create_revert_test':
            True,
        'auto_commit_revert_test':
            True,
        'auto_commit_revert_daily_threshold_test':
            4,
        'auto_create_revert_daily_threshold_test':
            10,
        'auto_create_revert_daily_threshold_flake':
            10,
        'auto_commit_revert_daily_threshold_flake':
            4,
        'rotations_url': ('https://rota-ng.appspot.com/legacy/all_rotations.js'
                         ),
        'max_flake_bug_updates_per_day':
            30,
    }, waterfall_config.GetActionSettings())

  def testGetCheckFlakeSettings(self):
    self.assertEqual({
        'iterations_to_run_after_timeout': 10,
        'lower_flake_threshold': 1e-7,
        'max_commit_positions_to_look_back': 5000,
        'max_iterations_per_task': 200,
        'max_iterations_to_rerun': 400,
        'minimum_confidence_to_create_bug': 0.7,
        'minimum_confidence_to_update_cr': 0.7,
        'per_iteration_timeout_seconds': 60,
        'swarming_task_cushion': 2,
        'swarming_task_retries_per_build': 3,
        'throttle_flake_analyses': False,
        'timeout_per_swarming_task_seconds': 3600,
        'timeout_per_test_seconds': 180,
        'upper_flake_threshold': 0.9999999
    }, waterfall_config.GetCheckFlakeSettings())

  def testGetCodeReviewSettings(self):
    self.assertEqual({
        'rietveld_hosts': ['codereview.chromium.org'],
        'gerrit_hosts': ['chromium-review.googlesource.com'],
        'commit_bot_emails': ['commit-bot@chromium.org'],
    }, waterfall_config.GetCodeReviewSettings())
