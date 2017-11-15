-- Copyright 2016 The Chromium Authors. All Rights Reserved.
--
-- Use of this source code is governed by a BSD-style
-- license that can be found in the LICENSE file or at
-- https://developers.google.com/open-source/licenses/bsd


-- Create issue-realted tables in monorail db.


CREATE TABLE StatusDef (
  id INT NOT NULL AUTO_INCREMENT,
  project_id SMALLINT UNSIGNED NOT NULL,
  status VARCHAR(80) BINARY NOT NULL,
  rank SMALLINT UNSIGNED,
  means_open BOOLEAN,
  docstring TEXT,
  deprecated BOOLEAN DEFAULT FALSE,

  PRIMARY KEY (id),
  UNIQUE KEY (project_id, status),
  FOREIGN KEY (project_id) REFERENCES Project(project_id)
) ENGINE=INNODB;


CREATE TABLE ComponentDef (
  id INT NOT NULL AUTO_INCREMENT,
  project_id SMALLINT UNSIGNED NOT NULL,

  -- Note: parent components have paths that are prefixes of child components.
  path VARCHAR(255) BINARY NOT NULL,
  docstring TEXT,
  deprecated BOOLEAN DEFAULT FALSE,
  created INT,
  creator_id INT UNSIGNED,
  modified INT,
  modifier_id INT UNSIGNED,

  PRIMARY KEY (id),
  UNIQUE KEY (project_id, path),
  FOREIGN KEY (project_id) REFERENCES Project(project_id),
  FOREIGN KEY (creator_id) REFERENCES User(user_id),
  FOREIGN KEY (modifier_id) REFERENCES User(user_id)
) ENGINE=INNODB;


CREATE TABLE Component2Admin (
  component_id INT NOT NULL,
  admin_id INT UNSIGNED NOT NULL,

  PRIMARY KEY (component_id, admin_id),

  FOREIGN KEY (component_id) REFERENCES ComponentDef(id),
  FOREIGN KEY (admin_id) REFERENCES User(user_id)
) ENGINE=INNODB;


CREATE TABLE Component2Cc (
  component_id INT NOT NULL,
  cc_id INT UNSIGNED NOT NULL,

  PRIMARY KEY (component_id, cc_id),

  FOREIGN KEY (component_id) REFERENCES ComponentDef(id),
  FOREIGN KEY (cc_id) REFERENCES User(user_id)
) ENGINE=INNODB;


CREATE TABLE LabelDef (
  id INT NOT NULL AUTO_INCREMENT,
  project_id SMALLINT UNSIGNED NOT NULL,
  label VARCHAR(80) BINARY NOT NULL,
  rank SMALLINT UNSIGNED,
  docstring TEXT,
  deprecated BOOLEAN DEFAULT FALSE,

  PRIMARY KEY (id),
  UNIQUE KEY (project_id, label),
  FOREIGN KEY (project_id) REFERENCES Project(project_id)
) ENGINE=INNODB;


CREATE TABLE Component2Label (
  component_id INT NOT NULL,
  label_id INT NOT NULL,

  PRIMARY KEY (component_id, label_id),

  FOREIGN KEY (component_id) REFERENCES ComponentDef(id),
  FOREIGN KEY (label_id) REFERENCES LabelDef(id)
) ENGINE=INNODB;


CREATE TABLE FieldDef (
  id INT NOT NULL AUTO_INCREMENT,
  project_id SMALLINT UNSIGNED NOT NULL,
  rank SMALLINT UNSIGNED,

  field_name VARCHAR(80) BINARY NOT NULL,
  -- TODO(jrobbins): more types
  field_type ENUM ('enum_type', 'int_type', 'str_type', 'user_type', 'date_type', 'url_type') NOT NULL,
  applicable_type VARCHAR(80),   -- No value means: offered for all issue types
  applicable_predicate TEXT,   -- No value means: TRUE
  is_required BOOLEAN,  -- true means required if applicable
  is_niche BOOLEAN,  -- true means user must click to reveal widget
  is_multivalued BOOLEAN,
  -- TODO(jrobbins): access controls: restrict, grant
  -- Validation for int_type fields
  min_value INT,
  max_value INT,
  -- Validation for str_type fields
  regex VARCHAR(80),
  -- Validation for user_type fields
  needs_member BOOLEAN,  -- User value can only be set to users who are members
  needs_perm VARCHAR(80),  -- User value can only be set to users w/ that perm
  grants_perm VARCHAR(80),  -- User named in this field gains this perm in the issue
  -- notification options for user_type fields
  notify_on ENUM ('never', 'any_comment') DEFAULT 'never' NOT NULL,
  -- notification options for date_type fields
  date_action ENUM ('no_action', 'ping_owner_only', 'ping_participants'),

  -- TODO(jrobbins): default value
  -- TODO(jrobbins): deprecated boolean?
  docstring TEXT,
  is_deleted BOOLEAN,  -- If true, reap this field def after all values reaped.

  PRIMARY KEY (id),
  UNIQUE KEY (project_id, field_name),
  FOREIGN KEY (project_id) REFERENCES Project(project_id)
) ENGINE=INNODB;


CREATE TABLE FieldDef2Admin (
  field_id INT NOT NULL,
  admin_id INT UNSIGNED NOT NULL,

  PRIMARY KEY (field_id, admin_id),
  FOREIGN KEY (field_id) REFERENCES FieldDef(id),
  FOREIGN KEY (admin_id) REFERENCES User(user_id)
) ENGINE=INNODB;


CREATE TABLE Issue (
  id INT NOT NULL AUTO_INCREMENT,
  shard SMALLINT UNSIGNED DEFAULT 0 NOT NULL,
  project_id SMALLINT UNSIGNED NOT NULL,
  local_id INT NOT NULL,

  reporter_id INT UNSIGNED NOT NULL,
  owner_id INT UNSIGNED,
  status_id INT,

  -- These are each timestamps in seconds since the epoch.
  modified INT NOT NULL,
  opened INT,
  closed INT,
  owner_modified INT,
  status_modified INT,
  component_modified INT,

  derived_owner_id INT UNSIGNED,
  derived_status_id INT,

  deleted BOOLEAN,

  -- These are denormalized fields that should be updated when child
  -- records are added or removed for stars or attachments.  If they
  -- get out of sync, they can be updated via an UPDATE ... SELECT statement.
  star_count INT DEFAULT 0,
  attachment_count INT DEFAULT 0,

  is_spam BOOLEAN DEFAULT FALSE,

  PRIMARY KEY(id),
  UNIQUE KEY (project_id, local_id),
  INDEX (shard, status_id),
  INDEX (shard, project_id),

  FOREIGN KEY (project_id) REFERENCES Project(project_id),
  FOREIGN KEY (reporter_id) REFERENCES User(user_id),
  FOREIGN KEY (owner_id) REFERENCES User(user_id),
  FOREIGN KEY (status_id) REFERENCES StatusDef(id),
  FOREIGN KEY (derived_owner_id) REFERENCES User(user_id)
) ENGINE=INNODB;


-- This is a parallel table to the Issue table because we don't want
-- any very wide columns in the Issue table that would slow it down.
CREATE TABLE IssueSummary (
  issue_id INT NOT NULL,
  summary mediumtext COLLATE utf8mb4_unicode_ci,

  PRIMARY KEY (issue_id),
  FOREIGN KEY (issue_id) REFERENCES Issue(id)
) ENGINE=INNODB CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE Issue2Component (
  issue_id INT NOT NULL,
  issue_shard SMALLINT UNSIGNED DEFAULT 0 NOT NULL,
  component_id INT NOT NULL,
  derived BOOLEAN DEFAULT FALSE,

  PRIMARY KEY (issue_id, component_id, derived),
  INDEX (component_id, issue_shard),

  FOREIGN KEY (issue_id) REFERENCES Issue(id),
  FOREIGN KEY (component_id) REFERENCES ComponentDef(id)
) ENGINE=INNODB;


CREATE TABLE Issue2Label (
  issue_id INT NOT NULL,
  issue_shard SMALLINT UNSIGNED DEFAULT 0 NOT NULL,
  label_id INT NOT NULL,
  derived BOOLEAN DEFAULT FALSE,

  PRIMARY KEY (issue_id, label_id, derived),
  INDEX (label_id, issue_shard),

  FOREIGN KEY (issue_id) REFERENCES Issue(id),
  FOREIGN KEY (label_id) REFERENCES LabelDef(id)
) ENGINE=INNODB;


CREATE TABLE Issue2FieldValue (
  issue_id INT NOT NULL,
  issue_shard SMALLINT UNSIGNED DEFAULT 0 NOT NULL,
  field_id INT NOT NULL,

  int_value INT,
  str_value VARCHAR(1024),
  user_id INT UNSIGNED,
  date_value INT,

  derived BOOLEAN DEFAULT FALSE,

  INDEX (issue_id, field_id),
  INDEX (field_id, issue_shard, int_value),
  INDEX (field_id, issue_shard, str_value(255)),
  INDEX (field_id, issue_shard, user_id),
  INDEX (field_id, issue_shard, date_value),

  FOREIGN KEY (issue_id) REFERENCES Issue(id),
  FOREIGN KEY (field_id) REFERENCES FieldDef(id),
  FOREIGN KEY (user_id) REFERENCES User(user_id)
) ENGINE=INNODB;


CREATE TABLE Issue2Cc (
  issue_id INT NOT NULL,
  issue_shard SMALLINT UNSIGNED DEFAULT 0 NOT NULL,
  cc_id INT UNSIGNED NOT NULL,
  derived BOOLEAN DEFAULT FALSE,

  PRIMARY KEY (issue_id, cc_id),
  INDEX (cc_id, issue_shard),

  FOREIGN KEY (issue_id) REFERENCES Issue(id),
  FOREIGN KEY (cc_id) REFERENCES User(user_id)
) ENGINE=INNODB;


CREATE TABLE Issue2Notify (
  issue_id INT NOT NULL,
  email VARCHAR(80) NOT NULL,

  PRIMARY KEY (issue_id, email),

  FOREIGN KEY (issue_id) REFERENCES Issue(id)
) ENGINE=INNODB;

CREATE TABLE IssueVisitHistory (
  issue_id INT NOT NULL,
  user_id INT UNSIGNED NOT NULL,
  viewed INT NOT NULL,

  PRIMARY KEY (user_id, issue_id),
  FOREIGN KEY (issue_id) REFERENCES Issue(id),
  FOREIGN KEY (user_id) REFERENCES User(user_id)
) ENGINE=INNODB;


CREATE TABLE IssueStar (
  issue_id INT NOT NULL,
  user_id INT UNSIGNED NOT NULL,

  PRIMARY KEY (issue_id, user_id),
  INDEX (user_id),
  FOREIGN KEY (issue_id) REFERENCES Issue(id),
  FOREIGN KEY (user_id) REFERENCES User(user_id)
) ENGINE=INNODB;


CREATE TABLE IssueRelation (
  issue_id INT NOT NULL,
  dst_issue_id INT NOT NULL,

  -- Read as: src issue is blocked on dst issue.
  kind ENUM ('blockedon', 'mergedinto') NOT NULL,

  rank BIGINT,

  PRIMARY KEY (issue_id, dst_issue_id, kind),
  INDEX (issue_id),
  INDEX (dst_issue_id),
  FOREIGN KEY (issue_id) REFERENCES Issue(id),
  FOREIGN KEY (dst_issue_id) REFERENCES Issue(id)
) ENGINE=INNODB;


CREATE TABLE DanglingIssueRelation (
  issue_id INT NOT NULL,
  dst_issue_project VARCHAR(80),
  dst_issue_local_id INT,

  -- This table uses 'blocking' so that it can guarantee the src issue
  -- always exists, while the dst issue is always the dangling one.
  kind ENUM ('blockedon', 'blocking', 'mergedinto') NOT NULL,

  PRIMARY KEY (issue_id, dst_issue_project, dst_issue_local_id, kind),
  INDEX (issue_id),
  FOREIGN KEY (issue_id) REFERENCES Issue(id)
) ENGINE=INNODB;


CREATE TABLE CommentContent (
  id INT NOT NULL AUTO_INCREMENT,
  -- TODO(jrobbins): drop comment_id after Comment.commentcontent_id is added.
  comment_id INT NOT NULL,  -- Note: no forign key reference.
  content MEDIUMTEXT COLLATE utf8mb4_unicode_ci,
  inbound_message MEDIUMTEXT COLLATE utf8mb4_unicode_ci,

  PRIMARY KEY (id)
) ENGINE=INNODB CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE Comment (
  id INT NOT NULL AUTO_INCREMENT,
  issue_id INT NOT NULL,
  created INT NOT NULL,
  project_id SMALLINT UNSIGNED NOT NULL,

  commenter_id INT UNSIGNED NOT NULL,
  commentcontent_id INT,  -- TODO(jrobbins) make this NOT NULL.

  deleted_by INT UNSIGNED,
  is_spam BOOLEAN DEFAULT FALSE,
  -- TODO(lukasperaza) Update first comments SET is_description=TRUE
  is_description BOOLEAN DEFAULT FALSE,

  PRIMARY KEY(id),
  INDEX (is_spam, project_id, created),
  INDEX (commenter_id, created),
  INDEX (commenter_id, deleted_by, issue_id),

  FOREIGN KEY (project_id) REFERENCES Project(project_id),
  FOREIGN KEY (issue_id) REFERENCES Issue(id),
  FOREIGN KEY (commenter_id) REFERENCES User(user_id),
  FOREIGN KEY (deleted_by) REFERENCES User(user_id),
  FOREIGN KEY (commentcontent_id) REFERENCES CommentContent(id)
) ENGINE=INNODB CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE Attachment (
  id INT NOT NULL AUTO_INCREMENT,

  issue_id INT NOT NULL,
  comment_id INT,

  filename VARCHAR(255) NOT NULL,
  filesize INT NOT NULL,
  mimetype VARCHAR(255) NOT NULL,
  deleted BOOLEAN,
  gcs_object_id VARCHAR(1024) NOT NULL,

  PRIMARY KEY (id),
  INDEX (issue_id),
  INDEX (comment_id),
  FOREIGN KEY (issue_id) REFERENCES Issue(id)
) ENGINE=INNODB;


CREATE TABLE IssueUpdate (
  id INT NOT NULL AUTO_INCREMENT,
  issue_id INT NOT NULL,
  comment_id INT,

  field ENUM (
  'summary', 'status', 'owner', 'cc', 'labels', 'blockedon', 'blocking', 'mergedinto',
  'project', 'components', 'custom', 'is_spam' ) NOT NULL,
  old_value MEDIUMTEXT COLLATE utf8mb4_unicode_ci,
  new_value MEDIUMTEXT COLLATE utf8mb4_unicode_ci,
  added_user_id INT UNSIGNED,
  removed_user_id INT UNSIGNED,
  custom_field_name VARCHAR(255),
  is_spam BOOLEAN DEFAULT FALSE,

  PRIMARY KEY (id),
  INDEX (issue_id),
  INDEX (comment_id),
  FOREIGN KEY (issue_id) REFERENCES Issue(id)
  -- FOREIGN KEY (added_user_id) REFERENCES User(user_id),
  -- FOREIGN KEY (removed_user_id) REFERENCES User(user_id)
) ENGINE=INNODB CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE IssueFormerLocations (
  issue_id INT NOT NULL,
  project_id SMALLINT UNSIGNED NOT NULL,
  local_id INT NOT NULL,

  INDEX (issue_id),
  UNIQUE KEY (project_id, local_id),
  FOREIGN KEY (issue_id) REFERENCES Issue(id)
) ENGINE=INNODB;


CREATE TABLE Template (
  id INT NOT NULL AUTO_INCREMENT,
  project_id SMALLINT UNSIGNED NOT NULL,
  name VARCHAR(255) BINARY NOT NULL,

  content TEXT,
  summary TEXT,
  summary_must_be_edited BOOLEAN,
  owner_id INT UNSIGNED,
  status VARCHAR(255),
  members_only BOOLEAN,
  owner_defaults_to_member BOOLEAN,
  component_required BOOLEAN DEFAULT FALSE,

  PRIMARY KEY (id),
  UNIQUE KEY (project_id, name),
  FOREIGN KEY (project_id) REFERENCES Project(project_id)
) ENGINE=INNODB;


CREATE TABLE Template2Label (
  template_id INT NOT NULL,
  label VARCHAR(255) NOT NULL,

  PRIMARY KEY (template_id, label),
  FOREIGN KEY (template_id) REFERENCES Template(id)
) ENGINE=INNODB;


CREATE TABLE Template2Admin (
  template_id INT NOT NULL,
  admin_id INT UNSIGNED NOT NULL,

  PRIMARY KEY (template_id, admin_id),
  FOREIGN KEY (template_id) REFERENCES Template(id),
  FOREIGN KEY (admin_id) REFERENCES User(user_id)
) ENGINE=INNODB;


CREATE TABLE Template2FieldValue (
  template_id INT NOT NULL,
  field_id INT NOT NULL,

  int_value INT,
  str_value VARCHAR(1024),
  user_id INT UNSIGNED,
  date_value INT,

  INDEX (template_id, field_id),

  FOREIGN KEY (template_id) REFERENCES Template(id),
  FOREIGN KEY (field_id) REFERENCES FieldDef(id),
  FOREIGN KEY (user_id) REFERENCES User(user_id)
) ENGINE=INNODB;


CREATE TABLE Template2Component (
  template_id INT NOT NULL,
  component_id INT NOT NULL,

  PRIMARY KEY (template_id, component_id),

  FOREIGN KEY (template_id) REFERENCES Template(id),
  FOREIGN KEY (component_id) REFERENCES ComponentDef(id)
) ENGINE=INNODB;


CREATE TABLE ProjectIssueConfig (
  project_id SMALLINT UNSIGNED NOT NULL,

  statuses_offer_merge VARCHAR(255) NOT NULL,
  exclusive_label_prefixes VARCHAR(255) NOT NULL,
  default_template_for_developers INT NOT NULL,
  default_template_for_users INT NOT NULL,
  default_col_spec TEXT,
  default_sort_spec TEXT,
  default_x_attr TEXT,
  default_y_attr TEXT,

  member_default_query TEXT,
  custom_issue_entry_url TEXT,

  PRIMARY KEY (project_id),
  FOREIGN KEY (project_id) REFERENCES Project(project_id)
) ENGINE=INNODB;


CREATE TABLE FilterRule (
  project_id SMALLINT UNSIGNED NOT NULL,
  rank SMALLINT UNSIGNED,

  -- TODO: or should this be broken down into structured fields?
  predicate TEXT NOT NULL,
  -- TODO: or should this be broken down into structured fields?
  consequence TEXT NOT NULL,

  INDEX (project_id),
  FOREIGN KEY (project_id) REFERENCES Project(project_id)
) ENGINE=INNODB;


-- Each row in this table indicates an issue that needs to be reindexed
-- in the GAE fulltext index by our batch indexing cron job.
CREATE TABLE ReindexQueue (
  issue_id INT NOT NULL,
  created TIMESTAMP,

  PRIMARY KEY (issue_id),
  FOREIGN KEY (issue_id) REFERENCES Issue(id)
) ENGINE=INNODB;


-- This holds counters with the highest issue local_id that is
-- already used in each project.  Clients should atomically increment
-- the value for current project and then use the new counter value
-- when creating an issue.
CREATE TABLE LocalIDCounter (
  project_id SMALLINT UNSIGNED NOT NULL,
  used_local_id INT NOT NULL,
  used_spam_id INT NOT NULL,

  PRIMARY KEY (project_id),
  FOREIGN KEY (project_id) REFERENCES Project(project_id)
) ENGINE=INNODB;


-- This is a saved query.  It can be configured by a project owner to
-- be used by all visitors to that project.  Or, it can be a a
-- personal saved query that appears on a user's "Saved queries" page
-- and executes in the scope of one or more projects.
CREATE TABLE SavedQuery (
  id INT NOT NULL AUTO_INCREMENT,
  name VARCHAR(80) NOT NULL,

  -- For now, we only allow saved queries to be based off ane of the built-in
  -- query scopes, and those can never be deleted, so there can be no nesting,
  -- dangling references, and thus no need for cascading deletes.
  base_query_id INT,
  query TEXT NOT NULL,

  PRIMARY KEY (id)
) ENGINE=INNODB;


-- Rows for built-in queries.  These are in the database soley so that
-- foreign key constraints are satisfied. These rows ar never read or updated.
INSERT IGNORE INTO SavedQuery VALUES
  (1, 'All issues', 0, ''),
  (2, 'Open issues', 0, 'is:open'),
  (3, 'Open and owned by me', 0, 'is:open owner:me'),
  (4, 'Open and reported by me', 0, 'is:open reporter:me'),
  (5, 'Open and starred by me', 0, 'is:open is:starred'),
  (6, 'New issues', 0, 'status:new'),
  (7, 'Issues to verify', 0, 'status=fixed,done'),
  (8, 'Open with comment by me', 0, 'is:open commentby:me');

-- The sole purpose of this statement is to force user defined saved queries
-- to have IDs greater than 100 so that 1-100 are reserved for built-ins.
INSERT IGNORE INTO SavedQuery VALUES (100, '', 0, '');


-- User personal queries default to executing in the context of the
-- project where they were created, but the user can edit them to make
-- them into cross-project queries.  Project saved queries always
-- implicitly execute in the context of a project.
CREATE TABLE SavedQueryExecutesInProject (
  query_id INT NOT NULL,
  project_id SMALLINT UNSIGNED NOT NULL,

  PRIMARY KEY (query_id, project_id),
  INDEX (project_id),
  FOREIGN KEY (project_id) REFERENCES Project(project_id),
  FOREIGN KEY (query_id) REFERENCES SavedQuery(id)
) ENGINE=INNODB;


-- These are the queries edited by the project owner on the project
-- admin pages.
CREATE TABLE Project2SavedQuery (
  project_id SMALLINT UNSIGNED NOT NULL,
  rank SMALLINT UNSIGNED NOT NULL,
  query_id INT NOT NULL,

  -- TODO(jrobbins): visibility: owners, committers, contributors, anyone

  PRIMARY KEY (project_id, rank),
  FOREIGN KEY (project_id) REFERENCES Project(project_id),
  FOREIGN KEY (query_id) REFERENCES SavedQuery(id)
) ENGINE=INNODB;


-- These are personal saved queries.
CREATE TABLE User2SavedQuery (
  user_id INT UNSIGNED NOT NULL,
  rank SMALLINT UNSIGNED NOT NULL,
  query_id INT NOT NULL,

  -- TODO(jrobbins): daily and weekly digests, and the ability to have
  -- certain subscriptions go to username+SOMETHING@example.com.
  subscription_mode ENUM ('noemail', 'immediate') DEFAULT 'noemail' NOT NULL,

  PRIMARY KEY (user_id, rank),
  FOREIGN KEY (user_id) REFERENCES User(user_id),
  FOREIGN KEY (query_id) REFERENCES SavedQuery(id)
) ENGINE=INNODB;


-- Created whenever a user reports an issue or comment as spam.
-- Note this is distinct from a SpamVerdict, which is issued by
-- the system rather than a human user.
CREATE TABLE SpamReport (
  -- when this report was generated
  created TIMESTAMP NOT NULL,
  -- when the reported content was generated
  -- TODO(jrobbins): needs default current_time in MySQL 5.7.
  content_created TIMESTAMP NOT NULL,
  -- id of the reporting user
  user_id INT UNSIGNED NOT NULL,
  -- id of the reported user
  reported_user_id INT UNSIGNED NOT NULL,
  -- either this or issue_id must be set
  comment_id INT,
  -- either this or comment_id must be set
  issue_id INT,

  INDEX (issue_id),
  INDEX (comment_id),
  FOREIGN KEY (issue_id) REFERENCES Issue(id),
  FOREIGN KEY (comment_id) REFERENCES Comment(id)
) ENGINE=INNODB;


-- Any time a human or the system sets is_spam to true,
-- or changes it from true to false, we want to have a
-- record of who did it and why.
CREATE TABLE SpamVerdict (
  -- when this verdict was generated
  created TIMESTAMP NOT NULL,

  -- id of the reporting user, may be null if it was
  -- an automatic classification.
  user_id INT UNSIGNED,

  -- id of the containing project.
  project_id INT NOT NULL,

  -- either this or issue_id must be set.
  comment_id INT,

  -- either this or comment_id must be set.
  issue_id INT,

  -- If the classifier issued the verdict, this should be set.
  classifier_confidence FLOAT,

  -- This should reflect the new is_spam value that was applied
  -- by this verdict, not the value it had prior.
  is_spam BOOLEAN NOT NULL,

  -- manual: a project owner marked it as spam.
  -- threshhold: number of SpamReports from non-members was exceeded.
  -- classifier: the automatic classifier reports it as spam.
  -- fail_open: the classifier failed, resulting in a ham decision.
  reason ENUM ("manual", "threshold", "classifier", "fail_open") NOT NULL,

  overruled BOOL NOT NULL,

  -- True indicates that the prediction service PRC failed and we gave up.
  fail_open BOOL DEFAULT FALSE,

  INDEX (issue_id),
  INDEX (comment_id),
  INDEX (classifier_confidence),
  FOREIGN KEY (issue_id) REFERENCES Issue(id),
  FOREIGN KEY (comment_id) REFERENCES Comment(id)

) ENGINE=INNODB;


-- These are user-curated lists of issues which can be re-ordered to
-- prioritize work.
CREATE TABLE Hotlist (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  name VARCHAR(80) NOT NULL,

  summary TEXT,
  description TEXT,

  is_private BOOLEAN DEFAULT FALSE,
  default_col_spec TEXT,

  PRIMARY KEY (id)
) ENGINE=INNODB;


CREATE TABLE Hotlist2Issue (
  hotlist_id INT UNSIGNED NOT NULL,
  issue_id INT NOT NULL,

  rank BIGINT NOT NULL,
  adder_id INT UNSIGNED,
  added INT,
  note TEXT,

  PRIMARY KEY (hotlist_id, issue_id),
  INDEX (hotlist_id),
  INDEX (issue_id),
  FOREIGN KEY (hotlist_id) REFERENCES Hotlist(id),
  FOREIGN KEY (issue_id) REFERENCES Issue(id),
  FOREIGN KEY (adder_id) REFERENCES User(user_id)
) ENGINE=INNODB;


CREATE TABLE Hotlist2User (
  hotlist_id INT UNSIGNED NOT NULL,
  user_id INT UNSIGNED NOT NULL,

  role_name ENUM ('owner', 'editor', 'follower') NOT NULL,

  PRIMARY KEY (hotlist_id, user_id),
  INDEX (hotlist_id),
  INDEX (user_id),
  FOREIGN KEY (hotlist_id) REFERENCES Hotlist(id),
  FOREIGN KEY (user_id) REFERENCES User(user_id)
) ENGINE=INNODB;


CREATE TABLE HotlistStar (
  hotlist_id INT UNSIGNED NOT NULL,
  user_id INT UNSIGNED NOT NULL,

  PRIMARY KEY (hotlist_id, user_id),
  INDEX (user_id),
  FOREIGN KEY (hotlist_id) REFERENCES Hotlist(id),
  FOREIGN KEY (user_id) REFERENCES User(user_id)
) ENGINE=INNODB;

CREATE TABLE HotlistVisitHistory (
  hotlist_id INT UNSIGNED NOT NULL,
  user_id INT UNSIGNED NOT NULL,
  viewed INT NOT NULL,

  PRIMARY KEY (user_id, hotlist_id),
  FOREIGN KEY (hotlist_id) REFERENCES Hotlist(id),
  FOREIGN KEY (user_id) REFERENCES User(user_id)
) ENGINE=INNODB;
