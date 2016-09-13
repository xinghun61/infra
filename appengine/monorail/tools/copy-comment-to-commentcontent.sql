-- Copyright 2016 The Chromium Authors. All Rights Reserved.
--
-- Use of this source code is governed by a BSD-style
-- license that can be found in the LICENSE file or at
-- https://developers.google.com/open-source/licenses/bsd


DROP PROCEDURE IF EXISTS CopyCommentToCommentContent;

delimiter //

CREATE PROCEDURE CopyCommentToCommentContent(
    IN in_pid SMALLINT UNSIGNED, IN in_chunk_size SMALLINT UNSIGNED)
BEGIN

  INSERT INTO CommentContent (comment_id, content, inbound_message)
  SELECT id, content, inbound_message
  FROM Comment
  WHERE project_id = in_pid
  AND Comment.id NOT IN (SELECT comment_id FROM CommentContent)
  LIMIT in_chunk_size;

END;


//


delimiter ;

