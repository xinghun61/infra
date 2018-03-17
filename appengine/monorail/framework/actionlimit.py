# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A set of functions to test action limits.

Action limits help prevent an individual user from abusing the system
by performing an excessive number of operations.  E.g., creating
thousands of projects.

If the user reaches a soft limit within a given time period, the
servlets will start demanding that the user solve a CAPTCHA.

If the user reaches a hard limit within a given time period, any further
requests to perform that type of action will fail.

When the user reaches a lifetime limit, they are shown an error page.
We can increase the lifetime limit for individual users who contact us.
"""

import logging
import time

from framework import framework_constants
from proto import user_pb2


# Action types
PROJECT_CREATION = 1
ISSUE_COMMENT = 2
ISSUE_ATTACHMENT = 3
ISSUE_BULK_EDIT = 4
FLAG_SPAM = 5
API_REQUEST = 6

ACTION_TYPE_NAMES = {
    'project_creation': PROJECT_CREATION,
    'issue_comment': ISSUE_COMMENT,
    'issue_attachment': ISSUE_ATTACHMENT,
    'issue_bulk_edit': ISSUE_BULK_EDIT,
    'flag_spam': FLAG_SPAM,
    'api_request': API_REQUEST,
    }

# Action Limit definitions
# {action_type: (period, soft_limit, hard_limit, life_max),...}
ACTION_LIMITS = {
    PROJECT_CREATION: (framework_constants.SECS_PER_DAY, 2, 5, 25),
    ISSUE_COMMENT: (framework_constants.SECS_PER_DAY / 4, 5, 100, 10000),
    ISSUE_ATTACHMENT: (framework_constants.SECS_PER_DAY, 25, 100, 1000),
    ISSUE_BULK_EDIT: (framework_constants.SECS_PER_DAY, 100, 500, 10000),
    FLAG_SPAM: (framework_constants.SECS_PER_DAY, 100, 100, 10000),
    API_REQUEST: (framework_constants.SECS_PER_DAY, 100000, 100000, 10000000),
    }


# Determine scaling of CAPTCHA frequency.
MAX_SOFT_LIMITS = max([ACTION_LIMITS[key][2] - ACTION_LIMITS[key][1]
                       for key in ACTION_LIMITS])
SQUARES = {i**2 for i in range(1, MAX_SOFT_LIMITS)}
SQUARES.add(1)


def NeedCaptcha(user, action_type, now=None, skip_lifetime_check=False):
  """Check that the user is under the limit on a given action.

  Args:
    user: instance of user_pb2.User.
    action_type: int action type.
    now: int time in millis. Defaults to int(time.time()). Used for testing.
    skip_lifetime_check: No limit for lifetime actions.

  Raises:
    ExcessiveActivityException: when user is over hard or lifetime limits.

  Returns:
    False if user is under the soft-limit. True if user is over the
    soft-limit, but under the hard and lifetime limits.
  """
  if not user:  # Anything that can be done by anon users (which is not
    return False   # much) can be done any number of times w/o CAPTCHA.
  if not now:
    now = int(time.time())

  period, soft, hard, life_max = ACTION_LIMITS[action_type]
  actionlimit_pb = GetLimitPB(user, action_type)

  # First, users that we explicitly trust as non-abusers are allowed to take
  # and unlimited number of actions. And, site admins are trusted non-abusers.
  if user.ignore_action_limits or user.is_site_admin:
    return False

  # Second, check if user has reached lifetime limit.
  if actionlimit_pb.lifetime_limit:
    life_max = actionlimit_pb.lifetime_limit
  if actionlimit_pb.period_soft_limit:
    soft = actionlimit_pb.period_soft_limit
  if actionlimit_pb.period_hard_limit:
    hard = actionlimit_pb.period_hard_limit
  if (not skip_lifetime_check and life_max is not None
      and actionlimit_pb.lifetime_count >= life_max):
    raise ExcessiveActivityException()

  # Third, check for unexpired hard rate limits.
  if (hard is not None and actionlimit_pb.recent_count >= hard and
      now - actionlimit_pb.reset_timestamp <= period):
    raise ExcessiveActivityException()

  # Fourth, users with no previous actions or at the start of a new period must
  # solve one captcha as a barrier to spam accounts.
  # Temporarily reversed until high frequency CAPTCHA requirements are robust.
  # TODO(jrobbins): change this back to return True after CAPTCHAs requirement
  # is determined dynamically, and works on all browsers.
  if not actionlimit_pb or now - actionlimit_pb.reset_timestamp > period:
    return False

  # Finally, check the soft limit in this time period.
  action_limit = False
  if soft is not None:
    recent_count = actionlimit_pb.recent_count
    if recent_count == soft:
      action_limit = True
    elif recent_count > soft:
      remaining_soft = hard - recent_count
      if remaining_soft in SQUARES:
        action_limit = True

  if action_limit:
    logging.info('soft limit captcha: %d', recent_count)
  return action_limit


def GetLimitPB(user, action_type):
  """Return the apporiate action limit PB part of the given User PB."""
  if action_type == PROJECT_CREATION:
    if not user.project_creation_limit:
      user.project_creation_limit = user_pb2.ActionLimit()
    return user.project_creation_limit
  elif action_type == ISSUE_COMMENT:
    if not user.issue_comment_limit:
      user.issue_comment_limit = user_pb2.ActionLimit()
    return user.issue_comment_limit
  elif action_type == ISSUE_ATTACHMENT:
    if not user.issue_attachment_limit:
      user.issue_attachment_limit = user_pb2.ActionLimit()
    return user.issue_attachment_limit
  elif action_type == ISSUE_BULK_EDIT:
    if not user.issue_bulk_edit_limit:
      user.issue_bulk_edit_limit = user_pb2.ActionLimit()
    return user.issue_bulk_edit_limit
  elif action_type == FLAG_SPAM:
    if not user.flag_spam_limit:
      user.flag_spam_limit = user_pb2.ActionLimit()
    return user.flag_spam_limit
  elif action_type == API_REQUEST:
    if not user.api_request_limit:
      user.api_request_limit = user_pb2.ActionLimit()
    return user.api_request_limit
  raise Exception('unexpected action type %r' % action_type)


def ResetRecentActions(user, action_type):
  """Reset the recent counter for an action.

  Args:
    user: instance of user_pb2.User.
    action_type: int action type.
  """
  al = GetLimitPB(user, action_type)
  al.recent_count = 0
  al.reset_timestamp = 0


def CountAction(user, action_type, delta=1, now=int(time.time())):
  """Reset recent counter if eligible, then increment recent and lifetime.

  Args:
    user: instance of user_pb2.User.
    action_type: int action type.
    delta: int number to increment count by.
    now: int time in millis. Defaults to int(time.time()). Used for testing.
  """
  al = GetLimitPB(user, action_type)
  period = ACTION_LIMITS[action_type][0]

  if now - al.reset_timestamp > period:
    al.reset_timestamp = now
    al.recent_count = 0

  al.recent_count = al.recent_count + delta
  al.lifetime_count = al.lifetime_count + delta


def CustomizeLimit(user, action_type, soft_limit, hard_limit, lifetime_limit):
  """Set custom action limits for a user.

  The recent counters are reset to zero, so the user will not run into
  a hard limit.

  Args:
    user: instance of user_pb2.User.
    action_type: int action type.
    soft_limit: soft limit of period.
    hard_limit: hard limit of period.
    lifetime_limit: lifetime limit.
  """
  al = GetLimitPB(user, action_type)
  al.lifetime_limit = lifetime_limit
  al.period_soft_limit = soft_limit
  al.period_hard_limit = hard_limit

  # The mutator will mark the ActionLimit as present, but does not
  # necessarily *initialize* the protobuf. We need to ensure that the
  # lifetime_count is set (a required field). Additional required
  # fields will be set below.
  if not al.lifetime_count:
    al.lifetime_count = 0

  # Clear the recent counters so the user will not hit the period limit.
  al.recent_count = 0
  al.reset_timestamp = 0


class Error(Exception):
  """Base exception class for this package."""


class ExcessiveActivityException(Error):
  """No user with the specified name exists."""
