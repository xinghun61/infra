CREATE OR REPLACE VIEW `APP_ID.events.sheriffable_failures`
AS
/*
Sheriffable failures table.
This view represents a set of steps that are currently failing,
and for each includes information about when (commit position, build number)
the step began failing in the latest run of failures.
This is the view that the bigquery analyzer will poll to collect alertable failures.
*/
WITH
  latest_failure_transitions AS (
  SELECT
    s.project,
    s.bucket,
    s.builder,
    s.mastername,
    s.step_name,
    # Latest, meaning sort by output commit position if it exists, otherwise by the build number.
    ARRAY_AGG(s
    ORDER BY
      s.output_commit.position DESC, number DESC
    LIMIT
      1)[
  OFFSET
    (0)] latest
  FROM
    `APP_ID.events.step_status_transitions` s
  WHERE
    s.step_status = 'FAILURE'
    AND s.previous_status = 'SUCCESS'
  GROUP BY
    project,
    bucket,
    builder,
    mastername,
    step_name)
SELECT
  s.project AS Project,
  s.bucket AS Bucket,
  s.builder AS Builder,
  s.mastername AS MasterName,
  s.step AS StepName,
  t.latest.number AS BuildRangeBegin,
  s.number AS BuildRangeEnd,
  t.latest.previous_output_commit AS CPRangeOutputBegin,
  t.latest.previous_input_commit AS CPRangeInputBegin,
  t.latest.output_commit AS CPRangeOutputEnd,
  t.latest.input_commit AS CPRangeInputEnd,
  t.latest.end_time AS StartTime
FROM
  `APP_ID.events.failing_steps` s
  # Deal with steps who have *never* been green by using a left outer join.
  # Include all of the latest failing steps, and for the ones whose beginnings
  # we can identify, include git pos etc. Otherwise just include the current
  # failing step's end git position. Still need to show these to sheriffs.
LEFT OUTER JOIN
  latest_failure_transitions t
ON
  s.project = t.project
  AND s.bucket = t.bucket
  AND s.builder = t.builder
  AND s.step = t.step_name
