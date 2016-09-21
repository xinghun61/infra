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

    DROP TEMPORARY TABLE IF EXISTS temp_comment;
    CREATE TEMPORARY TABLE temp_comment (
      id INT NOT NULL,
      issue_id INT NOT NULL,
      created INT NOT NULL,
      project_id SMALLINT UNSIGNED NOT NULL,
      commenter_id INT UNSIGNED NOT NULL,
      content MEDIUMTEXT COLLATE utf8mb4_unicode_ci,
      inbound_message MEDIUMTEXT COLLATE utf8mb4_unicode_ci,
      deleted_by INT UNSIGNED,
      is_spam BOOLEAN DEFAULT FALSE,
      is_description BOOLEAN DEFAULT FALSE,

      PRIMARY KEY(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


    INSERT INTO temp_comment
    SELECT Comment.id, Comment.issue_id, Comment.created, Comment.project_id,
           Comment.commenter_id, CommentContent.content,
	   CommentContent.inbound_message, Comment.deleted_by, Comment.is_spam,
	   Comment.is_description
    FROM Comment
    LEFT JOIN CommentContent on CommentContent.comment_id = Comment.id
    WHERE CommentContent.comment_id >= in_start
    AND CommentContent.comment_id < in_start + in_step;


    REPLACE INTO Comment (id, issue_id, created, project_id, commenter_id,
        content, inbound_message, deleted_by, is_spam, is_description)
    SELECT id, issue_id, created, project_id, commenter_id,
        content, inbound_message, deleted_by, is_spam, is_description
    FROM temp_comment;

    SET in_start = in_start + in_step;

  END LOOP;

END;


//


delimiter ;


-- Temporarily disable these foreign key references so that we can do
-- REPLACE commands.
-- ALTER TABLE SpamReport DROP FOREIGN KEY spamreport_ibfk_2;
-- ALTER TABLE SpamVerdict DROP FOREIGN KEY spamverdict_ibfk_2;

-- This ID is the first comment entered that was stored in CommentContent only.
-- CALL CopyNewCommentContentBackToComment(31459489, 40 * 1000000, 5000);

-- Add back foreign key constraints.
-- ALTER TABLE SpamReport ADD FOREIGN KEY (comment_id) REFERENCES Comment(id);
-- ALTER TABLE SpamVerdict ADD FOREIGN KEY (comment_id) REFERENCES Comment(id);
