# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re

from google.appengine.ext import ndb

from common.swarmbucket import swarmbucket
from gae_libs import appengine_util
from libs import test_name_util
from libs import time_util
from model.flake.flake import Flake
from model.flake.flake import FlakeIssue
from model.test_inventory import LuciTest
from services import bigquery_helper
from services import step_util
from services import test_tag_util

_DEFAULT_LUCI_PROJECT = 'chromium'

_DEFAULT_CONFIG = 'Unknown'

_ISSUE_LINK_REGEX = [
    re.compile(r'^(?:https?://)?crbug.com/([0-9]+)$'),
    re.compile(
      r'^(?:https?://)?bugs.chromium.org/p/chromium/issues/detail\?id=([0-9]+)$'
    )
]

_MEMORY_FLAGS_REGEX = [
    (re.compile('ASan', re.I), 'ASan:True'),
    (re.compile('LSan', re.I), 'LSan:True'),
    (re.compile('MSan', re.I), 'MSan:True'),
    (re.compile('TSan', re.I), 'TSan:True'),
    (re.compile('UBSan', re.I), 'UBSan:True'),
]

_LOCATION_BASED_TAGS = [
    'watchlist',
    'directory',
    'source',
    'parent_component',
    'component',
]

_STEP_BASED_TAGS = [
    'step',
    'test_type',
]


def _GetQueryParameters():
  return [
      bigquery_helper.GenerateArrayQueryParameter(
          'supported_masters', 'STRING',
          swarmbucket.GetMasters('luci.chromium.ci') +
          swarmbucket.GetMasters('luci.chromium.try'))
  ]


def _ExecuteQuery(parameters=None):

  def GetQuery():
    path = os.path.realpath(
        os.path.join(__file__, os.path.pardir, 'disabled_tests.sql'))
    with open(path) as f:
      query = f.read()
    return query

  component_mapping = test_tag_util._GetChromiumDirectoryToComponentMapping()
  watchlists = test_tag_util._GetChromiumWATCHLISTS()

  query = GetQuery()
  local_tests = {}
  total_rows = 0
  for row in bigquery_helper.QueryResultIterator(
      appengine_util.GetApplicationId(), query, parameters=parameters):
    total_rows += 1
    _CreateLocalTests(row, local_tests, component_mapping, watchlists)

  assert total_rows > 0, '0 rows fetched for disabled tests from BigQuery.'

  logging.info('Total fetched %d rows for disabled tests from BigQuery.',
               total_rows)
  return local_tests


def _GetMemoryFlags(builder_name):
  """Parses the builder_name for memory flags."""
  memory_flags = []
  for pattern, flag in _MEMORY_FLAGS_REGEX:
    if re.search(pattern, builder_name):
      memory_flags.append(flag)
  return memory_flags


def _CreateDisabledVariant(build_id, builder_name, step_name):
  """Creates a test variant for which a test is disabled.

  Args:
    build_id (int): Build id of the build.
    builder_name (str): Builder name of the build.
    step_name (str): The name of the step.

  Returns:
    variant_configurations (tuple): Alphabetically sorted tuple of key-value
      pairs defining the test variant or 'Unknown' if no configurations found.
  """
  variant_configurations = []
  os_name = step_util.GetOS(
      build_id, builder_name, step_name, partial_match=True)
  if os_name:
    variant_configurations.append('os:%s' % os_name)
  else:
    logging.info('Failed to obtain os for build_id: %s', build_id)

  variant_configurations.extend(_GetMemoryFlags(builder_name))
  variant_configurations.sort()

  if not variant_configurations:
    logging.info(
        'Failed to define test variant for build_id: %s, step_name: %s',
        build_id, step_name)
    variant_configurations = (_DEFAULT_CONFIG,)

  return tuple(variant_configurations)


def _GetNewTestTags(test_tags, step_name, test_name, normalized_step_name,
                    normalized_test_name, build_id, component_mapping,
                    watchlists):
  """Gets new tags for a LuciTest-test variant pair.

  Args:
    test_tags (set([str])): Tags that specify the category of the test.
    step_name (str): The name of the step.
    test_name (str): The name of the test.
    normalized_step_name (str): The normalized version of the step name.
    normalized_test_name (str): The normalized version of the test name.
    build_id (int): Build id of the build.
    component_mapping (dict): Mapping from directories to crbug components.
    watchlists (dict): Mapping from directories to watchlists.

  Returns:
    new_tags (set([str])): Set of new tags for a test-test variant pair.
  """
  new_tags = {'step::%s' % step_name, 'test_type::%s' % step_name.split(' ')[0]}
  new_tags.update(
      _GetLocationBasedTags(test_tags, step_name, test_name,
                            normalized_step_name, normalized_test_name,
                            build_id, component_mapping, watchlists))
  return new_tags


def _GetLocationBasedTags(test_tags, step_name, test_name, normalized_step_name,
                          normalized_test_name, build_id, component_mapping,
                          watchlists):
  """Gets location-based tags for a LuciTest.

  Only gets location-based tags if they do not already appear in test_tags.
  If location-based tags do not already appear in test_tags, first attempts to
  retrieve them from a related flake. Otherwise, tries to generate them.
  There is a special case for GPU tests. GPU location-based tags consist only of
  component tags and are added based on the canonical step name of each variant.
  Because of the dependency on test variants, location-based tags for a GPU test
  cannot be retrieved from Flake and must be generated for every test variant.

  Args:
    test_tags (set([str])): Tags that specify the category of the test.
    step_name (str): The name of the step.
    test_name (str): The name of the test.
    normalized_step_name (str): The normalized version of the step name.
    normalized_test_name (str): The normalized version of the test name.
    build_id (int): Build id of the build.
    component_mapping (dict): Mapping from directories to crbug components.
    watchlists (dict): Mapping from directories to watchlists.

  Returns:
    Set of location-based tags for a test if they do not already exist in
    test_tags, empty set otherwise.
  """
  if normalized_step_name == 'telemetry_gpu_integration_test':
    return _GetLocationBasedTagsForGPUTest(build_id, step_name)
  if any(tag.startswith('component::') for tag in test_tags):
    return set()
  tags_from_flake = _GetLocationBasedTagsFromFlake(
      _DEFAULT_LUCI_PROJECT, normalized_step_name, normalized_test_name)
  if tags_from_flake:
    return tags_from_flake
  return _CreateLocationBasedTags(build_id, step_name, test_name,
                                  normalized_step_name, normalized_test_name,
                                  component_mapping, watchlists)


def _GetLocationBasedTagsFromFlake(luci_project, normalized_step_name,
                                   normalized_test_name):
  """Gets the location-based tags from a Flake if it exists."""
  flake = ndb.Key(
      'Flake', '%s@%s@%s' % (luci_project, normalized_step_name,
                             normalized_test_name)).get()
  if not flake:
    return set()
  return set([
      t for t in (flake.tags or []) if t.split('::')[0] in _LOCATION_BASED_TAGS
  ])


def _CreateLocationBasedTags(build_id, step_name, test_name,
                             normalized_step_name, normalized_test_name,
                             component_mapping, watchlists):
  """Creates location-based tags for gtests and webkit layout tests."""
  location = test_tag_util.GetTestLocation(
      build_id, step_name, test_name, normalized_step_name
  ) if not test_name_util.GTEST_REGEX.match(normalized_test_name) else None
  if location:
    component = test_tag_util.GetTestComponentFromLocation(
        location, component_mapping)
    return test_tag_util.GetTagsFromLocation(set(), location, component,
                                             watchlists)
  return {
      'component::%s' % test_tag_util.DEFAULT_COMPONENT,
      'parent_component::%s' % test_tag_util.DEFAULT_COMPONENT
  }


def _GetLocationBasedTagsForGPUTest(build_id, step_name):
  """Gets location-based tags for GPU tests."""
  components = test_tag_util.GetTestComponentsForGPUTest(
      build_id, step_name) or [test_tag_util.DEFAULT_COMPONENT]
  return test_tag_util.GetTagsForGPUTest(set(),
                                         components) if components else set()


def _CreateIssueKeys(bugs):
  """Creates a list of FlakeIssue keys from a list of bugs.

  Args:
    bugs (list): list of crbug.com links.

  Returns:
    issue_keys (list): List of FlakeIssue keys for each valid bug link.
  """
  issue_keys = set()
  for bug in bugs:
    if bug and isinstance(bug, basestring):
      match = _ISSUE_LINK_REGEX[0].match(bug) or _ISSUE_LINK_REGEX[1].match(bug)
      if not match:
        continue
      issue_id = int(match.groups()[0])
      issue_key = ndb.Key('FlakeIssue',
                          '%s@%d' % (_DEFAULT_LUCI_PROJECT, issue_id))
      issue_keys.add(issue_key)
  return issue_keys


def _CreateLocalTests(row, local_tests, component_mapping, watchlists):
  """Creates a LuciTest key-test variant pair for a row fetched from BigQuery.

  Args:
    row: A row of query results.
    local_tests (dict): LuciTest entities in local memory in the format
      {LuciTest.key: {'disabled_test_variants : set(), issue_keys: set()},
      mutated by this function.
    component_mapping (dict): Mapping from directories to crbug components.
    watchlists (dict): Mapping from directories to watchlists.
  """
  build_id = row['build_id']
  builder_name = row['builder_name']
  step_name = row['step_name']
  test_name = row['test_name']
  bugs = row['bugs']

  if int(build_id) == 1:
    # To filter out tests results with invalid build_id.
    # TODO (crbug.com/999215): Remove this check after test-results is fixed.
    logging.info('Failed to define test variant for build_id: %s, row is %r',
                 build_id, row)
    return

  normalized_step_name = Flake.NormalizeStepName(build_id, step_name)
  normalized_test_name = Flake.NormalizeTestName(test_name, step_name)
  test_key = LuciTest.CreateKey(_DEFAULT_LUCI_PROJECT, normalized_step_name,
                                normalized_test_name)
  if not local_tests.get(test_key):
    local_tests[test_key] = {
        'disabled_test_variants': set(),
        'issue_keys': set(),
        'tags': set()
    }
  local_tests[test_key]['tags'].update(
      _GetNewTestTags(local_tests[test_key]['tags'], step_name, test_name,
                      normalized_step_name, normalized_test_name, build_id,
                      component_mapping, watchlists))

  disabled_variant = _CreateDisabledVariant(build_id, builder_name, step_name)
  local_tests[test_key]['disabled_test_variants'].add(disabled_variant)
  local_tests[test_key]['issue_keys'].update(_CreateIssueKeys(bugs))


def _TagsNeedToBeUpdated(test, new_tags):
  """Determines if a test's tags need to be updated.

  GPU tests and Webkit Layout Tests need to update their tags if new_tags do not
  equal existing test.tags.
  GTests need to update their tags if the set of step-based tags in new_tags
  does not equal the set of step-based tags in test.tags. Location-based tags
  for GTests will be updated in a separate job, therefore existing
  location-based tags will be kept.

  Args:
    test (LuciTest): LuciTest for which to get updated test tags.
    new_tags (set([str])): Test tags generated based on the results of the
      latest disabled test query.

  Returns:
    Boolean indicating if a tags should be updated.
  """
  if not test_name_util.GTEST_REGEX.match(test.normalized_test_name):
    return bool(new_tags.symmetric_difference(test.tags))

  existing_step_based_tags = {
      tag for tag in test.tags if tag.split('::')[0] in _STEP_BASED_TAGS
  }
  new_step_based_tags = {
      tag for tag in new_tags if tag.split('::')[0] in _STEP_BASED_TAGS
  }
  return bool(
      new_step_based_tags.symmetric_difference(existing_step_based_tags))


def _GetUpdatedTags(test, new_tags):
  """Returns most up-to-date tags by comparing new and existing tags.

  Determines most up-to-date and accurate tags based on the following:
    - Step-based tags must come from new_tags.
    - For GPU Tests, location-based test tags must always come from new_tags.
    - For GTests, use existing location-based tags.
    - For all other tests, use location-based tags from new_tags. If
      new_tags is empty assume test is no longer disabled and keep existing
      location-based tags.

  Step-based tags are determined by the step name of each test variant.
  Therefore, step-based tags must always come from new_tags.
  Location-based tags are determined by the location of the LuciTest and are not
  expected to change based on the disabled test variants. Therefore, it is safe
  to use existing location-based tags when new location-based tags could not be
  found. This does not hold true for GPU Tests as location-based tags for GPU
  Tests are dependent on the canonical step name of each test variant.

  Args:
    test (LuciTest): LuciTest for which to get updated test tags.
    new_tags (set([str])): Test tags generated based on the results of the
      latest disabled test query.

  Returns:
    Most up-to-date and accurate set of tags for a LuciTest.
  """
  if test.normalized_step_name == 'telemetry_gpu_integration_test':
    return new_tags
  if test_name_util.GTEST_REGEX.match(
      test.normalized_test_name) or not new_tags:
    new_step_based_tags = {
        tag for tag in new_tags if tag.split('::')[0] in _STEP_BASED_TAGS
    }
    existing_location_based_tags = {
        tag for tag in test.tags if tag.split('::')[0] in _LOCATION_BASED_TAGS
    }
    return new_step_based_tags.union(existing_location_based_tags)
  return new_tags


@ndb.tasklet
def _UpdateDatastore(test_key, test_attributes, query_time):
  """Updates a LuciTest's disabled_test_variants, issue_keys, tags in datastore.

  This function modifies LuciTest attributes as follows:
  - Overwrites existing disabled_test_variants.
  - Adds new issue_keys to existing issue_keys,
  - Overwrites existing tags.

  Args:
    test_key (ndb.Key): Key of LuciTest entities.
    test_attributes (dict): Dictionary that contains the new property values for
    a LuciTest of the form
      {'disabled_test_variants': set(), 'issue_keys': set(), 'tags': set()}
    query_time (datetime): The time of the latest query.
  """
  test = yield test_key.get_async()
  if not test:
    test = LuciTest(key=test_key)
    test.issue_keys = []
    test.tags = []

  test.disabled_test_variants = test_attributes.get('disabled_test_variants',
                                                    set())
  new_issue_keys = test_attributes.get('issue_keys',
                                       set()).difference(test.issue_keys)
  for new_issue_key in new_issue_keys:
    _CreateIssue(new_issue_key)
  test.issue_keys.extend(new_issue_keys)
  test.issue_keys.sort()

  test.tags = _GetUpdatedTags(test, test_attributes.get('tags', set()))
  test.tags.sort()

  test.last_updated_time = query_time
  yield test.put_async()


@ndb.tasklet
def _CreateIssue(issue_key):
  """Creates an issue in the datastore for the given issue_key.

  Creates an issue if one does not already exist. Does not overwrite existing
  entities.

  Args:
    issue_key (ndb.Key): FlakeIssue key for which to create a FlakeIssue entity.
  """
  issue = yield issue_key.get_async()
  if not issue:
    monorail_project, issue_id = issue_key.id().split('@')
    issue_id = int(issue_id)
    issue = FlakeIssue.Create(monorail_project, issue_id)
    yield issue.put_async()


@ndb.toplevel
def _UpdateCurrentlyDisabledTests(local_tests, query_time):
  """Updates currently disabled tests.

  Overwrites existing disabled_test_variants and tags and adds to issue_keys if
  new monorail issues are associated with the test.

  Args:
    local_tests (dict): LuciTest entities in local memory in the format
      {LuciTest.key: {'disabled_test_variants : set(), issue_keys: set()},
      mutated by this function.
    query_time(datetime): The time of the latest query.
  """
  remote_tests = ndb.get_multi(local_tests.keys())

  # (LuciTest key, set of disabled test variants)
  updated_test_keys = []
  for remote_test, local_test in zip(remote_tests, local_tests.items()):
    if not remote_test:
      updated_test_keys.append(local_test[0])
    elif local_test[1]['disabled_test_variants'].symmetric_difference(
        remote_test.disabled_test_variants):
      updated_test_keys.append(local_test[0])
    elif local_test[1]['issue_keys'].difference(remote_test.issue_keys):
      updated_test_keys.append(local_test[0])
    elif _TagsNeedToBeUpdated(remote_test, local_test[1]['tags']):
      updated_test_keys.append(local_test[0])

  logging.info('Updating or Creating %d LuciTests: ', len(updated_test_keys))
  for updated_test_key in updated_test_keys:
    _UpdateDatastore(updated_test_key, local_tests[updated_test_key],
                     query_time)


@ndb.toplevel
def _UpdateNoLongerDisabledTests(currently_disabled_test_keys, query_time):
  """Updates LuciTest entities which are no longer disabled.

  Overwrites existing disabled_test_variants and tags.

  Args:
    currently_disabled_test_keys (list): Keys of currently disabled LuciTest
      entities.
    query_time (datetime): The time of the latest query.
  """
  # pylint: disable=singleton-comparison
  disabled_test_keys = LuciTest.query(LuciTest.disabled == True).fetch(
      keys_only=True)

  no_longer_disabled_test_keys = set(disabled_test_keys) - set(
      currently_disabled_test_keys)

  logging.info('%d tests are no longer disabled: ',
               len(no_longer_disabled_test_keys))
  for no_longer_disabled_test_key in no_longer_disabled_test_keys:
    _UpdateDatastore(no_longer_disabled_test_key, {}, query_time)


def ProcessQueryForDisabledTests():
  query_time = time_util.GetUTCNow()
  local_tests = _ExecuteQuery(parameters=_GetQueryParameters())
  _UpdateCurrentlyDisabledTests(local_tests, query_time)
  _UpdateNoLongerDisabledTests(local_tests.keys(), query_time)
