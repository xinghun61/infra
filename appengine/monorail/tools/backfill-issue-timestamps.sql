-- Copyright 2016 The Chromium Authors. All Rights Reserved.
--
-- Use of this source code is governed by a BSD-style
-- license that can be found in the LICENSE file or at
-- https://developers.google.com/open-source/licenses/bsd


DROP PROCEDURE IF EXISTS BackfillIssueTimestampsChunk;
DROP PROCEDURE IF EXISTS BackfillIssueTimestampsManyChunks;

delimiter //

CREATE PROCEDURE BackfillIssueTimestampsChunk(
    IN in_pid SMALLINT UNSIGNED, IN in_chunk_size SMALLINT UNSIGNED)
BEGIN

  DECLARE done INT DEFAULT FALSE;

  DECLARE c_issue_id INT;

  DECLARE curs CURSOR FOR
    SELECT id FROM Issue
    WHERE project_id=in_pid
    AND (owner_modified = 0 OR owner_modified IS NULL)
    AND (status_modified = 0 OR status_modified IS NULL)
    AND (component_modified = 0 OR component_modified IS NULL)
    LIMIT in_chunk_size;

  DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;
  OPEN curs;

  issue_loop: LOOP
    FETCH curs INTO c_issue_id;
    IF done THEN
      LEAVE issue_loop;
    END IF;

    -- Indicate progress.
    SELECT c_issue_id AS 'Processing:';

    -- Set the fields to the largest timestamp of any relevant update.
    UPDATE Issue 
    SET 
    owner_modified     = (SELECT MAX(created)
                          FROM IssueUpdate
                          JOIN Comment ON IssueUpdate.comment_id = Comment.id
                          WHERE field = 'owner'
                          AND IssueUpdate.issue_id = c_issue_id),
    status_modified    = (SELECT MAX(created)
                          FROM IssueUpdate
                          JOIN Comment ON IssueUpdate.comment_id = Comment.id
                          WHERE field = 'status'
                          AND IssueUpdate.issue_id = c_issue_id),
    component_modified = (SELECT MAX(created)
                          FROM IssueUpdate
                          JOIN Comment ON IssueUpdate.comment_id = Comment.id
                          WHERE field = 'component'
                          AND IssueUpdate.issue_id = c_issue_id)
    WHERE id = c_issue_id;

    -- If no update was found, use the issue opened timestamp.
    UPDATE Issue SET owner_modified = opened
    WHERE id = c_issue_id AND owner_modified IS NULL;

    UPDATE Issue SET status_modified = opened
    WHERE id = c_issue_id AND status_modified IS NULL;

    UPDATE Issue SET component_modified = opened
    WHERE id = c_issue_id AND component_modified IS NULL;

  END LOOP;

  CLOSE curs;
END;

CREATE PROCEDURE BackfillIssueTimestampsManyChunks(
    IN in_pid SMALLINT UNSIGNED, IN in_num_chunks SMALLINT UNSIGNED)
BEGIN
  WHILE in_num_chunks > 0 DO
    CALL BackfillIssueTimestampsChunk(in_pid, 1000);
    SET in_num_chunks = in_num_chunks - 1;
  END WHILE;
END;


//


delimiter ;

