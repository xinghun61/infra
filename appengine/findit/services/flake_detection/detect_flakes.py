# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from gae_libs import appengine_util
from libs import time_util
from model.flake.detection import flake_occurrence
from model.flake.detection.flake import Flake
from model.flake.detection.flake_occurrence import FlakeOccurrence
from model.flake.detection.flake_occurrence import FlakeType
from services import bigquery_helper
from services.flake_detection import detection_filing_util

# Query for CQ flakes.
# TODO (crbug.com/831307): Consistent naming for attempt_ts.
_CQ_FLAKES_QUERY = ("""
WITH

  # Stores (issue, patch) with a failed and passed builds (includes false cq rejections).
  # Map (issue, patchset, bucket, builder) to the builds that occurred for them.
  # For each build that's mapped, store the steps for that build.
  # Each row will have a unique combination of
  #  issue,
  #  patchset,
  #  cq_name,
  #  committed,
  #  builds.builder.project,
  #  builds.builder.bucket,
  #  builds.builder.builder
  # Example
  # [
  #  {
  #    "issue": "138133",
  #    "patchset": "2",
  #    "cq_name": "fuchsia/zircon",
  #    "committed": "true",
  #    "luci_project": "fuchsia",
  #    "bucket": "try",
  #    "builder": "zircon-x86-gcc",
  #    "failures": "1",
  #    "successes": "1",
  #    "build_failures": [
  #      {
  #        "id": "8950685706099464064",
  #        "build_status": "FAILURE",
  #        "steps": [ .. ]
  #      },
  #      {
  #        "id": "8950684888673164560",
  #        "build_status": "SUCCESS",
  #        "steps": [ ... ]
  #      }
  #    ]
  #  }
  # ]
  possible_flakes AS (
  SELECT
    ca.issue,
    ca.patchset,
    LOGICAL_OR(ca.committed) as committed,
    ca.cq_name,
    builds.builder.project as luci_project,
    builds.builder.bucket,
    builds.builder.builder,
    ARRAY_AGG(
      CASE
        WHEN builds.status = 'FAILURE' THEN
          STRUCT(builds.id as id, builds.status as build_status, builds.steps)
        ELSE NULL
      END
      IGNORE NULLS
    ) AS build_failures
  FROM
    `chrome-infra-events.aggregated.cq_attempts` ca
  CROSS JOIN
    UNNEST(ca.contributing_bbucket_ids) as build_id
  INNER JOIN
    `cr-buildbucket.builds.completed_BETA` builds
  ON
    build_id = builds.id
  WHERE
    builds.create_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 day)
  GROUP BY
    issue,
    patchset,
    cq_name,
    builds.builder.project,
    builds.builder.bucket,
    builds.builder.builder
  HAVING
    LOGICAL_OR(builds.status = 'FAILURE')
    AND LOGICAL_OR(builds.status = 'SUCCESS')),

  # A list of flaky steps associated with (issue, patchset, bucket, builder, build_id [of failed build])
  # as well as a number of passing/failing with patch/without patch. Filter results by the steps that
  # have failed (with patch) and passed (without patch).
  # Example
  # {
  #  info from above ...
  #  "step_pass_fail": [
  #    {
  #      "step_name": "unittests ",
  #      "with_patch_fail_num": 1,
  #      "without_patch_pass_num": 1
  #    }
  #  ]
  # }
  flaky_steps AS (
  SELECT
      pf.issue,
      pf.patchset,
      pf.committed,
      pf.cq_name,
      pf.luci_project,
      pf.bucket,
      pf.builder,
      (ARRAY(SELECT AS STRUCT
         result.id as build_id,
         REGEXP_REPLACE(step.name, '[(](with(out)? patch)[)]', '') AS step_name,
         ANY_VALUE(CASE
          WHEN step.name LIKE '%(with patch)%'
          THEN step.name
          ELSE
          NULL
         END) as step_name_with_patch
       FROM
         pf.build_failures result,
         result.steps step
       WHERE
         result.build_status = 'FAILURE'
         AND (step.name LIKE '%(with patch)%'
              OR step.name LIKE '%(without patch)%')
         # Filter out layout tests for now since determining a pass/failure for
         # those tests is a bit tricky.
         AND step.name NOT LIKE '%layout%'
       GROUP BY
         result.id,
         step_name
       HAVING
         LOGICAL_OR(step.name LIKE '%(with patch)%' AND step.status = 'FAILURE')
         AND LOGICAL_OR(step.name LIKE '%(without patch)%' AND step.status = 'SUCCESS'))) as step_map
  FROM
    possible_flakes pf),

  # Use the flaky steps and flaky builds with the test results to find the
  # failures F -> F -> F -> F within the failed build.
  flaky_tests AS (
    SELECT
      fs.issue,
      fs.patchset,
      fs.committed,
      fs.cq_name,
      fs.luci_project,
      fs.bucket,
      fs.builder,
      step.build_id,
      tr.buildbot_info.*,
      step.step_name_with_patch as step_name,
      tr.run.name as test_name,
      FORMAT_TIMESTAMP("%Y-%m-%d %H:%M:%S %Z", tr.start_time) AS attempt_ts,
      'CQ_FALSE_REJECTION' AS flake_type
    FROM flaky_steps fs
    CROSS JOIN UNNEST(fs.step_map) step
    INNER JOIN
      # Get the test results that have a build_id. This is better than just joining directly
      # because empty strings can be filtered out. The other way would be to convert the
      # build_ids to strings and string compare, but that's massively slow. Better to just
      # do this.
      (SELECT *
       FROM `test-results-hrd.events.test_results`
       WHERE
         build_id != ''
         AND ARRAY_LENGTH(run.actual) = 4
         AND 'PASS' NOT IN UNNEST(run.actual)
         AND _PARTITIONTIME >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 day)) tr
      ON
        step.build_id = CAST(tr.build_id AS INT64)
        # Find tests that belong to the step that failed (with patch).
        AND step.step_name_with_patch = tr.step_name)


SELECT * FROM flaky_tests
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
  timestamp = time_util.DatetimeFromString(row['attempt_ts'])
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
      appengine_util.GetApplicationId(), _CQ_FLAKES_QUERY)
  if not success:  # pragma: no cover
    logging.error('CQ flakes query failed, check logs for debugging.')
    return

  logging.info('Found a total of %d flake occurrences.', len(rows))

  # Iterate through the query results and store them. Keep track of the changed
  # parent Flakes and kick off a job for each of them.
  changed_flakes = []
  for row in rows:
    success, parent = _StoreFlake(row)

    if success:
      changed_flakes.append(parent)

  logging.info('Total of %d parent flakes were affected.', len(changed_flakes))

  # For each of the changed flakes, check for bugs to be filed.
  for flake in changed_flakes:
    detection_filing_util.CheckAndFileBugForDetectedFlake(flake)
