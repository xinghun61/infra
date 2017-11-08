# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Handles requests to the findit config page."""

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
    return False

  # 'supported_masters' is mandatory and must be a dict.
  supported_masters = steps_for_masters_rules.get('supported_masters')
  if not isinstance(supported_masters, dict):
    return False

  for supported_master, rules in supported_masters.iteritems():
    # Masters must be strings, rules must be dicts.
    if (not isinstance(supported_master, basestring) or
        not isinstance(rules, dict)):
      return False

    # If 'check_global' is specified, it must be a bool.
    check_global = rules.get('check_global')
    if check_global is not None and not isinstance(check_global, bool):
      return False

    supported_steps = rules.get('supported_steps')
    if supported_steps is not None:
      if not _IsListOfType(supported_steps, basestring):
        return False

      supported_steps = _RemoveDuplicatesAndSort(supported_steps)

    unsupported_steps = rules.get('unsupported_steps')
    if unsupported_steps is not None:
      # If check global is False, disallow 'unsupported_steps'.
      if check_global is False:
        return False

      if not _IsListOfType(unsupported_steps, basestring):
        return False

      # 'supported_list' and 'unsupported_list' must not overlap.
      if (supported_steps and
          not set(supported_steps).isdisjoint(unsupported_steps)):
        return False

      unsupported_steps = _RemoveDuplicatesAndSort(unsupported_steps)

  # Check format of 'global'.
  global_rules = steps_for_masters_rules.get('global')
  if not isinstance(global_rules, dict):
    return False

  global_unsupported_steps = global_rules.get('unsupported_steps')
  if global_unsupported_steps is not None:
    if not _IsListOfType(global_unsupported_steps, basestring):
      return False
    global_unsupported_steps = _RemoveDuplicatesAndSort(
        global_unsupported_steps)

  return True


def _ValidateTrybotMapping(builders_to_trybots):

  def xor(a, b):
    return bool(a) != bool(b)

  if not isinstance(builders_to_trybots, dict):
    return False
  for builders in builders_to_trybots.values():
    if not isinstance(builders, dict):
      return False
    for trybot_config in builders.values():
      if not isinstance(trybot_config, dict):
        return False
      if xor(
          trybot_config.get('swarmbucket_mastername'),
          trybot_config.get('swarmbucket_trybot')):
        return False
      if (not isinstance(
          trybot_config.get('swarmbucket_mastername', ''), basestring) or
          not isinstance(
              trybot_config.get('swarmbucket_trybot', ''), basestring)):
        return False
      if not trybot_config.get('swarmbucket_mastername'):
        # Validate buildbucket style config. (Not swarmbucket).
        if (not trybot_config.get('mastername') or
            not trybot_config.get('waterfall_trybot') or
            not isinstance(trybot_config['waterfall_trybot'], basestring)):
          return False
      if (trybot_config.get('flake_trybot') is not None and
          not isinstance(trybot_config['flake_trybot'], basestring)):
        # Specifying a flake_trybot is optional in case flake analysis is not
        # supported, i.e. in case not_run_tests is True. If it is set, it must
        # be a string.
        return False
      if (trybot_config.has_key('strict_regex') and
          not isinstance(trybot_config['strict_regex'], bool)):
        return False
      if (trybot_config.has_key('not_run_tests') and
          not isinstance(trybot_config['not_run_tests'], bool)):
        return False
  return True


def _ValidateTryJobSettings(settings):
  return (isinstance(settings, dict) and
          isinstance(settings.get('server_query_interval_seconds'), int) and
          isinstance(settings.get('job_timeout_hours'), int) and
          isinstance(settings.get('allowed_response_error_times'), int) and
          isinstance(settings.get('pubsub_token'), basestring) and
          isinstance(settings.get('pubsub_topic'), basestring) and
          isinstance(settings.get('pubsub_swarming_topic'), basestring) and
          isinstance(settings.get('max_seconds_look_back_for_group'), int))


def _ValidateSwarmingSettings(settings):
  return (isinstance(settings, dict) and
          isinstance(settings.get('server_host'), basestring) and
          isinstance(settings.get('default_request_priority'), int) and
          isinstance(settings.get('request_expiration_hours'), int) and
          isinstance(settings.get('server_query_interval_seconds'), int) and
          isinstance(settings.get('task_timeout_hours'), int) and
          isinstance(settings.get('isolated_server'), basestring) and
          isinstance(settings.get('isolated_storage_url'), basestring) and
          isinstance(settings.get('iterations_to_rerun'), int) and isinstance(
              settings.get('get_swarming_task_id_timeout_seconds'), int) and
          isinstance(settings.get('get_swarming_task_id_wait_seconds'), int) and
          isinstance(settings.get('server_retry_timeout_hours'), int) and
          isinstance(
              settings.get('maximum_server_contact_retry_interval_seconds'),
              int) and isinstance(settings.get('should_retry_server'), bool) and
          isinstance(settings.get('minimum_number_of_available_bots'), int) and
          isinstance(
              settings.get('minimum_percentage_of_available_bots'),
              (float, int)) and
          isinstance(settings.get('per_iteration_timeout_seconds'), int))


def _ValidateDownloadBuildDataSettings(settings):
  return (isinstance(settings, dict) and isinstance(
      settings.get('download_interval_seconds'), int) and isinstance(
          settings.get('memcache_master_download_expiration_seconds'), int) and
          isinstance(settings.get('use_ninja_output_log'), bool))


def _ValidateActionSettings(settings):
  return (
      isinstance(settings, dict) and
      isinstance(settings.get('cr_notification_build_threshold'), int) and
      isinstance(settings.get('cr_notification_latency_limit_minutes'), int) and
      isinstance(settings.get('auto_create_revert_compile'), bool) and
      isinstance(settings.get('auto_commit_revert_compile'), bool) and
      isinstance(settings.get('culprit_commit_limit_hours'), int) and
      isinstance(settings.get('auto_commit_daily_threshold'), int) and
      isinstance(settings.get('auto_revert_daily_threshold'), int) and
      isinstance(
          settings.get('cr_notification_should_notify_flake_culprit'), bool))


def _ValidateFlakeAnalyzerSwarmingRerunSettings(settings):
  return (isinstance(settings, dict) and
          isinstance(settings.get('lower_flake_threshold'), (float, int)) and
          isinstance(settings.get('upper_flake_threshold'), (float, int)) and
          isinstance(settings.get('max_flake_in_a_row'), int) and
          isinstance(settings.get('max_stable_in_a_row'), int) and
          isinstance(settings.get('iterations_to_rerun'), int) and
          isinstance(settings.get('max_build_numbers_to_look_back'), int) and
          isinstance(settings.get('use_nearby_neighbor'), bool) and
          isinstance(settings.get('max_dive_in_a_row'), int) and
          isinstance(settings.get('dive_rate_threshold'), (float, int)) and
          isinstance(settings.get('max_iterations_to_rerun'), int) and
          isinstance(settings.get('per_iteration_timeout_seconds'), int) and
          isinstance(settings.get('timeout_per_test_seconds'), int) and
          isinstance(settings.get('timeout_per_swarming_task_seconds'), int) and
          isinstance(settings.get('swarming_task_cushion'), (float, int)) and
          isinstance(settings.get('swarming_task_retries_per_build'), int) and
          isinstance(settings.get('iterations_to_run_after_timeout'), int) and
          isinstance(settings.get('max_iterations_per_task'), int))


def _ValidateFlakeAnalyzerTryJobRerunSettings(settings):
  return (isinstance(settings, dict) and
          isinstance(settings.get('lower_flake_threshold'), (float, int)) and
          isinstance(settings.get('upper_flake_threshold'), (float, int)) and
          isinstance(settings.get('max_flake_in_a_row'), int) and
          isinstance(settings.get('max_stable_in_a_row'), int) and
          isinstance(settings.get('iterations_to_rerun'), int))


def _ValidateCheckFlakeSettings(settings):
  return (
      isinstance(settings, dict) and
      _ValidateFlakeAnalyzerSwarmingRerunSettings(
          settings.get('swarming_rerun')) and
      _ValidateFlakeAnalyzerTryJobRerunSettings(settings.get('try_job_rerun'))
      and isinstance(
          settings.get('minimum_confidence_score_to_run_tryjobs'),
          (float, int)) and
      isinstance(settings.get('create_monorail_bug'), bool) and
      isinstance(settings.get('new_flake_bugs_per_day'), int) and
      isinstance(settings.get('update_monorail_bug'), bool) and
      isinstance(settings.get('minimum_confidence_to_update_cr'), (float, int)))


def _ValidateCodeReviewSettings(settings):
  return (isinstance(settings, dict) and
          isinstance(settings.get('commit_bot_emails'), list) and
          isinstance(settings.get('rietveld_hosts'), list) and
          isinstance(settings.get('gerrit_hosts'), list))


# Maps config properties to their validation functions.
_CONFIG_VALIDATION_FUNCTIONS = {
    'steps_for_masters_rules': _ValidateMastersAndStepsRulesMapping,
    'builders_to_trybots': _ValidateTrybotMapping,
    'try_job_settings': _ValidateTryJobSettings,
    'swarming_settings': _ValidateSwarmingSettings,
    'download_build_data_settings': _ValidateDownloadBuildDataSettings,
    'action_settings': _ValidateActionSettings,
    'check_flake_settings': _ValidateCheckFlakeSettings,
    'code_review_settings': _ValidateCodeReviewSettings,
}


def _ConfigurationDictIsValid(configuration_dict):
  """Checks that each configuration setting is properly formatted.

  Args:
      configuration_dict: A dictionary expected to map configuration properties
      by name to their intended settings. For example,

      configuration_dict = {
          'some_config_property': (some dictionary),
          'some_other_config_property': (some list),
          'another_config_property': (some value),
          ...
      }

  Returns:
      True if all configuration properties are properly formatted, False
      otherwise.
  """
  if not isinstance(configuration_dict, dict):
    return False

  for configurable_property, configuration in configuration_dict.iteritems():
    validation_function = _CONFIG_VALIDATION_FUNCTIONS.get(
        configurable_property)
    if validation_function is None or not validation_function(configuration):
      return False

  return True


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

    if not _ConfigurationDictIsValid(new_config_dict):  # pragma: no cover
      return self.CreateError(
          'New configuration settings is not properly formatted.', 400)

    wf_config.FinditConfig.Get().Update(
        users.get_current_user(),
        users.IsCurrentUserAdmin(),
        message=message,
        **new_config_dict)

    return self.HandleGet()
