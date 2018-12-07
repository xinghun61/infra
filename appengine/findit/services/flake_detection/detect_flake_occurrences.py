# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ast
import collections
import json
import logging
import os
import re

from google.appengine.ext import ndb

from common.findit_http_client import FinditHttpClient
from gae_libs import appengine_util
from gae_libs.caches import CompressedMemCache
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs import test_name_util
from libs import time_util
from libs.cache_decorator import Cached
from model.flake.detection.flake_occurrence import FlakeOccurrence
from model.flake.flake import Flake
from model.flake.flake import TestLocation
from model.flake import flake_type
from model.flake.flake_type import FlakeType
from services import bigquery_helper
from services import monitoring
from services import step_util
from services import swarmed_test_util

_MAP_FLAKY_TESTS_QUERY_PATH = {
    FlakeType.CQ_FALSE_REJECTION:
        os.path.realpath(
            os.path.join(__file__, os.path.pardir,
                         'flaky_tests.cq_false_rejection.sql')),
    FlakeType.RETRY_WITH_PATCH:
        os.path.realpath(
            os.path.join(__file__, os.path.pardir,
                         'flaky_tests.retry_with_patch.sql'))
}

# Url to the file with the mapping from the directories to crbug components.
_COMPONENT_MAPPING_URL = ('https://storage.googleapis.com/chromium-owners/'
                          'component_map_subdirs.json')

# The tags used to filter flakes.
# TODO(crbug.com/907688): find a way to keep the list updated.
TAG_SEPARATOR = '::'
SUPPORTED_TAGS = (
    'gerrit_project',
    'luci_project',
    'bucket',
    'master',
    'builder',
    'binary',
    'test_type',
    'step',
    'flake',
    'suite',
    'watchlist',
    'directory',
    'component',
    'parent_component',
    'source',
)


def _CreateFlakeFromRow(row):
  """Creates a Flake entity from a row fetched from BigQuery."""
  luci_project = row['luci_project']
  luci_builder = row['luci_builder']
  legacy_master_name = row['legacy_master_name']
  legacy_build_number = row['legacy_build_number']
  step_ui_name = row['step_ui_name']
  test_name = row['test_name']

  normalized_step_name = Flake.NormalizeStepName(
      step_name=step_ui_name,
      master_name=legacy_master_name,
      builder_name=luci_builder,
      build_number=legacy_build_number)
  normalized_test_name = Flake.NormalizeTestName(test_name, step_ui_name)
  test_label_name = Flake.GetTestLabelName(test_name, step_ui_name)

  return Flake.Create(
      luci_project=luci_project,
      normalized_step_name=normalized_step_name,
      normalized_test_name=normalized_test_name,
      test_label_name=test_label_name)


def _CreateFlakeOccurrenceFromRow(row, flake_type_enum):
  """Creates a FlakeOccurrence from a row fetched from BigQuery."""
  gerrit_project = row['gerrit_project']
  luci_project = row['luci_project']
  luci_bucket = row['luci_bucket']
  luci_builder = row['luci_builder']
  step_ui_name = row['step_ui_name']
  test_name = row['test_name']
  legacy_master_name = row['legacy_master_name']
  legacy_build_number = row['legacy_build_number']

  normalized_step_name = Flake.NormalizeStepName(
      step_name=step_ui_name,
      master_name=legacy_master_name,
      builder_name=luci_builder,
      build_number=legacy_build_number)
  normalized_test_name = Flake.NormalizeTestName(test_name, step_ui_name)

  flake_id = Flake.GetId(
      luci_project=luci_project,
      normalized_step_name=normalized_step_name,
      normalized_test_name=normalized_test_name)
  flake_key = ndb.Key(Flake, flake_id)

  build_id = row['build_id']
  luci_bucket = row['luci_bucket']
  time_happened = row['test_start_msec']
  gerrit_cl_id = row['gerrit_cl_id']

  # Not add the original test name as a tag here, because all the tags will be
  # merged into Flake model, and there might be 100s of parameterized tests
  # which might lead to too large data for a single Flake entity.
  tags = [
      'gerrit_project::%s' % gerrit_project,
      'luci_project::%s' % luci_project,
      'bucket::%s' % luci_bucket,
      'master::%s' % legacy_master_name,
      'builder::%s' % luci_builder,
      'binary::%s' % normalized_step_name,  # e.g. "tests"
      'test_type::%s' % step_ui_name.split(' ', 1)[0],  # e.g. "flavored_tests"
      'step::%s' % step_ui_name,  # e.g. "flavored_tests on Mac 10.13"
      'flake::%s' % normalized_test_name,
  ]
  suite = test_name_util.GetTestSuiteName(normalized_test_name, step_ui_name)
  if suite:
    tags.append('suite::%s' % suite)
  tags.sort()

  flake_occurrence = FlakeOccurrence.Create(
      flake_type=flake_type_enum,
      build_id=build_id,
      step_ui_name=step_ui_name,
      test_name=test_name,
      luci_project=luci_project,
      luci_bucket=luci_bucket,
      luci_builder=luci_builder,
      legacy_master_name=legacy_master_name,
      legacy_build_number=legacy_build_number,
      time_happened=time_happened,
      gerrit_cl_id=gerrit_cl_id,
      parent_flake_key=flake_key,
      tags=tags)

  return flake_occurrence


def _StoreMultipleLocalEntities(local_entities):
  """Stores multiple ndb Model entities.

  NOTE: This method doesn't overwrite existing entities.

  Args:
    local_entities: A list of Model entities in local memory. It is OK for
                    local_entities to have duplicates, this method will
                    automatically de-duplicate them.

  Returns:
    Distinct new entities that were written to the ndb.
  """
  key_to_local_entities = {}
  for entity in local_entities:
    key_to_local_entities[entity.key] = entity

  # |local_entities| may have duplicates, need to de-duplicate them.
  unique_entity_keys = key_to_local_entities.keys()

  # get_multi returns a list, and a list item is None if the key wasn't found.
  remote_entities = ndb.get_multi(unique_entity_keys)
  non_existent_entity_keys = [
      unique_entity_keys[i]
      for i in range(len(remote_entities))
      if not remote_entities[i]
  ]
  non_existent_local_entities = [
      key_to_local_entities[key] for key in non_existent_entity_keys
  ]
  ndb.put_multi(non_existent_local_entities)
  return non_existent_local_entities


def _NormalizePath(path):
  """Returns the normalized path of the given one.

     Normalization include:
     * Convert '\\' to '/'
     * Convert '\\\\' to '/'
     * Resolve '../' and './'

     Example:
     '..\\a/../b/./c/test.cc' --> 'b/c/test.cc'
  """
  path = path.replace('\\', '/')
  path = path.replace('//', '/')

  filtered_parts = []
  for part in path.split('/'):
    if part == '..':
      if filtered_parts:
        filtered_parts.pop()
    elif part == '.':
      continue
    else:
      filtered_parts.append(part)

  return '/'.join(filtered_parts)


def _GetTestLocation(flake_occurrence):
  """Returns a TestLocation for the given FlakeOccurrence instance."""
  step_metadata = step_util.GetStepMetadata(
      flake_occurrence.build_configuration.legacy_master_name,
      flake_occurrence.build_configuration.luci_builder,
      flake_occurrence.build_configuration.legacy_build_number,
      flake_occurrence.step_ui_name)
  task_ids = step_metadata.get('swarm_task_ids')
  for task_id in task_ids:
    test_path = swarmed_test_util.GetTestLocation(task_id,
                                                  flake_occurrence.test_name)
    if test_path:
      return TestLocation(
          file_path=_NormalizePath(test_path.file), line_number=test_path.line)
  return None


@Cached(CompressedMemCache(), expire_time=3600)
def _GetChromiumDirectoryToComponentMapping():
  """Returns a dict mapping from directories to components."""
  status, content, _ = FinditHttpClient().Get(_COMPONENT_MAPPING_URL)
  if status != 200:
    # None result won't be cached.
    return None
  mapping = json.loads(content).get('dir-to-component')
  if not mapping:
    return None
  result = {}
  for path, component in mapping.iteritems():
    path = path + '/' if path[-1] != '/' else path
    result[path] = component
  return result


@Cached(CompressedMemCache(), expire_time=3600)
def _GetChromiumWATCHLISTS():
  repo_url = 'https://chromium.googlesource.com/chromium/src'
  source = CachedGitilesRepository(FinditHttpClient(), repo_url).GetSource(
      'WATCHLISTS', 'master')
  if not source:
    return None

  # https://cs.chromium.org/chromium/src/WATCHLISTS is in python.
  definitions = ast.literal_eval(source).get('WATCHLIST_DEFINITIONS')
  return dict((k, v['filepath']) for k, v in definitions.iteritems())


def _UpdateTestLocationAndTags(flake, occurrences, component_mapping,
                               watchlists):
  """Updates the test location and tags of the given flake.

  Currently only support gtests and webkit layout tests in chromium/src.

  Returns:
    True if flake is updated; otherwise False.
  """
  chromium_tag = 'gerrit_project::chromium/src'
  if chromium_tag not in flake.tags:
    logging.debug('Flake is not from chromium/src: %r', flake)
    return False

  # No need to update if the test location and related tags were updated within
  # the last 7 days.
  if (flake.last_test_location_based_tag_update_time and
      (flake.last_test_location_based_tag_update_time <
       time_util.GetDateDaysBeforeNow(7))):
    logging.debug('Flake test location tags were updated recently : %r', flake)
    return False

  # Update the test definition location, and then components/tags, etc.
  test_location = None

  if 'webkit_layout_tests' in occurrences[0].step_ui_name:
    # For Webkit layout tests, assume that the normalized test name is
    # the directory name.
    # TODO(crbug.com/835960): use new location third_party/blink/web_tests.
    test_location = TestLocation(
        file_path=_NormalizePath('third_party/blink/web_tests/%s' %
                                 flake.normalized_test_name))
  elif test_name_util.GTEST_REGEX.match(flake.normalized_test_name):
    # For Gtest, we read the test location from the output.json
    test_location = _GetTestLocation(occurrences[0])

  if test_location:
    flake.test_location = test_location
    file_path = test_location.file_path

    # Ignore old test-location-based tags.
    all_tags = set([
        t for t in (flake.tags or [])
        if not t.startswith(('watchlist::', 'directory::', 'source::',
                             'parent_component::', 'component::'))
    ])

    # Use watchlist to set the watchlist tags for the flake.
    for watchlist, pattern in watchlists.iteritems():
      if re.search(pattern, file_path):
        all_tags.add('watchlist::%s' % watchlist)

    component = None
    # Use test file path to find the best matched component in the mapping.
    # Each parent directory will become a tag.
    index = len(file_path)
    while index > 0:
      index = file_path.rfind('/', 0, index)
      if index > 0:
        if not component and file_path[0:index + 1] in component_mapping:
          component = component_mapping[file_path[0:index + 1]]
        all_tags.add('directory::%s' % file_path[0:index + 1])
    all_tags.add('source::%s' % file_path)

    if component:
      flake.component = component

      all_tags.add('component::%s' % component)
      all_tags.add('parent_component::%s' % component)
      index = len(component)
      while index > 0:
        index = component.rfind('>', 0, index)
        if index > 0:
          all_tags.add('parent_component::%s' % component[0:index])

    flake.tags = sorted(all_tags)
    flake.last_test_location_based_tag_update_time = time_util.GetUTCNow()

  return test_location is not None


def _UpdateFlakeMetadata(all_occurrences):
  """Updates flakes' metadata including last_occurred_time and tags.

  Args:
    all_occurrences(list): A list of FlakeOccurrence entities.
  """
  flake_key_to_occurrences = collections.defaultdict(list)
  for occurrence in all_occurrences:
    flake_key_to_occurrences[occurrence.key.parent()].append(occurrence)

  component_mapping = _GetChromiumDirectoryToComponentMapping() or {}
  watchlist = _GetChromiumWATCHLISTS() or {}

  for flake_key, occurrences in flake_key_to_occurrences.iteritems():
    flake = flake_key.get()
    new_latest_occurred_time = max(o.time_happened for o in occurrences)
    new_tags = set()
    for occurrence in occurrences:
      new_tags.update(occurrence.tags)

    changed = False

    if (not flake.last_occurred_time or
        flake.last_occurred_time < new_latest_occurred_time):
      # There are new occurrences.
      flake.last_occurred_time = new_latest_occurred_time
      changed = True

    if not new_tags.issubset(flake.tags):
      # There are new tags.
      new_tags.update(flake.tags)
      flake.tags = sorted(new_tags)
      changed = True

    # The "gerrit_project:" tag should be updated first.
    updated = _UpdateTestLocationAndTags(flake, occurrences, component_mapping,
                                         watchlist)

    if changed or updated:  # Avoid io if there was no update.
      flake.put()


def QueryAndStoreFlakes(flake_type_enum):
  """Runs the query to fetch flake occurrences and store them."""
  path = _MAP_FLAKY_TESTS_QUERY_PATH[flake_type_enum]
  flake_type_desc = flake_type.FLAKE_TYPE_DESCRIPTIONS.get(
      flake_type_enum, 'N/A')
  with open(path) as f:
    query = f.read()

  success, rows = bigquery_helper.ExecuteQuery(
      appengine_util.GetApplicationId(), query)

  if not success:
    logging.error('Failed executing the query to detect %s flakes.',
                  flake_type_desc)
    monitoring.OnFlakeDetectionQueryFailed(flake_type=flake_type_desc)
    return

  logging.info('Fetched %d %s flake occurrences from BigQuery.', len(rows),
               flake_type_desc)

  local_flakes = [_CreateFlakeFromRow(row) for row in rows]
  _StoreMultipleLocalEntities(local_flakes)

  local_flake_occurrences = [
      _CreateFlakeOccurrenceFromRow(row, flake_type_enum) for row in rows
  ]
  new_occurrences = _StoreMultipleLocalEntities(local_flake_occurrences)
  _UpdateFlakeMetadata(new_occurrences)
  monitoring.OnFlakeDetectionDetectNewOccurrences(
      flake_type=flake_type_desc, num_occurrences=len(new_occurrences))
