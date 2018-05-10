# To query cq-attempt-level false CQ rejections in the past 7 days up to NOW.
#
# False CQ rejection:
# For the same CL/patch, "Submit to CQ" was manually clicked 2+ times to get the
# CL submitted, and those failed CQ attempts are false rejections.
#
# To be more inclusive for analysis:
# 1. This query includes data of CQ "Dry run".
# 2. The concept of equivalent patchset group is introduced. For the same CL,
#    two patchsets are equivalent if there is no code change between them. In
#    other words, Gerrit shows no code diff between the two patchsets. This
#    could happen in the following cases:
#    * A new patchset is generated due to editing the commit message.
#    * A trivial rebase: the files touched by the CL are not changed between the
#      two base commits of the two patchsets.
#      Example: https://chromium-review.googlesource.com/c/chromium/src/+/1000000/2..3
#    This is represented by the cq_attempts.earliest_equivalent_patchset.

WITH
  # Group CQ attempts by cq_name/CL/earliest_equivalent_patchset.
  patch_groups AS (
  SELECT
    cq_name,
    issue,
    (CASE
        WHEN earliest_equivalent_patchset IS NOT NULL THEN
          # Integer type. Added on April 5, 2018.
          CAST(earliest_equivalent_patchset AS STRING)
        ELSE patchset  # String type.
      END) AS patchset_group_id,
    ARRAY_AGG(STRUCT(patchset, failed, fail_type)) AS attempts,
    LOGICAL_OR(NOT failed) AS has_success,
    COUNT(*) AS total_attempts
  FROM
    `chrome-infra-events.aggregated.cq_attempts`
  WHERE
    attempt_start_msec >= UNIX_MILLIS(TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 day))
    # Below is for debug reference.
    # AND attempt_start_msec >= UNIX_MILLIS(TIMESTAMP('2018-04-24')) # To test in a time range.
    # AND cq_name = 'chromium/chromium/src'  # To look at a specific commit queue.
    # AND not dry_run  # To exclude CQ dry runs.
    # AND issue = '919044'  # To test against a Chromium CL.
  GROUP BY
    cq_name,
    issue,
    patchset_group_id ),

  # Record the total attempts in each queue.
  total_attempts_by_queue AS (
  SELECT
    cq_name,
    SUM(total_attempts) AS total_attempts
  FROM
    patch_groups
  GROUP BY
    cq_name ),

  # Count false rejections by cq_name/fail_type.
  false_rejections AS (
  SELECT
    cq_name,
    a.fail_type,
    COUNT(*) AS rejected_num
  FROM
    patch_groups AS pg,
    pg.attempts AS a
  WHERE
    # A false rejection is a failed attempt that has matching successful one.
    pg.has_success
    AND a.failed
    # To exclude non-infra-related or non-test-related failed attempts.
    AND a.fail_type NOT IN ('NOT_LGTM',
      'OPEN_DEPENDENCY',
      'MANUAL_CANCEL',
      'NO_SIGNCLA',
      'FAILED_SIGNCLA_REQUEST',
      'MISSING_LGTM',
      'RETRY_QUOTA_EXCEEDED')
  GROUP BY
    cq_name,
    fail_type )

SELECT
  fr.cq_name,
  fr.fail_type,
  FORMAT('%.2f%%', SAFE_DIVIDE(fr.rejected_num, tabq.total_attempts) * 100) AS percentage,
  tabq.total_attempts,
  fr.rejected_num
FROM
  false_rejections AS fr
INNER JOIN
  total_attempts_by_queue AS tabq
ON
  fr.cq_name = tabq.cq_name
ORDER BY
  cq_name ASC,
  percentage DESC
