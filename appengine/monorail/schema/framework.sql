-- Copyright 2016 The Chromium Authors. All Rights Reserved.
--
-- Use of this source code is governed by a BSD-style
-- license that can be found in the LICENSE file or at
-- https://developers.google.com/open-source/licenses/bsd


-- Create app framework tables in the monorail DB.

ALTER DATABASE monorail CHARACTER SET = utf8 COLLATE = utf8_unicode_ci;

-- This table allows frontends to selectively invalidate their RAM caches.
-- On each incoming request, the frontend queries this table to get all rows
-- that are newer than the last row that it saw. Then it processes each such
-- row by dropping entries from its RAM caches, and remembers the new highest
-- timestep that it has seen.
CREATE TABLE Invalidate (
  -- The time at which the invalidation took effect, by that time new data
  -- should be available to retrieve to fill local caches as needed.
  -- This is not a clock value, it is just an integer that counts up by one
  -- on each change.
  timestep BIGINT NOT NULL AUTO_INCREMENT,

  -- Which kind of entity was invalidated?  Each kind is broad, e.g.,
  -- invalidating a project also invalidates all issue tracker config within
  -- that project.  But, they do not nest.  E.g., invalidating a project does
  -- not invalidate all issues in the project.
  kind enum('user', 'project', 'issue', 'issue_id', 'hotlist', 'comment') NOT NULL,

  -- Which cache entry should be invalidated?  Special value 0 indicates
  -- that all entries should be invalidated.
  cache_key INT UNSIGNED,

  INDEX (timestep)
) ENGINE=INNODB;

