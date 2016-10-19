-- Copyright 2016 The Chromium Authors. All Rights Reserved.
--
-- Use of this source code is governed by a BSD-style
-- license that can be found in the LICENSE file or at
-- https://developers.google.com/open-source/licenses/bsd


DROP PROCEDURE IF EXISTS BackfillLastVisitTimestamp;

delimiter //

CREATE PROCEDURE BackfillLastVisitTimestamp(
    IN in_now_ts INT, IN in_days_ago INT, IN in_num_days INT)
BEGIN

  DECLARE done INT DEFAULT FALSE;

  DECLARE c_user_id INT;
  DECLARE c_comment_ts INT;

  DECLARE curs CURSOR FOR
    SELECT MAX(created), commenter_id FROM Comment
    WHERE created >= in_now_ts - 60 * 60 * 24 * in_days_ago
    AND   created < in_now_ts - 60 * 60 * 24 * (in_days_ago - in_num_days)
    GROUP BY commenter_id
    ORDER BY MAX(created);

  DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;
  OPEN curs;

  user_loop: LOOP
    FETCH curs INTO c_comment_ts, c_user_id;
    IF done THEN
      LEAVE user_loop;
    END IF;

    -- Indicate progress.
    SELECT c_comment_ts AS 'Processing:';

    -- Set last_visit_timestamp for one user if not already set.
    UPDATE User
    SET last_visit_timestamp = IFNULL(last_visit_timestamp, c_comment_ts)
    WHERE user_id = c_user_id;

  END LOOP;

END;


//


delimiter ;


-- If run locally do all at once:
-- CALL BackfillLastVisitTimestamp(1476915669, 180, 180);

-- If run on staging or production, consider the last 180 days
-- in chunks of 30 days at a time:
-- CALL BackfillLastVisitTimestamp(1476915669,  30, 30);
-- CALL BackfillLastVisitTimestamp(1476915669,  60, 30);
-- CALL BackfillLastVisitTimestamp(1476915669,  90, 30);
-- CALL BackfillLastVisitTimestamp(1476915669, 120, 30);
-- CALL BackfillLastVisitTimestamp(1476915669, 150, 30);
-- CALL BackfillLastVisitTimestamp(1476915669, 180, 30);

