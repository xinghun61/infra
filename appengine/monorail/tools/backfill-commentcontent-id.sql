-- Copyright 2016 The Chromium Authors. All Rights Reserved.
--
-- Use of this source code is governed by a BSD-style
-- license that can be found in the LICENSE file or at
-- https://developers.google.com/open-source/licenses/bsd


DROP PROCEDURE IF EXISTS BackfillCommentContentID;

delimiter //

CREATE PROCEDURE BackfillCommentContentID(
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
      commentcontent_id INT UNSIGNED NOT NULL,
      deleted_by INT UNSIGNED,
      is_spam BOOLEAN DEFAULT FALSE,
      is_description BOOLEAN DEFAULT FALSE,

      PRIMARY KEY(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


    INSERT INTO temp_comment
    SELECT Comment.id, Comment.issue_id, Comment.created, Comment.project_id,
           Comment.commenter_id, CommentContent.id,
           Comment.deleted_by, Comment.is_spam, Comment.is_description
    FROM Comment
    LEFT JOIN CommentContent on CommentContent.comment_id = Comment.id
    WHERE CommentContent.comment_id >= in_start
    AND CommentContent.comment_id < in_start + in_step;


    REPLACE INTO Comment (id, issue_id, created, project_id, commenter_id,
        commentcontent_id, deleted_by, is_spam, is_description)
    SELECT id, issue_id, created, project_id, commenter_id,
        commentcontent_id, deleted_by, is_spam, is_description
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

-- If run locally do all at once:
-- CALL BackfillCommentContentID(           0,  1 * 1000000, 10000);

-- If run on staging or production, do it in steps and check that
-- users are not hitting errors or timeouts as you go:
-- CALL BackfillCommentContentID(           0, 13 * 1000000, 10000);
-- CALL BackfillCommentContentID(13 * 1000000, 16 * 1000000, 10000);
-- CALL BackfillCommentContentID(16 * 1000000, 17 * 1000000, 10000);
-- CALL BackfillCommentContentID(17 * 1000000, 18 * 1000000, 10000);
-- CALL BackfillCommentContentID(18 * 1000000, 19 * 1000000, 10000);
-- CALL BackfillCommentContentID(19 * 1000000, 20 * 1000000, 10000);
-- CALL BackfillCommentContentID(20 * 1000000, 21 * 1000000, 10000);
-- CALL BackfillCommentContentID(21 * 1000000, 22 * 1000000, 10000);
-- CALL BackfillCommentContentID(22 * 1000000, 23 * 1000000, 10000);
-- CALL BackfillCommentContentID(23 * 1000000, 24 * 1000000, 10000);
-- CALL BackfillCommentContentID(24 * 1000000, 25 * 1000000, 10000);
-- CALL BackfillCommentContentID(25 * 1000000, 26 * 1000000, 10000);
-- CALL BackfillCommentContentID(26 * 1000000, 27 * 1000000, 10000);
-- CALL BackfillCommentContentID(27 * 1000000, 28 * 1000000, 10000);
-- CALL BackfillCommentContentID(28 * 1000000, 29 * 1000000, 10000);
-- CALL BackfillCommentContentID(29 * 1000000, 30 * 1000000, 10000);
-- CALL BackfillCommentContentID(30 * 1000000, 40 * 1000000, 10000);

-- Add back foreign key constraints.
-- ALTER TABLE SpamReport ADD FOREIGN KEY (comment_id) REFERENCES Comment(id);
-- ALTER TABLE SpamVerdict ADD FOREIGN KEY (comment_id) REFERENCES Comment(id);
