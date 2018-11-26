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

_MOCK_CHECK_FLAKE_SETTINGS = {
    'iterations_to_run_after_timeout': 10,
    'lower_flake_threshold': 1e-7,
    'upper_flake_threshold': 0.9999999,
    'max_commit_positions_to_look_back': 5000,
    'max_iterations_per_task': 200,
    'max_iterations_to_rerun': 400,
    'minimum_confidence_to_create_bug': .9,
    'minimum_confidence_to_update_cr': 0.5,
    'per_iteration_timeout_seconds': 60,
    'swarming_task_cushion': 2.0,
    'swarming_task_retries_per_build': 2,
    'throttle_flake_analyses': True,
    'timeout_per_test_seconds': 120,
    'timeout_per_swarming_task_seconds': 3600,
}

_MOCK_FLAKE_DETECTION_SETTINGS = {
    'report_flakes_to_flake_analyzer': True,
    'min_required_impacted_cls_per_day': 3,
}

_MOCK_CODE_REVIEW_SETTINGS = {
    'rietveld_hosts': ['rietveld.org'],
    'gerrit_hosts': ['gerrit.org'],
    'commit_bot_emails': ['commit-bot@gerrit.org'],
}

_MOCK_VERSION_NUMBER = 12


class ConfigTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/config', config.Configuration),
  ],
                                       debug=True)

  def testGetConfigurationSettings(self):
    config_data = {
        'steps_for_masters_rules': _MOCK_STEPS_FOR_MASTERS_RULES,
        'builders_to_trybots': _MOCK_BUILDERS_TO_TRYBOTS,
        'try_job_settings': _MOCK_TRY_JOB_SETTINGS,
        'swarming_settings': _MOCK_SWARMING_SETTINGS,
        'download_build_data_settings': _MOCK_DOWNLOAD_BUILD_DATA_SETTINGS,
        'action_settings': _MOCK_ACTION_SETTINGS,
        'check_flake_settings': _MOCK_CHECK_FLAKE_SETTINGS,
        'flake_detection_settings': _MOCK_FLAKE_DETECTION_SETTINGS,
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
        'flake_detection_settings': _MOCK_FLAKE_DETECTION_SETTINGS,
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
        'flake_detection_settings': _MOCK_FLAKE_DETECTION_SETTINGS,
        'code_review_settings': _MOCK_CODE_REVIEW_SETTINGS,
    }
    wf_config.FinditConfig.Get().Update(
        users.GetCurrentUser(), True, message='message', **config_data)

    response = self.test_app.get(
        '/config', params={
            'version': 1,
            'format': 'json'
        })
    self.assertEquals(response.status_int, 200)

    expected_response = {
        'masters': _MOCK_STEPS_FOR_MASTERS_RULES,
        'builders': _MOCK_BUILDERS_TO_TRYBOTS,
        'try_job_settings': _MOCK_TRY_JOB_SETTINGS,
        'swarming_settings': _MOCK_SWARMING_SETTINGS,
        'download_build_data_settings': _MOCK_DOWNLOAD_BUILD_DATA_SETTINGS,
        'action_settings': _MOCK_ACTION_SETTINGS,
        'check_flake_settings': _MOCK_CHECK_FLAKE_SETTINGS,
        'flake_detection_settings': _MOCK_FLAKE_DETECTION_SETTINGS,
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
        params={
            'version': 0,
            'format': 'json'
        })
    self.assertRaisesRegexp(
        webtest.app.AppError,
        re.compile('The requested version is invalid or not found.',
                   re.MULTILINE | re.DOTALL),
        self.test_app.get,
        '/config',
        params={
            'version': 2,
            'format': 'json'
        })

  def testIsListOfType(self):
    self.assertFalse(config._IsListOfType({}, basestring))
    self.assertFalse(config._IsListOfType([], basestring))
    self.assertFalse(config._IsListOfType([1], basestring))
    self.assertFalse(config._IsListOfType(['a', 1], basestring))
    self.assertTrue(config._IsListOfType(['a', 'b'], basestring))

  def testValidateSupportedMastersDict(self):
    self.assertTrue(
        config._ValidateMastersAndStepsRulesMapping(
            _MOCK_STEPS_FOR_MASTERS_RULES_OLD_FORMAT))
    self.assertTrue(config._ValidateMastersAndStepsRulesMapping(None))
    self.assertTrue(config._ValidateMastersAndStepsRulesMapping([]))
    self.assertTrue(config._ValidateMastersAndStepsRulesMapping({}))
    self.assertTrue(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': [],  # Should be a dict.
        }))
    self.assertTrue(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {},
            # 'global' is missing.
        }))
    self.assertTrue(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {},
            'global': []  # Should be a dict.
        }))
    self.assertFalse(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {},
            'global': {}
        }))
    self.assertTrue(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                3: {},  # Key should be a string.
            },
            'global': {}
        }))
    self.assertTrue(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master': [],  # Value should be a dict.
            },
            'global': {}
        }))
    self.assertTrue(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master': {
                    'check_global': 1  # Should be a bool.
                },
            },
            'global': {}
        }))
    self.assertFalse(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master': {},
            },
            'global': {}
        }))
    self.assertTrue(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master': {
                    'supported_steps': {},  # Should be a list.
                }
            },
            'global': {}
        }))
    self.assertTrue(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master': {
                    'supported_steps': [],  # List should not be empty.
                }
            },
            'global': {}
        }))
    self.assertTrue(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master': {
                    'supported_steps': [1],  # List should be of strings.
                }
            },
            'global': {}
        }))
    self.assertFalse(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master': {
                    'supported_steps': ['step1'],
                }
            },
            'global': {}
        }))
    self.assertTrue(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master': {
                    'supported_steps': ['step1'],
                    'unsupported_steps': 'blabla',  # Should be a list.
                }
            },
            'global': {}
        }))
    self.assertTrue(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master': {
                    'supported_steps': ['step1'],
                    'unsupported_steps': [],  # List should not be empty.
                }
            },
            'global': {}
        }))
    self.assertTrue(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master': {
                    'supported_steps': ['step1'],
                    'unsupported_steps': [{}],  # List should be of strings.
                }
            },
            'global': {}
        }))
    self.assertTrue(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master': {
                    'supported_steps': ['step1'],
                    'unsupported_steps': ['step1'],  # Should not overlap.
                }
            },
            'global': {}
        }))
    self.assertFalse(
        config._ValidateMastersAndStepsRulesMapping({
            'supported_masters': {
                'master': {
                    'supported_steps': ['step1'],
                    'unsupported_steps': ['step2'],
                }
            },
            'global': {}
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
                'unsupported_steps': 1  # Should be a list.
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
                'unsupported_steps': []  # Should not be empty.
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
                'unsupported_steps': [1]  # Should be a list of strings.
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
                'unsupported_steps': ['step3']
            }
        }))
    self.assertFalse(
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
    self.assertTrue(
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
    self.assertFalse(
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
    self.assertFalse(
        config._ValidateTrybotMapping({
            'master1': {
                'builder1': {
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
                    'flake_trybot': 'trybot1_flake'
                }
            }
        }))
    self.assertFalse(
        config._ValidateTrybotMapping({
            'master1': {
                'builder1': {
                    'mastername': 'tryserver1',
                    'waterfall_trybot': 'trybot1',
                    'strict_regex': True,
                }
            }
        }))
    self.assertTrue(
        config._ValidateTrybotMapping({
            'master1': {
                'builder1': {
                    'mastername': 'tryserver1',
                    'waterfall_trybot': 'trybot1',
                    'strict_regex': 'a',
                }
            }
        }))
    self.assertFalse(
        config._ValidateTrybotMapping({
            'master1': {
                'builder1': {
                    'mastername': 'tryserver1',
                    'waterfall_trybot': 'trybot1',
                    'not_run_tests': True,
                }
            }
        }))
    self.assertFalse(
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
                    'use_swarmbucket': True
                }
            }
        }))
    self.assertTrue(
        config._ValidateTrybotMapping({
            'master1': {
                'builder1': {
                    'use_swarmbucket': 'bad_value'
                }
            }
        }))
    self.assertTrue(
        config._ValidateTrybotMapping({
            'master1': {
                'builder1': {
                    'swarmbucket_mastername': 'tryserver1',
                    'waterfall_trybot': 'trybot1',
                }
            }
        }))
    self.assertTrue(
        config._ValidateTrybotMapping({
            'master1': {
                'builder1': {
                    'swarmbucket_mastername': 'tryserver1',
                    'swarmbucket_trybot': ['trybot1'],
                }
            }
        }))
    self.assertTrue(
        config._ValidateTrybotMapping({
            'master1': {
                'builder1': {
                    'swarmbucket_trybot': 'trybot2',
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
                    'not_run_tests': 1,  # Should be a bool.
                }
            }
        }))
    self.assertTrue(
        config._ValidateTrybotMapping({
            'master1': {
                'builder1': {
                    'mastername': 'tryserver1',
                    'waterfall_trybot': {},  # Should be a string.
                    'flake_trybot': 'trybot2',
                }
            }
        }))
    self.assertTrue(
        config._ValidateTrybotMapping({
            'master1': {
                'builder1': {
                    'mastername': 'tryserver1',
                    'waterfall_trybot': 'trybot1',
                    'flake_trybot': 1,  # Should be a string.
                }
            }
        }))
    self.assertTrue(config._ValidateTrybotMapping(['a']))
    self.assertTrue(config._ValidateTrybotMapping({'a': ['b']}))
    self.assertTrue(config._ValidateTrybotMapping({'a': {'b': ['1']}}))
    self.assertTrue(config._ValidateTrybotMapping({'a': {'b': {}}}))

  def testFormatTimestamp(self):
    self.assertIsNone(config._FormatTimestamp(None))
    self.assertEqual(
        '2016-02-25 01:02:03',
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
        'flake_detection_settings':
            json.dumps(_MOCK_FLAKE_DETECTION_SETTINGS),
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
        'flake_detection_settings': _MOCK_FLAKE_DETECTION_SETTINGS,
        'code_review_settings': _MOCK_CODE_REVIEW_SETTINGS,
        'version': 1,
        'latest_version': 1,
        'updated_by': 'test',
        'updated_ts': response.json_body.get('updated_ts'),
        'message': 'reason',
        'xsrf_token': response.json_body['xsrf_token'],
    }

    self.assertEquals(expected_response, response.json_body)

  @mock.patch('gae_libs.token.ValidateAuthToken')
  def testPostConfigurationSettingsFail(self, mocked_ValidateAuthToken):
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)
    mocked_ValidateAuthToken.side_effect = [(True, False)]

    self.assertRaisesRegexp(
        webtest.app.AppError,
        re.compile('not present in config', re.MULTILINE | re.DOTALL),
        self.test_app.post,
        '/config',
        params={
            'format': 'json',
            'message': 'forgot how to config',
        })

  def testValidateConfig(self):
    spec = {
        'required_int':
            int,
        'required_float': (float,),  # One item tuple must be supported.
        'optional_string': (str, False),
        'required_even_length_list': (list, True,
                                      lambda x: ['odd'] * (len(x) % 2)),
        'optional_nested_dict': (dict, False, {
            'inner_key': int
        })
    }
    good_config = {
        'required_int': 1,
        'required_float': 2.5,
        'optional_string': 'hello world',
        'required_even_length_list': [1, 2, 3, 4],
        'optional_nested_dict': {
            'inner_key': 5,
        }
    }
    good_config_2 = {
        'required_int': 1,
        'required_float': 2,  # int should satisfy float req.
        'optional_string': u'hello world',  # Unicode should satisfy str req.
        'required_even_length_list': [],
        'optional_nested_dict': {
            'inner_key': 5,
            'extra_key': 'whimsy',  # extra keys should not break the config.
        }
    }
    good_config_3 = {
        'required_int': 1,
        'required_float': 2.5,  # int should satisfy float req.
        'required_even_length_list': [],
        # optional should be optional.
    }
    bad_types = {
        'required_int': 1.5,
        'required_float': False,
        'optional_string': ['h', 'e', 'l', 'l', 'o'],
        'required_even_length_list': (1, 2, 3, 4),
        'optional_nested_dict': {
            'inner_key': 5.0,
        }
    }
    bad_custom_validation = {
        'required_int': 1,
        'required_float': 2.5,
        'optional_string': 'hello world',
        'required_even_length_list': [1, 2, 3],
        'optional_nested_dict': {
            'inner_missing': 5,
        }
    }
    self.assertEqual([], config._ValidateConfig('', good_config, spec))
    self.assertEqual([], config._ValidateConfig('', good_config_2, spec))
    self.assertEqual([], config._ValidateConfig('', good_config_3, spec))
    self.assertEqual([
        'Expected key inner_key, value 5.0 to be <type \'int\'> in config '
        '/optional_nested_dict',
        'Expected key optional_string, value [\'h\', \'e\', \'l\', \'l\', \'o\''
        '] to be <type \'basestring\'> in config ',
        'Expected key required_int, value 1.5 to be <type \'int\'> in config ',
        'Expected key required_even_length_list, value (1, 2, 3, 4) to be '
        '<type \'list\'> in config '
    ], config._ValidateConfig('', bad_types, spec))
    self.assertEqual([
        'Required key inner_key not present in config /optional_nested_dict',
        'odd'
    ], config._ValidateConfig('', bad_custom_validation, spec))
    self.assertNotEqual([], config._ValidateConfig('', 'not_a_dict', spec))
