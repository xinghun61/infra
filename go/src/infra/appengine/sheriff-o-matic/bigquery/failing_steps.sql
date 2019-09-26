CREATE OR REPLACE VIEW `APP_ID.PROJECT_NAME.failing_steps`
AS
/*
Failing steps table.
Each row represents a step that has failed in the most recent run of the
given builder (bucket, project etc).
As the status of the build system changes, so should the contents of this
view.
*/
WITH
  latest_builds AS (
  SELECT
    b.builder.project,
    b.builder.bucket,
    b.builder.builder,
    JSON_EXTRACT_SCALAR(input.properties,
      "$.mastername") AS mastername,
    ARRAY_AGG(b
    ORDER BY
      # Latest, meaning sort by commit position if it exists, otherwise by the build id or number.
      b.output.gitiles_commit.position DESC, id, number DESC
    LIMIT
      1)[
  OFFSET
    (0)] latest
  FROM
    `cr-buildbucket.PROJECT_NAME.builds` AS b
  WHERE
    create_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  GROUP BY
    1,
    2,
    3,
    4),
  recent_tests AS (
  SELECT
    tr.build_id,
    tr.step_name,
    tr.path,
    tr.run
  FROM
    `test-results-hrd.events.test_results` tr
  WHERE
    # Add extra conditions to filter for actual unexpectedly failing tests.
    # As-is, this may pick up tests that have unexpected results but do not
    # represent actual "failures".
    tr.run.is_unexpected
    # This is limited to 1 day of test results because this table is huge
    # and will cost a lot of money to scan for longer periods of time.
    # Increase this INTERVAL value only if it turns out that we need test
    # results from futher than 1 day back in practice.
    AND _PARTITIONTIME > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 DAY) )
SELECT
  project,
  bucket,
  builder,
  latest.number,
  b.latest.id build_id,
  JSON_EXTRACT_SCALAR(latest.input.properties,
    "$.mastername") AS mastername,
  s.name step,
  ANY_VALUE(b.latest.output.gitiles_commit) output_commit,
  ANY_VALUE(b.latest.input.gitiles_commit) input_commit,
  FARM_FINGERPRINT(STRING_AGG(tr.path, "\n"
    ORDER BY
      tr.path)) AS test_names_fp,
  STRING_AGG(tr.path, "\n"
  ORDER BY
    tr.path
  LIMIT
    40) AS test_names_trunc,
  COUNT(tr.path) AS num_tests
FROM
  latest_builds b,
  b.latest.steps s
LEFT OUTER JOIN
  recent_tests tr
ON
  SAFE_CAST(tr.build_id AS int64) = b.latest.id
  AND tr.step_name = s.name
WHERE
  b.latest.status = 'FAILURE'
  AND s.status = 'FAILURE'
GROUP BY
  1,
  2,
  3,
  4,
  5,
  6,
  7
