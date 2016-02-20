# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

from model.wf_config import FinditConfig
from waterfall import waterfall_config


class MastersTest(testing.AppengineTestCase):

  def setUp(self):
    super(MastersTest, self).setUp()
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)

    config_data = {
        'steps_for_masters_rules': {
            'supported_masters': {
                'master1': {
                    # supported_steps override global.
                    'supported_steps': ['step6'],
                    'unsupported_steps': ['step1', 'step2', 'step3'],
                },
                'master2': {
                    # Only supports step4 and step5 regardless of global.
                    'supported_steps': ['step4', 'step5'],
                    'check_global': False
                },
                'master3': {
                    # Supports everything not blacklisted in global.
                },
            },
            'global': {
                # Blacklists all listed steps for all masters unless overridden.
                'unsupported_steps': ['step6', 'step7'],
            }
        },
        'builders_to_trybots': {
            'master1': {
                'builder1': {
                    'mastername': 'tryserver1',
                    'buildername': 'trybot1',
                }
            }
        },
        'try_job_settings': {
            'server_query_interval_seconds': 60,
            'job_timeout_hours': 5,
            'allowed_response_error_times': 1
        },
        'swarming_settings': {
            'server_host': 'chromium-swarm.appspot.com',
            'default_request_priority': 150,
            'request_expiration_hours': 20,
            'server_query_interval_seconds': 60,
            'task_timeout_hours': 23,
            'isolated_server': 'https://isolateserver.appspot.com',
            'isolated_storage_url': 'isolateserver.storage.googleapis.com',
            'iterations_to_rerun': 10
        }
    }

    FinditConfig.Get().Update(**config_data)

  def testConvertOldMastersFormatToNew(self):
    self.assertEqual(
        {
            'supported_masters': {
                'master1': {
                    'unsupported_steps': ['1', '2']
                },
                'master2': {}
            },
            'global': {}
        },
        waterfall_config._ConvertOldMastersFormatToNew(
            {
                'master1': ['1', '2'],
                'master2': {}

            }))

  def testMasterIsSupported(self):
    self.assertTrue(waterfall_config.MasterIsSupported('master1'))
    self.assertFalse(waterfall_config.MasterIsSupported('blabla'))

  def testStepIsSupportedForMaster(self):
    self.assertFalse(
        waterfall_config.StepIsSupportedForMaster('step1', 'master1'))
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
        waterfall_config.StepIsSupportedForMaster('step7', 'master2'))
    self.assertTrue(
        waterfall_config.StepIsSupportedForMaster('step6', 'master1'))
    self.assertFalse(
        waterfall_config.StepIsSupportedForMaster('step6', 'master2'))
    self.assertFalse(
        waterfall_config.StepIsSupportedForMaster('step6', 'master3'))
    self.assertFalse(
        waterfall_config.StepIsSupportedForMaster('step7', 'master3'))

  def testGetTrybotForWaterfallBuilder(self):
    self.assertEqual(
        ('tryserver1', 'trybot1'),
        waterfall_config.GetTrybotForWaterfallBuilder('master1', 'builder1'))
    self.assertEqual(
        (None, None),
        waterfall_config.GetTrybotForWaterfallBuilder('master2', 'builder2'))

  def testGetTryJobSettings(self):
    self.assertEqual(
        {
            'server_query_interval_seconds': 60,
            'job_timeout_hours': 5,
            'allowed_response_error_times': 1
        },
        waterfall_config.GetTryJobSettings())

  def testGetSwarmingSettings(self):
    self.assertEqual(
        {
            'server_host': 'chromium-swarm.appspot.com',
            'default_request_priority': 150,
            'request_expiration_hours': 20,
            'server_query_interval_seconds': 60,
            'task_timeout_hours': 23,
            'isolated_server': 'https://isolateserver.appspot.com',
            'isolated_storage_url': 'isolateserver.storage.googleapis.com',
            'iterations_to_rerun': 10
        },
        waterfall_config.GetSwarmingSettings())
