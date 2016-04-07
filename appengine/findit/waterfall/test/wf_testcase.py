# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.api import users

import copy

from common.findit_testcase import FinditTestCase
from model.wf_config import FinditConfig


_DEFAULT_STEPS_FOR_MASTERS_RULES = {
    'supported_masters': {
        'm': {
            'check_global': True
        },
        'm3': {
            'check_global': True
        },
        'master1': {
            # supported_steps override global.
            'supported_steps': ['unsupported_step6'],
            'unsupported_steps': ['unsupported_step1',
                                  'unsupported_step2',
                                  'unsupported_step3'],
            'check_global': True
        },
        'master2': {
            # Only supports step4 and step5 regardless of global.
            'supported_steps': ['step4', 'step5'],
            'check_global': False
        },
        'master3': {
            # Supports everything not blacklisted in global.
            'check_global': True
        },
    },
    'global': {
        # Blacklists all listed steps for all masters unless overridden.
        'unsupported_steps': ['unsupported_step6', 'unsupported_step7'],
    }
}


_DEFAULT_TRY_BOT_MAPPING = {
    'master1': {
        'builder1': {
            'mastername': 'tryserver1',
            'buildername': 'trybot1',
            'strict_regex': True,
        }
    },
    'm': {
        'b': {
            'mastername': 'tryserver.master',
            'buildername': 'tryserver.builder',
        }
    }
}


_DEFAULT_TRY_JOB_SETTINGS = {
    'server_query_interval_seconds': 60,
    'job_timeout_hours': 5,
    'allowed_response_error_times': 5
}


_DEFAULT_SWARMING_SETTINGS = {
    'server_host': 'chromium-swarm.appspot.com',
    'default_request_priority': 150,
    'request_expiration_hours': 20,
    'server_query_interval_seconds': 60,
    'task_timeout_hours': 23,
    'isolated_server': 'https://isolateserver.appspot.com',
    'isolated_storage_url': 'isolateserver.storage.googleapis.com',
    'iterations_to_rerun': 10
}


DEFAULT_CONFIG_DATA = {
    'steps_for_masters_rules': _DEFAULT_STEPS_FOR_MASTERS_RULES,
    'builders_to_trybots': _DEFAULT_TRY_BOT_MAPPING,
    'try_job_settings': _DEFAULT_TRY_JOB_SETTINGS,
    'swarming_settings': _DEFAULT_SWARMING_SETTINGS
}


class WaterfallTestCase(FinditTestCase):  # pragma: no cover.

  def UpdateUnitTestConfigSettings(self, config_property=None,
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

    FinditConfig.Get().Update(users.User(email='admin@chromium.org'), True,
                              **config_data)

  def setUp(self):
    super(WaterfallTestCase, self).setUp()
    self.UpdateUnitTestConfigSettings()


