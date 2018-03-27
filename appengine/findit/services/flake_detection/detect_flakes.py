# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from gae_libs import appengine_util
from libs import time_util
from model.flake.detection import flake_occurrence
from model.flake.detection.flake import Flake
from model.flake.detection.flake_occurrence import FlakeOccurrence
from model.flake.detection.flake_occurrence import FlakeType
from services import bigquery_helper
from services.flake_detection import detection_filing_util

# Placeholder will just return an empty list.
# TODO(wylieb@): Replace this placeholder with the actual query.
_FLAKES_QUERY = ("""
  SELECT * FROM `findit-for-me.events.compile` WHERE true = false
""")


def MonorailProjectForCqName(cq_name):
  """Given a cq_name, return the monorail project."""
  if 'v8' in cq_name:
    return 'v8'
  elif 'webrtc' in cq_name:
    return 'webrtc'
  else:
    return 'chromium'


def _StoreFlake(row):
  """Store one row as a flake occurrence."""
  # Schema:
  # attempt_ts (str)
  # test_name (str)
  # step_name (str)
  # master_name (str)
  # builder_name (str)
  # build_number (int)
  # build_id (int)
  # flake_type (str)
  # cq_name (str)
  timestamp = time_util.DatetimeFromString(
      row['attempt_ts']) if 'attempt_ts' in row else None
  test_name = row['test_name']
  step_name = row['step_name']
  master_name = row['master_name']
  builder_name = row['builder_name']
  build_number = row['build_number']
  build_id = row['build_id']
  flake_type = flake_occurrence.FlakeTypeFromString(row['flake_type'])
  cq_name = row['cq_name']
  luci_project = row['luci_project']
  if (not timestamp or not test_name or not step_name or not master_name or
      not builder_name or not build_number or not build_id or not flake_type or
      not cq_name or not luci_project):
    return False, None

  # Get or create the parent flake.
  flake = Flake.Get(step_name, test_name)
  if not flake:
    flake = Flake.Create(
        step_name, test_name, project_id=MonorailProjectForCqName(cq_name))
    flake.put()

  # Get or create the flake occurrence.
  occurrence = FlakeOccurrence.Get(step_name, test_name, build_id)
  if not occurrence:
    occurrence = FlakeOccurrence.Create(step_name, test_name, build_id,
                                        master_name, builder_name, build_number,
                                        time_util.GetUTCNow(), flake_type)
    occurrence.put()

  return True, flake


def QueryAndStoreFlakes():
  """Run a query to fetch flake occurrences and kick off issue filing."""
  # Fetch rows.
  # TODO(crbug.com/825992): Store row in structured object.
  success, rows = bigquery_helper.ExecuteQuery(
      appengine_util.GetApplicationId(), _FLAKES_QUERY)
  if not success:  # pragma: no cover
    return

  # Iterate through the query results and store them. Keep track of the changed
  # parent Flakes and kick off a job for each of them.
  changed_flakes = []
  for row in rows:
    success, parent = _StoreFlake(row)

    if success:
      changed_flakes.append(parent)

  # For each of the changed flakes, check for bugs to be filed.
  for flake in changed_flakes:
    detection_filing_util.CheckAndFileBugForDetectedFlake(flake)
