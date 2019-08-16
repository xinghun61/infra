CREATE OR REPLACE VIEW `APP_ID.events.failing_steps`
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
      # Latest, meaning sort by commit position if it exists, otherwise by the build number.
      b.output.gitiles_commit.position DESC, number DESC
    LIMIT
      1)[
  OFFSET
    (0)] latest
  FROM
    `cr-buildbucket.builds.completed_BETA` AS b
  WHERE
    create_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  GROUP BY
    1,
    2,
    3,
    4 )
SELECT
  project,
  bucket,
  builder,
  latest.number,
  b.latest.id,
  JSON_EXTRACT_SCALAR(latest.input.properties,
    "$.mastername") AS mastername,
  b.latest.output.gitiles_commit,
  b.latest.input.gitiles_commit input_commit,
  s.name step
FROM
  latest_builds b,
  b.latest.steps s
WHERE
  b.latest.status = 'FAILURE'
  AND s.status = 'FAILURE'
