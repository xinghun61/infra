-- Copyright 2016 The Chromium Authors. All Rights Reserved.
--
-- Use of this source code is governed by a BSD-style
-- license that can be found in the LICENSE file or at
-- https://developers.google.com/open-source/licenses/bsd


DROP PROCEDURE IF EXISTS CopyNewCommentContentBackToComment;

delimiter //

CREATE PROCEDURE CopyNewCommentContentBackToComment(
    IN in_start INT, IN in_stop INT, IN in_step INT)
BEGIN
  comment_loop: LOOP
    IF in_start >= in_stop THEN
      LEAVE comment_loop;
    END IF;

    SELECT in_start AS StartingAt;
    SELECT count(*)
    FROM CommentContent
    WHERE comment_id >= in_start
    AND comment_id < in_start + in_step;

    INSERT INTO Comment (content, inbound_message)
    SELECT content, inbound_message
    FROM CommentContent
    WHERE CommentContent.comment_id >= in_start
    AND CommentContent.comment_id < in_start + in_step;

    SET in_start = in_start + in_step;

  END LOOP;

END;


//


delimiter ;


-- This ID is the first comment entered that was stored in CommentContent only.
-- CALL CopyNewCommentContentBackToComment(31459489, 40 * 1000000, 5000);
