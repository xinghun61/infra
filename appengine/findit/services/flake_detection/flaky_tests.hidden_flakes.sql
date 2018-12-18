  # To detect hidden flaky tests causing test retries in the past 1 day.
  #
  # Assumptions for the hidden flakes in this query are:
  # 1. A hidden flaky test is a test passed eveutally in a test step and has
  #    * At least one PASS or expected test result
  #    * At least two FAILED or unexpected test result
  #    These two imply that the test was retried at least twice to avoid flake
  #    due to resource starvation in parallel test execution mode.
  #
  # 2. For disabled tests, they should not be run at all and have an empty list
  #    or just ['SKIP'] for run.actual of test-results-hrd:events.test_results
  #    https://bigquery.cloud.google.com/table/test-results-hrd:events.test_results
  #
  # Caveat:
  # 1. This query does NOT support projects that do not retry test failures.
  # 2. This query only supports Luci builds, because
  #    cr-buildbucket.builds.completed_BETA has no steps for buildbot-based
  #    builds even they are through buildbucket.
  # 3. This query does NOT support the case that the test have multiple
  #    unexpected test results without a PASS or expected one. This category
  #    is expected to be caught by the other queries.

WITH
  # patchset_groups is to build up:
  # 1. the equivalent patchset groups with their metadata (cq name, group id,
  #    committed, etc)
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
    ca.attempt_start_usec >= UNIX_MICROS(
      TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 day))
    AND ca.cq_name IN (
      'chromium/chromium/src'
      #, 'chromium/angle/angle'
      #, 'webrtc/src'
      #, 'chromium/v8/v8'
      )
  GROUP BY
    ca.cq_name,
    ca.issue,
    patchset_group_id ),

  # A row is a CL/patchset_group/builder/build completed in that builder.
  builds AS (
  SELECT
    pg.cq_name,
    pg.issue,
    pg.patchset_group_id,
    STRUCT( build.builder.project,
      build.builder.bucket,
      build.builder.builder) AS builder,
    STRUCT( build.build_id,
      build.gerrit_change,
      build.patch_project,
      build.gitiles_repository,
      build.gitiles_revision_cp,
      build.steps  # TODO: optimize to filter out non-test steps.
      ) AS build
  FROM
    patchset_groups AS pg
  CROSS JOIN
    UNNEST(pg.build_ids) AS build_id
  INNER JOIN (
      # Load ONLY needed data before joining for better performance.
      # https://cloud.google.com/bigquery/docs/best-practices-performance-communication#reduce_data_before_using_a_join
      # StandardSql does not optimize much for join query. That said, if a
      # filter applies against a field in one table AFTER joining, the filter
      # will not be pushed down to the data read of that table and instead the
      # filter applies after the join is done. As a result more data than needed
      # is loaded to participate in the join. And that would make the join less
      # efficient.
    SELECT
      build.builder,
      build.id AS build_id,
      build.status,
      gerrit_change,
      JSON_EXTRACT_SCALAR(build.output.properties,
        '$.patch_project') AS patch_project,
      JSON_EXTRACT_SCALAR(build.output.properties,
        '$.repository') AS gitiles_repository,
      JSON_EXTRACT_SCALAR(build.output.properties,
        '$.got_revision_cp') AS gitiles_revision_cp,
      build.steps
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
      AND ARRAY_LENGTH(build.input.gerrit_changes) = 1 ) AS build
  ON
    build_id = build.build_id),

  # Hidden flakes is to find ALL the passed tests due to 2+ retries.
  # This includes ALL test steps with/without patch.
  # It is possible to limit the data further with a whitelist of master names.
  hidden_flakes AS (
  SELECT
    *
  FROM (
    SELECT
      # Convert build_id to integer for better performance in joining.
      CAST(build_id AS INT64) AS build_id,
      step_name,
      # path is the full test name.
      path AS test_name,
      buildbot_info,
      start_time,
      chromium_revision,
      (
        # This is to count the expected test results of the test.
        # For gtests, this is straightforward:
        #  1. Passing status is only PASS.
        #  2. Expected statuses could only be SKIP and PASS.
        # For WebKit layout tests, this is very tricky:
        #  1. Passing statuses include PASS and those *BASELINE.
        #  2. Expected statuses include FAIL, CRASH, TIMEOUT, LEAK, TEXT, etc.
        #  3. For retried layout test, if all runs have the same result like
        #     TIMEOUT, run.actual will be [TIMEOUT] instead of [TIMEOUT * 4].
        #  https://chromium.googlesource.com/chromium/tools/build/+/80940a8/scripts/slave/recipe_modules/test_utils/util.py#65
        # At least one run should be a PASS or an expected failure.
      SELECT
        countif ( actual = 'PASS'
          OR actual IN UNNEST(run.expected) OR
          # For WebKit layout tests, an unexpected failing status might not mean
          # a failing test.
          # https://chromium.googlesource.com/chromium/src/+/5319d9b60/third_party/blink/tools/blinkpy/web_tests/models/test_expectations.py#969
          # In BigQuery table, it is 'IMAGE_TEXT' instead of 'IMAGE+TEXT'.
          # https://crbug.com/601405
          (step_name LIKE '%webkit_layout_tests%'
            AND ( (
                # 'TEXT', 'AUDIO', 'IMAGE_TEXT', and 'IMAGE' map to 'FAIL' in
                # the expected.
                actual IN ('TEXT',
                  'AUDIO',
                  'IMAGE_TEXT',
                  'IMAGE')
                AND 'FAIL' IN UNNEST(run.expected))
              OR (
                # 'TEXT', 'AUDIO', 'IMAGE_TEXT', 'IMAGE' and 'MISSING' map to
                # 'NEEDSMANUALREBASELINE' in the expected.
                # TODO (crbug.com/839657): remove this case.
                actual IN ('TEXT',
                  'AUDIO',
                  'IMAGE_TEXT',
                  'IMAGE',
                  'MISSING')
                AND 'NEEDSMANUALREBASELINE' IN UNNEST(run.expected))
              OR (
                # 'MISSING' maps to 'REBASELINE' in the expected.
                # No REBASELINE in the expected in the past 120 days, while the
                # linked python code above still handles this case. This should
                # be removed once the python code stops this support.
                actual = 'MISSING'
                AND 'REBASELINE' IN UNNEST(run.expected)))))
      FROM
        UNNEST(run.actual) AS actual) AS num_expected_runs,
      run.actual,
      run.expected
    FROM
      `test-results-hrd.events.test_results`
    WHERE
      # According to https://cloud.google.com/bigquery/docs/partitioned-tables,
      # _PARTITIONTIME is always the start of each day, so to make sure all data
      # within the past 1 day is included, _PARTITIONTIME needs to be greater
      # than the timestamp of 2 days ago.
      _PARTITIONTIME >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 2 day)
      # Only builds going through buildbucket have build ids, including:
      # 1. All Luci-based builds.
      # 2. A subset of buildbot-based builds, e.g. all CQ builds.
      AND build_id != ''
      # Due to resource starvation, a test may pass in the first retry. so
      # hidden flakes are required to have at least 2 retries after the failure.
      AND ARRAY_LENGTH(run.actual) >= 3
      # Ignore disabled tests.
      AND 'SKIP' NOT IN UNNEST(run.actual))
  WHERE
    # Hidden flakes have both expected and unexpected test results.
    num_expected_runs > 0
    AND num_expected_runs < ARRAY_LENGTH(actual))

SELECT
  ## Refer to individual fields to avoid duplicate fields.
  build.cq_name,
  # Info about the patch.
  build.build.gerrit_change.host AS gerrit_host,
  # Buildbucket does not populate gerrit_change.project yet.
  IF(build.build.gerrit_change.project IS NOT NULL
    AND build.build.gerrit_change.project != '',
    build.build.gerrit_change.project,
    build.build.patch_project) AS gerrit_project,
  build.build.gerrit_change.change AS gerrit_cl_id,
  build.build.gerrit_change.patchset AS gerrit_cl_patchset_number,
  build.patchset_group_id AS gerrit_cl_patchset_group_number,
  # Info about the code checkout.
  build.build.gitiles_repository,
  build.build.gitiles_revision_cp,
  flake.chromium_revision,
  # Info about the build.
  build.builder.project AS luci_project,
  build.builder.bucket AS luci_bucket,
  build.builder.builder AS luci_builder,
  build.build.build_id,
  flake.buildbot_info.master_name AS legacy_master_name,
  flake.buildbot_info.build_number AS legacy_build_number,
  # Info about the test.
  step.name,
  flake.test_name,
  flake.start_time AS test_start_msec,
  flake.num_expected_runs,
  flake.actual AS test_actual,
  flake.expected AS test_expected
FROM
  builds AS build
  CROSS JOIN
    UNNEST(build.build.steps) AS step
  INNER JOIN hidden_flakes AS flake
  ON
    build.build.build_id = flake.build_id
    AND step.name = flake.step_name
