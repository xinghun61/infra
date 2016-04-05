# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
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
            'buildername': 'trybot1',
        }
    }
}

_MOCK_TRY_JOB_SETTINGS = {
    'server_query_interval_seconds': 60,
    'job_timeout_hours': 5,
    'allowed_response_error_times': 1
}

_MOCK_SWARMING_SETTINGS = {
    'server_host': 'chromium-swarm.appspot.com',
    'default_request_priority': 150,
    'request_expiration_hours': 20,
    'server_query_interval_seconds': 60,
    'task_timeout_hours': 23,
    'isolated_server': 'https://isolateserver.appspot.com',
    'isolated_storage_url': 'isolateserver.storage.googleapis.com',
    'iterations_to_rerun': 10
}

_MOCK_VERSION_NUMBER = 12


class ConfigTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/config', config.Configuration),
  ], debug=True)

  def testGetConfigurationSettings(self):
    config_data = {
        'steps_for_masters_rules': _MOCK_STEPS_FOR_MASTERS_RULES,
        'builders_to_trybots': _MOCK_BUILDERS_TO_TRYBOTS,
        'try_job_settings': _MOCK_TRY_JOB_SETTINGS,
        'swarming_settings': _MOCK_SWARMING_SETTINGS
    }

    self.mock_current_user(user_email='test@chromium.org', is_admin=True)

    wf_config.FinditConfig.Get().Update(users.GetCurrentUser(), True,
                                        **config_data)

    response = self.test_app.get('/config', params={'format': 'json'})
    self.assertEquals(response.status_int, 200)

    expected_response = {
        'masters': _MOCK_STEPS_FOR_MASTERS_RULES,
        'builders': _MOCK_BUILDERS_TO_TRYBOTS,
        'try_job_settings': _MOCK_TRY_JOB_SETTINGS,
        'swarming_settings': _MOCK_SWARMING_SETTINGS,
        'version': 1,
        'latest_version': 1,
        'updated_by': 'test',
        'updated_ts': response.json_body.get('updated_ts')
    }

    self.assertEquals(expected_response, response.json_body)

  def testGetVersionOfConfigurationSettings(self):
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)

    config_data = {
        'steps_for_masters_rules': _MOCK_STEPS_FOR_MASTERS_RULES,
        'builders_to_trybots': _MOCK_BUILDERS_TO_TRYBOTS,
        'try_job_settings': _MOCK_TRY_JOB_SETTINGS,
        'swarming_settings': _MOCK_SWARMING_SETTINGS
    }
    wf_config.FinditConfig.Get().Update(users.GetCurrentUser(), True,
                                        **config_data)

    response = self.test_app.get(
        '/config', params={'version': 1, 'format': 'json'})
    self.assertEquals(response.status_int, 200)

    expected_response = {
        'masters': _MOCK_STEPS_FOR_MASTERS_RULES,
        'builders': _MOCK_BUILDERS_TO_TRYBOTS,
        'try_job_settings': _MOCK_TRY_JOB_SETTINGS,
        'swarming_settings': _MOCK_SWARMING_SETTINGS,
        'version': 1,
        'latest_version': 1,
        'updated_by': 'test',
        'updated_ts': response.json_body.get('updated_ts')
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
        self.test_app.get, '/config', params={'version': 0, 'format': 'json'})
    self.assertRaisesRegexp(
        webtest.app.AppError,
        re.compile('The requested version is invalid or not found.',
                   re.MULTILINE | re.DOTALL),
        self.test_app.get, '/config', params={'version': 2, 'format': 'json'})

  def testIsListOfType(self):
    self.assertFalse(config._IsListOfType({}, basestring))
    self.assertFalse(config._IsListOfType([], basestring))
    self.assertFalse(config._IsListOfType([1], basestring))
    self.assertFalse(config._IsListOfType(['a', 1], basestring))
    self.assertTrue(config._IsListOfType(['a', 'b'], basestring))

  def testValidateSupportedMastersDict(self):
    self.assertFalse(config._ValidateMastersAndStepsRulesMapping(
        _MOCK_STEPS_FOR_MASTERS_RULES_OLD_FORMAT))
    self.assertFalse(config._ValidateMastersAndStepsRulesMapping(None))
    self.assertFalse(config._ValidateMastersAndStepsRulesMapping([]))
    self.assertFalse(config._ValidateMastersAndStepsRulesMapping({}))
    self.assertFalse(config._ValidateMastersAndStepsRulesMapping({
        'supported_masters': [],  # Should be a dict.
        }))
    self.assertFalse(config._ValidateMastersAndStepsRulesMapping({
        'supported_masters': {},
        # 'global' is missing.
        }))
    self.assertFalse(config._ValidateMastersAndStepsRulesMapping({
        'supported_masters': {},
        'global': []  # Should be a dict.
    }))
    self.assertTrue(config._ValidateMastersAndStepsRulesMapping({
        'supported_masters': {},
        'global': {}
    }))
    self.assertFalse(config._ValidateMastersAndStepsRulesMapping({
        'supported_masters': {
            3: {},  # Key should be a string.
        },
        'global': {}
    }))
    self.assertFalse(config._ValidateMastersAndStepsRulesMapping({
        'supported_masters': {
            'master': [],  # Value should be a dict.
        },
        'global': {}
    }))
    self.assertFalse(config._ValidateMastersAndStepsRulesMapping({
        'supported_masters': {
            'master': {
                'check_global': 1  # Should be a bool.
            },
        },
        'global': {}
    }))
    self.assertTrue(config._ValidateMastersAndStepsRulesMapping({
        'supported_masters': {
            'master': {},
        },
        'global': {}
    }))
    self.assertFalse(config._ValidateMastersAndStepsRulesMapping({
        'supported_masters': {
            'master': {
                'supported_steps': {},  # Should be a list.
            }
        },
        'global': {}
    }))
    self.assertFalse(config._ValidateMastersAndStepsRulesMapping({
        'supported_masters': {
            'master': {
                'supported_steps': [],  # List should not be empty.
            }
        },
        'global': {}
    }))
    self.assertFalse(config._ValidateMastersAndStepsRulesMapping({
        'supported_masters': {
            'master': {
                'supported_steps': [1],  # List should be of strings.
            }
        },
        'global': {}
    }))
    self.assertTrue(config._ValidateMastersAndStepsRulesMapping({
        'supported_masters': {
            'master': {
                'supported_steps': ['step1'],
            }
        },
        'global': {}
    }))
    self.assertFalse(config._ValidateMastersAndStepsRulesMapping({
        'supported_masters': {
            'master': {
                'supported_steps': ['step1'],
                'unsupported_steps': 'blabla',  # Should be a list.
            }
        },
        'global': {}
    }))
    self.assertFalse(config._ValidateMastersAndStepsRulesMapping({
        'supported_masters': {
            'master': {
                'supported_steps': ['step1'],
                'unsupported_steps': [],  # List should not be empty.
            }
        },
        'global': {}
    }))
    self.assertFalse(config._ValidateMastersAndStepsRulesMapping({
        'supported_masters': {
            'master': {
                'supported_steps': ['step1'],
                'unsupported_steps': [{}],  # List should be of strings.
            }
        },
        'global': {}
    }))
    self.assertFalse(config._ValidateMastersAndStepsRulesMapping({
        'supported_masters': {
            'master': {
                'supported_steps': ['step1'],
                'unsupported_steps': ['step1'],  # Should not overlap.
            }
        },
        'global': {}
    }))
    self.assertTrue(config._ValidateMastersAndStepsRulesMapping({
        'supported_masters': {
            'master': {
                'supported_steps': ['step1'],
                'unsupported_steps': ['step2'],
            }
        },
        'global': {}
    }))
    self.assertFalse(config._ValidateMastersAndStepsRulesMapping({
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
    self.assertFalse(config._ValidateMastersAndStepsRulesMapping({
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
    self.assertFalse(config._ValidateMastersAndStepsRulesMapping({
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
    self.assertTrue(config._ValidateMastersAndStepsRulesMapping({
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
    self.assertTrue(config._ValidateMastersAndStepsRulesMapping({
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
    self.assertFalse(config._ValidateMastersAndStepsRulesMapping({
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
    self.assertEqual(
        {
            'supported_masters': {
                'master1': {
                    'supported_steps': ['step1', 'step1'],
                    'unsupported_steps': ['step2', 'step2'],
                },
            },
            'global': {
                'unsupported_steps': ['step3', 'step3']
            }
        },
        valid_rules_with_duplicates)

  def testValidateTrybotMapping(self):
    self.assertTrue(config._ValidateTrybotMapping({
        'master1': {
            'builder1': {
                'mastername': 'tryserver1',
                'buildername': 'trybot1',
            }
        }
    }))
    self.assertTrue(config._ValidateTrybotMapping({
        'master1': {
            'builder1': {
                'mastername': 'tryserver1',
                'buildername': 'trybot1',
                'strict_regex': True,
            }
        }
    }))
    self.assertFalse(config._ValidateTrybotMapping({
        'master1': {
            'builder1': {
                'mastername': 'tryserver1',
                'buildername': 'trybot1',
                'strict_regex': 'a',
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
    self.assertFalse(config._ValidateTryJobSettings({
        'server_query_interval_seconds': '1',  # Should be an int.
        'job_timeout_hours': 1,
        'allowed_response_error_times': 1
    }))
    self.assertFalse(config._ValidateTryJobSettings({
        'server_query_interval_seconds': 1,
        'job_timeout_hours': '1',  # Should be an int.
        'allowed_response_error_times': 1
    }))
    self.assertFalse(config._ValidateTryJobSettings({
        'server_query_interval_seconds': 1,
        'job_timeout_hours': 1,
        'allowed_response_error_times': '1',  # Should be an int.
    }))
    self.assertTrue(config._ValidateTryJobSettings({
        'server_query_interval_seconds': 1,
        'job_timeout_hours': 1,
        'allowed_response_error_times': 1
    }))
    self.assertTrue(config._ValidateSwarmingSettings(_MOCK_SWARMING_SETTINGS))

  def testValidateSwarmingSettings(self):
    self.assertFalse(config._ValidateSwarmingSettings([]))
    self.assertFalse(config._ValidateSwarmingSettings({}))
    self.assertFalse(config._ValidateSwarmingSettings({
        'server_host': ['chromium-swarm.appspot.com'],  # Should be a string.
        'default_request_priority': 150,
        'request_expiration_hours': 20,
        'server_query_interval_seconds': 60,
        'task_timeout_hours': 23,
        'isolated_server': 'https://isolateserver.appspot.com',
        'isolated_storage_url': 'isolateserver.storage.googleapis.com',
        'iterations_to_rerun': 10
    }))
    self.assertFalse(config._ValidateSwarmingSettings({
        'server_host': 'chromium-swarm.appspot.com',
        'default_request_priority': '150',  # Should be an int.
        'request_expiration_hours': 20,
        'server_query_interval_seconds': 60,
        'task_timeout_hours': 23,
        'isolated_server': 'https://isolateserver.appspot.com',
        'isolated_storage_url': 'isolateserver.storage.googleapis.com',
        'iterations_to_rerun': 10
    }))
    self.assertFalse(config._ValidateSwarmingSettings({
        'server_host': 'chromium-swarm.appspot.com',
        'default_request_priority': 150,
        'request_expiration_hours': {},  # Should be an int.
        'server_query_interval_seconds': 60,
        'task_timeout_hours': 23,
        'isolated_server': 'https://isolateserver.appspot.com',
        'isolated_storage_url': 'isolateserver.storage.googleapis.com',
        'iterations_to_rerun': 10
    }))
    self.assertFalse(config._ValidateSwarmingSettings({
        'server_host': 'chromium-swarm.appspot.com',
        'default_request_priority': 150,
        'request_expiration_hours': 20,
        'server_query_interval_seconds': [],  # Should be an int.
        'task_timeout_hours': 23,
        'isolated_server': 'https://isolateserver.appspot.com',
        'isolated_storage_url': 'isolateserver.storage.googleapis.com',
        'iterations_to_rerun': 10
    }))
    self.assertFalse(config._ValidateSwarmingSettings({
        'server_host': 'chromium-swarm.appspot.com',
        'default_request_priority': 150,
        'request_expiration_hours': 20,
        'server_query_interval_seconds': 60,
        'task_timeout_hours': None,  # should be an int.
        'isolated_server': 'https://isolateserver.appspot.com',
        'isolated_storage_url': 'isolateserver.storage.googleapis.com',
        'iterations_to_rerun': 10
    }))
    self.assertFalse(config._ValidateSwarmingSettings({
        'server_host': 'chromium-swarm.appspot.com',
        'default_request_priority': 150,
        'request_expiration_hours': 20,
        'server_query_interval_seconds': 60,
        'task_timeout_hours': 23,
        'isolated_server': 1,  # Should be a string.
        'isolated_storage_url': 'isolateserver.storage.googleapis.com',
        'iterations_to_rerun': 10
    }))
    self.assertFalse(config._ValidateSwarmingSettings({
        'server_host': 'chromium-swarm.appspot.com',
        'default_request_priority': 150,
        'request_expiration_hours': 20,
        'server_query_interval_seconds': 60,
        'task_timeout_hours': 23,
        'isolated_server': 'https://isolateserver.appspot.com',
        'isolated_storage_url': 3.2,  # Should be a string.
        'iterations_to_rerun': 10
    }))
    self.assertFalse(config._ValidateSwarmingSettings({
        'server_host': 'chromium-swarm.appspot.com',
        'default_request_priority': 150,
        'request_expiration_hours': 20,
        'server_query_interval_seconds': 60,
        'task_timeout_hours': 23,
        'isolated_server': 'https://isolateserver.appspot.com',
        'isolated_storage_url': 'isolateserver.storage.googleapis.com',
        'iterations_to_rerun': 1.0  # Should be an int.
    }))
    self.assertTrue(config._ValidateSwarmingSettings({
        'server_host': 'chromium-swarm.appspot.com',
        'default_request_priority': 150,
        'request_expiration_hours': 20,
        'server_query_interval_seconds': 60,
        'task_timeout_hours': 23,
        'isolated_server': 'https://isolateserver.appspot.com',
        'isolated_storage_url': 'isolateserver.storage.googleapis.com',
        'iterations_to_rerun': 10
    }))

  def testConfigurationDictIsValid(self):
    self.assertTrue(config._ConfigurationDictIsValid({
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
    self.assertFalse(config._ConfigurationDictIsValid({
        'this_is_not_a_valid_property': []
    }))

  def testFormatTimestamp(self):
    self.assertIsNone(config._FormatTimestamp(None))
    self.assertEqual('2016-02-25 01:02:03',
                     config._FormatTimestamp(
                         datetime.datetime(2016, 2, 25, 1, 2, 3, 123456)))

  def testPostConfigurationSettings(self):
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)

    params = {
        'format': 'json',
        'data': json.dumps({
            'steps_for_masters_rules': {
                'supported_masters': {
                    'a': {
                    },
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
            'builders_to_trybots': _MOCK_BUILDERS_TO_TRYBOTS,
            'try_job_settings': _MOCK_TRY_JOB_SETTINGS,
            'swarming_settings': _MOCK_SWARMING_SETTINGS
        })
    }

    response = self.test_app.post('/config', params=params)

    expected_response = {
        'masters': {
            'supported_masters': {
                'a': {
                },
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
        'version': 1,
        'latest_version': 1,
        'updated_by': 'test',
        'updated_ts': response.json_body.get('updated_ts')
    }

    self.assertEquals(expected_response, response.json_body)
