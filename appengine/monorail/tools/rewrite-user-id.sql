-- Copyright 2019 The Chromium Authors. All Rights Reserved.
--
-- Use of this source code is governed by a BSD-style
-- license that can be found in the LICENSE file or at
-- https://developers.google.com/open-source/licenses/bsd

-- There have been cases of imported data that used the wrong email
-- address for a user.  This script can change all the user_ids in our
-- database from the ID for old_email to the ID for new_email.

DROP PROCEDURE IF EXISTS RewriteUserID;

delimiter //

CREATE PROCEDURE RewriteUserID(
    IN in_old_email VARCHAR(255), IN in_new_email VARCHAR(255))
proc_label:BEGIN
  DECLARE old_id INT UNSIGNED;
  DECLARE new_id INT UNSIGNED;

  IF in_old_email is NULL OR in_old_email = '' THEN
    SELECT CONCAT('in_old_email cannot be null or empty') as ErrorMsg;
    LEAVE proc_label;
  END IF;

  IF in_new_email is NULL OR in_new_email = '' THEN
    SELECT CONCAT('in_new_email cannot be null or empty') as ErrorMsg;
    LEAVE proc_label;
  END IF;

  SET old_id = (SELECT user_id FROM User WHERE email = in_old_email);
  SET new_id = (SELECT user_id FROM User WHERE email = in_new_email);

  IF old_id is NULL THEN
    SELECT CONCAT('User ', in_old_email, ' not found') as ErrorMsg;
    LEAVE proc_label;
  END IF;

  IF new_id is NULL THEN
    SELECT CONCAT('User ', in_new_email, ' not found') as ErrorMsg;
    LEAVE proc_label;
  END IF;

  SELECT CONCAT('Rewriting ', old_id, ' to ', new_id) AS Progress;

  UPDATE Component2Admin SET admin_id = new_id
  WHERE admin_id = old_id LIMIT 1000;

  UPDATE Component2Cc SET cc_id = new_id
  WHERE cc_id = old_id LIMIT 1000;

  UPDATE FieldDef2Admin SET admin_id = new_id
  WHERE admin_id = old_id LIMIT 1000;

  UPDATE Issue SET reporter_id = new_id
  WHERE reporter_id = old_id LIMIT 1000;

  UPDATE Issue SET owner_id = new_id
  WHERE owner_id = old_id LIMIT 1000;

  UPDATE IGNORE Issue2FieldValue SET user_id = new_id
  WHERE user_id = old_id LIMIT 1000;

  UPDATE IGNORE Issue2Cc SET cc_id = new_id
  WHERE cc_id = old_id LIMIT 1000;

  UPDATE IGNORE IssueStar SET user_id = new_id
  WHERE user_id = old_id LIMIT 1000;

  UPDATE Comment SET commenter_id = new_id
  WHERE commenter_id = old_id LIMIT 10000;

  UPDATE IssueUpdate SET added_user_id = new_id
  WHERE added_user_id = old_id LIMIT 10000;

  UPDATE IssueUpdate SET removed_user_id = new_id
  WHERE removed_user_id = old_id LIMIT 10000;

  UPDATE Template SET owner_id = new_id
  WHERE owner_id = old_id LIMIT 1000;

  UPDATE Template2Admin SET admin_id = new_id
  WHERE admin_id = old_id LIMIT 1000;

  -- Ignore filter rules, saved queries, hotlists, deleted_by, approvers.

  UPDATE IssueSnapshot SET reporter_id = new_id
  WHERE reporter_id = old_id LIMIT 10000;

  UPDATE IssueSnapshot SET owner_id = new_id
  WHERE owner_id = old_id LIMIT 10000;

  UPDATE IGNORE IssueSnapshot2Cc SET cc_id = new_id
  WHERE cc_id = old_id LIMIT 10000;

END;

//

delimiter ;
