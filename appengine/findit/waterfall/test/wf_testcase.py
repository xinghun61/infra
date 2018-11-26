# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import mock

from google.appengine.api import users
from google.appengine.api import urlfetch

import gae_ts_mon

from gae_libs.testcase import TestCase
from libs.structured_object import StructuredObject
from model.wf_config import FinditConfig

_DEFAULT_STEPS_FOR_MASTERS_RULES = {
    'supported_masters': {
        'm': {
            'check_global': True,
        },
        'm3': {
            'check_global': True,
        },
        'master1': {
            # supported_steps override global.
            'supported_steps': ['unsupported_step6'],
            'unsupported_steps': [
                'unsupported_step1', 'unsupported_step2', 'unsupported_step3'
            ],
            'check_global':
                True,
        },
        'master2': {
            # Only supports step4 and step5 regardless of global.
            'supported_steps': ['step4', 'step5'],
            'check_global': False,
        },
        'master3': {
            # Supports everything not blacklisted in global.
            'check_global': True,
        },
    },
    'global': {
        # Blacklists all listed steps for all masters unless overridden.
        'unsupported_steps': ['unsupported_step6', 'unsupported_step7'],
    },
}

_DEFAULT_TRY_BOT_MAPPING = {
    'master1': {
        'builder1': {
            'mastername': 'tryserver1',
            'waterfall_trybot': 'trybot1',
            'flake_trybot': 'trybot1_flake',
            'strict_regex': True,
        }
    },
    'master2': {
        'builder2': {
            'mastername': 'tryserver2',
            'waterfall_trybot': 'trybot2',
            'flake_trybot': 'trybot2_flake',
            'not_run_tests': True,
        },
        'builder3': {
            'mastername': 'tryserver2',
            'waterfall_trybot': 'trybot2',
            'flake_trybot': 'trybot2_flake',
            'not_run_tests': False,
        },
        'builder4': {
            'swarmbucket_mastername': 'swarming_tryserver2',
            'swarmbucket_trybot': 'swarming_trybot2',
            'mastername': 'tryserver2',
            'waterfall_trybot': 'trybot2',
            'flake_trybot': 'trybot2_flake',
            'not_run_tests': False,
        },
        'builder5': {
            'use_swarmbucket': True,
            'mastername': 'tryserver2',
            'waterfall_trybot': 'trybot2',
            'flake_trybot': 'trybot2_flake',
            'not_run_tests': False,
            'dimensions': ['os:Mac-10.9', 'cpu:x86-64']
        },
    },
    'm': {
        'b': {
            'mastername': 'tryserver.master',
            'waterfall_trybot': 'tryserver.builder',
            'flake_trybot': 'tryserver.flake_builder',
            'dimensions': ['os:Mac-10.9', 'cpu:x86-64']
        },
    },
    'chromium': {
        'Linux': {
            'mastername': 'tryserver.master',
            'waterfall_trybot': 'tryserver.builder',
            'flake_trybot': 'tryserver.flake_builder',
            'dimensions': ['os:Ubuntu-14.04', 'cpu:x86-64'],
        },
    },
}

_DEFAULT_TRY_JOB_SETTINGS = {
    'server_query_interval_seconds': 60,
    'job_timeout_hours': 5,
    'allowed_response_error_times': 5,
    'max_seconds_look_back_for_group': 86400,
}

_DEFAULT_SWARMING_SETTINGS = {
    'server_host': 'chromium-swarm.appspot.com',
    'default_request_priority': 150,
    'request_expiration_hours': 20,
    'server_query_interval_seconds': 60,
    'task_timeout_hours': 23,
    'isolated_server': 'https://isolateserver.appspot.com',
    'isolated_storage_url': 'isolateserver.storage.googleapis.com',
    'iterations_to_rerun': 10,
    'get_swarming_task_id_timeout_seconds': 5 * 60,  # 5 minutes.
    'get_swarming_task_id_wait_seconds': 10,
    'server_retry_timeout_hours': 2,
    'maximum_server_contact_retry_interval_seconds': 5 * 60,  # 5 minutes.
    'should_retry_server': False,  # No retry for unit testing.
    'minimum_number_of_available_bots': 5,
    'minimum_percentage_of_available_bots': 0.1,
}

_DEFAULT_DOWNLOAD_BUILD_DATA_SETTINGS = {
    'download_interval_seconds': 10,
    'memcache_master_download_expiration_seconds': 3600,
    'use_ninja_output_log': True,
}

_DEFAULT_ACTION_SETTINGS = {
    'cr_notification_build_threshold': 2,
    'cr_notification_latency_limit_minutes': 30,
    'cr_notification_should_notify_flake_culprit': True,
    'culprit_commit_limit_hours': 24,
    'auto_create_revert_compile': True,
    'auto_commit_revert_compile': True,
    'auto_commit_revert_daily_threshold_compile': 4,
    'auto_create_revert_daily_threshold_compile': 10,
    'auto_create_revert_test': True,
    'auto_commit_revert_test': True,
    'auto_commit_revert_daily_threshold_test': 4,
    'auto_create_revert_daily_threshold_test': 10,
    'auto_create_revert_daily_threshold_flake': 10,
    'auto_commit_revert_daily_threshold_flake': 4,
    'rotations_url': ('https://rota-ng.appspot.com/legacy/all_rotations.js'),
    'max_flake_bug_updates_per_day': 30,
}

_DEFAULT_CHECK_FLAKE_SETTINGS = {
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
}

_DEFAULT_FLAKE_DETECTION_SETTINGS = {
    'report_flakes_to_flake_analyzer': True,
    'min_required_impacted_cls_per_day': 3,
}

_DEFAULT_CODE_REVIEW_SETTINGS = {
    'rietveld_hosts': ['codereview.chromium.org'],
    'gerrit_hosts': ['chromium-review.googlesource.com'],
    'commit_bot_emails': ['commit-bot@chromium.org'],
}

DEFAULT_CONFIG_DATA = {
    'steps_for_masters_rules': _DEFAULT_STEPS_FOR_MASTERS_RULES,
    'builders_to_trybots': _DEFAULT_TRY_BOT_MAPPING,
    'try_job_settings': _DEFAULT_TRY_JOB_SETTINGS,
    'swarming_settings': _DEFAULT_SWARMING_SETTINGS,
    'download_build_data_settings': _DEFAULT_DOWNLOAD_BUILD_DATA_SETTINGS,
    'action_settings': _DEFAULT_ACTION_SETTINGS,
    'check_flake_settings': _DEFAULT_CHECK_FLAKE_SETTINGS,
    'flake_detection_settings': _DEFAULT_FLAKE_DETECTION_SETTINGS,
    'code_review_settings': _DEFAULT_CODE_REVIEW_SETTINGS,
}

SAMPLE_STEP_METADATA = {
    'waterfall_mastername': 'm',
    'waterfall_buildername': 'b',
    'canonical_step_name': 'browser_tests',
    'full_step_name': 'browser_tests on platform',
    'dimensions': {
        'os': 'platform'
    },
    'swarm_task_ids': ['1000', '1001']
}

SAMPLE_STEP_METADATA_NOT_SWARMED = {
    'waterfall_mastername': 'm',
    'waterfall_buildername': 'b',
    'canonical_step_name': 'browser_tests',
    'full_step_name': 'browser_tests on platform',
    'dimensions': {
        'os': 'platform'
    }
}


class WaterfallTestCase(TestCase):  # pragma: no cover.

  def UpdateUnitTestConfigSettings(self,
                                   config_property=None,
                                   override_data=None):
    """Sets up Findit's config for unit tests.

    Args:
      config_property: The name of the config property to update.
      override_data: A dict to override any default settings.
    """
    config_data = DEFAULT_CONFIG_DATA

    if config_property and override_data:
      config_data = copy.deepcopy(DEFAULT_CONFIG_DATA)
      config_data[config_property].update(override_data)

    FinditConfig.Get().Update(
        users.User(email='admin@chromium.org'), True, **config_data)

  def setUp(self):
    super(WaterfallTestCase, self).setUp()
    self.UpdateUnitTestConfigSettings()
    self.maxDiff = None
    # Make sure that no tests derived from this actually call urlfetch.fetch.
    mock.patch.object(
        urlfetch,
        'fetch',
        side_effect=AssertionError(
            'unittests must not perform actual network requests. Instead, '
            'mocks should be provided for the methods that do any network '
            'operations')).start()
    gae_ts_mon.reset_for_unittest(disable=True)

  def tearDown(self):
    mock.patch.stopall()
    super(WaterfallTestCase, self).tearDown()
