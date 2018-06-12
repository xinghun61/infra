# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from gae_libs import appengine_util
from model.flake.detection.flake import Flake
from model.flake.detection.flake_occurrence import (
    CQFalseRejectionFlakeOccurrence)
from services import bigquery_helper

# Path to the query used to detect flaky tests that caused cq false rejections.
PATH_TO_FLAKY_TESTS_QUERY = os.path.realpath(
    os.path.join(__file__, os.path.pardir,
                 'flaky_tests.cq_false_rejection.sql'))


def _StoreFlakeOccurrence(row):
  """Stores one row fetched from BigQuery as a FlakeOccurrence entity.

  Please refer to the sql query for the format of the fetched rows.
  """
  luci_project = row['luci_project']
  step_name = row['step_name']
  test_name = row['test_name']

  normalized_step_name = Flake.NormalizeStepName(step_name)
  normalized_test_name = Flake.NormalizeTestName(test_name)
  flake = Flake.Get(
      luci_project=luci_project,
      normalized_step_name=normalized_step_name,
      normalized_test_name=normalized_test_name)
  if not flake:
    flake = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name)
    flake.put()

  build_id = row['build_id']
  luci_bucket = row['luci_bucket']
  luci_builder = row['luci_builder']
  legacy_master_name = row['legacy_master_name']
  reference_succeeded_build_id = row['reference_succeeded_build_id']
  time_happened = row['test_start_msec']

  flake_occurrence = CQFalseRejectionFlakeOccurrence.Get(
      build_id=build_id,
      step_name=step_name,
      test_name=test_name,
      parent_flake_key=flake.key)
  if not flake_occurrence:
    flake_occurrence = CQFalseRejectionFlakeOccurrence.Create(
        build_id=build_id,
        step_name=step_name,
        test_name=test_name,
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder=luci_builder,
        legacy_master_name=legacy_master_name,
        reference_succeeded_build_id=reference_succeeded_build_id,
        time_happened=time_happened,
        parent_flake_key=flake.key)
    flake_occurrence.put()


def QueryAndStoreFlakes():
  """Runs the query to fetch flake occurrences and store them."""
  with open(PATH_TO_FLAKY_TESTS_QUERY) as f:
    query = f.read()

  success, rows = bigquery_helper.ExecuteQuery(
      appengine_util.GetApplicationId(), query)

  if not success:
    logging.error(
        'Failed executing the query to detect cq false rejection flakes.')
    return

  logging.info('Fetched %d cq false rejection flake occurrences from BigQuery.',
               len(rows))
  for row in rows:
    _StoreFlakeOccurrence(row)
