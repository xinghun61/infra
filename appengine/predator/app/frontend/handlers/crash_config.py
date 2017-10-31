# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Handles requests to the crash config page."""

import json

from google.appengine.api import users

from common.model.crash_config import CrashConfig as CrashConfigModel
from gae_libs.handlers.base_handler import BaseHandler, Permission

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
      if host.endswith('/'):
        hosts[index] = host[:-1]

    if hosts:
      hosts.sort(key=lambda host: -len(host.split('/')))


def _IsListOfStrings(obj):
  """Determines whether an object is a list of strings."""
  return isinstance(obj, list) and all(isinstance(entry, basestring)
                                       for entry in obj)


# TODO(katesonia): Raise exceptions instead of return False if config
# validation failed.
def _ValidateChromeCrashConfig(chrome_crash_config):
  # TODO(cweakliam): update the pubsub topic once we migrate predator project id
  # from 'google.com: findit-for-me' to 'predator-for-me'
  """Checks that a chrome_crash_config dict is properly formatted.

  Args:
    chrome_crash_config (dict): A dictionary that provides configuration of
      chrome crash clients - Cracas and Fracas.
  {
    'analysis_result_pubsub_topic': (
        'projects/google.com:findit-for-me/topics/result-for-cracas'),
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


def _ValidateClusterfuzzConfig(clusterfuzz_config):
  """Checks that a clusterfuzz_config dict is properly formatted.

  Args:
    chrome_crash_config (dict): A dictionary that provides configuration of
      chrome crash clients - Cracas and Fracas.
      {
        'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
        'try_bot_topic': 'projects/project-name/topics/name',
        'signature_blacklist_markers': [],
        'blacklist_crash_type': ['out-of-memory'],
        'top_n': 7
      }
  """
  if not isinstance(clusterfuzz_config, dict):
    return False

  analysis_result_pubsub_topic = clusterfuzz_config.get(
      'analysis_result_pubsub_topic')
  if not isinstance(analysis_result_pubsub_topic, basestring):
    return False

  try_bot_topic = clusterfuzz_config.get('try_bot_topic')
  if not isinstance(try_bot_topic, basestring):
    return False

  try_bot_supported_platforms = clusterfuzz_config.get(
      'try_bot_supported_platforms')
  if not _IsListOfStrings(try_bot_supported_platforms):
    return False

  signature_blacklist_markers = clusterfuzz_config.get(
      'signature_blacklist_markers', [])
  if not _IsListOfStrings(signature_blacklist_markers):
    return False

  blacklist_crash_type = clusterfuzz_config.get('blacklist_crash_type')
  if not _IsListOfStrings(blacklist_crash_type):
    return False

  top_n = clusterfuzz_config.get('top_n')
  if not isinstance(top_n, int):
    return False

  return True


def _ValidateUMASamplingProfilerConfig(uma_profiler_config):
  """Checks that a uma_profiler_config dict is properly formatted.

  Args:
    uma_profiler_config (dict): A dictionary that provides configuration of
      the UMA Sampling Profiler client. E.g.:
      {
        'analysis_result_pubsub_topic': (
            'projects/google.com:findit-for-me/topics/'
            'result-for-uma-sampling-profiler'),
        'signature_blacklist_markers': ['black sig1', 'black sig2'],
      }
  Return:
    True if uma_profiler_config has the correct format, False if not.
  """
  if not isinstance(uma_profiler_config, dict):
    return False

  analysis_result_pubsub_topic = uma_profiler_config.get(
      'analysis_result_pubsub_topic')
  if not isinstance(analysis_result_pubsub_topic, basestring):
    return False

  signature_blacklist_markers = uma_profiler_config.get(
      'signature_blacklist_markers')
  if not _IsListOfStrings(signature_blacklist_markers):
    return False

  return True


def _ValidateComponentClassifierConfig(component_classifier_config):
  """Checks that a component_classifier_config dict is properly formatted.

  Args:
    commponent_classifier_config (dict): A dictionary that provides component to
      its function and path patterns, and some other settings.
      For example:
      {
          'component_info': [
              {
                'component': 'Platform>Apps>AppLauncher>Install',
                'dirs': [
                  'src/third_party/WebKit/public/platform/modules/installedapp',
                  'src/third_party/WebKit/Source/modules/installedapp'
                ]
              },
              ...,
              {
                'component': 'Internals>GPU>Testing',
                'dirs': [
                  'src/gpu/gles2_conform_support',
                  'src/gpu/command_buffer/tests',
                  'src/content/test/gpu/'
                ]
              },
           ],
          'owner_mapping_url': 'mapping_url',
          'top_n': 4
      }

  Returns:
    True if ``component_classifier_config`` is properly formatted, False
    otherwise.
  """
  if not isinstance(component_classifier_config, dict):
    return False

  component_info = component_classifier_config.get(
      'component_info')
  if not isinstance(component_info, list):
    return False

  if not all(isinstance(component, dict)
             for component in component_info):
    return False

  owner_mapping_url = component_classifier_config.get('owner_mapping_url')
  if not isinstance(owner_mapping_url, basestring):
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


def _ValidateRepoToDepPathConfig(repo_to_dep_path):
  """Checks that the repo_to_dep_path is properly formatted.

  Args:
    repo_to_dep_path (dict): A dictionary mapping repository url to its
      chromium repo path.
      For example:
      {
          "https://boringssl.googlesource.com/boringssl.git":
              "src/third_party/boringssl/src",
          "https://chromium.googlesource.com/android_tools.git":
              "src/third_party/android_tools",
          "https://chromium.googlesource.com/angle/angle.git":
              "src/third_party/angle",
          ...
      }

  Returns:
    True if ``repo_to_dep_path`` is properly formatted, False otherwise.
  """
  if not isinstance(repo_to_dep_path, dict):
    return False

  return True


def _ValidateFeatureOptions(feature_options):
  """Checks that the feature_options is properly formatted.

  Args:
    feature_options (dict): A dictionary mapping feature to its
      configurations.
      For example:
      {
          'TouchCrashedComponent': {
              'blacklist': ['Internals>Core'],
      }
  Returns:
    True if ``feature_options`` is properly formatted, False otherwise.
  """
  if not isinstance(feature_options, dict):
    return False

  touch_crashed_directory_options = feature_options.get('TouchCrashedDirectory')
  if not isinstance(touch_crashed_directory_options, dict):
    return False

  directory_blacklist = touch_crashed_directory_options.get('blacklist')
  if not isinstance(directory_blacklist, list):
    return False

  touch_crashed_component_options = feature_options.get('TouchCrashedComponent')
  if not isinstance(touch_crashed_component_options, dict):
    return False

  component_blacklist = touch_crashed_component_options.get('blacklist')
  if not isinstance(component_blacklist, list):
    return False

  return True


_CONFIG_VALIDATION_FUNCTIONS = {
    'fracas': _ValidateChromeCrashConfig,
    'cracas': _ValidateChromeCrashConfig,
    'clusterfuzz': _ValidateClusterfuzzConfig,
    'uma_sampling_profiler': _ValidateUMASamplingProfilerConfig,
    'component_classifier': _ValidateComponentClassifierConfig,
    'project_classifier': _ValidateProjectClassifierConfig,
    'repo_to_dep_path': _ValidateRepoToDepPathConfig,
    'feature_options': _ValidateFeatureOptions,
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
        'clusterfuzz': settings.clusterfuzz,
        'uma_sampling_profiler': settings.uma_sampling_profiler,
        'component_classifier': settings.component_classifier,
        'project_classifier': settings.project_classifier,
        'repo_to_dep_path': settings.repo_to_dep_path,
        'feature_options': settings.feature_options,
    }

    return {'template': 'crash_config.html', 'data': data}

  def HandlePost(self):
    data = self.request.params.get('data')
    new_config_dict = json.loads(data)
    if not _ConfigurationDictIsValid(new_config_dict):
      return self.CreateError(
          'New configuration settings are not properly formatted.', 400)

    # Sort config dict in place.
    _SortConfig(new_config_dict)

    crash_config = CrashConfigModel.Get()
    crash_config.Update(
        users.get_current_user(), users.IsCurrentUserAdmin(), **new_config_dict)
    return self.HandleGet()
