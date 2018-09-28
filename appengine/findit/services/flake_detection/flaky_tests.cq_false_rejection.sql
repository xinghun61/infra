# To detect flaky tests causing Chromium CQ false rejections in the past 1 days.
#
# Assumptions for the flake detection in this query are:
# 1. In the same build of the same CL/patchset/builder_id (a bulid id is a tuple
#    of <luci_project_name, buildbucket_name, builder_name>), if a test failed
#    (with patch), it will get retried (without patch). This assumption is
#    required because in such cases, even with multiple builds of the same
#    CL/patchset/builder_id, it is still difficult to tell reliably that the
#    failed tests are flaky ones instead of consistently failing ones on ToT due
#    to a bad commit landed into the codebase already. However, this will filter
#    out true flaky tests in these two scenarios, although they are too rare to
#    worry about for now:
#    * A test is so flaky and fails in both (with patch) and (without patch).
#    * A consistently failing test on ToT is made flaky by the patch being
#      tested and it is so flaky that it fails in (with patch).
# 2. In a test step, the last try of a failed test (with retries) should not be
#    a PASS or an expected failure.
# 3. For disabled tests, they should not be run at all and have an empty list or
#    just ['SKIP'] for run.actual of test-results-hrd:events.test_results
#    https://bigquery.cloud.google.com/table/test-results-hrd:events.test_results
#
# A flaky test causing CQ false rejections is a test that:
# 1. Failed in a flaky build. A flaky build is a failed build that has a
#    matching passed build for the same CL/patchset/builder_id.
# 2. Failed in the (retry with patch) step in a flaky build as defined above,
#    note that if a test failed in the (retry with patch) step, it implies that
#    this test failed in the matching (with patch) step and succeeded in the
#    matching (without patch) step.
#
# Caveat:
# 1. This query does NOT support projects that have no (without patch) in CQ.
# 2. This query only supports Luci builds, because cr-buildbucket.builds.completed_BETA
#    has no steps for buildbot-based builds even they are through buildbucket.

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
    # Below is for debug reference.
    #AND ca.cq_name = 'chromium/chromium/src'  # To test on Chromium CQ only.
    #AND ca.issue = '1000137'  # To test against a Chromium CL.
    #AND ca.attempt_start_msec >= UNIX_MILLIS(TIMESTAMP('2018-04-06')) # To test at a time range.
  GROUP BY
    ca.cq_name,
    ca.issue,
    patchset_group_id ),

  # flaky_build_groups is to find the failed builds that have matching
  # successful builds for the SAME CL/patchset_group/builder_id.
  #
  # A row here is a CL/patchset_group/builder and the flaky builds that were
  # completed in that builder.
  flaky_build_groups AS (
  SELECT
    pg.cq_name,
    pg.issue,
    pg.patchset_group_id,
    STRUCT(
      build.builder.project,
      build.builder.bucket,
      build.builder.builder) AS builder,
    ARRAY_AGG( CASE
        WHEN build.status = 'FAILURE' THEN
          STRUCT(
            build.build_id,
            build.gerrit_change,
            build.gitiles_repository,
            build.gitiles_revision_cp,
            build.steps)
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
      JSON_EXTRACT_SCALAR(build.output.properties,  '$.repository') AS gitiles_repository,
      JSON_EXTRACT_SCALAR(build.output.properties, '$.got_revision_cp') AS gitiles_revision_cp,
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
    AND LOGICAL_OR(build.status = 'SUCCESS')),

  # flaky_test_steps is to find the failed (retry with patch) test step.
  # A row here is a CL/patchset_group/patchset/builder/build and the flaky test steps within that build.
  flaky_test_steps AS (
  SELECT
    fbg.cq_name,
    # Info about the patch.
    failed_build.gerrit_change,
    fbg.patchset_group_id AS patchset_group_id,
    # Info about the code checkouted in the build.
    failed_build.gitiles_repository,
    failed_build.gitiles_revision_cp,
    # Info about the build.
    failed_build.build_id,
    fbg.builder,
    (ARRAY(
      SELECT
        AS STRUCT
        # Group (with patch), (retry with patch) of the same
        # test step by the normalized step name.
        # For ios-simulator, two normalized step names of the SAME build could
        # be "net_unittests (iPad Air 2 iOS 10.0)" and
        # "net_unittests (iPhone 6s iOS 11.2)". Thus, it is wrong to use the
        # test target/type name "net_unittests" for grouping.
        REGEXP_REPLACE(
          step.name, ' [(](with patch|retry with patch)[)].*', ''
        ) AS normalized_step_name,
        ANY_VALUE(CASE
            WHEN step.name LIKE '%(with patch)%' THEN step.name
            ELSE NULL END) AS step_name_with_patch,
        ANY_VALUE(CASE
            WHEN step.name LIKE '%(retry with patch)%' THEN step.name
            ELSE NULL END) AS step_name_retry_with_patch
      FROM
        UNNEST(failed_build.steps) AS step
      WHERE
        step.name LIKE '%(with patch)%'
        OR step.name LIKE '%(retry with patch)%'
      GROUP BY
        normalized_step_name
      HAVING
        # In a flaky build, a test step is flaky if some tests failed in
        # both (with patch) and (retry with patch). There is no need to check
        # (without patch) step because if a test is consistently failing on ToT
        # due to a bad commit, it would fail in (without patch), and it won't
        # run in the (retry with patch) step at all.
        # https://cs.chromium.org/chromium/build/scripts/slave/recipe_modules/test_utils/api.py?l=31
        LOGICAL_OR(step.name LIKE '%(retry with patch)%'
          AND step.status = 'FAILURE'))) AS step_pairs
  FROM
      flaky_build_groups AS fbg
    CROSS JOIN
      UNNEST(fbg.failed_builds) AS failed_build ),

  # failed_tests is to find ALL the failed tests in ALL test steps that are
  # shown as red FAILURES on build pages.
  # It is possible to limit the data further with a whitelist of master names.
  #
  failed_tests AS (SELECT
    # Convert build_id to integer for better performance in joining.
    CAST(build_id AS INT64) AS build_id,
    step_name,
    REGEXP_REPLACE(
      step_name, ' [(](with patch|retry with patch)[)].*', ''
    ) AS normalized_step_name,
    # path is the full test name.
    path AS test_name,
    buildbot_info,
    start_time,
    chromium_revision,
    run.actual,
    run.expected
  FROM
    `test-results-hrd.events.test_results`
  WHERE
    # According to https://cloud.google.com/bigquery/docs/partitioned-tables,
    # _PARTITIONTIME is always the start of each day, so to make sure all data
    # within the past 1 day is included, _PARTITIONTIME needs to be greater than
    # the timestamp of 2 days ago.
    _PARTITIONTIME >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 2 day)
    # Only builds going through buildbucket have build ids, including:
    # 1. All Luci-based builds.
    # 2. A subset of buildbot-based builds, e.g. all CQ builds.
    AND build_id != ''
    # Ignore disabled tests.
    AND ARRAY_LENGTH(run.actual) > 0
    AND 'SKIP' NOT IN UNNEST(run.actual)
    # A failed test should have at least one run with an unexpected status.
    # For gtests, this is straightforward:
    #  1. Passing status is only PASS.
    #  2. Expected statuses could only be SKIP and PASS.
    # For WebKit layout tests, this is very tricky:
    #  1. Passing statuses include PASS and those *BASELINE.
    #  2. Expected statuses include FAIL, CRASH, TIMEOUT, LEAK, TEXT, etc.
    #  3. For retried layout test, if all runs have the same result like
    #     TIMEOUT, run.actual will be [TIMEOUT] instead of [TIMEOUT * 4].
    #  https://chromium.googlesource.com/chromium/tools/build/+/80940a8/scripts/slave/recipe_modules/test_utils/util.py#65
    # The last run of a failed test should not be a PASS or expected failures.
    AND run.actual[ORDINAL(ARRAY_LENGTH(run.actual))] != 'PASS'
    AND run.actual[ORDINAL(ARRAY_LENGTH(run.actual))] NOT IN UNNEST(run.expected)
    # For WebKit layout tests, an unexpected failing status might not mean a
    # failing test. https://chromium.googlesource.com/chromium/src/+/5319d9b60/third_party/blink/tools/blinkpy/web_tests/models/test_expectations.py#969
    # In BigQuery table, it is 'IMAGE_TEXT' instead of 'IMAGE+TEXT'. https://crbug.com/601405
    AND NOT (step_name LIKE '%webkit_layout_tests%'
      AND ( (
          # 'TEXT', 'AUDIO', 'IMAGE_TEXT', and 'IMAGE' map to 'FAIL' in the
          # expected.
          run.actual[ORDINAL(ARRAY_LENGTH(run.actual))] IN ('TEXT',
            'AUDIO',
            'IMAGE_TEXT',
            'IMAGE')
          AND 'FAIL' IN UNNEST(run.expected))
        OR (
          # 'TEXT', 'AUDIO', 'IMAGE_TEXT', 'IMAGE' and 'MISSING' map to
          # 'NEEDSMANUALREBASELINE' in the expected.
          # TODO (crbug.com/839657): remove this case.
          run.actual[ORDINAL(ARRAY_LENGTH(run.actual))] IN ('TEXT',
            'AUDIO',
            'IMAGE_TEXT',
            'IMAGE',
            'MISSING')
          AND 'NEEDSMANUALREBASELINE' IN UNNEST(run.expected))
        OR (
          # 'MISSING' maps to 'REBASELINE' in the expected.
          # No REBASELINE in the expected in the past 120 days, while the
          # linked python code above still handles this case. This should be
          # removed once the python code stops this support.
          run.actual[ORDINAL(ARRAY_LENGTH(run.actual))] = 'MISSING'
            AND 'REBASELINE' IN UNNEST(run.expected))))),

  # flaky_tests is to find the failed tests (Pattern: F {1,}) within the flaky
  # test steps (with patch).
  #
  # A row here is a CL/patchset_group/patchset/builder/build/step/test and its
  # flaky run.
  flaky_tests AS (
  SELECT
    ANY_VALUE(build) entire_build,
    # The same test result data could be uploaded to BigQuery table multiple
    # times, thus we use ANY_VALUE to dedup here. https://crbug.com/806422
    ANY_VALUE( CASE
        # Only keep the failing test runs in the step (with patch).
        WHEN step_pair.normalized_step_name = failed_test.normalized_step_name THEN
          failed_test
        ELSE NULL  # NULL is ignored by ANY_VALUE.
      END) AS test_run,
    step_pair.step_name_with_patch AS step_ui_name
  FROM
    flaky_test_steps AS build
  CROSS JOIN
    UNNEST(build.step_pairs) AS step_pair
  INNER JOIN failed_tests AS failed_test
  ON
    build.build_id = failed_test.build_id
    AND step_pair.normalized_step_name = failed_test.normalized_step_name
  GROUP BY
    build.build_id,
    step_pair.step_name_with_patch,
    failed_test.test_name
  HAVING
    # Flaky tests are those that failed in (retry with patch).
    LOGICAL_OR(failed_test.step_name LIKE '%(retry with patch)%'))

SELECT
  ## Refer to individual fields to avoid duplicate fields.
  entire_build.cq_name,
  # Info about the patch.
  entire_build.gerrit_change.host AS gerrit_host,
  entire_build.gerrit_change.project AS gerrit_project,
  entire_build.gerrit_change.change AS gerrit_cl_id,
  entire_build.gerrit_change.patchset AS gerrit_cl_patchset_number,
  entire_build.patchset_group_id AS gerrit_cl_patchset_group_number,
  # Info about the code checkout.
  entire_build.gitiles_repository,
  entire_build.gitiles_revision_cp,
  test_run.chromium_revision,
  # Info about the build.
  entire_build.builder.project AS luci_project,
  entire_build.builder.bucket AS luci_bucket,
  entire_build.builder.builder AS luci_builder,
  entire_build.build_id,
  test_run.buildbot_info.master_name AS legacy_master_name,
  test_run.buildbot_info.build_number AS legacy_build_number,
  # Info about the test.
  step_ui_name,
  test_run.test_name,
  test_run.start_time AS test_start_msec,
  test_run.actual AS test_actual,
  test_run.expected AS test_expected
FROM
  flaky_tests
