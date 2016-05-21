# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Findit for Waterfall configuration."""

from google.appengine.ext import ndb

from model.versioned_config import VersionedConfig


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
  # re-run compile to identify culprits for compile failures.
  builders_to_trybots = ndb.JsonProperty(indexed=False, default={})

  # A dict containing common settings for try jobs. For example,
  # {
  #     'server_query_interval_seconds': 60,
  #     'job_timeout_hours': 5,
  #     'allowed_response_error_times': 5
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
  #     'iterations_to_rerun': 10
  # }
  swarming_settings = ndb.JsonProperty(indexed=False, default={})

  # A dict containing build data download settings. For example,
  # {
  #     'download_interval_seconds': 10,
  #     'memcache_download_expiration_seconds': 3600,
  #     'use_chrome_build_extract': True
  # }
  download_build_data_settings = ndb.JsonProperty(indexed=False, default={})
  