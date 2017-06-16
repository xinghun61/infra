-- Copyright 2016 The Chromium Authors. All Rights Reserved.
--
-- Use of this source code is governed by a BSD-style
-- license that can be found in the LICENSE file or at
-- https://developers.google.com/open-source/licenses/bsd


-- Create project-related tables in monorail db.


CREATE TABLE User (
  user_id INT UNSIGNED NOT NULL,
  email VARCHAR(255) NOT NULL,  -- lowercase

  is_site_admin BOOLEAN DEFAULT FALSE,
  obscure_email BOOLEAN DEFAULT TRUE,
  notify_issue_change BOOLEAN DEFAULT TRUE,
  notify_starred_issue_change BOOLEAN DEFAULT TRUE,
  email_compact_subject BOOLEAN DEFAULT FALSE,
  email_view_widget BOOLEAN DEFAULT TRUE,
  notify_starred_ping BOOLEAN DEFAULT FALSE,
  banned VARCHAR(80),
  after_issue_update ENUM ('up_to_list', 'stay_same_issue', 'next_in_list'),
  keep_people_perms_open BOOLEAN DEFAULT FALSE,
  preview_on_hover BOOLEAN DEFAULT TRUE,
  ignore_action_limits BOOLEAN DEFAULT FALSE,
  last_visit_timestamp INT,
  email_bounce_timestamp INT,
  vacation_message VARCHAR(80),

  PRIMARY KEY (user_id),
  UNIQUE KEY (email)
) ENGINE=INNODB;



CREATE TABLE Project (
  project_id SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  project_name VARCHAR(80) NOT NULL,

  summary TEXT,
  description TEXT,

  state ENUM ('live', 'archived', 'deletable') NOT NULL,
  access ENUM ('anyone', 'members_only') NOT NULL,
  read_only_reason VARCHAR(80),  -- normally empty for read-write.
  state_reason VARCHAR(80),  -- optional reason for doomed project.
  delete_time INT,  -- if set, automatically transition to state deletable.

  issue_notify_address VARCHAR(80),
  attachment_bytes_used BIGINT DEFAULT 0,
  attachment_quota BIGINT DEFAULT 0,  -- 50 MB default set in python code.

  cached_content_timestamp INT,
  recent_activity_timestamp INT,
  moved_to VARCHAR(250),
  process_inbound_email BOOLEAN DEFAULT FALSE,

  only_owners_remove_restrictions BOOLEAN DEFAULT FALSE,
  only_owners_see_contributors BOOLEAN DEFAULT FALSE,

  revision_url_format VARCHAR(250),

  home_page VARCHAR(250),
  docs_url VARCHAR(250),
  source_url VARCHAR(250),
  logo_gcs_id VARCHAR(250),
  logo_file_name VARCHAR(250),

  PRIMARY KEY (project_id),
  UNIQUE KEY (project_name)
) ENGINE=INNODB;


CREATE TABLE ActionLimit (
  user_id INT UNSIGNED NOT NULL,
  action_kind ENUM (
      'project_creation', 'issue_comment', 'issue_attachment',
      'issue_bulk_edit', 'api_request'),
  recent_count INT,
  reset_timestamp INT,
  lifetime_count INT,
  lifetime_limit INT,
  period_soft_limit INT,
  period_hard_limit INT,

  PRIMARY KEY (user_id, action_kind)
) ENGINE=INNODB;


CREATE TABLE DismissedCues (
  user_id INT UNSIGNED NOT NULL,
  cue VARCHAR(40),  -- names of the cue cards that the user has dismissed.

  INDEX (user_id)
) ENGINE=INNODB;


CREATE TABLE User2Project (
  project_id SMALLINT UNSIGNED NOT NULL,
  user_id INT UNSIGNED NOT NULL,
  role_name ENUM ('owner', 'committer', 'contributor'),

  PRIMARY KEY (project_id, user_id),
  INDEX (user_id),
  FOREIGN KEY (project_id) REFERENCES Project(project_id),
  FOREIGN KEY (user_id) REFERENCES User(user_id)
) ENGINE=INNODB;


CREATE TABLE LinkedAccount (
  parent_email VARCHAR(255) NOT NULL,  -- lowercase
  child_email VARCHAR(255) NOT NULL,  -- lowercase

  KEY (parent_email),
  UNIQUE KEY (child_email)
) ENGINE=INNODB;


CREATE TABLE ExtraPerm (
  project_id SMALLINT UNSIGNED NOT NULL,
  user_id INT UNSIGNED NOT NULL,
  perm VARCHAR(80),

  PRIMARY KEY (project_id, user_id, perm),
  FOREIGN KEY (project_id) REFERENCES Project(project_id),
  FOREIGN KEY (user_id) REFERENCES User(user_id)
) ENGINE=INNODB;


CREATE TABLE MemberNotes (
  project_id SMALLINT UNSIGNED NOT NULL,
  user_id INT UNSIGNED NOT NULL,
  notes TEXT,

  PRIMARY KEY (project_id, user_id),
  FOREIGN KEY (project_id) REFERENCES Project(project_id),
  FOREIGN KEY (user_id) REFERENCES User(user_id)
) ENGINE=INNODB;


CREATE TABLE AutocompleteExclusion (
  project_id SMALLINT UNSIGNED NOT NULL,
  user_id INT UNSIGNED NOT NULL,

  PRIMARY KEY (project_id, user_id),
  FOREIGN KEY (project_id) REFERENCES Project(project_id),
  FOREIGN KEY (user_id) REFERENCES User(user_id)
) ENGINE=INNODB;


CREATE TABLE UserStar (
  starred_user_id INT UNSIGNED NOT NULL,
  user_id INT UNSIGNED NOT NULL,

  PRIMARY KEY (starred_user_id, user_id),
  INDEX (user_id),
  FOREIGN KEY (user_id) REFERENCES User(user_id),
  FOREIGN KEY (starred_user_id) REFERENCES User(user_id)
) ENGINE=INNODB;


CREATE TABLE ProjectStar (
  project_id SMALLINT UNSIGNED NOT NULL,
  user_id INT UNSIGNED NOT NULL,

  PRIMARY KEY (project_id, user_id),
  INDEX (user_id),
  FOREIGN KEY (user_id) REFERENCES User(user_id),
  FOREIGN KEY (project_id) REFERENCES Project(project_id)
) ENGINE=INNODB;


CREATE TABLE UserGroup (
  user_id INT UNSIGNED NOT NULL,
  group_id INT UNSIGNED NOT NULL,
  role ENUM ('owner', 'member') NOT NULL DEFAULT 'member',

  PRIMARY KEY (user_id, group_id),
  INDEX (group_id),
  FOREIGN KEY (user_id) REFERENCES User(user_id),
  FOREIGN KEY (group_id) REFERENCES User(user_id)

) ENGINE=INNODB;


CREATE TABLE UserGroupSettings (
  group_id INT UNSIGNED NOT NULL,

  who_can_view_members ENUM ('owners', 'members', 'anyone'),

  external_group_type ENUM ('chrome_infra_auth', 'mdb', 'baggins'),
  -- timestamps in seconds since the epoch.
  last_sync_time INT,

  PRIMARY KEY (group_id),
  FOREIGN KEY (group_id) REFERENCES User(user_id)
) ENGINE=INNODB;


CREATE TABLE Group2Project (
  group_id INT UNSIGNED NOT NULL,
  project_id SMALLINT UNSIGNED NOT NULL,

  PRIMARY KEY (group_id, project_id),

  FOREIGN KEY (group_id) REFERENCES UserGroupSettings(group_id),
  FOREIGN KEY (project_id) REFERENCES Project(project_id)
) ENGINE=INNODB;


-- These are quick-edit commands that the user can easily repeat.
CREATE TABLE QuickEditHistory (
  user_id INT UNSIGNED NOT NULL,
  project_id SMALLINT UNSIGNED NOT NULL,
  slot_num SMALLINT UNSIGNED NOT NULL,

  command VARCHAR(255) NOT NULL,
  comment TEXT NOT NULL,

  PRIMARY KEY (user_id, project_id, slot_num),
  FOREIGN KEY (project_id) REFERENCES Project(project_id),
  FOREIGN KEY (user_id) REFERENCES User(user_id)
) ENGINE=INNODB;


-- This allows us to offer the most recent command to the user again
-- as the default quick-edit command for next time.
CREATE TABLE QuickEditMostRecent (
  user_id INT UNSIGNED NOT NULL,
  project_id SMALLINT UNSIGNED NOT NULL,
  slot_num SMALLINT UNSIGNED NOT NULL,

  PRIMARY KEY (user_id, project_id),
  FOREIGN KEY (project_id) REFERENCES Project(project_id),
  FOREIGN KEY (user_id) REFERENCES User(user_id)
) ENGINE=INNODB;
