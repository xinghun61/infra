# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Handler to update component classifier config."""

from collections import defaultdict
import json
import logging

from google.appengine.api import users

from gae_libs.handlers.base_handler import BaseHandler, Permission
from gae_libs.http.http_client_appengine import HttpClientAppengine
from model.crash.crash_config import CrashConfig

# CloudStorage of latest component/team informatio in OWNERS files.
# (Automatically updated by cron job).
OWNERS_MAPPING_URL = \
  'https://storage.googleapis.com/chromium-owners/component_map.json'
# List of mappings not covered by OWNERS files (e.g. file path -> component).
# These mappings are manually collected and upload to cloud storage.
PREDATOR_MAPPING_URL = \
  'https://storage.googleapis.com/chromium-owners/predator_config_v0.json'


def GetComponentClassifierConfig(owner_mapping_url=OWNERS_MAPPING_URL,
                                 predator_mapping_url=PREDATOR_MAPPING_URL,
                                 http_client=HttpClientAppengine()):
  """Get component mapping information from owners files and convert in
  Predator input format.

  The main purpose is to get the latest component/team information from
  OWNERS files and convert into predator mapping input format.

  Args:
    owner_mapping_url: url link to the component_mapping from OWNERS files.
    predator_mapping_url: url link to component mappings from predator that
    are not covered by OWNERS files.

  Returns:
    A dict of {'component_info': data}, where data is a list of dict in the
    form {'component': component name.
          'function': the function pattern.
          'dirs': a list of directories maps to this component.
          'team': the team owns this component.}.
    """
  component_dict = defaultdict(dict)
  # Mappings from OWNERS files.
  status_code, owner_mappings = http_client.Get(owner_mapping_url,
                                                {'format': 'json'})
  if status_code != 200:
    return None

  for dir_name, component in owner_mappings['dir-to-component'].items():
    if component_dict.get(component) == None:
      component_dict[component]['component'] = component
      component_dict[component]['dirs'] = []
      if owner_mappings['component-to-team'].get(component):
        component_dict[component]['team'] = (
            owner_mappings['component-to-team'].get(component))

    component_dict[component]['dirs'].append("src/" + dir_name)

  # Mappings manually collected for Predator in the Past.
  status_code, predator_mappings = http_client.Get(
      predator_mapping_url, {'format': 'json'})
  if status_code != 200:
    return None

  for path_function_component in predator_mappings['path_function_component']:
    for file_component in path_function_component[2].split('\n'):
      if component_dict.get(file_component) == None:
        component_dict[file_component]['component'] = file_component
        component_dict[file_component]['dirs'] = []
        if owner_mappings['component-to-team'].get(file_component):
          component_dict[file_component]['team'] = (
              owner_mappings['component-to-team'].get(file_component))

      component_dict[file_component]['dirs'].append(
          path_function_component[0])
      if path_function_component[1]:
        component_dict[file_component]['function'] = (
            path_function_component[1])

  component_classifier_config = {'component_info':
                                 component_dict.values()}
  return component_classifier_config


class UpdateComponentConfig(BaseHandler):
  PERMISSION_LEVEL = Permission.ADMIN

  def HandleGet(self):
    # Update component_classifier with latest component/team information.
    new_config_dict = {'component_classifier': GetComponentClassifierConfig(
        OWNERS_MAPPING_URL, PREDATOR_MAPPING_URL, HttpClientAppengine())}
    if not new_config_dict.get('component_classifier'):  # pragma: no cover.
      return BaseHandler.CreateError('Component Classifier Config Update Fail')

    crash_config = CrashConfig.Get()
    crash_config.Update(
        users.get_current_user(), users.IsCurrentUserAdmin(), **new_config_dict)
