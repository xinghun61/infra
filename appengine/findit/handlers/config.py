# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Handles requests to the findit config page."""

import logging
import json

from gae_libs import token
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from model import wf_config
from waterfall import waterfall_config

from google.appengine.api import users


def _RemoveDuplicatesAndSort(elements):
  return list(set(elements))


def _IsListOfType(elements, element_type):
  """Determines whether or not elements is a list of unique elements of type."""
  if not elements or not isinstance(elements, list):
    return False

  return all(isinstance(s, element_type) for s in elements)


def _ValidateMastersAndStepsRulesMapping(steps_for_masters_rules):
  """Checks that a masters configuration dict is properly formatted.

  Args:
    steps_for_masters_rules: A dictionary containing supported masters and
    global settings. For example:
    {
        'supported_masters': {
            master1: {
                'supported_steps': [steps],
                'unsupported_steps': [steps],
                'check_global': True or False.
            }
        },
        'global': {
            'unsupported_steps': [steps]
        }
    }

  Returns:
    True if steps_for_masters_rules is in the proper format, False
    otherwise.

  Rules:
    1.  The root-level dict must have both 'supported_masters' and 'global' as
        keys whose values are dicts.
    2.  'supported_masters' must have masters as string keys whose values are
        dicts.
    3.  'global' is a dict for settings that apply to all masters unless
        otherwise specified by the master.
    4.  'supported_steps' is an optional key whose value is a list of supported
        steps that override anything specified under 'global'.
    5.  'unsupported_steps' is an optional key whose value is a list of
        unsupported steps.
    6.  'check_global' is an optional key whose value is either True or False,
        True by default.
    7.  'check_global' = False disallows both 'supported_steps' and
        'unsupported_steps' to exist under the same master.
    8.  Steps in 'supported_steps' and 'unsupported_steps' under the same master
        may never overlap.
    9.  Lists will be sorted and duplicates removed at runtime.
    10. Lists should never be empty.
  """
  if not isinstance(steps_for_masters_rules, dict):
    return ['Expected steps_for_masters_rules to be dict']

  # 'supported_masters' is mandatory and must be a dict.
  supported_masters = steps_for_masters_rules.get('supported_masters')
  if not isinstance(supported_masters, dict):
    return ['Expected supported_masters to be dict']

  for supported_master, rules in supported_masters.iteritems():
    if (not isinstance(supported_master, basestring) or
        not isinstance(rules, dict)):
      return ['Supported_masters must map strings to dicts']

    check_global = rules.get('check_global')
    if check_global is not None and not isinstance(check_global, bool):
      return [
          'For %s, if "check_global" is specified, it must be a bool.' %
          supported_master
      ]

    supported_steps = rules.get('supported_steps')
    if supported_steps is not None:
      if not _IsListOfType(supported_steps, basestring):
        return [
            'For %s, if "supported_steps" is specified, '
            'it must be a list of str.' % supported_master
        ]

      supported_steps = _RemoveDuplicatesAndSort(supported_steps)

    unsupported_steps = rules.get('unsupported_steps')
    if unsupported_steps is not None:
      if check_global is False:
        return [
            'For %s, if "check_global" is False, '
            '"unsupported_steps" is not allowed.' % supported_master
        ]

      if not _IsListOfType(unsupported_steps, basestring):
        return [
            'For %s, if "unsupported_steps" is specified, '
            'it must be a list of str.' % supported_master
        ]

      if (supported_steps and
          not set(supported_steps).isdisjoint(unsupported_steps)):
        return [
            'For %s, "supported_list" and "unsupported_list" '
            'must not overlap.' % supported_master
        ]

      unsupported_steps = _RemoveDuplicatesAndSort(unsupported_steps)

  # Check format of 'global'.
  global_rules = steps_for_masters_rules.get('global')
  if not isinstance(global_rules, dict):
    return ['"global" must be provided and be a dict']

  global_unsupported_steps = global_rules.get('unsupported_steps')
  if global_unsupported_steps is not None:
    if not _IsListOfType(global_unsupported_steps, basestring):
      return [
          'If "global/unsupported_steps" is specified, '
          'it must be a list of str.'
      ]
    global_unsupported_steps = _RemoveDuplicatesAndSort(
        global_unsupported_steps)

  return []


def _ValidateTrybotMapping(builders_to_trybots):

  def xor(a, b):
    return bool(a) != bool(b)

  if not isinstance(builders_to_trybots, dict):
    return ['builders_to_trybots must be provided and be a dict.']
  for master, builders in builders_to_trybots.iteritems():
    if not isinstance(builders, dict):
      return [master + ': the trybot mapping must be a dict']
    for builder, trybot_config in builders.iteritems():
      builder = '%s/%s' % (master, builder)
      if not isinstance(trybot_config, dict):
        return ['The trybot_config for %s must be a dict' % builder]
      if xor(
          trybot_config.get('swarmbucket_mastername'),
          trybot_config.get('swarmbucket_trybot')):
        return [
            'For %s, both swarmbucket_mastername and swarmbucket_trybot'
            ' (or neither) must be specified' % builder
        ]
      if (not isinstance(
          trybot_config.get('swarmbucket_mastername', ''), basestring) or
          not isinstance(
              trybot_config.get('swarmbucket_trybot', ''), basestring)):
        return [
            'For %s, both swarmbucket_mastername and swarmbucket_trybot '
            'must be strings (if provided)' % builder
        ]
      if (not trybot_config.get('swarmbucket_mastername') and
          not trybot_config.get('use_swarmbucket')):
        # Validate buildbucket style config. (Not swarmbucket).
        if (not trybot_config.get('mastername') or
            not trybot_config.get('waterfall_trybot') or
            not isinstance(trybot_config['waterfall_trybot'], basestring)):
          return [
              'For %s, both mastername and waterfall_trybot must be strings' %
              builder
          ]
      if (trybot_config.get('flake_trybot') is not None and
          not isinstance(trybot_config['flake_trybot'], basestring)):
        # Specifying a flake_trybot is optional in case flake analysis is not
        # supported, i.e. in case not_run_tests is True. If it is set, it must
        # be a string.
        return [
            'For %s, if flake_trybot is specified, it must be a string' %
            builder
        ]
      if (trybot_config.has_key('strict_regex') and
          not isinstance(trybot_config['strict_regex'], bool)):
        return [
            'For %s, if strict_regex is specified, it must be a boolean' %
            builder
        ]
      if (trybot_config.has_key('use_swarmbucket') and
          not isinstance(trybot_config['use_swarmbucket'], bool)):
        return [
            'For %s, if use_swarmbucket is specified, it must be a boolean' %
            builder
        ]
      if (trybot_config.has_key('not_run_tests') and
          not isinstance(trybot_config['not_run_tests'], bool)):
        return [
            'For %s, if not_run_tests is specified, it must be a boolean' %
            builder
        ]
  return []


def _ValidateConfig(name, d, spec):
  """Validate that a given config matches the specification.

  Configs are dicts, and specs are dicts in the following format:
  {
    # Either format is okay. required is a boolean, defaults to True if not
    # given.
    'key_name': type,
    'key_name': (type, required),
    'key_name': (type, required, validator_or_nested_spec),
   }

  This function iterates over every key in the spec and
    - makes sure that the key is present in the given config(d) if required is
      true,
    - makes sure that the value is the type(s) given in the spec, note that it
      is okay to pass a tuple of types if the spec itself is a tuple
        e.g.((int, float), True)
    - makes sure that the value passes a custom validation if custom validation,
      if a validator function is provided, or if a nested spec is provided, it
      recursively calls _ValidateConfig on the value of the key (such as a
      nested dict)

  This function returns a list of errors (strings). It is expected that any
  custom validation functions will return a list of errors.

  A return value of [], indicates that there are no errors."""

  errors = []

  if not isinstance(d, dict):
    err = 'Expect %s to be a dictionary in config %s' % (d, name)
    logging.error(err)
    return [err]

  for key in spec:
    requirements = spec[key]

    # Sane defaults.
    required_type = int
    required_key = True
    custom_validator = None

    if isinstance(requirements, tuple):
      tuple_length = len(requirements)
      if tuple_length == 1:
        required_type = requirements[0]
      elif tuple_length == 2:
        required_type, required_key = requirements
      else:
        assert tuple_length == 3, 'The config tuple length must be < 3'
        required_type, required_key, custom_validator = requirements
    else:
      required_type = requirements

    if required_type == float:
      required_type = (int, float)
    elif required_type == str:
      required_type = basestring

    # Actual validation.

    # Validate key presence.
    if required_key and not key in d:
      err = 'Required key %s not present in config %s' % (key, name)
      logging.error(err)
      errors.append(err)
    # Validate type.
    elif key in d and not isinstance(d[key], required_type):
      err = 'Expected key %s, value %r to be %s in config % s' % (
          key, d[key], required_type, name)
      logging.error(err)
      errors.append(err)
    # Custom validator is a spec.
    elif (key in d and isinstance(custom_validator, dict)):
      errors += _ValidateConfig('%s/%s' % (name, key), d[key], custom_validator)
    # Custom validator is a function.
    elif key in d and callable(custom_validator):
      inner_errors = custom_validator(d[key])
      errors += inner_errors
      err = 'Key %s, value %r in config %s failed: %s' % (key, d[key], name,
                                                          inner_errors)
      logging.error(err)

  return errors


# Maps config properties to their validation specs.
# Please keep this config sorted by key name.
#
# Configs are dicts, and specs are dicts in the following format:
# {
#   'key_name': type,   # This implies required = True, and no custom validator.
#   'key_name': (type, required),
#   'key_name': (type, required, validator_or_nested_spec),
#  }
_CONFIG_SPEC = {  # yapf: disable
    'action_settings': (dict, True, {
        'auto_commit_revert_daily_threshold_compile': int,
        'auto_commit_revert_compile': bool,
        'auto_create_revert_compile': bool,
        'auto_create_revert_daily_threshold_compile': int,
        'auto_commit_revert_daily_threshold_test': int,
        'auto_create_revert_daily_threshold_flake': int,
        'auto_commit_revert_daily_threshold_flake': int,
        'auto_commit_revert_test': bool,
        'auto_create_revert_test': bool,
        'auto_create_revert_daily_threshold_test': int,
        'cr_notification_build_threshold': int,
        'cr_notification_latency_limit_minutes': int,
        'cr_notification_should_notify_flake_culprit': bool,
        'culprit_commit_limit_hours': int,
        'rotations_url': str,
        'max_flake_bug_updates_per_day': int,
    }),
    'builders_to_trybots': (dict, True, _ValidateTrybotMapping),
    'check_flake_settings': (dict, True, {
        'iterations_to_run_after_timeout': int,
        'lower_flake_threshold': float,
        'max_commit_positions_to_look_back': int,
        'max_iterations_per_task': int,
        'max_iterations_to_rerun': int,
        'minimum_confidence_to_create_bug': float,
        'minimum_confidence_to_update_cr': float,
        'per_iteration_timeout_seconds': int,
        'swarming_task_cushion': float,
        'swarming_task_retries_per_build': int,
        'throttle_flake_analyses': bool,
        'timeout_per_swarming_task_seconds': int,
        'timeout_per_test_seconds': int,
        'upper_flake_threshold': float,
    }),
    'flake_detection_settings': (dict, True, {
        'report_flakes_to_flake_analyzer': bool,
        'min_required_impacted_cls_per_day': int,
    }),
    'code_review_settings': (dict, True, {
        'commit_bot_emails': list,
        'gerrit_hosts': list,
        'rietveld_hosts': list,
    }),
    'download_build_data_settings': (dict, True, {
        'download_interval_seconds': int,
        'memcache_master_download_expiration_seconds': int,
        'use_ninja_output_log': bool,
    }),
    'steps_for_masters_rules': (dict, True,
                                _ValidateMastersAndStepsRulesMapping),
    'swarming_settings': (dict, True, {
        'default_request_priority': int,
        'get_swarming_task_id_timeout_seconds': int,
        'get_swarming_task_id_wait_seconds': int,
        'isolated_server': str,
        'isolated_storage_url': str,
        'iterations_to_rerun': int,
        'maximum_server_contact_retry_interval_seconds': int,
        'minimum_number_of_available_bots': int,
        'minimum_percentage_of_available_bots': float,
        'per_iteration_timeout_seconds': int,
        'request_expiration_hours': int,
        'server_host': str,
        'server_query_interval_seconds': int,
        'server_retry_timeout_hours': int,
        'should_retry_server': bool,
        'task_timeout_hours': int,
    }),
    'try_job_settings': (dict, True, {
        'allowed_response_error_times': int,
        'job_timeout_hours': int,
        'max_seconds_look_back_for_group': int,
        'pubsub_swarming_topic': str,
        'pubsub_token': str,
        'pubsub_topic': str,
        'server_query_interval_seconds': int,
    }),
}


def _FormatTimestamp(timestamp):
  if not timestamp:
    return None
  return timestamp.strftime('%Y-%m-%d %H:%M:%S')


class Configuration(BaseHandler):
  PERMISSION_LEVEL = Permission.ADMIN

  @token.AddXSRFToken(action_id='config')
  def HandleGet(self):
    version = self.request.params.get('version')

    if version is not None:
      version = int(version)

    settings = wf_config.FinditConfig.Get(version)

    if not settings:
      return self.CreateError('The requested version is invalid or not found.',
                              400)

    latest_version = settings.GetLatestVersionNumber()

    data = {
        'masters': waterfall_config.GetStepsForMastersRules(settings),
        'builders': settings.builders_to_trybots,
        'try_job_settings': settings.try_job_settings,
        'swarming_settings': settings.swarming_settings,
        'download_build_data_settings': settings.download_build_data_settings,
        'action_settings': settings.action_settings,
        'check_flake_settings': settings.check_flake_settings,
        'flake_detection_settings': settings.flake_detection_settings,
        'code_review_settings': settings.code_review_settings,
        'version': settings.version_number,
        'latest_version': latest_version,
        'updated_by': settings.updated_by,
        'updated_ts': _FormatTimestamp(settings.updated_ts),
        'message': settings.message,
    }

    return {'template': 'config.html', 'data': data}

  @token.VerifyXSRFToken(action_id='config')
  def HandlePost(self):
    new_config_dict = {}
    for name in self.request.params.keys():
      if name not in ('format', 'xsrf_token', 'message'):
        new_config_dict[name] = json.loads(self.request.params[name])

    message = self.request.get('message')
    if not message:  # pragma: no cover
      return self.CreateError('Please provide the reason to update the config',
                              400)

    errors = _ValidateConfig('', new_config_dict, _CONFIG_SPEC)
    if errors:
      return self.CreateError(
          'New configuration settings is not properly formatted.\n'
          'The following errors were detected \n %s' % '\n'.join(errors), 400)

    wf_config.FinditConfig.Get().Update(
        users.get_current_user(),
        users.IsCurrentUserAdmin(),
        message=message,
        **new_config_dict)

    return self.HandleGet()
