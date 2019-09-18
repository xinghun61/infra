CREATE OR REPLACE VIEW `APP_ID.events.sheriffable_failures`
AS
/*
Sheriffable failures table.
This view represents a set of steps that are currently failing,
and for each includes information about when (commit position, build number)
the step began failing in the latest run of failures.
This is the view that the bigquery analyzer will poll to collect alertable failures.

A simplified diagram of the values we care about for a particular failing step:

Commit Pos +---------------------------------+
              |-----| Culprit CP Range

Build ID   +--+     +  -    - - --     -- -+
              ^     ^                      ^
              |     |                      |
              |     |                      |
    Last Pass +     + First Fail           + Latest Fail

                    |----------------------| Failing Build Range

Things to note:
- Culprit CP range should bound the range of commits that contains
  the culprit causing the current range of build failures.
- Failing Build Range should end with the latest build (otherwise if
  the latest build is passing, we shouldn't have an alert to generate),
  and begin with the earliest failing build of the same build step in
  the latest run of failures for that step.
- Commit Positions usually increment more frequently than Build IDs.
- Builds can contain multiple commits. So a build that fails after a passing
  build may contain multiple commits, any one or a subset of which could be
  the culprit.
- Identifying a culprit range requires us to look at the build immediately
  preceeding the earliest failure to find its set of commits.

Complications and breaks with reality from the above:

Build Numbers:
Many chromium project builders still use Build *numbers*, which are a hold-over
from buildbot times. References to these still appear in various places in
the sheriff-o-matic code and the Milo UI. Importantly, build numbers are
monotonically *increasing*, while the newer buildbucket IDs are *decreasing*.
This may lead to some confusion when trying to grok any bits of code
that try to sort failures.

Commit Positions:
"Commit Pos" is the gold standard for ordering builds. It is guaranteed by
gnumd to be monotonically increasing for a given repo. However, some projects
do not have commit positions implemented, so we must rely instead on the
order of Build IDs and the assumption that Build IDs form at least a partial
ordering on commits: So Build ID N contains commits that landed prior to
commits contained in Build ID N-1 (Build IDs descend with age).  If this
assumption does not hold (e.g. official builders who build from multiple
branches on the same builder) the results may be meaningless or at least
inconsistent.

TODO: Deal with commit ranges in the absence of commit position data.
If commit positions are not implemented, we should probalby look at
the build preceeding the the earliest failure *by two* (not just the
immediately preceednig build).  This is so we can be sure we cover the
entire range of possible culprit commits. Since we don't know the order
of commits within the latest passing build, we have to start with
any of the commits in the build right *before* it.

Builds may refer to at least two types of commit positions, contained in
either input properties or output properties.  We generally prefer
to assume the output properties contain the commit positions we want,
but in some cases may fall back to using build input properties to
find it.  This varies from project to project.
*/

WITH
  latest_failure_transitions AS (
  SELECT
    s.project,
    s.bucket,
    s.builder,
    s.mastername,
    s.step_name,
    # Latest, meaning sort by commit position if it exists, then by build ID (ascending), otherwise by the build number.
    ARRAY_AGG(s
    ORDER BY
      s.output_commit.position DESC, id, number DESC
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
  s.test_names_fp as TestNamesFingerprint,
  s.test_names_trunc as TestNamesTrunc,
  s.num_tests as NumTests,
  t.latest.id AS BuildIdBegin,
  s.build_id AS BuildIdEnd,
  t.latest.number AS BuildNumberBegin,
  s.number AS BuildNumberEnd,
  t.latest.previous_output_commit AS CPRangeOutputBegin,
  t.latest.previous_input_commit AS CPRangeInputBegin,
  t.latest.output_commit AS CPRangeOutputEnd,
  t.latest.input_commit AS CPRangeInputEnd,
  t.latest.previous_id as CulpritIdRangeBegin,
  t.latest.id as CulpritIdRangeEnd,
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
