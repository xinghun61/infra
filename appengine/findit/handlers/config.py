# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Handles requests to the findit config page."""

import json

from base_handler import BaseHandler
from base_handler import Permission
from model import wf_config


def _SupportedMastersConfigIsValid(masters_to_blacklisted_steps):
  """Checks that a masters configuration dict is properly formatted.

  Args:
      masters_to_blacklisted_steps: A dictionary expected to map master names
      to lists of strings representing their list of unsupported steps. For
      example,

      masters_to_blacklisted_steps = {
          'master': ['unsupported step', 'another unsupported step', ...],
          'another master': ['unsupported step', ...],
          ...
      }

  Returns:
      True if masters_to_blacklisted_steps is in the proper format, False
      otherwise.
  """
  if not isinstance(masters_to_blacklisted_steps, dict):
    return False

  for unsupported_steps_list in masters_to_blacklisted_steps.itervalues():
    if not isinstance(unsupported_steps_list, list):
      return False
    for unsupported_step in unsupported_steps_list:
      if not isinstance(unsupported_step, basestring):
        return False

  return True


_CONFIG_VALIDATION_FUNCTIONS = {
    # Maps config properties to their validation functions.
    'masters_to_blacklisted_steps': _SupportedMastersConfigIsValid,
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


class Configuration(BaseHandler):
  PERMISSION_LEVEL = Permission.ADMIN

  def HandleGet(self):
    masters = wf_config.Settings().masters_to_blacklisted_steps
    version_number = wf_config.GetCurrentVersionNumber()

    data = {
        'masters': masters,
        'version': version_number,
    }

    return {'template': 'config.html', 'data': data}

  def HandlePost(self):
    data = self.request.params.get('data')
    new_config_dict = json.loads(data)

    if not _ConfigurationDictIsValid(new_config_dict):  # pragma: no cover
      raise ValueError('New configuration settings is not properly formatted.')

    wf_config.Update(new_config_dict)
    return self.HandleGet()
