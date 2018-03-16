# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""
Functions to support filing monorail bugs, but don't interact with the
service directly.
"""

import re
import json
import urllib
import logging

from services import test_results
from services import swarming
from services import swarmed_test_util


_COMPONENT_LINK = (
    'https://storage.googleapis.com/chromium-owners/component_map_subdirs.json')

_COMPONENT_PATH_REGEX = r'[\/][A-Za-z\._-]+$'

def GetComponent(http_client, master_name, builder_name, build_number,
                 step_name, test_name):
  """Return the component of the given information."""
  logging.info('Looking for component of config: %s/%s/%d/%s and test: %s',
               master_name, builder_name, build_number, step_name, test_name)

  # This is a layout test.
  if 'layout' in step_name.lower():
    logging.info('Found layout test.')
    return GetNearestComponentForPath(
        'third_party/WebKit/LayoutTests/' + test_name)

  # Look for the isolate data given the config.
  isolated_data = swarming.GetIsolatedDataForStep(
      master_name, builder_name, build_number, step_name, http_client)
  if not isolated_data:
    logging.info('No isolate data found.')
    return None

  # From the isolate data, get the test results for the given test_name.
  results = swarmed_test_util.RetrieveShardedTestResultsFromIsolatedServer(
      isolated_data, http_client)
  if not results:
    logging.info('No test results found for isolate data.')
    return None

  # This is a gtest. Use the result log to get the file path, and return the
  # component from that.
  return GetGTestComponent(test_name, results)


def GetGTestComponent(test_name, results):
  """Given a gtest test_name and results, return the component of the test."""
  location, err = test_results.GetTestLocation(results, test_name)
  if not location:
    logging.info('No location found for %s with error %s.', test_name, err)
    return None

  return GetNearestComponentForPath(location.file.replace('../../', ''))


def GetNearestComponentForPath(path):
  """Given the path, find the nearest match from the component directory."""
  original_path = path
  response = urllib.urlopen(_COMPONENT_LINK).read()
  components = json.loads(response)
  dir_to_component = components['dir-to-component']

  matches = re.search(_COMPONENT_PATH_REGEX, path, re.DOTALL)
  while matches and path not in dir_to_component:
    path = path[:matches.start()]
    matches = re.search(_COMPONENT_PATH_REGEX, path, re.DOTALL)

  if path in dir_to_component:
    component = dir_to_component[path]
    logging.info('Found component %s for path %s', component, original_path)
    return component

  logging.info('Couldn\'t find component for given path %s.', original_path)
  return None