# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import mock
import re
import webapp2
import webtest

from handlers import config
from model import wf_config
from testing_utils import testing
from google.appengine.api import users

_MOCK_STEPS_FOR_MASTERS_RULES_OLD_FORMAT = {
    'master1': ['unsupported_step1', 'unsupported_step2'],
    'master2': ['unsupported_step3', 'unsupported_step4'],
}

_MOCK_STEPS_FOR_MASTERS_RULES = {
    'supported_masters': {
        'master1': {
            # supported_steps override global.
            'supported_steps': ['step6'],
            'unsupported_steps': ['step1', 'step2', 'step3'],
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
        'unsupported_steps': ['step6', 'step7'],
    }
}

_MOCK_BUILDERS_TO_TRYBOTS = {
    'master1': {
        'builder1': {
            'mastername': 'tryserver1',
            'waterfall_trybot': 'trybot1',
            'flake_trybot': 'trybot1_flake'
        }
    }
}

_MOCK_TRY_JOB_SETTINGS = {
    'server_query_interval_seconds': 60,
    'job_timeout_hours': 5,
    'allowed_response_error_times': 1,
    'max_seconds_look_back_for_group': 1,
    'pubsub_topic': 'projects/findit/topics/jobs',
    'pubsub_swarming_topic': 'projects/findit/topics/swarm',
    'pubsub_token': 'DummyT0k3n$trin9z0rz',
}

_MOCK_SWARMING_SETTINGS = {
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
    'per_iteration_timeout_seconds': 60,
}

_MOCK_DOWNLOAD_BUILD_DATA_SETTINGS = {
    'download_interval_seconds': 10,
    'memcache_master_download_expiration_seconds': 3600,
    'use_ninja_output_log': True
}

_MOCK_ACTION_SETTINGS = {
    'cr_notification_build_threshold': 2,
    'cr_notification_latency_limit_minutes': 1000,
    'cr_notification_should_notify_flake_culprit': True,
    'auto_create_revert_compile': True,
    'auto_commit_revert_compile': False,
    'culprit_commit_limit_hours': 24,
    'auto_commit_daily_threshold': 4,
    'auto_revert_daily_threshold': 10,
}

_MOCK_CHECK_FLAKE_SETTINGS = {
    'swarming_rerun': {
        'lower_flake_threshold': 0.02,
        'upper_flake_threshold': 0.98,
        'max_flake_in_a_row': 4,
        'max_stable_in_a_row': 4,
        'iterations_to_rerun': 100,
        'max_build_numbers_to_look_back': 1000,
        'max_dive_in_a_row': 4,
        'dive_rate_threshold': 0.4,
        'use_nearby_neighbor': True,
        'max_iterations_to_rerun': 800,
        'per_iteration_timeout_seconds': 60,
        'timeout_per_test_seconds': 120,
        'timeout_per_swarming_task_seconds': 3600,
        'swarming_task_cushion': 2.0,
        'swarming_task_retries_per_build': 2,
        'iterations_to_run_after_timeout': 10,
        'max_iterations_per_task': 200,
    },
    'try_job_rerun': {
        'lower_flake_threshold': 0.02,
        'upper_flake_threshold': 0.98,
        'max_flake_in_a_row': 0,
        'max_stable_in_a_row': 0,
        'iterations_to_rerun': 100,
    },
    'create_monorail_bug': True,
    'new_flake_bugs_per_day': 2,
    'update_monorail_bug': True,
    'minimum_confidence_score_to_run_tryjobs': 0.6,
    'minimum_confidence_to_update_cr': 0.5,
}

_MOCK_CODE_REVIEW_SETTINGS = {
    'rietveld_hosts': ['rietveld.org'],
    'gerrit_hosts': ['gerrit.org'],
    'commit_bot_emails': ['commit-bot@gerrit.org'],
}

_MOCK_VERSION_NUMBER = 12


class ConfigTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/config', config.Configuration),
      ], debug=True)

  def testGetConfigurationSettings(self):
    config_data = {
        'steps_for_masters_rules': _MOCK_STEPS_FOR_MASTERS_RULES,
        'builders_to_trybots': _MOCK_BUILDERS_TO_TRYBOTS,
        'try_job_settings': _MOCK_TRY_JOB_SETTINGS,
        'swarming_settings': _MOCK_SWARMING_SETTINGS,
        'download_build_data_settings': _MOCK_DOWNLOAD_BUILD_DATA_SETTINGS,
        'action_settings': _MOCK_ACTION_SETTINGS,
        'check_flake_settings': _MOCK_CHECK_FLAKE_SETTINGS,
        'code_review_settings': _MOCK_CODE_REVIEW_SETTINGS,
    }

    self.mock_current_user(user_email='test@chromium.org', is_admin=True)

    wf_config.FinditConfig.Get().Update(
        users.GetCurrentUser(), True, message='message', **config_data)

    response = self.test_app.get('/config', params={'format': 'json'})
    self.assertEquals(response.status_int, 200)

    expected_response = {
        'masters': _MOCK_STEPS_FOR_MASTERS_RULES,
        'builders': _MOCK_BUILDERS_TO_TRYBOTS,
        'try_job_settings': _MOCK_TRY_JOB_SETTINGS,
        'swarming_settings': _MOCK_SWARMING_SETTINGS,
        'download_build_data_settings': _MOCK_DOWNLOAD_BUILD_DATA_SETTINGS,
        'action_settings': _MOCK_ACTION_SETTINGS,
        'check_flake_settings': _MOCK_CHECK_FLAKE_SETTINGS,
        'code_review_settings': _MOCK_CODE_REVIEW_SETTINGS,
        'version': 1,
        'latest_version': 1,
        'updated_by': 'test',
        'updated_ts': response.json_body.get('updated_ts'),
        'message': 'message',
        'xsrf_token': response.json_body['xsrf_token'],
    }

    self.assertEquals(expected_response, response.json_body)

  def testGetVersionOfConfigurationSettings(self):
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)

    config_data = {
        'steps_for_masters_rules': _MOCK_STEPS_FOR_MASTERS_RULES,
        'builders_to_trybots': _MOCK_BUILDERS_TO_TRYBOTS,
        'try_job_settings': _MOCK_TRY_JOB_SETTINGS,
        'swarming_settings': _MOCK_SWARMING_SETTINGS,
        'download_build_data_settings': _MOCK_DOWNLOAD_BUILD_DATA_SETTINGS,
        'action_settings': _MOCK_ACTION_SETTINGS,
        'check_flake_settings': _MOCK_CHECK_FLAKE_SETTINGS,
        'code_review_settings': _MOCK_CODE_REVIEW_SETTINGS,
    }
    wf_config.FinditConfig.Get().Update(
        users.GetCurrentUser(), True, message='message', **config_data)

    response = self.test_app.get(
        '/config', params={'version': 1,
                           'format': 'json'})
    self.assertEquals(response.status_int, 200)

    expected_response = {
        'masters': _MOCK_STEPS_FOR_MASTERS_RULES,
        'builders': _MOCK_BUILDERS_TO_TRYBOTS,
        'try_job_settings': _MOCK_TRY_JOB_SETTINGS,
        'swarming_settings': _MOCK_SWARMING_SETTINGS,
        'download_build_data_settings': _MOCK_DOWNLOAD_BUILD_DATA_SETTINGS,
        'action_settings': _MOCK_ACTION_SETTINGS,
        'check_flake_settings': _MOCK_CHECK_FLAKE_SETTINGS,
        'code_review_settings': _MOCK_CODE_REVIEW_SETTINGS,
        'version': 1,
        'latest_version': 1,
        'updated_by': 'test',
        'updated_ts': response.json_body.get('updated_ts'),
        'message': 'message',
        'xsrf_token': response.json_body['xsrf_token'],
    }

    self.assertEquals(expected_response, response.json_body)

  def testGetOutOfBoundsVersionOfConfigurationSettings(self):
    config_data = {
        'steps_for_masters_rules': _MOCK_STEPS_FOR_MASTERS_RULES,
        'builders_to_trybots': _MOCK_BUILDERS_TO_TRYBOTS,
        'try_job_settings': _MOCK_TRY_JOB_SETTINGS,
        'swarming_settings': _MOCK_SWARMING_SETTINGS
    }
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)

    wf_config.FinditConfig.Get().Update(users.GetCurrentUser(), True,
                                        **config_data)

    self.assertRaisesRegexp(
        webtest.app.AppError,
        re.compile('The requested version is invalid or not found.',
                   re.MULTILINE | re.DOTALL),
        self.test_app.get,
        '/config',
        params={'version': 0,
                'format': 'json'})
    self.assertRaisesRegexp(
        webtest.app.AppError,
        re.compile('The requested version is invalid or not found.',
                   re.MULTILINE | re.DOTALL),
        self.test_app.get,
        '/config',
        params={'version': 2,
                'format': 'json'})

  def testIsListOfType(self):
    self.assertFalse(config._IsListOfType({}, basestring))
    self.assertFalse(config._IsListOfType([], basestring))
    self.assertFalse(config._IsListOfType([1], basestring))
    self.assertFalse(config._IsListOfType(['a', 1], basestring))
    self.assertTrue(config._IsListOfType(['a', 'b'], basestring))

  def testValidateSupportedMastersDict(self):
    self.assertFalse(
        config._ValidateMastersAndStepsRulesMapping(
            _MOCK_STEPS_FOR_MASTERS_RULES_OLD_FORMAT))
    self.assertFalse(config._ValidateMastersAndStepsRulesMapping(None))
    self.assertFalse(config._ValidateMastersAndStepsRulesMapping([]))
    self.assertFalse(config._ValidateMastersAndStepsRulesMapping({}))
    self.assertFalse(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': [],  # Should be a dict.
        }))
    self.assertFalse(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {},
            # 'global' is missing.
        }))
    self.assertFalse(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {},
            'global': []  # Should be a dict.
        }))
    self.assertTrue(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {},
            'global': {}
        }))
    self.assertFalse(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                3: {},  # Key should be a string.
            },
            'global': {}
        }))
    self.assertFalse(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master': [],  # Value should be a dict.
            },
            'global': {}
        }))
    self.assertFalse(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master': {
                    'check_global': 1  # Should be a bool.
                },
            },
            'global': {}
        }))
    self.assertTrue(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master': {},
            },
            'global': {}
        }))
    self.assertFalse(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master': {
                    'supported_steps': {},  # Should be a list.
                }
            },
            'global': {}
        }))
    self.assertFalse(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master': {
                    'supported_steps': [],  # List should not be empty.
                }
            },
            'global': {}
        }))
    self.assertFalse(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master': {
                    'supported_steps': [1],  # List should be of strings.
                }
            },
            'global': {}
        }))
    self.assertTrue(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master': {
                    'supported_steps': ['step1'],
                }
            },
            'global': {}
        }))
    self.assertFalse(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master': {
                    'supported_steps': ['step1'],
                    'unsupported_steps': 'blabla',  # Should be a list.
                }
            },
            'global': {}
        }))
    self.assertFalse(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master': {
                    'supported_steps': ['step1'],
                    'unsupported_steps': [],  # List should not be empty.
                }
            },
            'global': {}
        }))
    self.assertFalse(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master': {
                    'supported_steps': ['step1'],
                    'unsupported_steps': [{}],  # List should be of strings.
                }
            },
            'global': {}
        }))
    self.assertFalse(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master': {
                    'supported_steps': ['step1'],
                    'unsupported_steps': ['step1'],  # Should not overlap.
                }
            },
            'global': {}
        }))
    self.assertTrue(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master': {
                    'supported_steps': ['step1'],
                    'unsupported_steps': ['step2'],
                }
            },
            'global': {}
        }))
    self.assertFalse(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master1': {
                    'supported_steps': ['step1'],
                    'unsupported_steps': ['step2'],
                },
            },
            'global': {
                'unsupported_steps': 1  # Should be a list.
            }
        }))
    self.assertFalse(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master1': {
                    'supported_steps': ['step1'],
                    'unsupported_steps': ['step2'],
                },
            },
            'global': {
                'unsupported_steps': []  # Should not be empty.
            }
        }))
    self.assertFalse(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master1': {
                    'supported_steps': ['step1'],
                    'unsupported_steps': ['step2'],
                },
            },
            'global': {
                'unsupported_steps': [1]  # Should be a list of strings.
            }
        }))
    self.assertTrue(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master1': {
                    'supported_steps': ['step1'],
                    'unsupported_steps': ['step2'],
                },
            },
            'global': {
                'unsupported_steps': ['step3']
            }
        }))
    self.assertTrue(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master1': {
                    'supported_steps': ['step1'],
                    'unsupported_steps': ['step2'],
                    'check_global': True  # 'check_global' is optional.
                },
            },
            'global': {
                'unsupported_steps': ['step3']
            }
        }))
    self.assertFalse(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master1': {
                    'supported_steps': ['step1'],
                    'unsupported_steps': ['step2'],  # Should not be specified.
                    'check_global': False
                },
            },
            'global': {
                'unsupported_steps': ['step3']
            }
        }))

  def testValidatingMastersAndStepRulesRemovesDuplicates(self):
    valid_rules_with_duplicates = {
        'supported_masters': {
            'master1': {
                'supported_steps': ['step1', 'step1'],
                'unsupported_steps': ['step2', 'step2'],
            },
        },
        'global': {
            'unsupported_steps': ['step3', 'step3']
        }
    }
    self.assertTrue(
        config._ValidateMastersAndStepsRulesMapping(
            valid_rules_with_duplicates))
    self.assertEqual({
        'supported_masters': {
            'master1': {
                'supported_steps': ['step1', 'step1'],
                'unsupported_steps': ['step2', 'step2'],
            },
        },
        'global': {
            'unsupported_steps': ['step3', 'step3']
        }
    }, valid_rules_with_duplicates)

  def testValidateTrybotMapping(self):
    self.assertTrue(
        config._ValidateTrybotMapping({
            'master1': {
                'builder1': {
                    'mastername': 'tryserver1',
                    'waterfall_trybot': 'trybot1',
                }
            }
        }))
    self.assertTrue(
        config._ValidateTrybotMapping({
            'master1': {
                'builder1': {
                    'mastername': 'tryserver1',
                    'waterfall_trybot': 'trybot1',
                    'flake_trybot': 'trybot1_flake'
                }
            }
        }))
    self.assertTrue(
        config._ValidateTrybotMapping({
            'master1': {
                'builder1': {
                    'mastername': 'tryserver1',
                    'waterfall_trybot': 'trybot1',
                    'strict_regex': True,
                }
            }
        }))
    self.assertFalse(
        config._ValidateTrybotMapping({
            'master1': {
                'builder1': {
                    'mastername': 'tryserver1',
                    'waterfall_trybot': 'trybot1',
                    'strict_regex': 'a',
                }
            }
        }))
    self.assertTrue(
        config._ValidateTrybotMapping({
            'master1': {
                'builder1': {
                    'mastername': 'tryserver1',
                    'waterfall_trybot': 'trybot1',
                    'not_run_tests': True,
                }
            }
        }))
    self.assertTrue(
        config._ValidateTrybotMapping({
            'master1': {
                'builder1': {
                    'swarmbucket_mastername': 'tryserver1',
                    'swarmbucket_trybot': 'trybot1',
                }
            }
        }))
    self.assertFalse(
        config._ValidateTrybotMapping({
            'master1': {
                'builder1': {
                    'swarmbucket_mastername': 'tryserver1',
                    'waterfall_trybot': 'trybot1',
                }
            }
        }))
    self.assertFalse(
        config._ValidateTrybotMapping({
            'master1': {
                'builder1': {
                    'swarmbucket_mastername': 'tryserver1',
                    'swarmbucket_trybot': ['trybot1'],
                }
            }
        }))
    self.assertFalse(
        config._ValidateTrybotMapping({
            'master1': {
                'builder1': {
                    'swarmbucket_trybot': 'trybot2',
                    'mastername': 'tryserver1',
                    'waterfall_trybot': 'trybot1',
                }
            }
        }))
    self.assertFalse(
        config._ValidateTrybotMapping({
            'master1': {
                'builder1': {
                    'mastername': 'tryserver1',
                    'waterfall_trybot': 'trybot1',
                    'not_run_tests': 1,  # Should be a bool.
                }
            }
        }))
    self.assertFalse(
        config._ValidateTrybotMapping({
            'master1': {
                'builder1': {
                    'mastername': 'tryserver1',
                    'waterfall_trybot': {},  # Should be a string.
                    'flake_trybot': 'trybot2',
                }
            }
        }))
    self.assertFalse(
        config._ValidateTrybotMapping({
            'master1': {
                'builder1': {
                    'mastername': 'tryserver1',
                    'waterfall_trybot': 'trybot1',
                    'flake_trybot': 1,  # Should be a string.
                }
            }
        }))
    self.assertFalse(config._ValidateTrybotMapping(['a']))
    self.assertFalse(config._ValidateTrybotMapping({'a': ['b']}))
    self.assertFalse(config._ValidateTrybotMapping({'a': {'b': ['1']}}))
    self.assertFalse(config._ValidateTrybotMapping({'a': {'b': {}}}))

  def testValidateTryJobSettings(self):
    self.assertFalse(config._ValidateTryJobSettings([]))
    self.assertFalse(config._ValidateTryJobSettings({}))
    self.assertFalse(
        config._ValidateTryJobSettings({
            'server_query_interval_seconds': '1',  # Should be an int.
            'job_timeout_hours': 1,
            'allowed_response_error_times': 1,
            'max_seconds_look_back_for_group': 1,
            'pubsub_topic': 'projects/findit/topics/jobs',
            'pubsub_token': 'DummyT0k3n$trin9z0rz',
        }))
    self.assertFalse(
        config._ValidateTryJobSettings({
            'server_query_interval_seconds': 1,
            'job_timeout_hours': '1',  # Should be an int.
            'allowed_response_error_times': 1,
            'max_seconds_look_back_for_group': 1,
            'pubsub_topic': 'projects/findit/topics/jobs',
            'pubsub_token': 'DummyT0k3n$trin9z0rz',
        }))
    self.assertFalse(
        config._ValidateTryJobSettings({
            'server_query_interval_seconds': 1,
            'job_timeout_hours': 1,
            'allowed_response_error_times': '1',  # Should be an int.
            'max_seconds_look_back_for_group': 1,
            'pubsub_topic': 'projects/findit/topics/jobs',
            'pubsub_token': 'DummyT0k3n$trin9z0rz',
        }))
    self.assertFalse(
        config._ValidateTryJobSettings({
            'server_query_interval_seconds': 1,
            'job_timeout_hours': 1,
            'allowed_response_error_times': 1,
            'max_seconds_look_back_for_group': 'a',  # Should be an int.
            'pubsub_topic': 'projects/findit/topics/jobs',
            'pubsub_token': 'DummyT0k3n$trin9z0rz',
        }))
    self.assertFalse(
        config._ValidateTryJobSettings({
            'server_query_interval_seconds': 1,
            'job_timeout_hours': 1,
            'allowed_response_error_times': 1,
            'max_seconds_look_back_for_group': 1,
            'pubsub_topic': 1,  # Should be str.
            'pubsub_token': 'DummyT0k3n$trin9z0rz',
        }))
    self.assertFalse(
        config._ValidateTryJobSettings({
            'server_query_interval_seconds': 1,
            'job_timeout_hours': 1,
            'allowed_response_error_times': 1,
            'max_seconds_look_back_for_group': 1,
            'pubsub_topic': 'projects/findit/topics/jobs',
            'pubsub_token': 1,  # Should be str.
        }))
    self.assertTrue(config._ValidateTryJobSettings(_MOCK_TRY_JOB_SETTINGS))

  def testValidateSwarmingSettings(self):
    self.assertFalse(config._ValidateSwarmingSettings([]))
    self.assertFalse(config._ValidateSwarmingSettings({}))
    self.assertFalse(
        config._ValidateSwarmingSettings({
            'server_host': ['chromium-swarm.appspot.com'
                           ],  # Should be a string.
            'default_request_priority': 150,
            'request_expiration_hours': 20,
            'server_query_interval_seconds': 60,
            'task_timeout_hours': 23,
            'isolated_server': 'https://isolateserver.appspot.com',
            'isolated_storage_url': 'isolateserver.storage.googleapis.com',
            'iterations_to_rerun': 10,
            'get_swarming_task_id_timeout_seconds': 300,
            'get_swarming_task_id_wait_seconds': 10
        }))
    self.assertFalse(
        config._ValidateSwarmingSettings({
            'server_host': 'chromium-swarm.appspot.com',
            'default_request_priority': '150',  # Should be an int.
            'request_expiration_hours': 20,
            'server_query_interval_seconds': 60,
            'task_timeout_hours': 23,
            'isolated_server': 'https://isolateserver.appspot.com',
            'isolated_storage_url': 'isolateserver.storage.googleapis.com',
            'iterations_to_rerun': 10,
            'get_swarming_task_id_timeout_seconds': 300,
            'get_swarming_task_id_wait_seconds': 10
        }))
    self.assertFalse(
        config._ValidateSwarmingSettings({
            'server_host': 'chromium-swarm.appspot.com',
            'default_request_priority': 150,
            'request_expiration_hours': {},  # Should be an int.
            'server_query_interval_seconds': 60,
            'task_timeout_hours': 23,
            'isolated_server': 'https://isolateserver.appspot.com',
            'isolated_storage_url': 'isolateserver.storage.googleapis.com',
            'iterations_to_rerun': 10,
            'get_swarming_task_id_timeout_seconds': 300,
            'get_swarming_task_id_wait_seconds': 10
        }))
    self.assertFalse(
        config._ValidateSwarmingSettings({
            'server_host': 'chromium-swarm.appspot.com',
            'default_request_priority': 150,
            'request_expiration_hours': 20,
            'server_query_interval_seconds': [],  # Should be an int.
            'task_timeout_hours': 23,
            'isolated_server': 'https://isolateserver.appspot.com',
            'isolated_storage_url': 'isolateserver.storage.googleapis.com',
            'iterations_to_rerun': 10,
            'get_swarming_task_id_timeout_seconds': 300,
            'get_swarming_task_id_wait_seconds': 10
        }))
    self.assertFalse(
        config._ValidateSwarmingSettings({
            'server_host': 'chromium-swarm.appspot.com',
            'default_request_priority': 150,
            'request_expiration_hours': 20,
            'server_query_interval_seconds': 60,
            'task_timeout_hours': None,  # should be an int.
            'isolated_server': 'https://isolateserver.appspot.com',
            'isolated_storage_url': 'isolateserver.storage.googleapis.com',
            'iterations_to_rerun': 10,
            'get_swarming_task_id_timeout_seconds': 300,
            'get_swarming_task_id_wait_seconds': 10
        }))
    self.assertFalse(
        config._ValidateSwarmingSettings({
            'server_host': 'chromium-swarm.appspot.com',
            'default_request_priority': 150,
            'request_expiration_hours': 20,
            'server_query_interval_seconds': 60,
            'task_timeout_hours': 23,
            'isolated_server': 1,  # Should be a string.
            'isolated_storage_url': 'isolateserver.storage.googleapis.com',
            'iterations_to_rerun': 10,
            'get_swarming_task_id_timeout_seconds': 300,
            'get_swarming_task_id_wait_seconds': 10
        }))
    self.assertFalse(
        config._ValidateSwarmingSettings({
            'server_host': 'chromium-swarm.appspot.com',
            'default_request_priority': 150,
            'request_expiration_hours': 20,
            'server_query_interval_seconds': 60,
            'task_timeout_hours': 23,
            'isolated_server': 'https://isolateserver.appspot.com',
            'isolated_storage_url': 3.2,  # Should be a string.
            'iterations_to_rerun': 10,
            'get_swarming_task_id_timeout_seconds': 300,
            'get_swarming_task_id_wait_seconds': 10
        }))
    self.assertFalse(
        config._ValidateSwarmingSettings({
            'server_host': 'chromium-swarm.appspot.com',
            'default_request_priority': 150,
            'request_expiration_hours': 20,
            'server_query_interval_seconds': 60,
            'task_timeout_hours': 23,
            'isolated_server': 'https://isolateserver.appspot.com',
            'isolated_storage_url': 'isolateserver.storage.googleapis.com',
            'iterations_to_rerun': 1.0,  # Should be an int.
            'get_swarming_task_id_timeout_seconds': 300,
            'get_swarming_task_id_wait_seconds': 10
        }))
    self.assertFalse(
        config._ValidateSwarmingSettings({
            'server_host': 'chromium-swarm.appspot.com',
            'default_request_priority': 150,
            'request_expiration_hours': 20,
            'server_query_interval_seconds': 60,
            'task_timeout_hours': 23,
            'isolated_server': 'https://isolateserver.appspot.com',
            'isolated_storage_url': 'isolateserver.storage.googleapis.com',
            'iterations_to_rerun': 1,
            'get_swarming_task_id_timeout_seconds': '300',  # Should be an int.
            'get_swarming_task_id_wait_seconds': 10
        }))
    self.assertFalse(
        config._ValidateSwarmingSettings({
            'server_host': 'chromium-swarm.appspot.com',
            'default_request_priority': 150,
            'request_expiration_hours': 20,
            'server_query_interval_seconds': 60,
            'task_timeout_hours': 23,
            'isolated_server': 'https://isolateserver.appspot.com',
            'isolated_storage_url': 'isolateserver.storage.googleapis.com',
            'iterations_to_rerun': 1,
            'get_swarming_task_id_timeout_seconds': 300,
            'get_swarming_task_id_wait_seconds': []  # Should be an int.
        }))
    self.assertFalse(
        config._ValidateSwarmingSettings({
            'server_host': 'chromium-swarm.appspot.com',
            'default_request_priority': 150,
            'request_expiration_hours': 20,
            'server_query_interval_seconds': 60,
            'task_timeout_hours': 23,
            'isolated_server': 'https://isolateserver.appspot.com',
            'isolated_storage_url': 'isolateserver.storage.googleapis.com',
            'iterations_to_rerun': 1,
            'get_swarming_task_id_timeout_seconds': 300,
            'get_swarming_task_id_wait_secondds': 10,
            'server_retry_timeout_hours': {}  # Should be an int.
        }))
    self.assertFalse(
        config._ValidateSwarmingSettings({
            'server_host': 'chromium-swarm.appspot.com',
            'default_request_priority': 150,
            'request_expiration_hours': 20,
            'server_query_interval_seconds': 60,
            'task_timeout_hours': 23,
            'isolated_server': 'https://isolateserver.appspot.com',
            'isolated_storage_url': 'isolateserver.storage.googleapis.com',
            'iterations_to_rerun': 1,
            'get_swarming_task_id_timeout_seconds': 300,
            'get_swarming_task_id_wait_secondds': 10,
            'server_retry_timeout_hours': 1,
            'maximum_server_contact_retry_interval_seconds':
                ''  # Should be an int.
        }))
    self.assertFalse(
        config._ValidateSwarmingSettings({
            'server_host': 'chromium-swarm.appspot.com',
            'default_request_priority': 150,
            'request_expiration_hours': 20,
            'server_query_interval_seconds': 60,
            'task_timeout_hours': 23,
            'isolated_server': 'https://isolateserver.appspot.com',
            'isolated_storage_url': 'isolateserver.storage.googleapis.com',
            'iterations_to_rerun': 1,
            'get_swarming_task_id_timeout_seconds': 300,
            'get_swarming_task_id_wait_secondds': 10,
            'server_retry_timeout_hours': 1,
            'maximum_server_contact_retry_interval_seconds': 2,
            'should_retry_server': 3  # Should be a bool.
        }))
    self.assertFalse(
        config._ValidateSwarmingSettings({
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
            'server_retry_timeout_hours': 1,
            'maximum_server_contact_retry_interval_seconds': 1,
            'should_retry_server': False,
            'minimum_number_of_available_bots': '5',  # Should be an int.
            'minimum_percentage_of_available_bots': 0.1
        }))
    self.assertFalse(
        config._ValidateSwarmingSettings({
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
            'server_retry_timeout_hours': 1,
            'maximum_server_contact_retry_interval_seconds': 1,
            'should_retry_server': False,
            'minimum_number_of_available_bots': 5,
            'minimum_percentage_of_available_bots': 10  # Should be a float.
        }))
    self.assertFalse(
        config._ValidateSwarmingSettings({
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
            'server_retry_timeout_hours': 1,
            'maximum_server_contact_retry_interval_seconds': 1,
            'should_retry_server': False,
            'minimum_number_of_available_bots': 5,
            'minimum_percentage_of_available_bots': 0.1,
            'per_iteration_timeout_seconds': 'a'  # Should be an int.
        }))
    self.assertTrue(
        config._ValidateSwarmingSettings({
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
            'server_retry_timeout_hours': 1,
            'maximum_server_contact_retry_interval_seconds': 1,
            'should_retry_server': False,
            'minimum_number_of_available_bots': 5,
            'minimum_percentage_of_available_bots': 0.1,
            'per_iteration_timeout_seconds': 60,
        }))

  def testValidateDownloadBuildDataSettings(self):
    self.assertFalse(config._ValidateDownloadBuildDataSettings({}))
    self.assertFalse(
        config._ValidateDownloadBuildDataSettings({
            'download_interval_seconds': {},  # Should be an int.
            'memcache_master_download_expiration_seconds': 10,
            'use_ninja_output_log': False
        }))
    self.assertFalse(
        config._ValidateDownloadBuildDataSettings({
            'download_interval_seconds': 10,
            'memcache_master_download_expiration_seconds': [
            ],  # Should be an int.
            'use_ninja_output_log': False
        }))
    self.assertFalse(
        config._ValidateDownloadBuildDataSettings({
            'download_interval_seconds': 10,
            'memcache_master_download_expiration_seconds': 3600,
            'use_ninja_output_log': 'blabla'  # Should be a bool.
        }))
    self.assertTrue(
        config._ValidateDownloadBuildDataSettings({
            'download_interval_seconds': 10,
            'memcache_master_download_expiration_seconds': 3600,
            'use_ninja_output_log': False
        }))

  def testConfigurationDictIsValid(self):
    self.assertTrue(
        config._ConfigurationDictIsValid({
            'steps_for_masters_rules': {
                'supported_masters': {
                    'master1': {
                        'unsupported_steps': ['step1', 'step2'],
                    },
                    'master2': {
                        'supported_steps': ['step3'],
                        'check_global': False
                    }
                },
                'global': {
                    'unsupported_steps': ['step5'],
                }
            }
        }))
    self.assertFalse(config._ConfigurationDictIsValid([]))
    self.assertFalse(
        config._ConfigurationDictIsValid({
            'this_is_not_a_valid_property': []
        }))

  def testFormatTimestamp(self):
    self.assertIsNone(config._FormatTimestamp(None))
    self.assertEqual('2016-02-25 01:02:03',
                     config._FormatTimestamp(
                         datetime.datetime(2016, 2, 25, 1, 2, 3, 123456)))

  @mock.patch('gae_libs.token.ValidateAuthToken')
  def testPostConfigurationSettings(self, mocked_ValidateAuthToken):
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)
    mocked_ValidateAuthToken.side_effect = [(True, False)]

    params = {
        'format':
            'json',
        'steps_for_masters_rules':
            json.dumps({
                'supported_masters': {
                    'a': {},
                    'b': {
                        'supported_steps': ['1'],
                        'unsupported_steps': ['2', '3', '4'],
                    },
                    'c': {
                        'supported_steps': ['5'],
                        'check_global': False
                    }
                },
                'global': {
                    'unsupported_steps': ['1']
                }
            }),
        'builders_to_trybots':
            json.dumps(_MOCK_BUILDERS_TO_TRYBOTS),
        'try_job_settings':
            json.dumps(_MOCK_TRY_JOB_SETTINGS),
        'swarming_settings':
            json.dumps(_MOCK_SWARMING_SETTINGS),
        'download_build_data_settings':
            json.dumps(_MOCK_DOWNLOAD_BUILD_DATA_SETTINGS),
        'action_settings':
            json.dumps(_MOCK_ACTION_SETTINGS),
        'check_flake_settings':
            json.dumps(_MOCK_CHECK_FLAKE_SETTINGS),
        'code_review_settings':
            json.dumps(_MOCK_CODE_REVIEW_SETTINGS),
        'message':
            'reason',
    }

    response = self.test_app.post('/config', params=params)

    expected_response = {
        'masters': {
            'supported_masters': {
                'a': {},
                'b': {
                    'supported_steps': ['1'],
                    'unsupported_steps': ['2', '3', '4'],
                },
                'c': {
                    'supported_steps': ['5'],
                    'check_global': False
                }
            },
            'global': {
                'unsupported_steps': ['1']
            }
        },
        'builders': _MOCK_BUILDERS_TO_TRYBOTS,
        'try_job_settings': _MOCK_TRY_JOB_SETTINGS,
        'swarming_settings': _MOCK_SWARMING_SETTINGS,
        'download_build_data_settings': _MOCK_DOWNLOAD_BUILD_DATA_SETTINGS,
        'action_settings': _MOCK_ACTION_SETTINGS,
        'check_flake_settings': _MOCK_CHECK_FLAKE_SETTINGS,
        'code_review_settings': _MOCK_CODE_REVIEW_SETTINGS,
        'version': 1,
        'latest_version': 1,
        'updated_by': 'test',
        'updated_ts': response.json_body.get('updated_ts'),
        'message': 'reason',
        'xsrf_token': response.json_body['xsrf_token'],
    }

    self.assertEquals(expected_response, response.json_body)

  def testValidateActionSettings(self):
    self.assertFalse(config._ValidateActionSettings({}))
    self.assertFalse(
        config._ValidateActionSettings({
            'cr_notification_build_threshold': 2,
            'cr_notification_latency_limit_minutes': 1000,
            'auto_create_revert_compile': 'True',  # Should be boolean.
        }))
    self.assertFalse(
        config._ValidateActionSettings({
            'cr_notification_build_threshold': 2,
            'cr_notification_latency_limit_minutes': 1000,
            'cr_notification_should_notify_flake_culprit': [
            ],  # Should be boolean.
            'auto_create_revert_compile': True,
        }))
    self.assertFalse(
        config._ValidateActionSettings({
            'cr_notification_build_threshold': 2,
            'cr_notification_latency_limit_minutes': 1000,
            'cr_notification_should_notify_flake_culprit': True,
            'auto_create_revert_compile': True,
            'auto_commit_revert_compile': 'False',  # Should be boolean.
            'culprit_commit_limit_hours': 24,
            'auto_commit_daily_threshold': 4,
            'auto_revert_daily_threshold': 10,
        }))
    self.assertFalse(
        config._ValidateActionSettings({
            'cr_notification_build_threshold': 2,
            'cr_notification_latency_limit_minutes': 1000,
            'cr_notification_should_notify_flake_culprit': True,
            'auto_create_revert_compile': True,
            'auto_commit_revert_compile': False,
            'culprit_commit_limit_hours': '24',  # Should be int.
            'auto_commit_daily_threshold': 4,
            'auto_revert_daily_threshold': 10,
        }))
    self.assertFalse(
        config._ValidateActionSettings({
            'cr_notification_build_threshold': 2,
            'cr_notification_latency_limit_minutes': 1000,
            'cr_notification_should_notify_flake_culprit': True,
            'auto_create_revert_compile': True,
            'auto_commit_revert_compile': False,
            'culprit_commit_limit_hours': 24,
            'auto_commit_daily_threshold': '4',  # Should be int.
            'auto_revert_daily_threshold': 10,
        }))
    self.assertFalse(
        config._ValidateActionSettings({
            'cr_notification_build_threshold': 2,
            'cr_notification_latency_limit_minutes': 1000,
            'cr_notification_should_notify_flake_culprit': True,
            'auto_create_revert_compile': True,
            'auto_commit_revert_compile': False,
            'culprit_commit_limit_hours': 24,
            'auto_commit_daily_threshold': 4,
            'auto_revert_daily_threshold': '10',  # Should be int.
        }))
    self.assertTrue(
        config._ValidateActionSettings({
            'cr_notification_build_threshold': 2,
            'cr_notification_latency_limit_minutes': 1000,
            'cr_notification_should_notify_flake_culprit': True,
            'auto_create_revert_compile': True,
            'auto_commit_revert_compile': False,
            'culprit_commit_limit_hours': 24,
            'auto_commit_daily_threshold': 4,
            'auto_revert_daily_threshold': 10,
        }))

  def testValidateFlakeAnalyzerTryJobRerunSettings(self):
    self.assertFalse(config._ValidateFlakeAnalyzerTryJobRerunSettings({}))
    self.assertFalse(
        config._ValidateFlakeAnalyzerTryJobRerunSettings({
            'lower_flake_threshold': 'b',  # Should be a float.
            'upper_flake_threshold': 0.98,
            'max_flake_in_a_row': 4,
            'max_stable_in_a_row': 4,
            'iterations_to_rerun': 100,
        }))
    self.assertFalse(
        config._ValidateFlakeAnalyzerTryJobRerunSettings({
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 'a',  # Should be a float.
            'max_flake_in_a_row': 4,
            'max_stable_in_a_row': 4,
            'iterations_to_rerun': 100,
        }))
    self.assertFalse(
        config._ValidateFlakeAnalyzerTryJobRerunSettings({
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98,
            'max_flake_in_a_row': [],  # Should be an int.
            'max_stable_in_a_row': 4,
            'iterations_to_rerun': 100,
        }))
    self.assertFalse(
        config._ValidateFlakeAnalyzerTryJobRerunSettings({
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98,
            'max_flake_in_a_row': 4,
            'max_stable_in_a_row': {},  # Should be an int.
            'iterations_to_rerun': 100,
        }))
    self.assertFalse(
        config._ValidateFlakeAnalyzerTryJobRerunSettings({
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98,
            'max_flake_in_a_row': 4,
            'max_stable_in_a_row': 4,
            'iterations_to_rerun': 3.2,  # Should be an int.
        }))
    self.assertTrue(
        config._ValidateFlakeAnalyzerTryJobRerunSettings({
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98,
            'max_flake_in_a_row': 4,
            'max_stable_in_a_row': 4,
            'iterations_to_rerun': 4,
        }))

  def testValidateFlakeAnalyzerSwarmingRerunSettings(self):
    self.assertFalse(config._ValidateFlakeAnalyzerSwarmingRerunSettings({}))
    self.assertFalse(
        config._ValidateFlakeAnalyzerSwarmingRerunSettings({
            'lower_flake_threshold': 1,  # Should be a float.
            'upper_flake_threshold': 0.98,
            'max_flake_in_a_row': 4,
            'max_stable_in_a_row': 4,
            'iterations_to_rerun': 100,
            'max_build_numbers_to_look_back': 1000,
            'create_monorail_bug': True,
            'new_flake_bugs_per_day': 2,
            'use_nearby_neighbor': True,
            'max_iterations_to_rerun': 800,
            'timeout_per_test_seconds': 120,
            'timeout_per_swarming_task_seconds': 3600,
            'swarming_task_cushion': 2.0,
            'swarming_task_retries_per_build': 2,
            'iterations_to_run_after_timeout': 10,
            'max_iterations_per_task': 200,
        }))
    self.assertFalse(
        config._ValidateFlakeAnalyzerSwarmingRerunSettings({
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 'a',  # Should be a float.
            'max_flake_in_a_row': 4,
            'max_stable_in_a_row': 4,
            'iterations_to_rerun': 100,
            'max_build_numbers_to_look_back': 1000,
            'create_monorail_bug': True,
            'new_flake_bugs_per_day': 2,
            'use_nearby_neighbor': True,
            'max_iterations_to_rerun': 800,
            'timeout_per_test_seconds': 120,
            'timeout_per_swarming_task_seconds': 3600,
            'swarming_task_cushion': 2.0,
            'swarming_task_retries_per_build': 2,
            'iterations_to_run_after_timeout': 10,
            'max_iterations_per_task': 200,
        }))
    self.assertFalse(
        config._ValidateFlakeAnalyzerSwarmingRerunSettings({
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98,
            'max_flake_in_a_row': [],  # Should be an int.
            'max_stable_in_a_row': 4,
            'iterations_to_rerun': 100,
            'max_build_numbers_to_look_back': 1000,
            'create_monorail_bug': True,
            'new_flake_bugs_per_day': 2,
            'use_nearby_neighbor': True,
            'max_iterations_to_rerun': 800,
            'timeout_per_test_seconds': 120,
            'timeout_per_swarming_task_seconds': 3600,
            'swarming_task_cushion': 2.0,
            'swarming_task_retries_per_build': 2,
            'iterations_to_run_after_timeout': 10,
            'max_iterations_per_task': 200,
        }))
    self.assertFalse(
        config._ValidateFlakeAnalyzerSwarmingRerunSettings({
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98,
            'max_flake_in_a_row': 4,
            'max_stable_in_a_row': {},  # Should be an int.
            'iterations_to_rerun': 100,
            'max_build_numbers_to_look_back': 1000,
            'create_monorail_bug': True,
            'new_flake_bugs_per_day': 2,
            'use_nearby_neighbor': True,
            'max_iterations_to_rerun': 800,
            'timeout_per_test_seconds': 120,
            'timeout_per_swarming_task_seconds': 3600,
            'swarming_task_cushion': 2.0,
            'swarming_task_retries_per_build': 2,
            'iterations_to_run_after_timeout': 10,
            'max_iterations_per_task': 200,
        }))
    self.assertFalse(
        config._ValidateFlakeAnalyzerSwarmingRerunSettings({
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98,
            'max_flake_in_a_row': 4,
            'max_stable_in_a_row': 4,
            'iterations_to_rerun': 3.2,  # Should be an int.
            'max_build_numbers_to_look_back': 1000,
            'create_monorail_bug': True,
            'new_flake_bugs_per_day': 2,
            'use_nearby_neighbor': True,
            'max_iterations_to_rerun': 800,
            'timeout_per_test_seconds': 120,
            'timeout_per_swarming_task_seconds': 3600,
            'swarming_task_cushion': 2.0,
            'swarming_task_retries_per_build': 2,
            'iterations_to_run_after_timeout': 10,
            'max_iterations_per_task': 200,
        }))
    self.assertFalse(
        config._ValidateFlakeAnalyzerSwarmingRerunSettings({
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98,
            'max_flake_in_a_row': 4,
            'max_stable_in_a_row': 4,
            'iterations_to_rerun': 4,
            'max_build_numbers_to_look_back': 'a',  # Should be an int.
            'create_monorail_bug': True,
            'new_flake_bugs_per_day': 2,
            'use_nearby_neighbor': True,
            'max_iterations_to_rerun': 800,
            'timeout_per_test_seconds': 120,
            'timeout_per_swarming_task_seconds': 3600,
            'swarming_task_cushion': 2.0,
            'swarming_task_retries_per_build': 2,
            'iterations_to_run_after_timeout': 10,
            'max_iterations_per_task': 200,
        }))
    self.assertFalse(
        config._ValidateFlakeAnalyzerSwarmingRerunSettings({
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98,
            'max_flake_in_a_row': 4,
            'max_stable_in_a_row': 4,
            'iterations_to_rerun': 4,
            'max_build_numbers_to_look_back': 1000,
            'create_monorail_bug': 10,  # Should be a bool.
            'new_flake_bugs_per_day': 2,
            'use_nearby_neighbor': True,
            'max_iterations_to_rerun': 800,
            'timeout_per_test_seconds': 120,
            'timeout_per_swarming_task_seconds': 3600,
            'swarming_task_cushion': 2.0,
            'swarming_task_retries_per_build': 2,
            'iterations_to_run_after_timeout': 10,
            'max_iterations_per_task': 200,
        }))
    self.assertFalse(
        config._ValidateFlakeAnalyzerSwarmingRerunSettings({
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98,
            'max_flake_in_a_row': 4,
            'max_stable_in_a_row': 4,
            'iterations_to_rerun': 4,
            'max_build_numbers_to_look_back': 100,
            'use_nearby_neighbor': [],  # Should be a bool.
            'max_iterations_to_rerun': 800,
            'timeout_per_test_seconds': 120,
            'timeout_per_swarming_task_seconds': 3600,
            'swarming_task_cushion': 2.0,
            'swarming_task_retries_per_build': 2,
            'iterations_to_run_after_timeout': 10,
            'max_iterations_per_task': 200,
        }))
    self.assertFalse(
        config._ValidateFlakeAnalyzerSwarmingRerunSettings({
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98,
            'max_flake_in_a_row': 4,
            'max_stable_in_a_row': 4,
            'iterations_to_rerun': 4,
            'max_build_numbers_to_look_back': 1000,
            'create_monorail_bug': True,
            'new_flake_bugs_per_day': {},  # Should be int.
            'use_nearby_neighbor': True,
            'max_iterations_to_rerun': 800,
            'timeout_per_test_seconds': 120,
            'timeout_per_swarming_task_seconds': 3600,
            'swarming_task_cushion': 2.0,
            'swarming_task_retries_per_build': 2,
            'iterations_to_run_after_timeout': 10,
            'max_iterations_per_task': 200,
        }))
    self.assertFalse(
        config._ValidateFlakeAnalyzerSwarmingRerunSettings({
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98,
            'max_flake_in_a_row': 4,
            'max_stable_in_a_row': 4,
            'iterations_to_rerun': 100,
            'max_build_numbers_to_look_back': 1000,
            'create_monorail_bug': True,
            'new_flake_bugs_per_day': 2,
            'update_monorail_bug': 'True',  # Should be a bool.
            'max_iterations_to_rerun': 800,
            'timeout_per_test_seconds': 120,
            'timeout_per_swarming_task_seconds': 3600,
            'swarming_task_cushion': 2.0,
            'swarming_task_retries_per_build': 2,
            'iterations_to_run_after_timeout': 10,
            'max_iterations_per_task': 200,
        }))
    self.assertFalse(
        config._ValidateFlakeAnalyzerSwarmingRerunSettings({
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98,
            'max_flake_in_a_row': 4,
            'max_stable_in_a_row': 4,
            'iterations_to_rerun': 100,
            'max_build_numbers_to_look_back': 1000,
            'create_monorail_bug': True,
            'new_flake_bugs_per_day': 2,
            'update_monorail_bug': True,
            'max_dive_in_a_row': 4.0,  # Should be an int.
            'dive_rate_threshold': 0.4,
            'max_iterations_to_rerun': 800,
            'timeout_per_test_seconds': 120,
            'timeout_per_swarming_task_seconds': 3600,
            'swarming_task_cushion': 2.0,
            'swarming_task_retries_per_build': 2,
            'iterations_to_run_after_timeout': 10,
            'max_iterations_per_task': 200,
        }))
    self.assertFalse(
        config._ValidateFlakeAnalyzerSwarmingRerunSettings({
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98,
            'max_flake_in_a_row': 4,
            'max_stable_in_a_row': 4,
            'iterations_to_rerun': 100,
            'max_build_numbers_to_look_back': 1000,
            'create_monorail_bug': True,
            'new_flake_bugs_per_day': 2,
            'update_monorail_bug': True,
            'dive_rate_threshold': 40,  # Should be a float.
            'max_iterations_to_rerun': 800,
            'timeout_per_test_seconds': 120,
            'timeout_per_swarming_task_seconds': 3600,
            'swarming_task_cushion': 2.0,
            'swarming_task_retries_per_build': 2,
            'iterations_to_run_after_timeout': 10,
            'max_iterations_per_task': 200,
        }))
    self.assertFalse(
        config._ValidateFlakeAnalyzerSwarmingRerunSettings({
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98,
            'max_flake_in_a_row': 4,
            'max_stable_in_a_row': 4,
            'iterations_to_rerun': 100,
            'max_build_numbers_to_look_back': 1000,
            'use_nearby_neighbor': True,
            'create_monorail_bug': True,
            'new_flake_bugs_per_day': 2,
            'update_monorail_bug': True,
            'max_dive_in_a_row': 4,
            'dive_rate_threshold': 0.4,
            'max_iterations_to_rerun': 800.0,  # Should be an int.
            'timeout_per_test_seconds': 120,
            'timeout_per_swarming_task_seconds': 3600,
            'swarming_task_cushion': 2.0,
            'swarming_task_retries_per_build': 2,
            'iterations_to_run_after_timeout': 10,
            'max_iterations_per_task': 200,
        }))
    self.assertFalse(
        config._ValidateFlakeAnalyzerSwarmingRerunSettings({
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98,
            'max_flake_in_a_row': 4,
            'max_stable_in_a_row': 4,
            'iterations_to_rerun': 100,
            'max_build_numbers_to_look_back': 1000,
            'use_nearby_neighbor': True,
            'create_monorail_bug': True,
            'new_flake_bugs_per_day': 2,
            'update_monorail_bug': True,
            'max_dive_in_a_row': 4,
            'dive_rate_threshold': 0.4,
            'max_iterations_to_rerun': 800,
            'per_iteration_timeout_seconds': {},  # Should be an int.
            'timeout_per_test_seconds': 120,
            'timeout_per_swarming_task_seconds': 3600,
            'swarming_task_cushion': 2.0,
            'swarming_task_retries_per_build': 2,
            'iterations_to_run_after_timeout': 10,
            'max_iterations_per_task': 200,
        }))
    self.assertFalse(
        config._ValidateFlakeAnalyzerSwarmingRerunSettings({
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98,
            'max_flake_in_a_row': 4,
            'max_stable_in_a_row': 4,
            'iterations_to_rerun': 100,
            'max_build_numbers_to_look_back': 1000,
            'use_nearby_neighbor': True,
            'create_monorail_bug': True,
            'new_flake_bugs_per_day': 2,
            'update_monorail_bug': True,
            'max_dive_in_a_row': 4,
            'dive_rate_threshold': 0.4,
            'max_iterations_to_rerun': 800,
            'per_iteration_timeout_seconds': 'a',  # Should be an int.
            'timeout_per_test_seconds': 120,
            'timeout_per_swarming_task_seconds': 3600,
            'swarming_task_cushion': 2.0,
            'swarming_task_retries_per_build': 2,
            'iterations_to_run_after_timeout': 10,
            'max_iterations_per_task': 200,
        }))
    self.assertFalse(
        config._ValidateFlakeAnalyzerSwarmingRerunSettings({
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98,
            'max_flake_in_a_row': 4,
            'max_stable_in_a_row': 4,
            'iterations_to_rerun': 100,
            'max_build_numbers_to_look_back': 1000,
            'use_nearby_neighbor': True,
            'create_monorail_bug': True,
            'new_flake_bugs_per_day': 2,
            'update_monorail_bug': True,
            'max_dive_in_a_row': 4,
            'dive_rate_threshold': 0.4,
            'max_iterations_to_rerun': 800,
            'per_iteration_timeout_seconds': 60,
            'timeout_per_test_seconds': 120,
            'timeout_per_swarming_task_seconds': 360.0,  # Should be an int.
            'swarming_task_cushion': 2.0,
            'swarming_task_retries_per_build': 2,
            'iterations_to_run_after_timeout': 10,
            'max_iterations_per_task': 200,
        }))
    self.assertFalse(
        config._ValidateFlakeAnalyzerSwarmingRerunSettings({
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98,
            'max_flake_in_a_row': 4,
            'max_stable_in_a_row': 4,
            'iterations_to_rerun': 100,
            'max_build_numbers_to_look_back': 1000,
            'use_nearby_neighbor': True,
            'create_monorail_bug': True,
            'new_flake_bugs_per_day': 2,
            'update_monorail_bug': True,
            'max_dive_in_a_row': 4,
            'dive_rate_threshold': 0.4,
            'max_iterations_to_rerun': 800,
            'per_iteration_timeout_seconds': 60,
            'timeout_per_test_seconds': 120,
            'timeout_per_swarming_task_seconds': 3600,
            'swarming_task_cushion': {},  # Should be an int
            'swarming_task_retries_per_build': 2,
            'iterations_to_run_after_timeout': 10,
            'max_iterations_per_task': 200,
        }))
    self.assertFalse(
        config._ValidateFlakeAnalyzerSwarmingRerunSettings({
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98,
            'max_flake_in_a_row': 4,
            'max_stable_in_a_row': 4,
            'iterations_to_rerun': 100,
            'max_build_numbers_to_look_back': 1000,
            'use_nearby_neighbor': True,
            'create_monorail_bug': True,
            'new_flake_bugs_per_day': 2,
            'update_monorail_bug': True,
            'max_dive_in_a_row': 4,
            'dive_rate_threshold': 0.4,
            'max_iterations_to_rerun': 800,
            'per_iteration_timeout_seconds': 60,
            'timeout_per_test_seconds': 120,
            'timeout_per_swarming_task_seconds': 3600,
            'swarming_task_cushion': 2.0,
            'swarming_task_retries_per_build': {},  # Should be an int.
            'iterations_to_run_after_timeout': 10,
            'max_iterations_per_task': 200,
        }))
    self.assertFalse(
        config._ValidateFlakeAnalyzerSwarmingRerunSettings({
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98,
            'max_flake_in_a_row': 4,
            'max_stable_in_a_row': 4,
            'iterations_to_rerun': 100,
            'max_build_numbers_to_look_back': 1000,
            'use_nearby_neighbor': True,
            'create_monorail_bug': True,
            'new_flake_bugs_per_day': 2,
            'update_monorail_bug': True,
            'max_dive_in_a_row': 4,
            'dive_rate_threshold': 0.4,
            'max_iterations_to_rerun': 800,
            'per_iteration_timeout_seconds': 60,
            'timeout_per_test_seconds': 120,
            'timeout_per_swarming_task_seconds': 3600,
            'swarming_task_cushion': 2.0,
            'swarming_task_retries_per_build': 2,
            'iterations_to_run_after_timeout': {},  # Should be an int.
            'max_iterations_per_task': 200,
        }))
    self.assertFalse(
        config._ValidateFlakeAnalyzerSwarmingRerunSettings({
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98,
            'max_flake_in_a_row': 4,
            'max_stable_in_a_row': 4,
            'iterations_to_rerun': 100,
            'max_build_numbers_to_look_back': 1000,
            'use_nearby_neighbor': True,
            'create_monorail_bug': True,
            'new_flake_bugs_per_day': 2,
            'update_monorail_bug': True,
            'max_dive_in_a_row': 4,
            'dive_rate_threshold': 0.4,
            'max_iterations_to_rerun': 800,
            'per_iteration_timeout_seconds': 60,
            'timeout_per_test_seconds': 120,
            'timeout_per_swarming_task_seconds': 3600,
            'data_point_sample_size': 5,
            'swarming_task_retries_per_build': 2,
            'iterations_to_run_after_timeout': 10,
            'max_iterations_per_task': 2.00,  # Should be an int.
        }))
    self.assertTrue(
        config._ValidateFlakeAnalyzerSwarmingRerunSettings({
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98,
            'max_flake_in_a_row': 4,
            'max_stable_in_a_row': 4,
            'iterations_to_rerun': 100,
            'max_build_numbers_to_look_back': 1000,
            'use_nearby_neighbor': True,
            'create_monorail_bug': True,
            'new_flake_bugs_per_day': 2,
            'update_monorail_bug': True,
            'max_dive_in_a_row': 4,
            'dive_rate_threshold': 0.4,
            'max_iterations_to_rerun': 800,
            'per_iteration_timeout_seconds': 60,
            'timeout_per_test_seconds': 120,
            'timeout_per_swarming_task_seconds': 3600,
            'swarming_task_cushion': 2.0,
            'swarming_task_retries_per_build': 2,
            'iterations_to_run_after_timeout': 10,
            'max_iterations_per_task': 200,
        }))

  def testValidateCodeReviewSettings(self):
    self.assertTrue(
        config._ValidateCodeReviewSettings({
            'rietveld_hosts': ['abc.com'],
            'gerrit_hosts': ['def.com'],
            'commit_bot_emails': ['commit-bot@abc.com'],
        }))
    self.assertFalse(
        config._ValidateCodeReviewSettings({
            'rietveld_hosts': 'abc.com',
            'gerrit_hosts': 'def.com',
        }))
    self.assertFalse(
        config._ValidateCodeReviewSettings({
            'rietveld_hosts': 'abc.com',
            'gerrit_hosts': 'def.com',
            'commit_bot_emails': 'commit-bot@abc.com',
        }))
