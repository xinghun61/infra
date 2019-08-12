# To detect flaky tests causing builds to retry failed steps in the past 1 day.
#
# Assumptions for the flake detection in this query are:
# 1. In the same CQ build of a given CL/patchset, if a test failed (with patch),
#    it will get retried (without patch), and if the test passed the (without
#    patch), it will get retried again in (retry with patch).
# 2. In a test step (with patch), a test is a failure if its first run and ALL
#    retries are failures (not PASS and not any expected result).
#    https://chromium.googlesource.com/chromium/tools/build/+/917f9c6/scripts/slave/recipe_modules/test_utils/api.py#328
# 3. In a test step (without patch) and (retry with patch), a test is a failure
#    if its first run or any retry is a failure (not PASS and not any expected
#    result).
#    https://chromium.googlesource.com/chromium/tools/build/+/917f9c6/scripts/slave/recipe_modules/test_utils/api.py#349
#    https://chromium.googlesource.com/chromium/tools/build/+/917f9c6/scripts/slave/recipe_modules/test_utils/api.py#369
#    https://chromium.googlesource.com/chromium/tools/build/+/917f9c6/scripts/slave/recipe_modules/test_utils/util.py#285
# 4. For disabled tests, they should not be run at all and have an empty list or
#    just ['SKIP'] for run.actual of test-results-hrd:events.test_results
#    https://bigquery.cloud.google.com/table/test-results-hrd:events.test_results
#
# A flaky test causing step retries in the same build is a test that:
#   * failed the "test step (with patch)"
#   * passed the "test step (without patch)"
#   * passed the "test step (retry with patch)"
#
# The easiest way to detect such flaky tests is to directly look for the
# succeeded tests in the (retry with patch) test steps, and the correctness is
# based on the assumption that only failed tests from the (with patch) steps,
# but passed in the (without patch) steps are rerun in the corresponding
# (retry with patch) steps, nothing else. However, the assumption is NOT true
# as of 10/3/2018 because if a step has more than 100 test failures, all tests
# (including the succeeded ones) will be retried in the (retry wit patch) steps.
# https://chromium.googlesource.com/chromium/tools/build/+/82e547eb55151c129ec00fd4c912d95c4dd180eb/scripts/slave/recipe_modules/chromium_tests/steps.py#1865
#
# Another way is to get the list of failed tests of (with patch) and
# (retry with patch) test steps and calculate their differences to figure out
# the flaky ones. However, it won't work reliably because  various bugs cause
# the test results of (retry with patch) test steps fail to upload.
# As of 10/3/2018, following query show that there are 333 (retry with patch)
# test steps whose test results were not uploaded successfully.
# https://bigquery.cloud.google.com/savedquery/306162750983:341f2a49768e49e9b758ce2d33862b33.
# For example, 'webkit_layout_tests on Intel GPU on Mac (retry with patch)' step
# on https://ci.chromium.org/b/8933628087027860096.
#
# Given that there is no reliable way to accurately detect such flaky tests,
# this query takes a conservative approach by only looking for (with patch) test
# steps that have succeeded (retry with patch) steps, and this way, the query
# doesn't depend on the test-result upload anymore, because there is NO failed
# tests in these (retry with patch) steps anyway, and all the tests that failed
# in the (with patch), but passed in the (without patch) are valid flakes.

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
    ca.issue),

  # cq_builds is to build up the metadata (builder, steps, etc) for
  # cr-buildbucket builds that are for cq attempts.
  cq_builds AS (
  SELECT
    issue.cq_name,
    issue.issue,
    build.build_id,
    build.gerrit_change,
    build.patch_project,
    build.gitiles_repository,
    build.gitiles_revision_cp,
    build.steps,
    STRUCT(
      build.builder.project,
      build.builder.bucket,
      build.builder.builder) AS builder
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
    build_id = build.build_id),

  # flaky_test_step_pairs is to find pairs of (with patch) and (without patch)
  # test steps whose corresponding (retry with patch) steps are successful.
  # A row here is a CL/patchset_group/patchset/builder/build and the test step
  # pairs within that build.
  flaky_test_step_pairs AS (
  SELECT
    cq_builds.cq_name,
    # Info about the patch.
    cq_builds.patch_project,
    cq_builds.gerrit_change,
    # Info about the code checkouted in the build.
    cq_builds.gitiles_repository,
    cq_builds.gitiles_revision_cp,
    # Info about the build.
    cq_builds.build_id,
    cq_builds.builder,
    (ARRAY(
      SELECT
        AS STRUCT
        # Group (with patch), (without patch) of the same test step by the
        # normalized step name.
        # For ios-simulator, two normalized step names of the SAME build could
        # be "net_unittests (iPad Air 2 iOS 10.0)" and
        # "net_unittests (iPhone 6s iOS 11.2)". Thus, it is wrong to use the
        # test target/type name "net_unittests" for grouping.
        REGEXP_REPLACE(
          step.name, ' [(](with(out)? patch|retry with patch)[)].*', ''
        ) AS normalized_step_name,
        ANY_VALUE(CASE
            WHEN step.name LIKE '%(with patch)%' THEN step.name
            ELSE NULL END) AS step_name_with_patch,
        ANY_VALUE(CASE
            WHEN step.name LIKE '%(without patch)%' THEN step.name
            ELSE NULL END) AS step_name_without_patch
      FROM
        UNNEST(cq_builds.steps) AS step
      WHERE
        step.name LIKE '%(with patch)%'
        OR step.name LIKE '%(without patch)%'
        OR step.name LIKE '%(retry with patch)%'
      GROUP BY
        normalized_step_name
      HAVING
        LOGICAL_OR(step.name LIKE '%(with patch)%'
                   AND step.status = 'FAILURE') AND
        LOGICAL_OR(step.name LIKE '%(without patch)%') AND
        LOGICAL_OR(step.name LIKE '%(retry with patch)%'
                   AND step.status = 'SUCCESS'))) AS step_pairs
  FROM
    cq_builds),

  # failed_tests is to find ALL the failed tests in ALL test steps that are
  # shown as red FAILURES on build pages.
  # It is possible to limit the data further with a whitelist of master names.
  #
  failed_tests AS (SELECT
    # Convert build_id to integer for better performance in joining.
    CAST(build_id AS INT64) AS build_id,
    step_name,
    REGEXP_REPLACE(
      step_name, ' [(]with(out)? patch[)].*', ''
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
    # Ignore disabled tests and tests with 'UNKNOWN' or 'NOTRUN' statuses.
    AND ARRAY_LENGTH(run.actual) > 0
    AND NOT EXISTS (SELECT *
                      FROM UNNEST(run.actual) AS x
                      WHERE x IN UNNEST(['SKIP', 'UNKNOWN', 'NOTRUN']))
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

  # flaky_tests is to find the tests that failed in the (with patch) test steps,
  # but passed in the (without patch) steps.
  # A row here is a CL/patchset_group/patchset/builder/build/step/test and its
  # flaky run.
  flaky_tests AS (
  SELECT
    ANY_VALUE(build) entire_build,
    # The same test result data could be uploaded to BigQuery table multiple
    # times, thus we use ANY_VALUE to dedup here. https://crbug.com/806422
    ANY_VALUE( CASE
        WHEN step_pair.normalized_step_name = failed_test.normalized_step_name THEN
          failed_test
        ELSE NULL  # NULL is ignored by ANY_VALUE.
      END) AS test_run,
    step_pair.step_name_with_patch AS step_ui_name
  FROM
    flaky_test_step_pairs AS build
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
    # Flaky tests are those that failed in the (with patch) test steps, but
    # passed in the (without patch) test steps.
    LOGICAL_OR(failed_test.step_name LIKE '%(with patch)%') AND
    NOT LOGICAL_OR(failed_test.step_name LIKE '%(without patch)%'))

SELECT
  ## Refer to individual fields to avoid duplicate fields.
  entire_build.cq_name,
  # Info about the patch.
  entire_build.gerrit_change.host AS gerrit_host,
  # Buildbucket does not populate gerrit_change.project yet.
  IF(entire_build.gerrit_change.project IS NOT NULL AND entire_build.gerrit_change.project != '', entire_build.gerrit_change.project, entire_build.patch_project) AS gerrit_project,
  entire_build.gerrit_change.change AS gerrit_cl_id,
  entire_build.gerrit_change.patchset AS gerrit_cl_patchset_number,
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
