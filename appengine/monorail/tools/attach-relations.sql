-- Copyright 2016 The Chromium Authors. All Rights Reserved.
--
-- Use of this source code is governed by a BSD-style
-- license that can be found in the LICENSE file or at
-- https://developers.google.com/open-source/licenses/bsd


DROP PROCEDURE IF EXISTS AttachDanglingRelations;

delimiter //

CREATE PROCEDURE AttachDanglingRelations()
BEGIN
  DROP TEMPORARY TABLE IF EXISTS temp_relations;

  CREATE TEMPORARY TABLE temp_relations (
    old_issue_id INT,
    old_dst_issue_project VARCHAR(80) COLLATE utf8_unicode_ci,
    old_dst_issue_local_id INT,
    old_kind enum('blockedon','blocking','mergedinto') COLLATE utf8_unicode_ci,
    new_issue_id INT,
    new_dst_issue_id INT,
    new_kind enum('blockedon','blocking','mergedinto') COLLATE utf8_unicode_ci
  );

  INSERT INTO temp_relations
  SELECT
    dir.issue_id AS old_issue_id,
    dir.dst_issue_project AS old_dst_issue_project,
    dir.dst_issue_local_id AS old_dst_issue_local_id,
    dir.kind AS old_kind,
    dir.issue_id AS new_issue_id,
    i.id AS new_dst_issue_id,
    dir.kind AS new_kind
  FROM Issue i
  JOIN Project p
  ON i.project_id=p.project_id
  JOIN DanglingIssueRelation dir
  ON dir.dst_issue_local_id=i.local_id
  AND dir.dst_issue_project=p.project_name
  WHERE dir.kind='blockedon';

  INSERT INTO temp_relations
  SELECT
    dir.issue_id AS old_issue_id,
    dir.dst_issue_project AS old_dst_issue_project,
    dir.dst_issue_local_id AS old_dst_issue_local_id,
    dir.kind AS old_kind,
    dir.issue_id AS new_issue_id,
    i.id AS new_dst_issue_id,
    dir.kind AS new_kind
  FROM Issue i
  JOIN Project p
  ON i.project_id=p.project_id
  JOIN DanglingIssueRelation dir
  ON dir.dst_issue_local_id=i.local_id
  AND dir.dst_issue_project=p.project_name
  WHERE dir.kind='mergedinto';

  INSERT INTO temp_relations
  SELECT
    dir.issue_id AS old_issue_id,
    dir.dst_issue_project AS old_dst_issue_project,
    dir.dst_issue_local_id AS old_dst_issue_local_id,
    dir.kind AS old_kind,
    i.id AS new_issue_id,
    dir.issue_id AS new_dst_issue_id,
    'blockedon' AS new_kind
  FROM Issue i
  JOIN Project p
  ON i.project_id=p.project_id
  JOIN DanglingIssueRelation dir
  ON dir.dst_issue_local_id=i.local_id
  AND dir.dst_issue_project=p.project_name
  WHERE dir.kind='blocking';

  INSERT IGNORE INTO IssueRelation
  SELECT new_issue_id, new_dst_issue_id, new_kind
  FROM temp_relations;

  DELETE from DanglingIssueRelation
  WHERE EXISTS (
    SELECT NULL FROM temp_relations
    WHERE issue_id=old_issue_id
    AND dst_issue_project=old_dst_issue_project
    AND dst_issue_local_id=old_dst_issue_local_id
    AND kind=old_kind
  );

END;
//

delimiter ;
