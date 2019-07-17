/*
Step status transition table.
This view represents status transitions for build steps over time.
Each row represents a build where the step produced a different status
output that it did in the previous run (on that builder etc).
*/
CREATE OR REPLACE VIEW `APP_ID.events.step_status_transitions`
AS
WITH
  step_lag AS (
  SELECT
    b.end_time AS end_time,
    b.builder.project AS project,
    b.builder.bucket AS bucket,
    b.builder.builder AS builder,
    JSON_EXTRACT_SCALAR(b.input.properties,
      "$.mastername") AS mastername,
    b.number,
    output.gitiles_commit,
    step.name AS step_name,
    step.status AS step_status,
    LAG(step.status) OVER (PARTITION BY b.builder.project, b.builder.bucket, b.builder.builder, b.output.gitiles_commit.host, b.output.gitiles_commit.project, b.output.gitiles_commit.ref, step.name ORDER BY b.output.gitiles_commit.position) AS previous_status,
    LAG(b.output.gitiles_commit.position) OVER (PARTITION BY b.builder.project, b.builder.bucket, b.builder.builder, b.output.gitiles_commit.host, b.output.gitiles_commit.project, b.output.gitiles_commit.ref, step.name ORDER BY b.output.gitiles_commit.position) AS previous_position
  FROM
    `cr-buildbucket.builds.completed_BETA` b,
    UNNEST(steps) AS step
  WHERE
    create_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 2 DAY)
    AND b.output.gitiles_commit.position IS NOT NULL )
SELECT
  end_time,
  project,
  bucket,
  builder,
  mastername,
  number,
  gitiles_commit,
  step_name,
  step_status,
  previous_position,
  previous_status
FROM
  step_lag s
WHERE
  s.previous_status != s.step_status;
