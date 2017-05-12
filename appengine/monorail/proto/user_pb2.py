# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Protocol buffers for Monorail users."""

from protorpc import messages


class ActionLimit(messages.Message):
  """In-memory business object for action rate limiting.

  We will keep track of the number of actions
  of various types by individual users and limit each user's ability
  to perform a large number of those actions.  E.g., no one user can
  create too many new projects.

  Our application code checks three kinds of action limits:
  1. A soft limit on the number of actions in a period of time.
     If this soft limit is exceeded, the user will need to solve a CAPTCHA.
  2. A hard limit on the number of actions in a period of time.
     if this hard limit is exceeded, the requested actions will fail.
  3. A lifetime limit. The user cannot perform this type of action more
     than this many times, ever.  We can adjust the lifetime limit
     for individual users who contact us.

  The numeric values for the actual limits are coded as constants in our
  application.  Only the lifetime limit is stored in this PB, and then only
  if it differs from the default.
  """
  # Number of times that the user has performed this type of action recently.
  recent_count = messages.IntegerField(1, required=True, default=0)

  # Time of most recent counter reset in seconds.
  # If (Now - reset_timestamp) > threshold, recent_count may be zeroed.
  reset_timestamp = messages.IntegerField(2, required=True, default=0)

  # Number of times that the user has performed this type of action ever.
  lifetime_count = messages.IntegerField(3, required=True, default=0)

  # This field is only present for users who have contacted us and
  # asked us to increase their lifetime limit.  When present, this value
  # overrides the application's built-in default limit.
  lifetime_limit = messages.IntegerField(4, default=0)

  # This field is only present for users who have contacted us and
  # asked us to increase their period limit.  When present, this value
  # overrides the application's built-in default limit.
  period_soft_limit = messages.IntegerField(5, default=0)
  period_hard_limit = messages.IntegerField(6, default=0)


class IssueUpdateNav(messages.Enum):
  """Pref for where a project member goes after an issue update."""
  UP_TO_LIST = 0       # Back to issue list or grid view.
  STAY_SAME_ISSUE = 1  # Show the same issue with the update.
  NEXT_IN_LIST = 2     # Triage mode: go to next issue, if any.


class User(messages.Message):
  """In-memory busines object for representing users."""
  user_id = messages.IntegerField(1)  # TODO(jrobbins): make it required.

  # Is this user a site administer?
  is_site_admin = messages.BooleanField(4, required=True, default=False)

  # User notification preferences.  These preferences describe when
  # a user is sent a email notification after an issue has changed.
  # The user is notified if either of the following is true:
  # 1. notify_issue_change is True and the user is named in the
  # issue's Owner or CC field.
  # 2. notify_starred_issue_change is True and the user has starred
  # the issue.
  notify_issue_change = messages.BooleanField(5, default=True)
  notify_starred_issue_change = messages.BooleanField(6, default=True)
  # Opt-in to email subject lines like "proj:123: issue summary".
  email_compact_subject = messages.BooleanField(14, default=False)
  # Opt-out of "View Issue" button in Gmail inbox.
  email_view_widget = messages.BooleanField(15, default=True)
  # Opt-in to ping emails from issues that the user starred.
  notify_starred_ping = messages.BooleanField(16, default=False)

  # This user has been banned, and this string describes why. All access
  # to Monorail pages should be disabled.
  banned = messages.StringField(7, default='')

  # User action counts and limits.
  project_creation_limit = messages.MessageField(ActionLimit, 8)
  issue_comment_limit = messages.MessageField(ActionLimit, 9)
  issue_attachment_limit = messages.MessageField(ActionLimit, 10)
  issue_bulk_edit_limit = messages.MessageField(ActionLimit, 11)
  ignore_action_limits = messages.BooleanField(13, default=False)

  after_issue_update = messages.EnumField(
      IssueUpdateNav, 29, default=IssueUpdateNav.STAY_SAME_ISSUE)

  # Should we obfuscate the user's email address and require solving a captcha
  # to reveal it entirely? The default value corresponds to requiring users to
  # opt into publishing their identities, but our code ensures that the
  # opposite takes place for Gmail accounts.
  obscure_email = messages.BooleanField(26, default=True)

  # The email address chosen by the user to reveal on the site.
  email = messages.StringField(27)

  # The user has seen these cue cards and dismissed them.
  dismissed_cues = messages.StringField(32, repeated=True)

  # Sticky state for show/hide widget on people details page.
  keep_people_perms_open = messages.BooleanField(33, default=False)

  deleted = messages.BooleanField(39, default=False)
  deleted_timestamp = messages.IntegerField(40, default=0)

  preview_on_hover = messages.BooleanField(42, default=True)

  flag_spam_limit = messages.MessageField(ActionLimit, 43)
  api_request_limit = messages.MessageField(ActionLimit, 44)

  last_visit_timestamp = messages.IntegerField(45, default=0)
  email_bounce_timestamp = messages.IntegerField(46, default=0)
  vacation_message = messages.StringField(47)


def MakeUser(user_id, email=None, obscure_email=False):
  """Create and return a new user record in RAM."""
  user = User(user_id=user_id, obscure_email=bool(obscure_email))
  if email:
    user.email = email
  user.project_creation_limit = ActionLimit()
  user.issue_comment_limit = ActionLimit()
  user.issue_attachment_limit = ActionLimit()
  user.issue_bulk_edit_limit = ActionLimit()
  user.flag_spam_limit = ActionLimit()
  user.api_request_limit = ActionLimit()
  return user
