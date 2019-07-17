/*
Sheriffable failures table.
This view represents a set of steps that are currently failing,
and for each includes information about when (commit position, build number)
the step began failing in the latest run of failures.
This is the view that the bigquery analyzer will poll to collect alertable failures.
*/
CREATE OR REPLACE VIEW `APP_ID.events.sheriffable_failures`
AS
WITH
  latest_failure_transitions AS (
  SELECT
    s.project,
    s.bucket,
    s.builder,
    s.number,
    s.end_time,
    s.step_name,
    s.previous_status,
    s.step_status,
    s.gitiles_commit.host AS git_host,
    s.gitiles_commit.project AS git_project,
    s.gitiles_commit.ref AS git_ref,
    s.gitiles_commit.id AS git_id,
    MAX(s.previous_position) AS previous_position,
    MAX(s.gitiles_commit.position) AS current_position
  FROM
    `APP_ID.events.step_status_transitions` s
  WHERE
    s.step_status = 'FAILURE'
    AND s.previous_status = 'SUCCESS'
  GROUP BY
    project,
    bucket,
    builder,
    number,
    end_time,
    step_name,
    previous_status,
    step_status,
    git_host,
    git_project,
    git_ref,
    git_id)
SELECT
  f.project AS Project,
  f.bucket AS Bucket,
  f.builder AS Builder,
  s.mastername AS MasterName,
  f.step_name AS StepName,
  MAX(f.number) AS BuildRangeBegin,
  s.number AS BuildRangeEnd,
  MAX(f.previous_position) AS CPRangeBegin,
  MAX(f.current_position) AS CPRangeEnd,
  MAX(f.end_time) AS StartTime,
  s.gitiles_commit.project AS GitProject,
  s.gitiles_commit.ref AS GitRef,
  s.gitiles_commit.host AS GitHost
FROM
  `sheriff-o-matic-staging.events.failing_steps` s
JOIN
  latest_failure_transitions f
ON
  s.project = f.project
  AND s.bucket = f.bucket
  AND s.builder = f.builder
  AND s.step = f.step_name
GROUP BY
  Project,
  Bucket,
  Builder,
  MasterName,
  StepName,
  BuildRangeEnd,
  GitProject,
  GitRef,
  GitHost;
