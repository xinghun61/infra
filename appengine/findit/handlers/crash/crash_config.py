# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Handles requests to the crash config page."""

import json

from google.appengine.api import users

from gae_libs.handlers.base_handler import BaseHandler, Permission
from model.crash.crash_config import CrashConfig as CrashConfigModel

# TODO(katesonia): Have the validate function return error messages, and make
# the error page surface those messages.


def _SortConfig(config):
  """Sorts ``host_direcotries`` list in config dict.

  N.B This method can only be called after validation function, namely the
  config should be properly formatted.
  """
  project_config = config.get('project_classifier')
  for project_pattern in project_config['project_path_function_hosts']:
    # Validation assures that the host_directories in the 3rd index of
    # project_pattern.
    hosts = project_pattern[3]
    for index, host in enumerate(hosts or []):
      if not host.endswith('/'):
        hosts[index] = host + '/'

    if hosts:
      hosts.sort(key=lambda host: -len(host.split('/')))


def _IsListOfStrings(obj):
  """Determines whether an object is a list of strings."""
  return isinstance(obj, list) and all(isinstance(entry, basestring)
                                       for entry in obj)


def _ValidateChromeCrashConfig(chrome_crash_config):
  """Checks that a chrome_crash__config dict is properly formatted.

  Args:
    chrome_crash_config (dict): A dictionary that provides configuration of
      chrome crash clients - Cracas and Fracas.
  {
    'analysis_result_pubsub_topic': (
        'projects/google.com:findit-for-me/topics/result-for-cracas'),
    'platform_rename': {
      'linux': 'unix'
    },
    'signature_blacklist_markers': ['black sig1', 'black sig2'],
    'supported_platform_list_by_channel': {
      'canary': [
        'win',
        'mac',
        'android',
        'linux'
      ]
    },
    'top_n': 7
  }
  """
  if not isinstance(chrome_crash_config, dict):
    return False

  analysis_result_pubsub_topic = chrome_crash_config.get(
      'analysis_result_pubsub_topic')
  if not isinstance(analysis_result_pubsub_topic, basestring):
    return False

  platform_rename = chrome_crash_config.get('platform_rename')
  if not isinstance(platform_rename, dict):
    return False

  signature_blacklist_markers = chrome_crash_config.get(
      'signature_blacklist_markers')
  if not _IsListOfStrings(signature_blacklist_markers):
    return False

  supported_platform_list_by_channel = chrome_crash_config.get(
      'supported_platform_list_by_channel')
  if not isinstance(supported_platform_list_by_channel, dict):
    return False

  for channel, platform_list in supported_platform_list_by_channel.iteritems():
    if not isinstance(channel, basestring):
      return False
    if not _IsListOfStrings(platform_list):
      return False

  top_n = chrome_crash_config.get('top_n')
  if not isinstance(top_n, int):
    return False

  return True


def _ValidateComponentClassifierConfig(component_classifier_config):
  """Checks that a component_classifier_config dict is properly formatted.

  Args:
    commponent_classifier_config (dict): A dictionary that provides component to
      its function and path patterns, and some other settings.
      For example:
      {
          'path_function_component': [
              [
                  'src/chrome/common/extensions/api/gcm.json',
                  '',
                  'Services>CloudMessaging'
              ],
              ...
              [
                  'src/chrome/browser/accessibility',
                  '',
                  'UI>Accessibility'
              ],
           ],
          'top_n': 4
      }

  Returns:
    True if ``component_classifier_config`` is properly formatted, False
    otherwise.
  """
  if not isinstance(component_classifier_config, dict):
    return False

  path_function_component = component_classifier_config.get(
      'path_function_component')
  if not isinstance(path_function_component, list):
    return False

  if not all(_IsListOfStrings(component)
             for component in path_function_component):
    return False

  top_n = component_classifier_config.get('top_n')
  if not isinstance(top_n, int):
    return False

  return True


def _ValidateProjectClassifierConfig(project_classifier_config):
  """Checks that a project_classifier_config dict is properly formatted.

  Args:
    project_classifier_config (dict): A dictionary that provides mapping from
      project to its function patterns, path patterns and its host_directories,
      and some other settings.
      For example:
      {
          'project_path_function_hosts': [
              ['android_os', ['googleplex-android/'], ['android.'], None],
              ['chromium', None, ['org.chromium'],
               ['src/chrome/browser/resources/',
                'src/chrome/test/data/layout_tests/',
                'src/media/']]
          ],
          'non_chromium_project_rank_priority': {
              'android_os': '-1',
              'others': '-2',
          },
          'top_n': 4
      }

  Returns:
    True if ``project_classifier_config`` is properly formatted, False
    otherwise.
  """
  if not isinstance(project_classifier_config, dict):
    return False

  project_path_function_hosts = project_classifier_config.get(
      'project_path_function_hosts')
  if not isinstance(project_path_function_hosts, list):
    return False

  non_chromium_project_rank_priority = project_classifier_config.get(
      'non_chromium_project_rank_priority')
  if not isinstance(non_chromium_project_rank_priority, dict):
    return False

  top_n = project_classifier_config.get('top_n')
  if not isinstance(top_n, int):
    return False

  return True


_CONFIG_VALIDATION_FUNCTIONS = {
    'fracas': _ValidateChromeCrashConfig,
    'cracas': _ValidateChromeCrashConfig,
    'component_classifier': _ValidateComponentClassifierConfig,
    'project_classifier': _ValidateProjectClassifierConfig
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

  for configurable_property, validation_function in (
      _CONFIG_VALIDATION_FUNCTIONS.iteritems()):
    if configurable_property not in configuration_dict:
      return False

    configuration = configuration_dict[configurable_property]
    if not validation_function(configuration):
      return False

  return True


class CrashConfig(BaseHandler):
  PERMISSION_LEVEL = Permission.ADMIN

  def HandleGet(self):
    settings = CrashConfigModel.Get()

    data = {
        'fracas': settings.fracas,
        'cracas': settings.cracas,
        'component_classifier': settings.component_classifier,
        'project_classifier': settings.project_classifier,
    }

    return {'template': 'crash/crash_config.html', 'data': data}

  def HandlePost(self):
    data = self.request.params.get('data')
    new_config_dict = json.loads(data)
    if not _ConfigurationDictIsValid(new_config_dict):
      return self.CreateError(
          'New configuration settings are not properly formatted.', 400)

    # Sort config dict in place.
    _SortConfig(new_config_dict)

    crash_config = CrashConfigModel.Get()
    crash_config.ClearCache()
    crash_config.Update(
        users.get_current_user(), users.IsCurrentUserAdmin(), **new_config_dict)
    return self.HandleGet()
