# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""The Monorail issue tracker uses ProtoRPC for storing business objects."""

from protorpc import messages


class FieldValue(messages.Message):
  """Holds a single custom field value in an issue.

  Multi-valued custom fields will have multiple such FieldValues on a given
  issue. Note that enumerated type custom fields are represented as key-value
  labels.
  """
  field_id = messages.IntegerField(1, required=True)
  # Only one of the following fields will hve any value.
  int_value = messages.IntegerField(2)
  str_value = messages.StringField(3)
  user_id = messages.IntegerField(4)
  date_value = messages.IntegerField(6)
  url_value = messages.StringField(7)

  derived = messages.BooleanField(5, default=False)


class DanglingIssueRef(messages.Message):
  """Holds a reference to an issue still on Google Codesite."""
  project = messages.StringField(1, required=True)
  issue_id = messages.IntegerField(2, required=True)


class Issue(messages.Message):
  """Holds all the current metadata about an issue.

  The most frequent searches can work by consulting solely the issue metadata.
  Display of the issue list is done solely with this issue metadata.
  Displaying one issue in detail with description and comments requires
  more info from other objects.

  The issue_id field is the unique primary key for retrieving issues.  Local ID
  is a small integer that counts up in each project.

  Summary, Status, Owner, CC, reporter, and opened_timestamp are hard
  fields that are always there.  All other metadata is stored as
  labels or custom fields.
  Next available tag: 55.
  """
  # Globally unique issue ID.
  issue_id = messages.IntegerField(42)
  # project_name is not stored in the DB, only the project_id is stored.
  # project_name is used in RAM to simplify formatting logic in lots of places.
  project_name = messages.StringField(1, required=True)
  project_id = messages.IntegerField(50)
  local_id = messages.IntegerField(2, required=True)
  summary = messages.StringField(3, default='')
  status = messages.StringField(4, default='')
  owner_id = messages.IntegerField(5)
  cc_ids = messages.IntegerField(6, repeated=True)
  labels = messages.StringField(7, repeated=True)
  component_ids = messages.IntegerField(39, repeated=True)

  # Denormalized count of stars on this Issue.
  star_count = messages.IntegerField(8, required=True, default=0)
  reporter_id = messages.IntegerField(9, required=True, default=0)
  # Time that the issue was opened, in seconds since the Epoch.
  opened_timestamp = messages.IntegerField(10, required=True, default=0)

  # This should be set when an issue is closed and cleared when a
  # closed issue is reopened.  Measured in seconds since the Epoch.
  closed_timestamp = messages.IntegerField(12, default=0)

  # This should be updated every time an issue is modified.  Measured
  # in seconds since the Epoch.
  modified_timestamp = messages.IntegerField(13, default=0)

  # These timestamps are updated whenever owner, status, or components
  # change, including when altered by a filter rule.
  owner_modified_timestamp = messages.IntegerField(19, default=0)
  status_modified_timestamp = messages.IntegerField(20, default=0)
  component_modified_timestamp = messages.IntegerField(21, default=0)

  # Issue IDs of issues that this issue is blocked on.
  blocked_on_iids = messages.IntegerField(16, repeated=True)

  # Rank values of issue relations that are blocking this issue. The issue
  # with id blocked_on_iids[i] has rank value blocked_on_ranks[i]
  blocked_on_ranks = messages.IntegerField(54, repeated=True)

  # Issue IDs of issues that this issue is blocking.
  blocking_iids = messages.IntegerField(17, repeated=True)

  # References to 'dangling' (still in codesite) issue relations.
  dangling_blocked_on_refs = messages.MessageField(
      DanglingIssueRef, 52, repeated=True)
  dangling_blocking_refs = messages.MessageField(
      DanglingIssueRef, 53, repeated=True)

  # Issue ID of issue that this issue was merged into most recently.  When it
  # is missing or 0, it is considered to be not merged into any other issue.
  merged_into = messages.IntegerField(18)

  # Default derived via rules, used iff status == ''.
  derived_status = messages.StringField(30, default='')
  # Default derived via rules, used iff owner_id == 0.
  derived_owner_id = messages.IntegerField(31, default=0)
  # Additional CCs derived via rules.
  derived_cc_ids = messages.IntegerField(32, repeated=True)
  # Additional labels derived via rules.
  derived_labels = messages.StringField(33, repeated=True)
  # Additional notification email addresses derived via rules.
  derived_notify_addrs = messages.StringField(34, repeated=True)
  # Additional components derived via rules.
  derived_component_ids = messages.IntegerField(40, repeated=True)
  # Software development process warnings and errors generated by filter rules.
  # TODO(jrobbins): these are not yet stored in the DB, they are only in RAM.
  derived_warnings = messages.StringField(55, repeated=True)
  derived_errors = messages.StringField(56, repeated=True)

  # Soft delete of the entire issue.
  deleted = messages.BooleanField(35, default=False)

  # Total number of attachments in the issue
  attachment_count = messages.IntegerField(36, default=0)

  # Total number of comments on the issue (not counting the initial comment
  # created when the issue is created).
  comment_count = messages.IntegerField(37, default=0)

  # Custom field values (other than enums)
  field_values = messages.MessageField(FieldValue, 41, repeated=True)

  is_spam = messages.BooleanField(51, default=False)
  # assume_stale is used in RAM to ensure that a value saved to the DB was
  # loaded from the DB in the same request handler (not via the cache).
  assume_stale = messages.BooleanField(57, default=True)


class FieldID(messages.Enum):
  """Possible fields that can be updated in an Amendment."""
  # The spelling of these names must match enum values in tracker.sql.
  SUMMARY = 1
  STATUS = 2
  OWNER = 3
  CC = 4
  LABELS = 5
  BLOCKEDON = 6
  BLOCKING = 7
  MERGEDINTO = 8
  PROJECT = 9
  COMPONENTS = 10
  CUSTOM = 11
  WARNING = 12
  ERROR = 13


class Amendment(messages.Message):
  """Holds info about one issue field change."""
  field = messages.EnumField(FieldID, 11, required=True)
  # User-visible string describing the change
  newvalue = messages.StringField(12, required=True)
  # Newvalue could have + or - characters to indicate that labels and CCs
  # were added or removed
  # Users added to owner or cc field
  added_user_ids = messages.IntegerField(29, repeated=True)
  # Users removed from owner or cc
  removed_user_ids = messages.IntegerField(30, repeated=True)
  custom_field_name = messages.StringField(31)
  # When having newvalue be a +/- string doesn't make sense (e.g. status),
  # store the old value here so that it can still be displayed.
  oldvalue = messages.StringField(32)


class Attachment(messages.Message):
  """Holds info about one attachment."""
  attachment_id = messages.IntegerField(21, required=True)
  # Client-side filename
  filename = messages.StringField(22, required=True)
  filesize = messages.IntegerField(23, required=True)
  # File mime-type, or at least our best guess.
  mimetype = messages.StringField(24, required=True)
  deleted = messages.BooleanField(27, default=False)
  gcs_object_id = messages.StringField(29, required=False)


class IssueComment(messages.Message):
  # TODO(lukasperaza): update first comment to is_description=True
  """Holds one issue description or one additional comment on an issue.

  The IssueComment with the lowest timestamp is the issue description,
  if there is no IssueComment with is_description=True; otherwise, the
  IssueComment with is_description=True and the highest timestamp is
  the issue description.
  Next available tag: 54
  """
  id = messages.IntegerField(32)
  # Issue ID of the issue that was commented on.
  issue_id = messages.IntegerField(31, required=True)
  project_id = messages.IntegerField(50)
  # User who entered the comment
  user_id = messages.IntegerField(4, required=True, default=0)
  # Time when comment was entered (seconds).
  timestamp = messages.IntegerField(5, required=True)
  # Text of the comment
  content = messages.StringField(6, required=True)
  # Audit trail of changes made w/ this comment
  amendments = messages.MessageField(Amendment, 10, repeated=True)

  # Soft delete that can be undeleted.
  # Deleted comments should not be shown to average users.
  # If deleted, deleted_by contains the user id of user who deleted.
  deleted_by = messages.IntegerField(13)

  attachments = messages.MessageField(Attachment, 20, repeated=True)

  # Sequence number of the comment
  # The field is optional for compatibility with code existing before
  # this field was added.
  sequence = messages.IntegerField(26)

  # The body text of the inbound email that caused this issue comment
  # to be automatically entered.  If this field is non-empty, it means
  # that the comment was added via an inbound email.  Headers and attachments
  # are not included.
  inbound_message = messages.StringField(28)

  is_spam = messages.BooleanField(51, default=False)

  is_description = messages.BooleanField(52, default=False)
  description_num = messages.StringField(53)

class SavedQuery(messages.Message):
  """Store a saved query, for either a project or a user."""
  query_id = messages.IntegerField(1)
  name = messages.StringField(2)
  base_query_id = messages.IntegerField(3)
  query = messages.StringField(4, required=True)

  # For personal cross-project queries.
  executes_in_project_ids = messages.IntegerField(5, repeated=True)

  # For user saved queries.
  subscription_mode = messages.StringField(6)


class NotifyTriggers(messages.Enum):
  """Issue tracker events that can trigger notification emails."""
  NEVER = 0
  ANY_COMMENT = 1
  # TODO(jrobbins): ANY_CHANGE, OPENED_CLOSED, ETC.


class FieldTypes(messages.Enum):
  """Types of custom fields that Monorail supports."""
  ENUM_TYPE = 1
  INT_TYPE = 2
  STR_TYPE = 3
  USER_TYPE = 4
  DATE_TYPE = 5
  BOOL_TYPE = 6
  URL_TYPE = 7
  # TODO(jrobbins): more types, see tracker.sql for all TODOs.


class DateAction(messages.Enum):
  """What to do when a date field value arrives."""
  NO_ACTION = 0
  PING_OWNER_ONLY = 1
  PING_PARTICIPANTS = 2


class FieldDef(messages.Message):
  """This PB stores info about one custom field definition."""
  field_id = messages.IntegerField(1, required=True)
  project_id = messages.IntegerField(2, required=True)
  field_name = messages.StringField(3, required=True)
  field_type = messages.EnumField(FieldTypes, 4, required=True)
  applicable_type = messages.StringField(11)
  applicable_predicate = messages.StringField(10)
  is_required = messages.BooleanField(5, default=False)
  is_niche = messages.BooleanField(19, default=False)
  is_multivalued = messages.BooleanField(6, default=False)
  docstring = messages.StringField(7)
  is_deleted = messages.BooleanField(8, default=False)
  admin_ids = messages.IntegerField(9, repeated=True)

  # validation details for int_type
  min_value = messages.IntegerField(12)
  max_value = messages.IntegerField(13)
  # validation details for str_type
  regex = messages.StringField(14)
  # validation details for user_type
  needs_member = messages.BooleanField(15, default=False)
  needs_perm = messages.StringField(16)

  # semantics for user_type fields
  grants_perm = messages.StringField(17)
  notify_on = messages.EnumField(NotifyTriggers, 18)

  # semantics for date_type fields
  date_action = messages.EnumField(DateAction, 20)


class ComponentDef(messages.Message):
  """This stores info about a component in a project."""
  component_id = messages.IntegerField(1, required=True)
  project_id = messages.IntegerField(2, required=True)
  path = messages.StringField(3, required=True)
  docstring = messages.StringField(4)
  admin_ids = messages.IntegerField(5, repeated=True)
  cc_ids = messages.IntegerField(6, repeated=True)
  deprecated = messages.BooleanField(7, default=False)
  created = messages.IntegerField(8)
  creator_id = messages.IntegerField(9)
  modified = messages.IntegerField(10)
  modifier_id = messages.IntegerField(11)
  label_ids = messages.IntegerField(12, repeated=True)


class FilterRule(messages.Message):
  """Filter rules implement semantics as project-specific if-then rules."""
  predicate = messages.StringField(10, required=True)

  # If the predicate is satisfied, these actions set some of the derived_*
  # fields on the issue: labels, status, owner, or CCs.
  add_labels = messages.StringField(20, repeated=True)
  default_status = messages.StringField(21)
  default_owner_id = messages.IntegerField(22)
  add_cc_ids = messages.IntegerField(23, repeated=True)
  add_notify_addrs = messages.StringField(24, repeated=True)
  warning = messages.StringField(25)
  error = messages.StringField(26)


class StatusDef(messages.Message):
  """Definition of one well-known issue status."""
  status = messages.StringField(11, required=True)
  means_open = messages.BooleanField(12, default=False)
  status_docstring = messages.StringField(13)
  deprecated = messages.BooleanField(14, default=False)


class LabelDef(messages.Message):
  """Definition of one well-known issue label."""
  label = messages.StringField(21, required=True)
  label_docstring = messages.StringField(22)
  deprecated = messages.BooleanField(23, default=False)


class TemplateDef(messages.Message):
  """Definition of one issue template."""
  template_id = messages.IntegerField(57)
  name = messages.StringField(31, required=True)
  content = messages.StringField(32, required=True)
  summary = messages.StringField(33)
  summary_must_be_edited = messages.BooleanField(34, default=False)
  owner_id = messages.IntegerField(35)
  status = messages.StringField(36)
  # Note: labels field is considered to have been set iff summary was set.
  labels = messages.StringField(37, repeated=True)
  # This controls what is listed in the template drop-down menu. Users
  # could still select any template by editing the URL, and that's OK.
  members_only = messages.BooleanField(38, default=False)
  # If no owner_id is specified, and owner_defaults_to_member is
  # true, then when an issue is entered by a member, fill in the initial
  # owner field with the signed in user's name.
  owner_defaults_to_member = messages.BooleanField(39, default=True)
  admin_ids = messages.IntegerField(41, repeated=True)

  # Custom field values (other than enums)
  field_values = messages.MessageField(FieldValue, 42, repeated=True)
  # Components.
  component_ids = messages.IntegerField(43, repeated=True)
  component_required = messages.BooleanField(44, default=False)


class ProjectIssueConfig(messages.Message):
  """This holds all configuration info for one project.

  That includes canned queries, well-known issue statuses,
  and well-known issue labels.

  "Well-known" means that they are always offered to the user in
  drop-downs, even if there are currently no open issues that have
  that label or status value.  Deleting a well-known value from the
  configuration does not change any issues that may still reference
  that old label, and users are still free to use it.

  Exclusive label prefixes mean that a given issue may only have one
  label that begins with that prefix.  E.g., Priority should be
  exclusive so that no issue can be labeled with both Priority-High
  and Priority-Low.
  """

  project_id = messages.IntegerField(60)
  well_known_statuses = messages.MessageField(StatusDef, 10, repeated=True)
  # If an issue's status is being set to one of these, show "Merge with:".
  statuses_offer_merge = messages.StringField(14, repeated=True)

  well_known_labels = messages.MessageField(LabelDef, 20, repeated=True)
  exclusive_label_prefixes = messages.StringField(2, repeated=True)

  field_defs = messages.MessageField(FieldDef, 5, repeated=True)
  component_defs = messages.MessageField(ComponentDef, 6, repeated=True)

  templates = messages.MessageField(TemplateDef, 30, repeated=True)

  default_template_for_developers = messages.IntegerField(3, required=True)
  default_template_for_users = messages.IntegerField(4, required=True)

  # These options control the default appearance of the issue list or grid
  # for non-members.
  default_col_spec = messages.StringField(50, default='')
  default_sort_spec = messages.StringField(51, default='')
  default_x_attr = messages.StringField(52, default='')
  default_y_attr = messages.StringField(53, default='')

  # These options control the default appearance of the issue list or grid
  # for project members.
  member_default_query = messages.StringField(57, default='')

  # This bool controls whether users are able to enter odd-ball
  # labels and status values, or whether they are limited to only the
  # well-known labels and status values defined on the admin subtab.
  restrict_to_known = messages.BooleanField(16, default=False)

  # Allow special projects to have a custom URL for the "New issue" link.
  custom_issue_entry_url = messages.StringField(56)
