/*
Failing steps table.
Each row represents a step that has failed in the most recent run of the
given builder (bucket, project etc).
As the status of the build system changes, so should the contents of this
view.
*/
CREATE OR REPLACE VIEW `APP_ID.events.failing_steps`
AS
WITH
  latest_builds AS (
  SELECT
    b.builder.project,
    b.builder.bucket,
    b.builder.builder,
    ARRAY_AGG(b
    ORDER BY
      number DESC
    LIMIT
      1)[
  OFFSET
    (0)] latest
  FROM
    `cr-buildbucket.builds.completed_BETA` AS b
  WHERE
    create_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 2 DAY)
  GROUP BY
    1,
    2,
    3 )
SELECT
  project,
  bucket,
  builder,
  latest.number,
  JSON_EXTRACT_SCALAR(latest.input.properties,
    "$.mastername") AS mastername,
  b.latest.output.gitiles_commit,
  s.name step
FROM
  latest_builds b,
  b.latest.steps s
WHERE
  b.latest.status = 'FAILURE'
  AND s.status = 'FAILURE'
  AND latest.output.gitiles_commit.position IS NOT NULL
