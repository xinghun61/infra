# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re

from google.appengine.ext import ndb

from common.swarmbucket import swarmbucket
from gae_libs import appengine_util
from libs import time_util
from model.flake.flake import Flake
from model.test_inventory import LuciTest
from services import bigquery_helper
from services import step_util

_DEFAULT_LUCI_PROJECT = 'chromium'

_MEMORY_FLAGS_REGEX = [
    (re.compile('ASan', re.I), 'ASan:True'),
    (re.compile('LSan', re.I), 'LSan:True'),
    (re.compile('MSan', re.I), 'MSan:True'),
    (re.compile('TSan', re.I), 'TSan:True'),
    (re.compile('UBSan', re.I), 'UBSan:True'),
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

  query = GetQuery()
  local_tests = {}

  total_rows = 0
  success, rows, job_id, page_token = bigquery_helper.ExecuteQuery(
      appengine_util.GetApplicationId(),
      query,
      parameters=parameters,
      polling_retries=5,
      paging=True)
  if rows:
    total_rows += len(rows)
    for row in rows:
      _CreateLocalTests(row, local_tests)

  while page_token:
    success, rows, job_id, page_token = bigquery_helper.ExecuteQuery(
        appengine_util.GetApplicationId(),
        parameters=parameters,
        paging=True,
        job_id=job_id,
        page_token=page_token)
    total_rows += len(rows)
    for row in rows:
      _CreateLocalTests(row, local_tests)

  if not success:
    raise Exception('Failed executing the query to detect disabled tests.')

  logging.info('Fetched %d rows for disabled tests from BigQuery.', total_rows)
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
      pairs defining the test variant.
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
  return tuple(variant_configurations)


def _CreateLocalTests(row, local_tests):
  """Creates a LuciTest key-test variant pair for a row fetched from BigQuery.

  Args:
    row: A row of query result.
    local_tests (dict): LuciTest entities in local memory in the format
      {LuciTest.key: set of disabled test variants}, mutated by this function.
  """
  build_id = row['build_id']
  builder_name = row['builder_name']
  step_name = row['step_name']
  test_name = row['test_name']
  normalized_step_name = Flake.NormalizeStepName(build_id, step_name)
  normalized_test_name = Flake.NormalizeTestName(test_name, step_name)

  test_key = LuciTest.CreateKey(_DEFAULT_LUCI_PROJECT, normalized_step_name,
                                normalized_test_name)
  disabled_variant = _CreateDisabledVariant(build_id, builder_name, step_name)
  if disabled_variant:
    if not local_tests.get(test_key):
      local_tests[test_key] = set()
    local_tests[test_key].add(disabled_variant)
  else:
    logging.info('Failed to define test variant for build_id: %s', build_id)


@ndb.transactional_tasklet
def _UpdateDatastore(test_key, disabled_test_variants, query_time):
  """Updates disabled_test_variants for a LuciTest in the datastore.

  Args:
    test_key(ndb.Key): Key of LuciTest entities.
    disabled_test_variants(set): Disabled test variants to write to datastore.
    query_time(datetime): The time of the latest query.
  """

  test = yield test_key.get_async()
  if not test:
    test = LuciTest(key=test_key)
  test.disabled_test_variants = disabled_test_variants
  test.last_updated_time = query_time
  yield test.put_async()


@ndb.toplevel
def _UpdateCurrentlyDisabledTests(local_tests, query_time):
  """Stores currently disabled tests.

  Args:
    local_tests (dict): LuciTest entities in local memory in the format
      {LuciTest.key: set of disabled test variants}
    query_time(datetime): The time of the latest query.
  """
  remote_tests = ndb.get_multi(local_tests.keys())

  # (LuciTest key, set of disabled test variants)
  updated_test_keys = []

  for remote_test, local_test in zip(remote_tests, local_tests.items()):
    # test not in datastore
    if not remote_test:
      updated_test_keys.append(local_test[0])
    # test variants changed
    elif local_test[1].symmetric_difference(remote_test.disabled_test_variants):
      updated_test_keys.append(local_test[0])

  for updated_test_key in updated_test_keys:
    _UpdateDatastore(updated_test_key, local_tests[updated_test_key],
                     query_time)


@ndb.toplevel
def _UpdateNoLongerDisabledTests(currently_disabled_test_keys, query_time):
  """Removes test variants from LuciTest entities which are no longer disabled.

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

  for no_longer_disabled_test_key in no_longer_disabled_test_keys:
    _UpdateDatastore(no_longer_disabled_test_key, set(), query_time)


def ProcessQueryForDisabledTests():
  query_time = time_util.GetUTCNow()
  # Stores disabled tests from latest test run locally
  # {LuciTest.key: set of disabled test variants}
  local_tests = _ExecuteQuery(parameters=_GetQueryParameters())
  _UpdateCurrentlyDisabledTests(local_tests, query_time)
  _UpdateNoLongerDisabledTests(local_tests.keys(), query_time)
