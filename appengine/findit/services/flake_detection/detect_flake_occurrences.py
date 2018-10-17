# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from google.appengine.ext import ndb

from gae_libs import appengine_util
from model.flake.detection.flake_occurrence import FlakeOccurrence
from model.flake.flake import Flake
from model.flake import flake_type
from model.flake.flake_type import FlakeType
from services import bigquery_helper
from services import monitoring

MAP_FLAKY_TESTS_QUERY_PATH = {
    FlakeType.CQ_FALSE_REJECTION:
        os.path.realpath(
            os.path.join(__file__, os.path.pardir,
                         'flaky_tests.cq_false_rejection.sql')),
    FlakeType.RETRY_WITH_PATCH:
        os.path.realpath(
            os.path.join(__file__, os.path.pardir,
                         'flaky_tests.retry_with_patch.sql'))
}


def _CreateFlakeFromRow(row):
  """Creates a Flake entity from a row fetched from BigQuery."""
  luci_project = row['luci_project']
  step_ui_name = row['step_ui_name']
  test_name = row['test_name']
  luci_builder = row['luci_builder']
  legacy_master_name = row['legacy_master_name']
  legacy_build_number = row['legacy_build_number']

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
  luci_project = row['luci_project']
  step_ui_name = row['step_ui_name']
  test_name = row['test_name']
  luci_builder = row['luci_builder']
  legacy_master_name = row['legacy_master_name']
  legacy_build_number = row['legacy_build_number']

  normalized_step_name = Flake.NormalizeStepName(
      step_name=step_ui_name,
      master_name=legacy_master_name,
      builder_name=luci_builder,
      build_number=legacy_build_number)
  normalized_test_name = Flake.NormalizeTestName(test_name)

  flake_id = Flake.GetId(
      luci_project=luci_project,
      normalized_step_name=normalized_step_name,
      normalized_test_name=normalized_test_name)
  flake_key = ndb.Key(Flake, flake_id)

  build_id = row['build_id']
  luci_bucket = row['luci_bucket']
  time_happened = row['test_start_msec']
  gerrit_cl_id = row['gerrit_cl_id']
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
      parent_flake_key=flake_key)

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


def _UpdateLastFlakeHappenedTimeForFlakes(occurrences):
  """Updates flakes' last_occurred_time.

  Args:
    occurrences(list): A list of FlakeOccurrence entities.
  """

  flake_key_to_latest_false_rejection_time = {}
  for occurrence in occurrences:
    flake_key = occurrence.key.parent()
    if (not flake_key_to_latest_false_rejection_time.get(flake_key) or
        flake_key_to_latest_false_rejection_time[flake_key] <
        occurrence.time_happened):
      flake_key_to_latest_false_rejection_time[
          flake_key] = occurrence.time_happened

  for flake_key, latest in flake_key_to_latest_false_rejection_time.iteritems():
    flake = flake_key.get()
    if (not flake.last_occurred_time or flake.last_occurred_time < latest):
      flake.last_occurred_time = latest
    flake.put()


def QueryAndStoreFlakes(flake_type_enum):
  """Runs the query to fetch flake occurrences and store them."""
  path = MAP_FLAKY_TESTS_QUERY_PATH[flake_type_enum]
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
  _UpdateLastFlakeHappenedTimeForFlakes(new_occurrences)
  monitoring.OnFlakeDetectionDetectNewOccurrences(
      flake_type=flake_type_desc, num_occurrences=len(new_occurrences))
