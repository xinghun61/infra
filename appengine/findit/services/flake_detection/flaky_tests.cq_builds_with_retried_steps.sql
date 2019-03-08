# To detect cq builds with step retries in the past 1 day.
# With such builds, Flake Detector downloads and parses the flakiness metadata
# from each to detect flaky tests that have caused step-level reruns.
#
# Builds detected by flaky_tests.cq_retried_builds should be a subset of builds here.

WITH
  # issues is to build up the metadata (cq name, committed, etc) and list of
  # builds for the issues that have cq attempts.
  issues AS (
  SELECT
    ca.cq_name,
    ca.issue,
    # As CQ will reuse successful builds within the last 24 hours from an early
    # equivalent patchset (including the patchset itself), dedup is needed.
    ARRAY_AGG(DISTINCT build_id) AS build_ids
  FROM
      `chrome-infra-events.raw_events.cq` AS ca
    CROSS JOIN
      UNNEST(ca.contributing_buildbucket_ids) AS build_id
  WHERE
    # cq_events table is not partitioned.
    ca.attempt_start_usec >= UNIX_MICROS(TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 day))
    AND ca.cq_name in (
      'chromium/chromium/src' # iOS does not support (without patch) yet.
      #, 'chromium/angle/angle' # Projects other than Chromium are not supported for now.
      #, 'webrtc/src'  # WebRTC does not retry (without patch) for failed tests.
      #, 'chromium/v8/v8'  # V8 does not retry (without patch) for failed tests.
    )
  GROUP BY
    ca.cq_name,
    ca.issue)

# Filter builds to keep the ones with 'FindIt Flakiness' step.
SELECT
  issue.cq_name,
  # Info about the patch.
  build.patch_project,
  build.gerrit_change.host AS gerrit_host,
  # Buildbucket does not populate gerrit_change.project yet.
  IF(build.gerrit_change.project IS NOT NULL AND build.gerrit_change.project != '', build.gerrit_change.project, build.patch_project) AS gerrit_project,
  build.gerrit_change.change AS gerrit_cl_id,
  build.gerrit_change.patchset AS gerrit_cl_patchset_number,
  # Info about the code checkouted in the build.
  build.gitiles_repository,
  build.gitiles_revision_cp,
  # Info about the build.
  build.build_id,
  build.builder.project AS luci_project,
  build.builder.bucket AS luci_bucket,
  build.builder.builder AS luci_builder,
  build.legacy_master_name,
  build.legacy_build_number
FROM
  issues AS issue
CROSS JOIN
  UNNEST(issue.build_ids) AS build_id
INNER JOIN (
  # Load ONLY needed data before joining for better performance.
  # https://cloud.google.com/bigquery/docs/best-practices-performance-communication#reduce_data_before_using_a_join
  # StandardSql does not optimize much for join query. That said, if a filter
  # applies against a field in one table AFTER joining, the filter will not be
  # pushed down to the data read of that table and instead the filter applies
  # after the join is done. As a result more data than needed is loaded to
  # participate in the join. And that would make the join less efficient.
  SELECT
    build.builder,
    build.id AS build_id,
    build.status,
    gerrit_change,
    build.number AS legacy_build_number,
    JSON_EXTRACT_SCALAR(build.input.properties,  '$.mastername') AS legacy_master_name,
    JSON_EXTRACT_SCALAR(build.output.properties,  '$.patch_project') AS patch_project,
    JSON_EXTRACT_SCALAR(build.output.properties,  '$.repository') AS gitiles_repository,
    JSON_EXTRACT_SCALAR(build.output.properties, '$.got_revision_cp') AS gitiles_revision_cp
  FROM
      `cr-buildbucket.builds.completed_BETA` AS build
    CROSS JOIN
      UNNEST(build.input.gerrit_changes) AS gerrit_change
  WHERE
    # cr-buildbucket is a partitioned table, but not by ingestion time.
    build.create_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 day)
    # Chromium CQ builds should have only one patchset, thus the arrary
    # cr-buildbucket.builds.completed_BETA.input.gerrit_changes would
    # effectively have only one element. But still check just in case.
    AND ARRAY_LENGTH(build.input.gerrit_changes) = 1
    AND
      EXISTS(SELECT *
       FROM UNNEST(build.steps) AS step
       WHERE LOWER(step.name) = 'findit flakiness')
) AS build
ON
  build_id = build.build_id
