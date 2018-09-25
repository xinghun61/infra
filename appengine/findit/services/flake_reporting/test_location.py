# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import logging
import os

import cloudstorage as gcs

from gae_libs.caches import CompressedMemCache
from libs.cache_decorator import Cached

from model.flake.flake import TestLocation
from services import step_util
from services import swarmed_test_util

_COMPONENT_MAPPING_LOCATION = '/chromium-owners/component_map_subdirs.json'


def UpdateFlakeComponent(flake_occurrence):
  """Sets the location and component properties of a flake.

  Note: It is only necessary to call this for one of the flake occurrences of a
  given flake.

  Args:
    flake_occurrence (CQFalseRejectionFlakeOccurrence): Update the flake parent
        of this.
  """
  # TODO: Remove this check to refresh the line number every time. We currently
  # don't use the line number, but it may be used in the future to link to code
  # search.
  if (not flake_occurrence.parent.test_location or
      not flake_occurrence.parent.test_location.file_path):
    step_metadata = step_util.GetStepMetadata(
        flake_occurrence.build_configuration.legacy_master_name,
        flake_occurrence.build_configuration.luci_builder,
        flake_occurrence.build_configuration.legacy_build_number,
        flake_occurrence.step_name)
    task_ids = step_metadata.get('swarm_task_ids')
    for task_id in task_ids:
      test_path = swarmed_test_util.GetTestLocation(task_id,
                                                    flake_occurrence.test_name)
      if test_path:
        flake_occurrence.parent.test_location = TestLocation()
        flake_occurrence.parent.test_location.file_path = test_path.file
        flake_occurrence.parent.test_location.line_number = test_path.line
        break
    if not flake_occurrence.parent.test_location.file_path:
      logging.error(
          'Unable to find test location for %s in %s',
          flake_occurrence.test_name, '/'.join([
              flake_occurrence.build_configuration.legacy_master_name,
              flake_occurrence.build_configuration.luci_builder,
              str(flake_occurrence.build_configuration.legacy_build_number),
              flake_occurrence.step_name
          ]))
      flake_occurrence.parent.component = 'Unknown'
      return

  flake_occurrence.parent.component = _GetComponentForPath(
      flake_occurrence.parent.test_location.file_path)


@Cached(CompressedMemCache(), expire_time=3600)
def _GetComponentAndTeamMapping():
  try:
    return json.load(gcs.open(_COMPONENT_MAPPING_LOCATION))
  except (ValueError, gcs.Error) as e:
    raise Exception(
        'ComponentAndTeam mapping at %s is unavailable or invalid: %s' %
        (_COMPONENT_MAPPING_LOCATION, e.message))


def _GetComponentForPath(path):
  component_map = _GetComponentAndTeamMapping()['dir-to-component']
  path_parts = _NormalizePath(path).split('/')
  # If the full path does not exist in the mapping, start removing parts from
  # the end until a match is found. This is required for WLT where the path may
  # be determined by heuristics rather than actually existing.
  for i in range(len(path_parts)):
    partial_path = '/'.join(path_parts[:len(path_parts) - i])
    if partial_path in component_map:
      return component_map[partial_path]
  return 'Unknown'


def _NormalizePath(path):
  # Remove file, keep directory.
  path = os.path.dirname(path)
  while path.startswith(os.pardir):
    # Remove leading '../'
    path = os.path.relpath(path, os.pardir)
  return path
