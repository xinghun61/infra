# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ast
import collections
from datetime import datetime
from datetime import timedelta
import json
import logging
import os
import re

from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb
from google.protobuf.field_mask_pb2 import FieldMask

from common import constants
from common.findit_http_client import FinditHttpClient
from common.waterfall import buildbucket_client
from gae_libs import appengine_util
from gae_libs.caches import CompressedMemCache
from gae_libs.caches import PickledMemCache
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs import test_name_util
from libs import time_util
from libs.cache_decorator import Cached
from libs.structured_object import StructuredObject
from model.flake.detection.flake_occurrence import FlakeOccurrence
from model.flake.flake import DEFAULT_COMPONENT
from model.flake.flake import Flake
from model.flake.flake import TestLocation
from model.flake.flake_type import DESCRIPTION_TO_FLAKE_TYPE
from model.flake.flake_type import FlakeType
from model.flake.flake_type import FLAKE_TYPE_DESCRIPTIONS
from model.wf_build import WfBuild
from services import bigquery_helper
from services import monitoring
from services import step_util
from services import swarmed_test_util
from waterfall import build_util

_MAP_FLAKY_TESTS_QUERY_PATH = {
    FlakeType.CQ_FALSE_REJECTION:
        os.path.realpath(
            os.path.join(__file__, os.path.pardir,
                         'flaky_tests.cq_retried_builds.sql')),
    FlakeType.RETRY_WITH_PATCH:
        os.path.realpath(
            os.path.join(__file__, os.path.pardir,
                         'flaky_tests.cq_builds_with_retried_steps.sql')),
    FlakeType.CQ_HIDDEN_FLAKE:
        os.path.realpath(
            os.path.join(__file__, os.path.pardir,
                         'flaky_tests.hidden_flakes.sql'))
}

# Url to the file with the mapping from the directories to crbug components.
_COMPONENT_MAPPING_URL = ('https://storage.googleapis.com/chromium-owners/'
                          'component_map_subdirs.json')

# The tags used to filter flakes.
# TODO(crbug.com/907688): find a way to keep the list updated.
# TODO: Collect user feedback on frequently used tags and order tags
# accordingly.
SUPPORTED_TAGS = (
    'binary',
    'bucket',
    'builder',
    'component',
    'directory',
    'flake',
    'gerrit_project',
    'luci_project',
    'master',
    'parent_component',
    'source',
    'step',
    'suite',
    'test_type',
    'watchlist',
)

# Runs query for cq hidden flakes every 2 hours.
_CQ_HIDDEN_FLAKE_QUERY_HOUR_INTERVAL = 2

# Roughly estimated max run time of a build.
_ROUGH_MAX_BUILD_CYCLE_HOURS = 2

# Overlap between queries.
_CQ_HIDDEN_FLAKE_QUERY_OVERLAP_MINUTES = 20

_FLAKE_TYPE_TO_FLAKINESS_METADATA_CATEGORY = {
    FlakeType.CQ_FALSE_REJECTION:
        'Failing With Patch Tests That Caused Build Failure',
    FlakeType.RETRY_WITH_PATCH:
        'Step Layer Flakiness',
}

_DETECT_FLAKES_IN_BUILD_TASK_URL = (
    '/flake/detection/task/detect-flakes-from-build')

_FLAKE_TASK_CACHED_SECONDS = 24 * 60 * 60

_FLAKINESS_METADATA_STEP = 'FindIt Flakiness'

# Special mapping between steps and components.
# So that Findit can still auto assign the component to some flakes' bugs even
# if cannot get their components based on test location.
_MAP_STEP_NAME_TO_COMPONENTS = {
    'context_lost_tests': ['Internals>GPU>Testing'],
    'depth_capture_tests': ['Internals>GPU>Testing'],
    'gpu_process_launch_tests': ['Internals>GPU>Testing'],
    'hardware_accelerated_feature_tests': ['Internals>GPU>Testing'],
    'info_collection_tests': ['Internals>GPU>Testing'],
    'maps_pixel_test': ['Internals>GPU>Testing'],
    'pixel_skia_gold_test': ['Internals>GPU>Testing'],
    'pixel_test': ['Internals>GPU>Testing'],
    'screenshot_sync': ['Internals>GPU>Testing'],
    'webgl_conformance_vulkan_passthrough_tests': [
        'Internals>GPU>Testing', 'Blink>WebGL'
    ],
    'webgl2_conformance_d3d11_validating_tests': ['Blink>WebGL'],
    'webgl2_conformance_gl_passthrough_tests': ['Blink>WebGL'],
    'webgl2_conformance_tests': ['Blink>WebGL'],
    'webgl_conformance_d3d11_validating_tests': ['Blink>WebGL'],
    'webgl_conformance_d3d9_passthrough_tests': ['Blink>WebGL'],
    'webgl_conformance_d3d9_validating_tests': ['Blink>WebGL'],
    'webgl_conformance_gl_passthrough_tests': ['Blink>WebGL'],
    'webgl_conformance_gles_passthrough': ['Blink>WebGL'],
    'webgl_conformance_tests': ['Blink>WebGL'],
}


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


def _GetTestSuiteForOccurrence(row, normalized_test_name, normalized_step_name):
  """ Gets test suite name from test_name or step_name

  Args:
    row: A row of query result.
    normalized_test_name: Test name without parameters.
    normalized_step_name: Isolated target of the step.
  """
  step_ui_name = row['step_ui_name']

  if normalized_step_name == 'telemetry_gpu_integration_test':
    # Special case for Telemetry-based GPU tests (identified by
    # telemetry_gpu_integration_test isolate). Suite not related to test
    # names but step names.
    return step_util.GetCanonicalStepName(
        master_name=row['legacy_master_name'],
        builder_name=row['luci_builder'],
        build_number=row['legacy_build_number'],
        step_name=step_ui_name) or step_ui_name.split()[0]

  return test_name_util.GetTestSuiteName(normalized_test_name, step_ui_name)


def _CreateFlakeOccurrenceFromRow(row, flake_type_enum):
  """Creates a FlakeOccurrence from a row fetched from BigQuery."""
  luci_project = row['luci_project']
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

  gerrit_project = row['gerrit_project']
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

  suite = _GetTestSuiteForOccurrence(row, normalized_test_name,
                                     normalized_step_name)
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
      (flake.last_test_location_based_tag_update_time >
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

  updated = False
  # Ignore old test-location-based tags.
  all_tags = set([
      t for t in (flake.tags or [])
      if not t.startswith(('watchlist::', 'directory::', 'source::',
                           'parent_component::', 'component::'))
  ])
  if test_location:
    updated = True
    flake.test_location = test_location
    file_path = test_location.file_path

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
    else:
      flake.component = DEFAULT_COMPONENT
      all_tags.add('component::%s' % DEFAULT_COMPONENT)
      all_tags.add('parent_component::%s' % DEFAULT_COMPONENT)

    flake.tags = sorted(all_tags)
    flake.last_test_location_based_tag_update_time = time_util.GetUTCNow()
  else:
    if flake.normalized_step_name == 'telemetry_gpu_integration_test':
      # Special case for telemetry_gpu_integration_test.
      components = []
      for occurrence in occurrences:
        canonical_step_name = step_util.GetCanonicalStepName(
            master_name=occurrence.build_configuration.legacy_master_name,
            builder_name=occurrence.build_configuration.luci_builder,
            build_number=occurrence.build_configuration.legacy_build_number,
            step_name=occurrence
            .step_ui_name) or occurrence.step_ui_name.split()[0]
        components.extend(
            _MAP_STEP_NAME_TO_COMPONENTS.get(canonical_step_name, []))
      components = list(set(components))  # To remove duplicates.

      if components:
        flake.component = components[0]
        all_tags = all_tags.union(
            set(['component::%s' % component for component in components]))
        flake.tags = sorted(all_tags)
        updated = True

  return updated


def _UpdateFlakeMetadata(all_occurrences):
  """Updates flakes' metadata including last_occurred_time, archived flag
    and tags.

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

    if flake.archived:
      # Occurrences of an old flake reoccur, resets the flake's archived.
      flake.archived = False
      changed = True

    # The "gerrit_project:" tag should be updated first.
    updated = _UpdateTestLocationAndTags(flake, occurrences, component_mapping,
                                         watchlist)

    if changed or updated:  # Avoid io if there was no update.
      flake.put()


def _GetLastCQHiddenFlakeQueryTimeCacheKey(namespace):
  return '{}-{}'.format(namespace, 'last_cq_hidden_flake_query_time')


def _CacheLastCQHiddenFlakeQueryTime(last_cq_hidden_flake_query_time,
                                     namespace='chromium/src'):
  """Saves last_cq_hidden_flake_query_time to memcache.

  Once cached, the value will never expires until next time this function is
  called.
  """
  if not last_cq_hidden_flake_query_time or not isinstance(
      last_cq_hidden_flake_query_time, datetime):
    return
  memcache.set(
      key=_GetLastCQHiddenFlakeQueryTimeCacheKey(namespace),
      value=last_cq_hidden_flake_query_time)


def _GetLastCQHiddenFlakeQueryTime(namespace='chromium/src'):
  return memcache.get(_GetLastCQHiddenFlakeQueryTimeCacheKey(namespace))


def _GetCQHiddenFlakeQueryStartTime():
  """Gets the latest happen time of cq hidden flakes.

  Uses this time to decide if we should run the query for cq hidden flakes.
  And also uses this time to decides the start time of the query.

  Returns:
    (str): String representation of a datetime in the format
      %Y-%m-%d %H:%M:%S UTC.
  """
  last_query_time_right_bourndary = time_util.GetUTCNow() - timedelta(
      hours=_CQ_HIDDEN_FLAKE_QUERY_HOUR_INTERVAL)
  hidden_flake_query_start_time = time_util.FormatDatetime(time_util.GetUTCNow(
  ) - timedelta(
      hours=_CQ_HIDDEN_FLAKE_QUERY_HOUR_INTERVAL + _ROUGH_MAX_BUILD_CYCLE_HOURS,
      minutes=_CQ_HIDDEN_FLAKE_QUERY_OVERLAP_MINUTES))
  hidden_flake_query_end_time = time_util.FormatDatetime(
      time_util.GetUTCNow() -
      timedelta(hours=_CQ_HIDDEN_FLAKE_QUERY_HOUR_INTERVAL))

  last_query_time = _GetLastCQHiddenFlakeQueryTime()

  if not last_query_time:
    # Only before the first time of running the query.
    return hidden_flake_query_start_time, hidden_flake_query_end_time
  return ((hidden_flake_query_start_time, hidden_flake_query_end_time) if
          last_query_time <= last_query_time_right_bourndary else (None, None))


def _ExecuteQuery(flake_type_enum, parameters=None):
  path = _MAP_FLAKY_TESTS_QUERY_PATH[flake_type_enum]
  flake_type_desc = FLAKE_TYPE_DESCRIPTIONS.get(flake_type_enum, 'N/A')
  with open(path) as f:
    query = f.read()
  success, rows = bigquery_helper.ExecuteQuery(
      appengine_util.GetApplicationId(), query, parameters=parameters)

  if not success:
    logging.error('Failed executing the query to detect %s flakes.',
                  flake_type_desc)
    monitoring.OnFlakeDetectionQueryFailed(flake_type=flake_type_desc)
    return None

  logging.info('Fetched %d rows for %s from BigQuery.', len(rows),
               flake_type_desc)
  return rows


class DetectFlakesFromFlakyCQBuildParam(StructuredObject):
  """Inputs of a task to detect a type of flakes from a flaky cq build.

  Supported flake types:
    - FlakeType.CQ_FALSE_REJECTION
    - FlakeType.RETRY_WITH_PATCH
  """
  build_id = int
  flake_type_desc = basestring


@Cached(
    PickledMemCache(),
    namespace='flake_task',
    expire_time=_FLAKE_TASK_CACHED_SECONDS)
def _EnqueueDetectFlakeByBuildTasks(build_id, flake_type_desc):
  """Enqueues a task to detect a type of flakes for the build in the row.

  Caches task names to deduplicate tasks for the same build and flake_type.
  """
  target = appengine_util.GetTargetNameForModule(
      constants.FLAKE_DETECTION_BACKEND)
  params = DetectFlakesFromFlakyCQBuildParam(
      build_id=build_id, flake_type_desc=flake_type_desc).ToSerializable()

  try:
    task_name = 'detect-flake-{}-{}'.format(build_id,
                                            flake_type_desc.replace(' ', '_'))
    taskqueue.add(
        name=task_name,
        url=_DETECT_FLAKES_IN_BUILD_TASK_URL,
        payload=json.dumps(params),
        target=target,
        queue_name=constants.FLAKE_DETECTION_MULTITASK_QUEUE)
    return task_name
  except (taskqueue.TombstonedTaskError, taskqueue.TaskAlreadyExistsError):
    logging.info('%s flakes of build %s was already checked.', flake_type_desc,
                 build_id)


def QueryAndStoreFlakes(flake_type_enum):
  """Runs the query to fetch flake related data and use it to detect flakes
     for cq false rejections and cq step level retries."""
  flake_type_desc = FLAKE_TYPE_DESCRIPTIONS.get(flake_type_enum)
  assert flake_type_enum in [
      FlakeType.CQ_FALSE_REJECTION, FlakeType.RETRY_WITH_PATCH
  ], ('{} is not supported in flakiness metadata.'.format(flake_type_desc))
  rows = _ExecuteQuery(flake_type_enum)
  if not rows:
    return

  for row in rows:
    _EnqueueDetectFlakeByBuildTasks(row['build_id'], flake_type_desc)


def QueryAndStoreHiddenFlakes(flake_type_enum=FlakeType.CQ_HIDDEN_FLAKE):
  """Runs the query to fetch hidden flake occurrences and store them.

  Currently only supports hidden flakes on CQ, later we could use the same
  approach for hidden flakes on CI.

  Hidden flakes are not listed in each build's flakiness metadata since
  there should be many of them in many builds.
  Use a query to directly query hidden flakes from bigquery.
  """
  start_time_string, end_time_string = _GetCQHiddenFlakeQueryStartTime()
  if not start_time_string:
    # Only runs this query every 2 hours.
    return
  parameters = [('hidden_flake_query_start_time', 'TIMESTAMP',
                 start_time_string),
                ('hidden_flake_query_end_time', 'TIMESTAMP', end_time_string)]

  rows = _ExecuteQuery(flake_type_enum, parameters)
  if rows is None:
    return

  local_flakes = [_CreateFlakeFromRow(row) for row in rows]
  _StoreMultipleLocalEntities(local_flakes)

  local_flake_occurrences = [
      _CreateFlakeOccurrenceFromRow(row, flake_type_enum) for row in rows
  ]
  new_occurrences = _StoreMultipleLocalEntities(local_flake_occurrences)
  _UpdateFlakeMetadata(new_occurrences)

  if flake_type_enum == FlakeType.CQ_HIDDEN_FLAKE:
    # Updates memecache for the new last_cq_hidden_flake_query_time.
    _CacheLastCQHiddenFlakeQueryTime(time_util.GetUTCNow())

  flake_type_desc = FLAKE_TYPE_DESCRIPTIONS.get(flake_type_enum, 'N/A')
  monitoring.OnFlakeDetectionDetectNewOccurrences(
      flake_type=flake_type_desc, num_occurrences=len(new_occurrences))


def StoreDetectedCIFlakes(master_name, builder_name, build_number, flaky_tests):
  """Stores detected CL flakes to datastore.

  Args:
    master_name(str): Name of the master.
    builder_name(str): Name of the builder.
    build_number(int): Number of the build.
    flaky_tests(dict): A dict of flaky tests, in the format:
    {
      'step1': ['test1', 'test2', ...],
      ...
    }
  """
  build = WfBuild.Get(master_name, builder_name, build_number)
  if not build or not build.build_id:
    logging.error(
        'Could not save CI flake on %s/%s/%d since the build or build_id'
        ' is missing.', master_name, builder_name, build_number)
    return

  luci_project, luci_bucket = build_util.GetBuilderInfoForLUCIBuild(
      build.build_id)

  if not luci_project or not luci_bucket:  # pragma: no branch.
    logging.debug(
        'Could not get luci_project or luci_bucket from'
        ' build %s/%s/%d.', master_name, builder_name, build_number)
    return

  row = {
      'luci_project': luci_project,
      'luci_bucket': luci_bucket,
      'luci_builder': builder_name,
      'legacy_master_name': master_name,
      'legacy_build_number': build_number,
      'build_id': int(build.build_id),
      'test_start_msec': time_util.GetUTCNow(),
      # No affected gerrit cls for CI flakes, set related fields to None.
      'gerrit_project': None,
      'gerrit_cl_id': -1
  }

  local_flakes = []
  local_flake_occurrences = []
  for step, step_flaky_tests in flaky_tests.iteritems():
    row['step_ui_name'] = step
    for flaky_test in step_flaky_tests:
      row['test_name'] = flaky_test
      local_flakes.append(_CreateFlakeFromRow(row))
      local_flake_occurrences.append(
          _CreateFlakeOccurrenceFromRow(row, FlakeType.CI_FAILED_STEP))

  _StoreMultipleLocalEntities(local_flakes)

  new_occurrences = _StoreMultipleLocalEntities(local_flake_occurrences)
  _UpdateFlakeMetadata(new_occurrences)

  flake_type_desc = FLAKE_TYPE_DESCRIPTIONS.get(FlakeType.CI_FAILED_STEP, 'N/A')
  monitoring.OnFlakeDetectionDetectNewOccurrences(
      flake_type=flake_type_desc, num_occurrences=len(new_occurrences))


def GetFlakesFromFlakyCQBuild(build_id, build_pb, flake_type_enum):
  """Looks for a specific type of flakes from a CQ build.

  This function currently supports two types of flakes:
  - flakes that caused retried builds.
  - flakes that caused retried steps.

  For cq hidden flakes and ci flakes, do not use this function.

  Args:
    build_id (int): Id of the build.
    build_pb (buildbucket build.proto): Information of the build.
    flake_type_enum (FlakeType): Type of the flakes being detected.

  Returns:
    (dict): A dict of list for steps containing flaky tests and the test list.
    {
      'abc_tests (with patch) on Windows-10-15063': [ # step_ui_name
        'test1',
        'test2',
        ...
      ],
      ...
    }
  """
  flake_category = _FLAKE_TYPE_TO_FLAKINESS_METADATA_CATEGORY.get(
      flake_type_enum)
  assert flake_category, '{} is not covered by flakiness metadata.'.format(
      FLAKE_TYPE_DESCRIPTIONS.get(flake_type_enum))

  http_client = FinditHttpClient()
  flakiness_metadata = step_util.GetStepLogFromBuildObject(
      build_pb, _FLAKINESS_METADATA_STEP, http_client, log_name='step_metadata')
  assert flakiness_metadata, (
      'Failed to get flakiness_metadata for build {}'.format(build_id))

  return flakiness_metadata.get(flake_category) or {}


def ProcessBuildForFlakes(task_param):
  """Detects a type of flakes from a build.

  Args:
    task_param(DetectFlakesFromFlakyCQBuildParam): Parameters of the task to
      detect cq false rejection or retry with patch flakes from a flaky cq
      build.
  """
  build_id = task_param.build_id
  flake_type_enum = DESCRIPTION_TO_FLAKE_TYPE.get(task_param.flake_type_desc)

  build_pb = buildbucket_client.GetV2Build(
      build_id, FieldMask(paths=['number', 'builder', 'input', 'steps']))
  assert build_pb, 'Error retrieving buildbucket build id: {}'.format(build_id)

  luci_project = build_pb.builder.project
  luci_bucket = build_pb.builder.bucket
  luci_builder = build_pb.builder.builder
  legacy_master_name = build_pb.input.properties['mastername']
  legacy_build_number = build_pb.number
  gerrit_changes = build_pb.input.gerrit_changes

  gerrit_cl_id = None
  gerrit_project = None
  if gerrit_changes:
    gerrit_cl_id = build_pb.input.gerrit_changes[0].change
    gerrit_project = build_pb.input.gerrit_changes[0].project

  # Fall-back approach to get gerrit_cl_id and gerrit_project
  gerrit_cl_id = gerrit_cl_id or (build_pb.input.properties['patch_issue']
                                  if 'patch_issue' in build_pb.input.properties
                                  else None)
  gerrit_project = gerrit_project or (
      build_pb.input.properties['patch_project']
      if 'patch_project' in build_pb.input.properties else None)

  if not gerrit_cl_id:
    return

  flake_info = GetFlakesFromFlakyCQBuild(build_id, build_pb, flake_type_enum)

  row = {
      'luci_project': luci_project,
      'luci_bucket': luci_bucket,
      'luci_builder': luci_builder,
      'legacy_master_name': legacy_master_name,
      'legacy_build_number': legacy_build_number,
      'build_id': build_id,
      'gerrit_project': gerrit_project,
      'gerrit_cl_id': gerrit_cl_id
  }

  new_flakes = []
  new_occurrences = []
  for step_ui_name, tests in flake_info.iteritems():
    # Uses the start time of a step as the flake happen time.
    step_start_time, _ = step_util.GetStepStartAndEndTime(
        build_pb, step_ui_name)
    row['step_ui_name'] = step_ui_name
    row['test_start_msec'] = step_start_time
    for test in tests:
      row['test_name'] = test
      new_flakes.append(_CreateFlakeFromRow(row))
      new_occurrences.append(
          _CreateFlakeOccurrenceFromRow(row, flake_type_enum))

  _StoreMultipleLocalEntities(new_flakes)
  _StoreMultipleLocalEntities(new_occurrences)
  _UpdateFlakeMetadata(new_occurrences)
