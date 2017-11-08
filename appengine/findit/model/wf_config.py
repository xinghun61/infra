# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Findit for Waterfall configuration."""

from google.appengine.ext import ndb

from gae_libs.model.versioned_config import VersionedConfig


class FinditConfig(VersionedConfig):
  """Global configuration of findit."""
  # Deprecated: A dict mapping supported masters to lists of unsupported steps.
  # The previous format of this dict is no longer also be supported, but is
  # instead converted to the new version at runtime if detected.
  # {
  #     master_name1: [unsupported_step1, unsupported_step2, ...],
  #     master_name2: [...],
  #     ...
  # }
  masters_to_blacklisted_steps = ndb.JsonProperty(indexed=False, default={})

  # steps_for_masters_rules is a dict containing rules for which steps
  # should and shouldn't run depending on the master.
  #
  # steps_for_masters_rules should have the format:
  # {
  #     'supported_masters': {
  #         master_name: {
  #            'supported_steps': [step1, step2, ...],
  #            'unsupported_steps': [step3, step4, ...],
  #            'check_global': True or False
  #         },
  #        ...
  #     },
  #     'global': {
  #         'unsupported_steps': [...]
  #     }
  # }
  #
  # 'supported_steps': Optional list used to override any 'unsupported_steps'
  # under global.
  # 'unsupported_steps': Optional list to supplement 'unsupported_steps' under
  # global.
  # 'check_global': Optional bool (True by default) to specify any settings in
  # global are to be obeyed or ignored entirely.
  steps_for_masters_rules = ndb.JsonProperty(indexed=False, default={})

  # Mapping of waterfall builders to try-server trybots, which are used to
  # re-run compile, test, and flake try jobs. Bots for failures on the main
  # waterfall (compile, test) have a dedicated pool separate from the bots
  # used to run flake try jobs.
  # {
  #     'Chromium':
  #         'Linux': {
  #              'waterfall_trybot': 'linux_chromium_variable',
  #              'flake_trybot': 'linux_chromium_variable_deflake',
  #              'mastername': 'tryserver.chromium.linux',
  #              'strict_regex": true
  #         },
  #         ...
  #      },
  #      ...
  # }
  builders_to_trybots = ndb.JsonProperty(indexed=False, default={})

  # A dict containing common settings for try jobs. For example,
  # {
  #     'server_query_interval_seconds': 60,
  #     'job_timeout_hours': 5,
  #     'allowed_response_error_times': 5
  #     'pubsub_token': 'SomeSecretString',
  #     'pubsub_topic': 'projects/findit-for-me/topics/jobs',
  #     'pubsub_swarming_topic': 'projects/findit-for-me/topics/swarm',
  # }
  try_job_settings = ndb.JsonProperty(indexed=False, default={})

  # A dict containing common settings for swarming tasks. For example,
  # {
  #     'server_host': 'chromium-swarm.appspot.com',
  #     'default_request_priority': 150,
  #     'request_expiration_hours': 20,
  #     'server_query_interval_seconds': 60,
  #     'task_timeout_hours': 23,
  #     'isolated_server': 'https://isolateserver.appspot.com',
  #     'isolated_storage_url': 'isolateserver.storage.googleapis.com',
  #     'iterations_to_rerun': 10,
  #     'get_swarming_task_id_timeout_seconds': 300,
  #     'get_swarming_task_id_wait_seconds': 10
  #     'server_retry_timeout_hours': 1,
  #     'maximum_server_contact_retry_interval_seconds': 1,
  #     'should_retry_server': False,
  #     'minimum_number_of_available_bots': 5,
  #     'minimum_percentage_of_available_bots': 0.1,
  # }
  swarming_settings = ndb.JsonProperty(indexed=False, default={})

  # A dict containing build data download settings. For example,
  # {
  #     'download_interval_seconds': 10,
  #     'memcache_download_expiration_seconds': 3600,
  #     'use_ninja_output_log': False
  # }
  download_build_data_settings = ndb.JsonProperty(indexed=False, default={})

  # A dict containing action settings for identified culprits or suspects.
  # {
  #     'cr_notification_build_threshold': 2,
  #     'cr_notification_latency_limit_minutes': 30,
  #     'auto_create_revert_compile': True,
  #     'auto_commit_revert_compile': False,
  #     'culprit_commit_limit_hours': 24,
  #     'auto_commit_daily_threshold': 4,
  #     'auto_revert_daily_threshold': 10,
  # }
  action_settings = ndb.JsonProperty(indexed=False, default={})

  # A dict containing settings for identifying the CL that introduced test
  # flakiness. For example,
  # {
  #     'swarming_rerun': {
  #         'lower_flake_threshold': 0.02,
  #         'upper_flake_threshold': 0.98,
  #         'max_flake_in_a_row': 4,
  #         'max_stable_in_a_row': 4,
  #         'iterations_to_rerun': 100,
  #         'max_build_numbers_to_look_back': 500,
  #         'dive_rate_threshold': 0.4,
  #         'max_dive_in_a_row': 4,
  #         'max_iterations_to_rerun': 800,
  #         'timeout_per_test_seconds': 120,
  #         'timeout_per_swarming_task_seconds': 3600,
  #         'swarming_task_cushion': 1.0,
  #         'swarming_task_retries_per_build': 2,
  #         'iterations_to_run_after_timeout': 10,
  #         'max_iterations_per_task': 200,
  #     },
  #     'try_job_rerun': {
  #         'lower_flake_threshold': 0.02,
  #         'upper_flake_threshold': 0.98,
  #         'max_flake_in_a_row': 4,
  #         'max_stable_in_a_row': 0,
  #         'iterations_to_rerun': 100
  #     },
  #     'create_monorail_bug': True,
  #     'new_flake_bugs_per_day': 2,
  #     'update_monorail_bug': False,
  #     'minimum_confidence_score_to_run_tryjobs': 0.6
  # }
  check_flake_settings = ndb.JsonProperty(indexed=False, default={})

  # A dict containing settings for interacting with code review systems.
  # For example,
  # {
  #     'rietveld_hosts': ['codereview.chromium.org'],
  #     'gerrit_hosts': ['chromium-review.googlesource.com'],
  #     'commit_bot_emails': ['commit-bot@chromium.org'],
  # }
  code_review_settings = ndb.JsonProperty(indexed=False, default={})
