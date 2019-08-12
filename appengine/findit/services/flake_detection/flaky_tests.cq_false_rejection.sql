# To detect flaky tests causing Chromium CQ false rejections in the past 1 day.
#
# Assumptions for the flake detection in this query are:
# 1. In the same build of the same CL/patchset/builder_id (a bulid id is a tuple
#    of <luci_project_name, buildbucket_name, builder_name>), if a test failed
#    (with patch), it will get retried (without patch) and optionally (retry
#    with patch). This assumption is required because in such cases, even with
#    multiple builds of the same CL/patchset/builder_id, it is still difficult
#    to tell reliably that the failed tests are flaky ones instead of
#    consistently failing ones on ToT due to a bad commit landed into the
#    codebase already. However, this will filter out true flaky tests in these
#    two scenarios, although they are too rare to worry about for now:
#    * A test is so flaky and fails in both (with patch) and (without patch).
#    * A consistently failing test on ToT is made flaky by the patch being
#      tested and it is so flaky that it fails in (with patch).
# 2. In a test step (with patch), a test is a failure if its first run and ALL
#    retries are failures (not PASS and not any expected result).
#    https://chromium.googlesource.com/chromium/tools/build/+/917f9c6/scripts/slave/recipe_modules/test_utils/api.py#328
# 3. In a test step (without patch) and (retry with patch), a test is a failure
#    if its first run or any retry is a failure (not PASS and not any expected
#    result). Note that failed tests in (without patch) are ignored, but failed
#    tests in (retry with patch) will fail the build.
#    https://chromium.googlesource.com/chromium/tools/build/+/917f9c6/scripts/slave/recipe_modules/test_utils/api.py#349
#    https://chromium.googlesource.com/chromium/tools/build/+/917f9c6/scripts/slave/recipe_modules/test_utils/api.py#369
#    https://chromium.googlesource.com/chromium/tools/build/+/917f9c6/scripts/slave/recipe_modules/test_utils/util.py#285
# 4. For disabled tests, they should not be run at all and have an empty list or
#    just ['SKIP'] for run.actual of test-results-hrd:events.test_results
#    https://bigquery.cloud.google.com/table/test-results-hrd:events.test_results
#
#
# A flaky test is said to have caused CQ false rejections if it is a new failure
# (it is a new test or passes ToT on the CI) that caused a flaky build. A flaky
# build is a failed build among the builds for the same CL/patchset/builder_id,
# while there is at least one sucessful build.
# The criteria to detect such flaky tests are:
# 1. If "retry with patch" is enabled, it failed in the (retry with patch) step
#    in a flaky build as defined above. Note that if a test failed in the (retry
#    with patch) step, it implies that the test failed in the matching (with
#    patch) step and passed in the matching (without patch) step, and the
#    equivalence of this is a failed (retry summary) step.
#    https://chromium.googlesource.com/chromium/tools/build/+/917f9c6/scripts/slave/recipe_modules/test_utils/api.py#341
# 2. If "retry with patch" is disabled, it failed in the (with patch) step in a
#    flaky build as defined above but passed in the (without patch) step. This
#    is implied by a failed (retry summary) step.
#    https://chromium.googlesource.com/chromium/tools/build/+/917f9c6/scripts/slave/recipe_modules/test_utils/api.py#294
#
# Caveat:
# 1. This query does NOT support projects that have no (without patch) in CQ.
# 2. This query only supports Luci builds, because cr-buildbucket.raw.completed_builds_prod
#    has no steps for buildbot-based builds even they are through buildbucket.

WITH
  # The full list of test types that opt out "(retry with patch)".
  # A test type can be expanded to multiple test steps, e.g.:
  #  "webgl_conformance_tests on NVIDIA GPU on Linux (with patch)"
  #  "webgl_conformance_tests on Android device Nexus 5X (with patch)"
  # Please keep the list in alphabetical order.
  test_types_without_retry_with_patch AS (
  SELECT
    name
  FROM
    UNNEST([
      'context_lost_tests',
      'depth_capture_tests',
      'gpu_process_launch_tests',
      'hardware_accelerated_feature_tests',
      'info_collection_tests',
      'maps_pixel_test',
      'pixel_test',
      'screenshot_sync_tests',
      'trace_test',
      'webgl2_conformance_d3d11_validating_tests',
      'webgl2_conformance_gl_passthrough_tests',
      'webgl2_conformance_tests',
      'webgl_conformance_d3d11_validating_tests',
      'webgl_conformance_d3d9_passthrough_tests',
      'webgl_conformance_d3d9_tests',
      'webgl_conformance_gles_passthrough_tests',
      'webgl_conformance_gl_passthrough_tests',
      'webgl_conformance_tests',
      'webgl_conformance_vulkan_passthrough_tests'
    ]) AS name ),

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
            build.patch_project,
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
      JSON_EXTRACT_SCALAR(build.output.properties,  '$.patch_project') AS patch_project,
      JSON_EXTRACT_SCALAR(build.output.properties,  '$.repository') AS gitiles_repository,
      JSON_EXTRACT_SCALAR(build.output.properties, '$.got_revision_cp') AS gitiles_revision_cp,
      build.steps
    FROM
        `cr-buildbucket.raw.completed_builds_prod` AS build
      CROSS JOIN
        UNNEST(build.input.gerrit_changes) AS gerrit_change
    WHERE
      # cr-buildbucket is a partitioned table, but not by ingestion time.
      build.create_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 day)
      # Chromium CQ builds should have only one patchset, thus the arrary
      # cr-buildbucket.raw.completed_builds_prod.input.gerrit_changes would
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

  # flaky_test_step_groups is to find the test steps that, for the same test
  # suites in the same build, have flaky test failures.
  # A row here is a CL/patchset_group/patchset/builder/build and the flaky test
  # step groups within that build. A test step group is a flaky one iff some
  # tests failed in "with patch" but passed in "without patch", regardless
  # whether "retry with patch" was run or not. In such cases, "retry summary"
  # always failed.
  # https://cs.chromium.org/chromium/build/scripts/slave/recipe_modules/test_utils/api.py?l=31
  # https://chromium.googlesource.com/chromium/tools/build/+/917f9c6/scripts/slave/recipe_modules/test_utils/api.py#239
  flaky_test_step_groups AS (
  SELECT
    fbg.cq_name,
    # Info about the patch.
    failed_build.patch_project,
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
          step.name, ' \\((with patch|without patch|retry summary|retry with patch)\\).*', ''
        ) AS normalized_step_name,
        ANY_VALUE(CASE
            WHEN step.name LIKE '%(with patch)%' THEN step.name
            ELSE NULL END) AS step_name_with_patch,
        ANY_VALUE(CASE
            WHEN step.name LIKE '%(without patch)%' THEN step.name
            ELSE NULL END) AS step_name_without_patch,
        ANY_VALUE(CASE
            WHEN step.name LIKE '%(retry with patch)%' THEN step.name
            ELSE NULL END) AS step_name_retry_with_patch
      FROM
        UNNEST(failed_build.steps) AS step
      WHERE
        step.name LIKE '%(with patch)%'
        OR step.name LIKE '%(without patch)%'
        OR step.name LIKE '%(retry summary)%'
        OR step.name LIKE '%(retry with patch)%'
      GROUP BY
        normalized_step_name
      HAVING
        # In a flaky build, a test step is flaky if some tests failed in
        # (with patch) while they passed in (without patch). In that case, the
        # (retry summary) step should fail as well.
        # If there is a consistently failing test on ToT due to a bad commit, it
        # would fail in both (with patch) and (without patch). When ALL failed
        # tests in (with patch) are consistently failing ones, both (with patch)
        # and (without patch) will fail while (retry summary) will succeed.
        # Thus failed (retry summary) means that some new tests are broken, and
        # checking it only is good enough to filter out the super set of flaky
        # tests in the flaky build.
        # https://chromium.googlesource.com/chromium/tools/build/+/40f838c/scripts/slave/recipe_modules/test_utils/api.py#164
        #
        # If "retry with patch" is enabled for the test step, those failed tests
        # will be retried in (retry with patch), and further filtering will be
        # handled later on by cross-checking with test results.
        #
        # For some CLs changing build configs, "without patch" is disabled and
        # flaky tests surfacing to those builds are excluded here. However, it
        # is expected that such CLs are rare, and the same flaky tests will also
        # be encounted by other CLs.
        LOGICAL_OR(step.name LIKE '%(retry summary)%'
          AND step.status = 'FAILURE'))) AS step_pairs
  FROM
      flaky_build_groups AS fbg
    CROSS JOIN
      UNNEST(fbg.failed_builds) AS failed_build ),

  # tests is to find ALL the tests that meet either condition below
  #   * Failed in any test step "with patch". In this step type, a test is
  #     failed if there is no successful run even in test-runner-level retries.
  #   * Failed in any test step "retry with patch". In this step type, a test is
  #     failed if there is any failed run even in test-runner-level retries.
  #   * Passed in any test step "without patch". In this step type, a test is
  #     passed if there is no failed run even in test-runner-level retries.
  #
  # It is possible to reduce the data volume with a whitelist of master names.
  tests AS (
  SELECT
    *
  FROM (
    SELECT
      # Convert build_id to integer for better performance in joining.
      CAST(build_id AS INT64) AS build_id,
      REGEXP_REPLACE(
        step_name, ' \\((with patch|without patch|retry with patch)\\).*', ''
      ) AS normalized_step_name,
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
      # Ignore disabled tests and tests with 'UNKNOWN' or 'NOTRUN' statuses.
      AND NOT EXISTS (SELECT *
                      FROM UNNEST(run.actual) AS x
                      WHERE x IN UNNEST(['SKIP', 'UNKNOWN', 'NOTRUN'])))
  WHERE
    # For tests with patch, they failed if there is no success.
    (step_name like '%(with patch)%' AND num_expected_runs = 0)
    # For tests without patch, they passed if there is no failure.
    OR (step_name like '%(without patch)%' AND
      num_expected_runs = ARRAY_LENGTH(actual))
    # For tests retry with patch, they failed if there is any failure.
    OR (step_name like '%(retry with patch)%' AND
      num_expected_runs != ARRAY_LENGTH(actual))
  ),

  # flaky_tests is to find the failed tests in flaky test steps (with patch).
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
        WHEN step_pair.normalized_step_name = test.normalized_step_name AND test.step_name like '%(with patch)%' THEN
          test
        ELSE NULL  # NULL is ignored by ANY_VALUE.
      END) AS test_run,
    step_pair.step_name_with_patch AS step_ui_name
  FROM
    flaky_test_step_groups AS build
  CROSS JOIN
    UNNEST(build.step_pairs) AS step_pair
  INNER JOIN tests AS test
  ON
    build.build_id = test.build_id
    AND step_pair.normalized_step_name = test.normalized_step_name
  GROUP BY
    build.build_id,
    step_pair.step_name_with_patch,
    test.test_name
  HAVING
    # When the test step opts out to NOT run "retry with patch", the flaky tests
    # are those:
    #   * Failing in "with patch"
    #   * Passing in "without patch"
    # When the test step opts in (by default) to run "retry with patch", the
    # flaky tests are those:
    #   * Failing in "with patch"
    #   * Passing in "without patch"
    #   * Failing in "retry with patch"
    # We have to check the test results in all steps because even a consistent
    # failing tests could still run in "retry with patch" according to
    # https://chromium.googlesource.com/chromium/tools/build/+/dd38309/scripts/slave/recipe_modules/chromium_tests/steps.py#1352
    LOGICAL_OR(test.step_name LIKE '%(with patch)%')
    AND LOGICAL_OR(test.step_name LIKE '%(without patch)%')
    AND LOGICAL_OR(
      test.step_name LIKE '%(retry with patch)%'
      OR
      (step_pair.step_name_retry_with_patch IS NULL AND
        EXISTS(
          SELECT * FROM test_types_without_retry_with_patch
          WHERE name = REGEXP_EXTRACT(test.step_name, r"^[^ ]+")))))

SELECT
  ## Refer to individual fields to avoid duplicate fields.
  entire_build.cq_name,
  # Info about the patch.
  entire_build.gerrit_change.host AS gerrit_host,
  # Buildbucket does not populate gerrit_change.project yet.
  IF(entire_build.gerrit_change.project IS NOT NULL AND entire_build.gerrit_change.project != '', entire_build.gerrit_change.project, entire_build.patch_project) AS gerrit_project,
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
