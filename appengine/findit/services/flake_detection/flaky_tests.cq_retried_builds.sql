# To detect failed builds in Chromium CQ with equivalent successful builds in pair in the past 1 day.
# With such failed builds, Flake Detector downloads and parses the flakiness metadata
# from each to detect flaky tests that have caused such builds to rerun.

WITH
  # patchset_groups is to build up:
  # 1. the equivalent patchset groups with their metadata (cq name, group id, committed, etc)
  # 2. the list of builds within that equivalent patchset group
  #
  # A row here is a equivalent patchset group with builds attached to any
  # patchset within the group.
  patchset_groups AS (
  SELECT
    ca.cq_name,
    ca.issue,
    # Use the earliest_equivalent_patchset as group id,
    # because more new equivalent patchsets could be created.
    (CASE
        WHEN ca.earliest_equivalent_patchset IS NOT NULL THEN
          # Integer type. This field was added on April 4, 2018.
          CAST(ca.earliest_equivalent_patchset AS STRING)
          # Replace with below to disable equivalent patchset grouping.
          # ca.patchset
        ELSE ca.patchset  # String type.
      END) AS patchset_group_id,
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
    ca.issue,
    patchset_group_id ),

  # Find the failed builds that have matching successful builds for the SAME
  # CL/patchset_group/builder_id.
  failed_build_groups AS
  (SELECT
    pg.cq_name,
    pg.issue,
    pg.patchset_group_id,
    ARRAY_AGG( CASE
      WHEN build.status = 'FAILURE'
      AND build.with_flakiness_metadata
      THEN
        STRUCT(
          build.build_id,
          build.gerrit_change,
          build.patch_project,
          build.gitiles_repository,
          build.gitiles_revision_cp,
          build.legacy_build_number,
          build.legacy_master_name,
          build.builder)
        ELSE NULL
      END IGNORE NULLS ) AS failed_builds
  FROM
    patchset_groups AS pg
  CROSS JOIN
    UNNEST(pg.build_ids) AS build_id
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
      EXISTS (SELECT *
          FROM UNNEST(build.steps) AS step
          WHERE LOWER(step.name) = 'findit flakiness') AS with_flakiness_metadata,
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
    ) AS build
  ON
    build_id = build.build_id
  GROUP BY
    pg.cq_name,
    pg.issue,
    pg.patchset_group_id,
    build.builder.project,
    build.builder.bucket,
    build.builder.builder
  HAVING
    # At least one failed build and has a matching successful build.
    LOGICAL_OR(build.status = 'FAILURE')
    AND LOGICAL_OR(build.status = 'SUCCESS'))

# Filter builds to keep the ones with 'FindIt Flakiness' step.
SELECT
  fbg.cq_name,
  # Info about the patch.
  failed_build.patch_project,
  failed_build.gerrit_change.host AS gerrit_host,
  # Buildbucket does not populate gerrit_change.project yet.
  IF(failed_build.gerrit_change.project IS NOT NULL AND failed_build.gerrit_change.project != '', failed_build.gerrit_change.project, failed_build.patch_project) AS gerrit_project,
  failed_build.gerrit_change.change AS gerrit_cl_id,
  failed_build.gerrit_change.patchset AS gerrit_cl_patchset_number,
  # Info about the code checkouted in the build.
  failed_build.gitiles_repository,
  failed_build.gitiles_revision_cp,
  # Info about the build.
  failed_build.build_id,
  failed_build.builder.project AS luci_project,
  failed_build.builder.bucket AS luci_bucket,
  failed_build.builder.builder AS luci_builder,
  failed_build.legacy_master_name,
  failed_build.legacy_build_number
FROM failed_build_groups AS fbg
CROSS JOIN
  UNNEST(fbg.failed_builds) AS failed_build
