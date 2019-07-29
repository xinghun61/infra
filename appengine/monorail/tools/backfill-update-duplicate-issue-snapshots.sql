-- Copyright 2019 The Chromium Authors. All Rights Reserved.
--
-- Use of this source code is governed by a BSD-style
-- license that can be found in the LICENSE file or at
-- https://developers.google.com/open-source/licenses/bsd

-- Update all IssueSnapshot rows that incorrectly have their period_end
-- set to the maximum value 4294967295. For all affected rows, this
-- script update them to the period_end time of the rows with same period_start time;
-- if such rows don't exist, update period_end to be the same as period_start.
-- Bug: crbug.com/monorail/6020

CREATE TABLE IssueSnapshotsToUpdate (id INT, issue_id INT, period_start INT UNSIGNED, update_time INT UNSIGNED);

INSERT INTO IssueSnapshotsToUpdate (id, issue_id, period_start, update_time)
    -- Get ids that needs update and append with correct period_end.
    (SELECT ToUpdate.id, IssueSnapshot.issue_id, IssueSnapshot.period_start, IssueSnapshot.period_end
        FROM IssueSnapshot INNER JOIN (
            -- Get correct period_end to update.
            SELECT NeedsUpdate.id, IssueSnapshot.issue_id, IssueSnapshot.period_start, MIN(IssueSnapshot.period_end)
            AS update_time FROM IssueSnapshot
            INNER JOIN (
                -- Get duplicate rows by filtering out the correct rows.
                SELECT id, issue_id, period_start, period_end FROM IssueSnapshot
                WHERE period_end = 4294967295
                AND id NOT IN (
                    -- Get ids of the correct rows.
                    SELECT id FROM IssueSnapshot
                    INNER JOIN (
                        -- Get correct rows for each issue_id that should have max period_end.
                        SELECT issue_id, MAX(period_start) AS maxStart
                        FROM IssueSnapshot
                        WHERE period_end = 4294967295
                        GROUP BY issue_id) AS MaxISTable
                ON IssueSnapshot.issue_id = MaxISTable.issue_id
                AND IssueSnapshot.period_start = MaxISTable.maxStart)
                ) AS NeedsUpdate
            ON NeedsUpdate.issue_id = IssueSnapshot.issue_id
            AND NeedsUpdate.period_start = IssueSnapshot.period_start
            GROUP BY NeedsUpdate.issue_id, IssueSnapshot.period_start
        ) AS ToUpdate
        ON IssueSnapshot.issue_id = ToUpdate.issue_id
        AND IssueSnapshot.period_start = ToUpdate.period_start
        AND IssueSnapshot.period_end = ToUpdate.update_time
    );

UPDATE IssueSnapshot INNER JOIN IssueSnapshotsToUpdate
ON IssueSnapshot.id = IssueSnapshotsToUpdate.id
SET IssueSnapshot.period_end = CASE WHEN IssueSnapshotsToUpdate.update_time = 4294967295
  THEN IssueSnapshotsToUpdate.period_start ELSE IssueSnapshotsToUpdate.update_time END;

DROP TABLE IssueSnapshotsToUpdate;
