# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import os

from google.appengine.ext import ndb

from gae_libs import appengine_util
from model.flake.flake import Flake
from model.flake.detection.flake_occurrence import (
    CQFalseRejectionFlakeOccurrence)
from services import bigquery_helper
from services import monitoring

# Path to the query used to detect flaky tests that caused cq false rejections.
PATH_TO_FLAKY_TESTS_QUERY = os.path.realpath(
    os.path.join(__file__, os.path.pardir,
                 'flaky_tests.cq_false_rejection.sql'))


def _CreateFlakeFromRow(row):
  """Creates a Flake entity from a row fetched from BigQuery."""
  luci_project = row['luci_project']
  step_name = row['step_name']
  test_name = row['test_name']
  luci_builder = row['luci_builder']
  legacy_master_name = row['legacy_master_name']
  legacy_build_number = row['legacy_build_number']

  normalized_step_name = Flake.NormalizeStepName(
      step_name=step_name,
      master_name=legacy_master_name,
      builder_name=luci_builder,
      build_number=legacy_build_number)
  normalized_test_name = Flake.NormalizeTestName(test_name)

  return Flake.Create(
      luci_project=luci_project,
      normalized_step_name=normalized_step_name,
      normalized_test_name=normalized_test_name)


def _CreateFlakeOccurrenceFromRow(row):
  """Creates a FlakeOccurrence from a row fetched from BigQuery."""
  luci_project = row['luci_project']
  step_name = row['step_name']
  test_name = row['test_name']
  luci_builder = row['luci_builder']
  legacy_master_name = row['legacy_master_name']
  legacy_build_number = row['legacy_build_number']

  normalized_step_name = Flake.NormalizeStepName(
      step_name=step_name,
      master_name=legacy_master_name,
      builder_name=luci_builder,
      build_number=legacy_build_number)
  normalized_test_name = Flake.NormalizeTestName(test_name)

  flake_id = Flake.GetId(
      luci_project=luci_project,
      normalized_step_name=normalized_step_name,
      normalized_test_name=normalized_test_name)
  flakey_key = ndb.Key(Flake, flake_id)

  build_id = row['build_id']
  luci_bucket = row['luci_bucket']
  reference_succeeded_build_id = row['reference_succeeded_build_id']
  time_happened = row['test_start_msec']
  gerrit_cl_id = row['gerrit_cl_id']
  flake_occurrence = CQFalseRejectionFlakeOccurrence.Create(
      build_id=build_id,
      step_name=step_name,
      test_name=test_name,
      luci_project=luci_project,
      luci_bucket=luci_bucket,
      luci_builder=luci_builder,
      legacy_master_name=legacy_master_name,
      legacy_build_number=legacy_build_number,
      reference_succeeded_build_id=reference_succeeded_build_id,
      time_happened=time_happened,
      gerrit_cl_id=gerrit_cl_id,
      parent_flake_key=flakey_key)

  return flake_occurrence


def _StoreMultipleLocalEntities(local_entities):
  """Stores multiple ndb Model entities.

  NOTE: This method doesn't overwrite existing entities.

  Args:
    local_entities: A list of Model entities in local memory. It is OK for
                    local_entities to have duplicates, this method will
                    automatically de-duplicate them.

  Returns:
    Number of distinct new entities that were written to the ndb.
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
  return len(non_existent_local_entities)


def QueryAndStoreFlakes():
  """Runs the query to fetch flake occurrences and store them."""
  with open(PATH_TO_FLAKY_TESTS_QUERY) as f:
    query = f.read()

  success, rows = bigquery_helper.ExecuteQuery(
      appengine_util.GetApplicationId(), query)

  if not success:
    logging.error(
        'Failed executing the query to detect cq false rejection flakes.')
    monitoring.OnFlakeDetectionQueryFailed(flake_type='cq false rejection')
    return

  logging.info('Fetched %d cq false rejection flake occurrences from BigQuery.',
               len(rows))

  local_flakes = [_CreateFlakeFromRow(row) for row in rows]
  _StoreMultipleLocalEntities(local_flakes)

  local_flake_occurrences = [_CreateFlakeOccurrenceFromRow(row) for row in rows]
  num_new_occurrences = _StoreMultipleLocalEntities(local_flake_occurrences)
  monitoring.OnFlakeDetectionDetectNewOccurrences(
      flake_type='cq false rejection', num_occurrences=num_new_occurrences)
