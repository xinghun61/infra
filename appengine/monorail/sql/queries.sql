-- Copyright 2016 The Chromium Authors. All Rights Reserved.
--
-- Use of this source code is governed by a BSD-style
-- license that can be found in the LICENSE file or at
-- https://developers.google.com/open-source/licenses/bsd


-- Example queries for common operations.

use monorail;

-- --------------------------
-- PROJECT-RELATED QUERIES

-- Look up the id of the project mention in the URL, and get info to display
-- in the page header.
SELECT project_id, summary, state, access
FROM Project
WHERE project_name = 'projb';

-- Get one project to display on the project home page.
SELECT summary, description, state, access
FROM Project
WHERE project_id = 1002;

-- Get the list of members in a project for the project peoeple list page.
SELECT email, role_name
FROM User2Project NATURAL JOIN User
WHERE project_id = 1002
ORDER BY role_name, email;

-- Get the list of all projects where a user has a role for the profile page.
SELECT project_name, role_name
FROM User2Project NATURAL JOIN Project
WHERE user_id = 111 AND state = 'live'
ORDER BY role_name, project_name;


-- TODO: user groups


-- --------------------------
-- ISSUE-RELATED QUERIES

-- Get all issues in a project, ordered by ID, no pagination.
SELECT Issue.*
FROM Issue
WHERE project_id = 1002
ORDER BY Issue.id;

-- Get the second page of issues in a project, ordered by ID. Pagination size is 10.
SELECT Issue.*
FROM Issue
WHERE project_id = 1002
ORDER BY Issue.id
LIMIT 10 OFFSET 10;

-- Get all open issues in a project.
SELECT Issue.*
FROM Issue
    LEFT JOIN StatusDef sd1 ON Issue.project_id = sd1.project_id AND LOWER(Issue.status) = LOWER(sd1.status)
WHERE Issue.project_id = 1002
    AND (sd1.means_open = TRUE OR sd1.means_open IS NULL);    -- this matches oddball or NULL status values

-- Search based on ID.
SELECT Issue.*
FROM Issue
WHERE project_id = 1002 AND Issue.local_id > 8;


-- Search based on status and owner_id.
SELECT Issue.*
FROM Issue
WHERE project_id = 1002 AND LOWER(status) = 'new' AND owner_id = 222;

-- Search based on date modiifed, opened, and closed.
-- TODO: Gives an empty result with the current test data.
SELECT Issue.*
FROM Issue
WHERE project_id = 1002 AND modified > '2011-01-01'
AND opened > '2010-01-01' AND closed > '2010-02-01';


-- Search for has:owner and has:status.
SELECT Issue.*
FROM Issue
WHERE project_id = 1002 AND status != '' AND owner_id IS NOT NULL;


-- All issues in a project that have a label Priority-High
SELECT Issue.*
FROM Issue NATURAL JOIN Issue2Label
WHERE project_id = 1002 AND label = 'Priority-High';

-- All issues in a project that DO NOT have a label Priority-High
SELECT Issue.*
FROM Issue
WHERE project_id = 1002
    AND NOT EXISTS (
        SELECT *
	FROM Issue2Label cond1
 	WHERE cond1.project_id = Issue.project_id AND cond1.id = Issue.id
	    AND label = 'Priority-High');


-- Search based on priority and milestone.
SELECT Issue.*
FROM Issue
    JOIN Issue2Label cond1 ON Issue.project_id = cond1.project_id AND Issue.id = cond1.id
    JOIN Issue2Label cond2 ON Issue.project_id = cond2.project_id AND Issue.id = cond2.id
WHERE Issue.project_id = 1002
    AND LOWER(cond1.label) = 'priority-medium'
    AND LOWER(cond2.label) = 'milestone-1.1';


-- Permissions checked
-- TODO: add additional permissions


-- Get all comments on issue
-- TODO: add some comment test data
SELECT Comment.*
FROM Comment
WHERE project_id = 1002 AND issue.local_id = 3
ORDER BY created;


-- Get non-deleted comments on an issue
-- TODO: add some comment test data
SELECT Comment.*
FROM Comment
WHERE project_id = 1002 AND issue.local_id = 3 AND deleted_by IS NULL
ORDER BY created;

-- Cross-project search
SELECT Issue.*
FROM Issue
    JOIN Issue2Label cond1 ON Issue.project_id = cond1.project_id AND Issue.id = cond1.id
    JOIN Issue2Label cond2 ON Issue.project_id = cond2.project_id AND Issue.id = cond2.id
WHERE LOWER(cond1.label) = 'priority-medium'
    AND LOWER(cond2.label) = 'type-defect';

-- All issues in a project, sorted by milestone.  Milestone order is defined by the rank field of the well-known labels table.
-- Issues with oddball milestones sort lexographcially after issues with well known milestones.
-- Issues which do not have milestone sort last.
-- Note that table sort_N holds the value needed for the Nth sort directive, and table rank_N holds the ranking
-- number of that value, if any.
SELECT Issue.*, sort1.label
FROM Issue
    LEFT JOIN (Issue2Label sort1 LEFT JOIN LabelDef rank1
               ON sort1.project_id = rank1.project_id AND LOWER(sort1.label) = LOWER(rank1.label))
    ON Issue.project_id = sort1.project_id AND Issue.id = sort1.id
        AND sort1.label LIKE 'milestone-%'
WHERE Issue.project_id = 1002
ORDER BY ISNULL(rank1.rank), rank1.rank, ISNULL(sort1.label), LOWER(sort1.label), Issue.id;

-- *Open* issues, sorted by milestone.  Any status that is not known to be closed is considered open.
SELECT Issue.project_id, Issue.local_id, Issue.summary, Issue.status, sort1.label
FROM Issue
    LEFT JOIN (Issue2Label sort1 LEFT JOIN LabelDef rank1
               ON sort1.project_id = rank1.project_id AND LOWER(sort1.label) = LOWER(rank1.label))
    ON Issue.project_id = sort1.project_id AND Issue.id = sort1.id
        AND sort1.label LIKE 'milestone-%'
    LEFT JOIN StatusDef sd1 ON Issue.project_id = sd1.project_id AND LOWER(Issue.status) = LOWER(sd1.status)
WHERE Issue.project_id = 1002
    AND (sd1.means_open = TRUE OR sd1.means_open IS NULL)    -- this matches oddball or NULL status values
ORDER BY ISNULL(rank1.rank), rank1.rank, ISNULL(sort1.label), LOWER(sort1.label),
      	 Issue.id;  -- tie breaker

-- *Open* issues, sorted by status.  Any status that is not known to be closed is considered open.
SELECT Issue.*
FROM Issue
    LEFT JOIN StatusDef rank1 ON Issue.project_id = rank1.project_id AND LOWER(Issue.status) = LOWER(rank1.status)
    LEFT JOIN StatusDef sr1 ON Issue.project_id = sr1.project_id AND LOWER(Issue.status) = LOWER(sr1.status)
WHERE Issue.project_id = 1002
    AND (sr1.means_open = TRUE or sr1.means_open IS NULL)    -- this matches oddball or NULL status values
ORDER BY ISNULL(rank1.rank), rank1.rank, ISNULL(Issue.status), LOWER(Issue.status),
      	 Issue.id;  -- tie breaker


-- Realistic query: Open issues with component != printing, sorted by milestone then priority.
SELECT Issue.local_id, Issue.summary, Issue.status, sort1.label, sort2.label
FROM Issue
    LEFT JOIN (Issue2Label sort1 LEFT JOIN LabelDef rank1
               ON sort1.project_id = rank1.project_id AND LOWER(sort1.label) = LOWER(rank1.label))
    ON Issue.project_id = sort1.project_id AND Issue.id = sort1.id
        AND sort1.label LIKE 'mstone-%'
    LEFT JOIN (Issue2Label sort2 LEFT JOIN LabelDef rank2
               ON sort2.project_id = rank2.project_id AND LOWER(sort2.label) = LOWER(rank2.label))
    ON Issue.project_id = sort2.project_id AND Issue.id = sort2.id
        AND sort2.label LIKE 'pri-%'
    LEFT JOIN StatusDef sr1 ON Issue.project_id = sr1.project_id AND LOWER(Issue.status) = LOWER(sr1.status)
WHERE Issue.project_id = 1002
    AND (sr1.means_open = TRUE or sr1.means_open IS NULL)    -- this matches oddball or NULL status values
    AND NOT EXISTS (
        SELECT *
	FROM Issue2Label cond1
	WHERE Issue.project_id = cond1.project_id AND Issue.id = cond1.id
	    AND LOWER(cond1.label) = 'component-printing'
	)
ORDER BY ISNULL(rank1.rank), rank1.rank, ISNULL(sort1.label), LOWER(sort1.label),
         ISNULL(rank2.rank), rank2.rank, ISNULL(sort2.label), LOWER(sort2.label),
      	 Issue.id;  -- tie breaker




