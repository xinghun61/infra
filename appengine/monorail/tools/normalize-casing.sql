-- Copyright 2016 The Chromium Authors. All Rights Reserved.
--
-- Use of this source code is governed by a BSD-style
-- license that can be found in the LICENSE file or at
-- https://developers.google.com/open-source/licenses/bsd


DROP PROCEDURE IF EXISTS InspectStatusCase;
DROP PROCEDURE IF EXISTS CleanupStatusCase;
DROP PROCEDURE IF EXISTS InspectLabelCase;
DROP PROCEDURE IF EXISTS CleanupLabelCase;
DROP PROCEDURE IF EXISTS InspectPermissionCase;
DROP PROCEDURE IF EXISTS CleanupPermissionCase;
DROP PROCEDURE IF EXISTS InspectComponentCase;
DROP PROCEDURE IF EXISTS CleanupComponentCase;
DROP PROCEDURE IF EXISTS CleanupCase;

delimiter //

CREATE PROCEDURE InspectStatusCase(IN in_pid SMALLINT UNSIGNED)
BEGIN
  DECLARE done INT DEFAULT FALSE;

  DECLARE c_id INT;
  DECLARE c_pid SMALLINT UNSIGNED;
  DECLARE c_status VARCHAR(80) BINARY;

  DECLARE curs CURSOR FOR SELECT id, project_id, status FROM StatusDef WHERE project_id=in_pid AND rank IS NOT NULL ORDER BY rank;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;

  OPEN curs;

  wks_loop: LOOP
    FETCH curs INTO c_id, c_pid, c_status;
    IF done THEN
      LEAVE wks_loop;
    END IF;

    -- This is the canonical capitalization of the well-known status.
    SELECT c_status AS 'Processing:';

    -- Alternate forms are a) in the same project, and b) spelled the same,
    -- but c) not the same exact status.
    DROP TEMPORARY TABLE IF EXISTS alt_ids;
    CREATE TEMPORARY TABLE alt_ids (id INT);
    INSERT INTO alt_ids SELECT id FROM StatusDef WHERE project_id=c_pid AND status COLLATE UTF8_GENERAL_CI LIKE c_status AND id!=c_id;
    SELECT status AS 'Alternate forms:' FROM StatusDef WHERE id IN (SELECT id FROM alt_ids);
    SELECT id AS 'Offending issues:' FROM Issue WHERE status_id IN (SELECT id FROM alt_ids);
  END LOOP;

  CLOSE curs;
END;
//

CREATE PROCEDURE CleanupStatusCase(IN in_pid SMALLINT UNSIGNED)
BEGIN
  DECLARE done INT DEFAULT FALSE;

  DECLARE c_id INT;
  DECLARE c_pid SMALLINT UNSIGNED;
  DECLARE c_status VARCHAR(80) BINARY;

  DECLARE curs CURSOR FOR SELECT id, project_id, status FROM StatusDef WHERE project_id=in_pid AND rank IS NOT NULL ORDER BY rank;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;

  OPEN curs;

  wks_loop: LOOP
    FETCH curs INTO c_id, c_pid, c_status;
    IF done THEN
      LEAVE wks_loop;
    END IF;

    SELECT c_status AS 'Processing:';
    DROP TEMPORARY TABLE IF EXISTS alt_ids;
    CREATE TEMPORARY TABLE alt_ids (id INT);
    INSERT INTO alt_ids SELECT id FROM StatusDef WHERE project_id=c_pid AND status COLLATE UTF8_GENERAL_CI LIKE c_status AND id!=c_id;

    -- Fix offending issues first, to avoid foreign key constraints.
    UPDATE Issue SET status_id=c_id WHERE status_id IN (SELECT id FROM alt_ids);

    -- Then remove the alternate status definitions.
    DELETE FROM StatusDef WHERE id IN (SELECT id FROM alt_ids);
  END LOOP;

  CLOSE curs;
END;
//

CREATE PROCEDURE InspectLabelCase(IN in_pid SMALLINT UNSIGNED)
BEGIN
  DECLARE done INT DEFAULT FALSE;

  DECLARE c_id INT;
  DECLARE c_pid SMALLINT UNSIGNED;
  DECLARE c_label VARCHAR(80) BINARY;

  DECLARE curs CURSOR FOR SELECT id, project_id, label FROM LabelDef WHERE project_id=in_pid AND rank IS NOT NULL ORDER BY rank;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;

  OPEN curs;

  wkl_loop: LOOP
    FETCH curs INTO c_id, c_pid, c_label;
    IF done THEN
      LEAVE wkl_loop;
    END IF;

    -- This is the canonical capitalization of the well-known label.
    SELECT c_label AS 'Processing:';

    -- Alternate forms are a) in the same project, and b) spelled the same,
    -- but c) not the same exact label.
    DROP TEMPORARY TABLE IF EXISTS alt_ids;
    CREATE TEMPORARY TABLE alt_ids (id INT);
    INSERT INTO alt_ids SELECT id FROM LabelDef WHERE project_id=c_pid AND label COLLATE UTF8_GENERAL_CI LIKE c_label AND id!=c_id;
    SELECT label AS 'Alternate forms:' FROM LabelDef WHERE id IN (SELECT id FROM alt_ids);
    SELECT issue_id AS 'Offending issues:' FROM Issue2Label WHERE label_id IN (SELECT id FROM alt_ids);
  END LOOP;

  CLOSE curs;
END;
//

CREATE PROCEDURE CleanupLabelCase(IN in_pid SMALLINT UNSIGNED)
BEGIN
  DECLARE done INT DEFAULT FALSE;

  DECLARE c_id INT;
  DECLARE c_pid SMALLINT UNSIGNED;
  DECLARE c_label VARCHAR(80) BINARY;

  DECLARE curs CURSOR FOR SELECT id, project_id, label FROM LabelDef WHERE project_id=in_pid AND rank IS NOT NULL ORDER BY rank;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;

  OPEN curs;

  wkl_loop: LOOP
    FETCH curs INTO c_id, c_pid, c_label;
    IF done THEN
      LEAVE wkl_loop;
    END IF;

    SELECT c_label AS 'Processing:';
    DROP TEMPORARY TABLE IF EXISTS alt_ids;
    CREATE TEMPORARY TABLE alt_ids (id INT);
    INSERT INTO alt_ids SELECT id FROM LabelDef WHERE project_id=c_pid AND label COLLATE UTF8_GENERAL_CI LIKE c_label AND id!=c_id;

    -- Fix offending issues first, to avoid foreign key constraints.
    -- DELETE after UPDATE IGNORE to catch issues with two spellings.
    UPDATE IGNORE Issue2Label SET label_id=c_id WHERE label_id IN (SELECT id FROM alt_ids);
    DELETE FROM Issue2Label WHERE label_id IN (SELECT id FROM alt_ids);

    -- Then remove the alternate label definitions.
    DELETE FROM LabelDef WHERE id IN (SELECT id FROM alt_ids);
  END LOOP;

  CLOSE curs;
END;
//

CREATE PROCEDURE InspectPermissionCase(IN in_pid SMALLINT UNSIGNED)
BEGIN
  DECLARE done INT DEFAULT FALSE;

  DECLARE c_id INT;
  DECLARE c_pid SMALLINT UNSIGNED;
  DECLARE c_label VARCHAR(80) BINARY;

  -- This crazy query takes the Actions table (defined below) and combines it
  -- with the set of all permissions granted in the project to construct a list
  -- of all possible Restrict-Action-Permission labels. It then combines that
  -- with LabelDef to see which ones are actually used (whether or not they are
  -- also defined as well-known labels).
  DECLARE curs CURSOR FOR SELECT LabelDef.id, LabelDef.project_id, RapDef.label FROM (
      SELECT DISTINCT CONCAT_WS('-', 'Restrict', Actions.action, ExtraPerm.perm)
      AS label FROM ExtraPerm, Actions where ExtraPerm.project_id=16) AS RapDef
    LEFT JOIN LabelDef
    ON BINARY RapDef.label = BINARY LabelDef.label
    WHERE LabelDef.project_id=in_pid;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;

  DROP TEMPORARY TABLE IF EXISTS Actions;
  CREATE TEMPORARY TABLE Actions (action VARCHAR(80));
  INSERT INTO Actions (action) VALUES ('View'), ('EditIssue'), ('AddIssueComment'), ('DeleteIssue'), ('ViewPrivateArtifact');

  OPEN curs;

  perm_loop: LOOP
    FETCH curs INTO c_id, c_pid, c_label;
    IF done THEN
      LEAVE perm_loop;
    END IF;

    -- This is the canonical capitalization of the permission.
    SELECT c_label AS 'Processing:';

    -- Alternate forms are a) in the same project, and b) spelled the same,
    -- but c) not the same exact label.
    DROP TEMPORARY TABLE IF EXISTS alt_ids;
    CREATE TEMPORARY TABLE alt_ids (id INT);
    INSERT INTO alt_ids SELECT id FROM LabelDef WHERE project_id=c_pid AND label COLLATE UTF8_GENERAL_CI LIKE c_label AND id!=c_id;
    SELECT label AS 'Alternate forms:' FROM LabelDef WHERE id IN (SELECT id FROM alt_ids);
    SELECT issue_id AS 'Offending issues:' FROM Issue2Label WHERE label_id IN (SELECT id FROM alt_ids);
  END LOOP;

  CLOSE curs;
END;
//

CREATE PROCEDURE CleanupPermissionCase(IN in_pid SMALLINT UNSIGNED)
BEGIN
  DECLARE done INT DEFAULT FALSE;

  DECLARE c_id INT;
  DECLARE c_pid SMALLINT UNSIGNED;
  DECLARE c_label VARCHAR(80) BINARY;

  -- This crazy query takes the Actions table (defined below) and combines it
  -- with the set of all permissions granted in the project to construct a list
  -- of all possible Restrict-Action-Permission labels. It then combines that
  -- with LabelDef to see which ones are actually used (whether or not they are
  -- also defined as well-known labels).
  DECLARE curs CURSOR FOR SELECT LabelDef.id, LabelDef.project_id, RapDef.label FROM (
      SELECT DISTINCT CONCAT_WS('-', 'Restrict', Actions.action, ExtraPerm.perm)
      AS label FROM ExtraPerm, Actions where ExtraPerm.project_id=16) AS RapDef
    LEFT JOIN LabelDef
    ON BINARY RapDef.label = BINARY LabelDef.label
    WHERE LabelDef.project_id=in_pid;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;

  DROP TEMPORARY TABLE IF EXISTS Actions;
  CREATE TEMPORARY TABLE Actions (action VARCHAR(80));
  INSERT INTO Actions (action) VALUES ('View'), ('EditIssue'), ('AddIssueComment'), ('DeleteIssue'), ('ViewPrivateArtifact');

  OPEN curs;

  perm_loop: LOOP
    FETCH curs INTO c_id, c_pid, c_label;
    IF done THEN
      LEAVE perm_loop;
    END IF;

    -- This is the canonical capitalization of the permission.
    SELECT c_label AS 'Processing:';

    -- Alternate forms are a) in the same project, and b) spelled the same,
    -- but c) not the same exact label.
    DROP TEMPORARY TABLE IF EXISTS alt_ids;
    CREATE TEMPORARY TABLE alt_ids (id INT);
    INSERT INTO alt_ids SELECT id FROM LabelDef WHERE project_id=c_pid AND label COLLATE UTF8_GENERAL_CI LIKE c_label AND id!=c_id;

    -- Fix offending issues first, to avoid foreign key constraings.
    -- DELETE after UPDATE IGNORE to catch issues with two spellings.
    UPDATE IGNORE Issue2Label SET label_id=c_id WHERE label_id IN (SELECT id FROM alt_ids);
    DELETE FROM Issue2Label WHERE label_id IN (SELECT id FROM alt_ids);

    -- Then remove the alternate label definitions.
    DELETE FROM LabelDef WHERE id IN (SELECT id FROM alt_ids);
  END LOOP;

  CLOSE curs;

  -- Remove ExtraPerm rows where the user isn't a member of the project.
  DELETE FROM ExtraPerm WHERE project_id=in_pid AND user_id NOT IN (
    SELECT user_id FROM User2Project WHERE project_id=in_pid);
END;
//

CREATE PROCEDURE InspectComponentCase(IN in_pid SMALLINT UNSIGNED)
BEGIN
  DECLARE done INT DEFAULT FALSE;

  DECLARE c_id INT;
  DECLARE c_pid SMALLINT UNSIGNED;
  DECLARE c_path VARCHAR(80) BINARY;

  DECLARE curs CURSOR FOR SELECT id, project_id, path FROM ComponentDef WHERE project_id=in_pid AND docstring IS NOT NULL ORDER BY path;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;

  OPEN curs;

  wks_loop: LOOP
    FETCH curs INTO c_id, c_pid, c_path;
    IF done THEN
      LEAVE wks_loop;
    END IF;

    -- This is the canonical capitalization of the component path.
    SELECT c_path AS 'Processing:';

    -- Alternate forms are a) in the same project, and b) spelled the same,
    -- but c) not the same exact path.
    DROP TEMPORARY TABLE IF EXISTS alt_ids;
    CREATE TEMPORARY TABLE alt_ids (id INT);
    INSERT INTO alt_ids SELECT id FROM ComponentDef WHERE project_id=c_pid AND path COLLATE UTF8_GENERAL_CI LIKE c_path AND id!=c_id;
    SELECT path AS 'Alternate forms:' FROM ComponentDef WHERE id IN (SELECT id FROM alt_ids);
    SELECT issue_id AS 'Offending issues:' FROM Issue2Component WHERE component_id IN (SELECT id FROM alt_ids);
  END LOOP;

  CLOSE curs;
END;
//

CREATE PROCEDURE CleanupComponentCase(IN in_pid SMALLINT UNSIGNED)
BEGIN
  DECLARE done INT DEFAULT FALSE;

  DECLARE c_id INT;
  DECLARE c_pid SMALLINT UNSIGNED;
  DECLARE c_path VARCHAR(80) BINARY;

  DECLARE curs CURSOR FOR SELECT id, project_id, path FROM ComponentDef WHERE project_id=in_pid AND docstring IS NOT NULL ORDER BY path;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;

  OPEN curs;

  wks_loop: LOOP
    FETCH curs INTO c_id, c_pid, c_path;
    IF done THEN
      LEAVE wks_loop;
    END IF;

    SELECT c_path AS 'Processing:';
    DROP TEMPORARY TABLE IF EXISTS alt_ids;
    CREATE TEMPORARY TABLE alt_ids (id INT);
    INSERT INTO alt_ids SELECT id FROM ComponentDef WHERE project_id=c_pid AND path COLLATE UTF8_GENERAL_CI LIKE c_path AND id!=c_id;

    -- Fix offending issues first, to avoid foreign key constraints.
    -- DELETE after UPDATE IGNORE to catch issues with two spellings.
    UPDATE IGNORE Issue2Component SET component_id=c_id WHERE component_id IN (SELECT id FROM alt_ids);
    DELETE FROM Issue2Component WHERE component_id IN (SELECT id FROM alt_ids);

    -- Then remove the alternate path definitions.
    DELETE FROM ComponentDef WHERE id IN (SELECT id FROM alt_ids);
  END LOOP;

  CLOSE curs;
END;
//


CREATE PROCEDURE CleanupCase(IN in_pid SMALLINT UNSIGNED)
BEGIN
  CALL CleanupStatusCase(in_pid);
  CALL CleanupLabelCase(in_pid);
  CALL CleanupPermissionCase(in_pid);
  CALL CleanupComponentCase(in_pid);
END;
//


delimiter ;
