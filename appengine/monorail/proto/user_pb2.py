# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Protocol buffers for Monorail users."""

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from protorpc import messages


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

  # Fields 8-13 are no longer used: they were User action counts and limits.

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

  last_visit_timestamp = messages.IntegerField(45, default=0)
  email_bounce_timestamp = messages.IntegerField(46, default=0)
  vacation_message = messages.StringField(47)

  linked_parent_id = messages.IntegerField(48)
  linked_child_ids = messages.IntegerField(49, repeated=True)


class UserPrefValue(messages.Message):
  """Holds a single non-default user pref."""
  name = messages.StringField(1, required=True)
  value = messages.StringField(2)


class UserPrefs(messages.Message):
  """In-memory business object for representing user preferences."""
  user_id = messages.IntegerField(1, required=True)
  prefs = messages.MessageField(UserPrefValue, 2, repeated=True)



def MakeUser(user_id, email=None, obscure_email=False):
  """Create and return a new user record in RAM."""
  user = User(user_id=user_id, obscure_email=bool(obscure_email))
  if email:
    user.email = email
  return user
