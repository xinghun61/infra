# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Protocol buffers for Monorail projects."""

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from protorpc import messages

# Project state affects permissions in that project, and project deletion.
# It is edited on the project admin page.  If it is anything other that LIVE
# it triggers a notice at the top of every project page.
# For more info, see the "Project deletion in Monorail" design doc.
class ProjectState(messages.Enum):
  """Enum for states in the project lifecycle."""
  # Project is visible and indexed. This is the typical state.
  #
  # If moved_to is set, this project is live but has been moved
  # to another location, so redirects will be used or links shown.
  LIVE = 1

  # Project owner has requested the project be archived. Project is
  # read-only to members only, off-limits to non-members.  Issues
  # can be searched when in the project, but should not appear in
  # site-wide searches.  The project name is still in-use by this
  # project.
  #
  # If a delete_time is set, then the project is doomed: (1) the
  # state can only be changed by a site admin, and (2) the project
  # will automatically transition to DELETABLE after that time is
  # reached.
  ARCHIVED = 2

  # Project can be deleted at any time.  The project name should
  # have already been changed to a generated string, so it's
  # impossible to navigate to this project, and the original name
  # can be reused by a new project.
  DELETABLE = 3


# Project access affects permissions in that project.
# It is edited on the project admin page.
class ProjectAccess(messages.Enum):
  """Enum for possible project access levels."""
  # Anyone may view this project, even anonymous users.
  ANYONE = 1

  # Only project members may view the project.
  MEMBERS_ONLY = 3


# A Project PB represents a project in Monorail, which is a workspace for
# project members to collaborate on issues.
# A project is created on the project creation page, searched on the project
# list page, and edited on the project admin page.
class Project(messages.Message):
  """This protocol buffer holds all the metadata associated with a project."""
  state = messages.EnumField(ProjectState, 1, required=True)
  access = messages.EnumField(ProjectAccess, 18, default=ProjectAccess.ANYONE)

  # The short identifier for this project. This value is lower-cased,
  # and must be between 3 and 20 characters (inclusive). Alphanumeric
  # and dashes are allowed, and it must start with an alpha character.
  # Project names must be unique.
  project_name = messages.StringField(2, required=True)

  # A numeric identifier for this project.
  project_id = messages.IntegerField(3, required=True)

  # A one-line summary (human-readable) name of the project.
  summary = messages.StringField(4, default='')

  # A detailed description of the project.
  description = messages.StringField(5, default='')

  # Description of why this project has the state set as it is.
  # This is used for administrative purposes to notify Owners that we
  # are going to delete their project unless they can provide a good
  # reason to not do so.
  state_reason = messages.StringField(9)

  # Time (in seconds) at which an ARCHIVED project may automatically
  # be changed to state DELETABLE.  The state change is done by a
  # cron job.
  delete_time = messages.IntegerField(10)

  # Note that these lists are disjoint (a user ID will not appear twice).
  owner_ids = messages.IntegerField(11, repeated=True)
  committer_ids = messages.IntegerField(12, repeated=True)
  contributor_ids = messages.IntegerField(15, repeated=True)

  class ExtraPerms(messages.Message):
    """Nested message for each member's extra permissions in a project."""
    member_id = messages.IntegerField(1, required=True)
    # Each custom perm is a single word [a-zA-Z0-9].
    perms = messages.StringField(2, repeated=True)

  extra_perms = messages.MessageField(ExtraPerms, 16, repeated=True)
  extra_perms_are_sorted = messages.BooleanField(17, default=False)

  # Project owners may choose to have ALL issue change notifications go to a
  # mailing list (in addition to going directly to the users interested
  # in that issue).
  issue_notify_address = messages.StringField(14)

  # These fields keep track of the cumulative size of all issue attachments
  # in a given project.  Normally, the number of bytes used is compared
  # to a constant defined in the web application.  However, if a custom
  # quota is specified here, it will be used instead.  An issue attachment
  # will fail if its size would put the project over its quota.  Not all
  # projects have these fields: they are only set when the first attachment
  # is uploaded.
  attachment_bytes_used = messages.IntegerField(38, default=0)
  # If quota is not set, default from tracker_constants.py is used.
  attachment_quota = messages.IntegerField(39)

  # NOTE: open slots 40, 41

  # Recent_activity is a timestamp (in seconds since the Epoch) of the
  # last time that an issue was entered, updated, or commented on.
  recent_activity = messages.IntegerField(42, default=0)

  # NOTE: open slots 43...

  # Timestamp (in seconds since the Epoch) of the most recent change
  # to this project that would invalidate cached content.  It is set
  # whenever project membership is edited, or any component config PB
  # is edited.  HTTP requests for auto-complete feeds include this
  # value in the URL.
  cached_content_timestamp = messages.IntegerField(53, default=0)

  # If set, this project has been moved elsewhere.  This can
  # be an absolute URL, the name of another project on the same site.
  moved_to = messages.StringField(60)

  # Enable inbound email processing for issues.
  process_inbound_email = messages.BooleanField(63, default=False)

  # Limit removal of Restrict-* labels to project owners.
  only_owners_remove_restrictions = messages.BooleanField(64, default=False)

  # A per-project read-only lock. This lock (1) is meant to be
  # long-lived (lasting as long as migration operations, project
  # deletion, or anything else might take and (2) is meant to only
  # limit user mutations; whether or not it limits automated actions
  # that would change project data (such as workflow items) is
  # determined based on the action.
  #
  # This lock is implemented as a user-visible string describing the
  # reason for the project being in a read-only state. An absent or empty
  # value indicates that the project is read-write; a present and
  # non-empty value indicates that the project is read-only for the
  # reason described.
  read_only_reason = messages.StringField(65)

  # This option is rarely used, but it makes sense for projects that aim for
  # hub-and-spoke collaboration bewtween a vendor organization (like Google)
  # and representatives of partner companies who are not supposed to know
  # about each other.
  # When true, it prevents project committers, contributors, and visitors
  # from seeing the list of project members on the project summary page,
  # on the People list page, and in autocomplete for issue owner and Cc.
  # Project owners can always see the complete list of project members.
  only_owners_see_contributors = messages.BooleanField(66, default=False)

  # This configures the URLs generated when autolinking revision numbers.
  # E.g., gitiles, viewvc, or crrev.com.
  revision_url_format = messages.StringField(67)

  # The home page of the Project.
  home_page = messages.StringField(68)
  # The url to redirect to for wiki/documentation links.
  docs_url = messages.StringField(71)
  # The url to redirect to for wiki/documentation links.
  source_url = messages.StringField(72)
  # The GCS object ID of the Project's logo.
  logo_gcs_id = messages.StringField(69)
  # The uploaded file name of the Project's logo.
  logo_file_name = messages.StringField(70)


# This PB documents some of the duties of some of the members
# in a given project.  This info is displayed on the project People page.
class ProjectCommitments(messages.Message):
  project_id = messages.IntegerField(50)

  # TODO(agable): Does it still make sense to call it a 'Commitment' when
  # it doesn't contain duties anymore?
  class MemberCommitment(messages.Message):
    member_id = messages.IntegerField(11, required=True)
    notes = messages.StringField(13)

  commitments = messages.MessageField(MemberCommitment, 2, repeated=True)


def MakeProject(
    project_name, project_id=None, state=ProjectState.LIVE,
    access=ProjectAccess.ANYONE, summary=None, description=None,
    moved_to=None, cached_content_timestamp=None,
    owner_ids=None, committer_ids=None, contributor_ids=None,
    read_only_reason=None, home_page=None, docs_url=None, source_url=None,
    logo_gcs_id=None, logo_file_name=None):
  """Returns a project protocol buffer with the given attributes."""
  project = Project(
      project_name=project_name, access=access, state=state)
  if project_id:
    project.project_id = project_id
  if moved_to:
    project.moved_to = moved_to
  if cached_content_timestamp:
    project.cached_content_timestamp = cached_content_timestamp
  if summary:
    project.summary = summary
  if description:
    project.description = description
  if home_page:
    project.home_page = home_page
  if docs_url:
    project.docs_url = docs_url
  if source_url:
    project.source_url = source_url
  if logo_gcs_id:
    project.logo_gcs_id = logo_gcs_id
  if logo_file_name:
    project.logo_file_name = logo_file_name

  project.owner_ids.extend(owner_ids or [])
  project.committer_ids.extend(committer_ids or [])
  project.contributor_ids.extend(contributor_ids or [])

  if read_only_reason is not None:
    project.read_only_reason = read_only_reason

  return project
