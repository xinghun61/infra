# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A set of functions that provide persistence for users.

Business objects are described in user_pb2.py.
"""

import logging
import time

import settings
from framework import actionlimit
from framework import framework_bizobj
from framework import framework_constants
from framework import framework_helpers
from framework import sql
from framework import validate
from proto import user_pb2
from services import caches


USER_TABLE_NAME = 'User'
ACTIONLIMIT_TABLE_NAME = 'ActionLimit'
DISMISSEDCUES_TABLE_NAME = 'DismissedCues'
HOTLISTVISITHISTORY_TABLE_NAME = 'HotlistVisitHistory'

USER_COLS = [
    'user_id', 'email', 'is_site_admin', 'notify_issue_change',
    'notify_starred_issue_change', 'email_compact_subject', 'email_view_widget',
    'banned', 'after_issue_update', 'keep_people_perms_open',
    'preview_on_hover', 'ignore_action_limits', 'obscure_email',
    'last_visit_timestamp', 'email_bounce_timestamp', 'vacation_message']
ACTIONLIMIT_COLS = [
    'user_id', 'action_kind', 'recent_count', 'reset_timestamp',
    'lifetime_count', 'lifetime_limit', 'period_soft_limit',
    'period_hard_limit']
DISMISSEDCUES_COLS = ['user_id', 'cue']
HOTLISTVISITHISTORY_COLS = ['hotlist_id', 'user_id', 'viewed']


class UserTwoLevelCache(caches.AbstractTwoLevelCache):
  """Class to manage RAM and memcache for User PBs."""

  def __init__(self, cache_manager, user_service):
    super(UserTwoLevelCache, self).__init__(
        cache_manager, 'user', 'user:', user_pb2.User,
        max_size=settings.user_cache_max_size)
    self.user_service = user_service

  def _CheckCompatibility(self, value):
    """Ignore old-format cached Users that lack user_id."""
    # TODO(jrobbins): remove this method after the version has been deployed
    # and memcache has been cleared.
    return value.user_id is not None

  def _DeserializeUsersByID(
      self, user_rows, actionlimit_rows, dismissedcue_rows):
    """Convert database row tuples into User PBs.

    Args:
      user_rows: rows from the User DB table.
      actionlimit_rows: rows from the ActionLimit DB table.
      dismissedcue_rows: rows from the DismissedCues DB table.

    Returns:
      A dict {user_id: user_pb} for all the users referenced in user_rows.
    """
    result_dict = {}

    # Make one User PB for each row in user_rows.
    for row in user_rows:
      (user_id, email, is_site_admin,
       notify_issue_change, notify_starred_issue_change,
       email_compact_subject, email_view_widget, banned,
       after_issue_update, keep_people_perms_open, preview_on_hover,
       ignore_action_limits, obscure_email, last_visit_timestamp,
       email_bounce_timestamp, vacation_message) = row
      user = user_pb2.MakeUser(
          user_id, email=email, obscure_email=obscure_email)
      user.is_site_admin = bool(is_site_admin)
      user.notify_issue_change = bool(notify_issue_change)
      user.notify_starred_issue_change = bool(notify_starred_issue_change)
      user.email_compact_subject = bool(email_compact_subject)
      user.email_view_widget = bool(email_view_widget)
      if banned:
        user.banned = banned
      if after_issue_update:
        user.after_issue_update = user_pb2.IssueUpdateNav(
            after_issue_update.upper())
      user.keep_people_perms_open = bool(keep_people_perms_open)
      user.preview_on_hover = bool(preview_on_hover)
      user.ignore_action_limits = bool(ignore_action_limits)
      user.last_visit_timestamp = last_visit_timestamp or 0
      user.email_bounce_timestamp = email_bounce_timestamp or 0
      if vacation_message:
        user.vacation_message = vacation_message
      result_dict[user_id] = user

    # Make an ActionLimit for each actionlimit row and attach it to a User PB.
    for row in actionlimit_rows:
      (user_id, action_type_name, recent_count, reset_timestamp,
       lifetime_count, lifetime_limit, period_soft_limit,
       period_hard_limit) = row
      if user_id not in result_dict:
        logging.error('Found action limits for missing user %r', user_id)
        continue
      user = result_dict[user_id]
      action_type = actionlimit.ACTION_TYPE_NAMES[action_type_name]
      al = actionlimit.GetLimitPB(user, action_type)
      al.recent_count = recent_count
      al.reset_timestamp = reset_timestamp
      al.lifetime_count = lifetime_count
      al.lifetime_limit = lifetime_limit
      al.period_soft_limit = period_soft_limit
      al.period_hard_limit = period_hard_limit

    # Build up a list of dismissed "cue card" help items for the users.
    for user_id, cue in dismissedcue_rows:
      if user_id not in result_dict:
        logging.error('Found dismissed cues for missing user %r', user_id)
        continue
      result_dict[user_id].dismissed_cues.append(cue)

    return result_dict

  def FetchItems(self, cnxn, keys):
    """On RAM and memcache miss, retrieve User objects from the database.

    Args:
      cnxn: connection to SQL database.
      keys: list of user IDs to retrieve.

    Returns:
      A dict {user_id: user_pb} for each user that satisfies the conditions.
    """
    user_rows = self.user_service.user_tbl.Select(
        cnxn, cols=USER_COLS, user_id=keys)
    actionlimit_rows = self.user_service.actionlimit_tbl.Select(
        cnxn, cols=ACTIONLIMIT_COLS, user_id=keys)
    dismissedcues_rows = self.user_service.dismissedcues_tbl.Select(
        cnxn, cols=DISMISSEDCUES_COLS, user_id=keys)
    return self._DeserializeUsersByID(
        user_rows, actionlimit_rows, dismissedcues_rows)


class UserService(object):
  """The persistence layer for all user data."""

  def __init__(self, cache_manager):
    """Constructor.

    Args:
      cache_manager: local cache with distributed invalidation.
    """
    self.user_tbl = sql.SQLTableManager(USER_TABLE_NAME)
    self.actionlimit_tbl = sql.SQLTableManager(ACTIONLIMIT_TABLE_NAME)
    self.dismissedcues_tbl = sql.SQLTableManager(DISMISSEDCUES_TABLE_NAME)
    self.hotlistvisithistory_tbl = sql.SQLTableManager(
        HOTLISTVISITHISTORY_TABLE_NAME)

    # Like a dictionary {user_id: email}
    self.email_cache = cache_manager.MakeCache('user', max_size=50000)

    # Like a dictionary {email: user_id}.
    # This will never invaidate, and it doesn't need to.
    self.user_id_cache = cache_manager.MakeCache('user', max_size=50000)

    # Like a dictionary {user_id: user_pb}
    self.user_2lc = UserTwoLevelCache(cache_manager, self)

  ### Creating users

  def _CreateUsers(self, cnxn, emails):
    """Create many users in the database."""
    emails = [email.lower() for email in emails]
    ids = [framework_helpers.MurmurHash3_x86_32(email) for email in emails]
    row_values = [
      (user_id, email, not framework_bizobj.IsPriviledgedDomainUser(email))
      for (user_id, email) in zip(ids, emails)]
    self.user_tbl.InsertRows(
        cnxn, ['user_id', 'email', 'obscure_email'], row_values)
    self.user_2lc.InvalidateKeys(cnxn, ids)

  ### Lookup of user ID and email address

  def LookupUserEmails(self, cnxn, user_ids):
    """Return a dict of email addresses for the given user IDs.

    Args:
      cnxn: connection to SQL database.
      user_ids: list of int user IDs to look up.

    Returns:
      A dict {user_id: email_addr} for all the requested IDs.

    Raises:
      NoSuchUserException: if any requested user cannot be found.
    """
    self.email_cache.CacheItem(framework_constants.NO_USER_SPECIFIED, '')
    emails_dict, missed_ids = self.email_cache.GetAll(user_ids)
    if missed_ids:
      logging.info('got %d user emails from cache', len(emails_dict))
      rows = self.user_tbl.Select(
          cnxn, cols=['user_id', 'email'], user_id=missed_ids)
      retrieved_dict = dict(rows)
      logging.info('looked up users %r', retrieved_dict)
      self.email_cache.CacheAll(retrieved_dict)
      emails_dict.update(retrieved_dict)

    # Check if there are any that we could not find.  ID 0 means "no user".
    nonexist_ids = [user_id for user_id in user_ids
                    if user_id and user_id not in emails_dict]
    if nonexist_ids:
      raise NoSuchUserException(
          'No email addresses found for users %r' % nonexist_ids)

    return emails_dict

  def LookupUserEmail(self, cnxn, user_id):
    """Get the email address of the given user.

    Args:
      cnxn: connection to SQL database.
      user_id: int user ID of the user whose email address is needed.

    Returns:
      String email address of that user or None if user_id is invalid.

    Raises:
      NoSuchUserException: if no email address was found for that user.
    """
    if not user_id:
      return None
    emails_dict = self.LookupUserEmails(cnxn, [user_id])
    return emails_dict[user_id]

  def LookupExistingUserIDs(self, cnxn, emails):
    """Return a dict of user IDs for the given emails for users that exist.

    Args:
      cnxn: connection to SQL database.
      emails: list of string email addresses.

    Returns:
      A dict {email_addr: user_id} for the requested emails.
    """
    # Look up these users in the RAM cache
    user_id_dict, missed_emails = self.user_id_cache.GetAll(emails)
    logging.info('hit %d emails, missed %r', len(user_id_dict), missed_emails)

    # Hit the DB to lookup any user IDs that were not cached.
    if missed_emails:
      rows = self.user_tbl.Select(
          cnxn, cols=['email', 'user_id'], email=missed_emails)
      retrieved_dict = dict(rows)
      # Cache all the user IDs that we retrieved to make later requests faster.
      self.user_id_cache.CacheAll(retrieved_dict)
      user_id_dict.update(retrieved_dict)

    logging.info('looked up User IDs %r', user_id_dict)
    return user_id_dict

  def LookupUserIDs(self, cnxn, emails, autocreate=False,
                    allowgroups=False):
    """Return a dict of user IDs for the given emails.

    Args:
      cnxn: connection to SQL database.
      emails: list of string email addresses.
      autocreate: set to True to create users that were not found.
      allowgroups: set to True to allow non-email user name for group
      creation.

    Returns:
      A dict {email_addr: user_id} for the requested emails.

    Raises:
      NoSuchUserException: if some users were not found and autocreate is
          False.
    """
    # Skip any addresses that look like "--", because that means "no user".
    # Also, make sure all email addresses are lower case.
    needed_emails = [email.lower() for email in emails
                     if not framework_constants.NO_VALUE_RE.match(email)]

    # Look up these users in the RAM cache
    user_id_dict = self.LookupExistingUserIDs(cnxn, needed_emails)
    if len(needed_emails) == len(user_id_dict):
      logging.info('found all %d emails', len(user_id_dict))
      return user_id_dict

    # If any were not found in the DB, create them or raise an exception.
    nonexist_emails = [email for email in needed_emails
                       if email not in user_id_dict]
    logging.info('nonexist_emails: %r, autocreate is %r',
                 nonexist_emails, autocreate)
    if not autocreate:
      raise NoSuchUserException('%r' % nonexist_emails)

    if not allowgroups:
      # Only create accounts for valid email addresses.
      nonexist_emails = [email for email in nonexist_emails
                         if validate.IsValidEmail(email)]
      if not nonexist_emails:
        return user_id_dict

    self._CreateUsers(cnxn, nonexist_emails)
    created_rows = self.user_tbl.Select(
      cnxn, cols=['email', 'user_id'], email=nonexist_emails)
    created_dict = dict(created_rows)
    # Cache all the user IDs that we retrieved to make later requests faster.
    self.user_id_cache.CacheAll(created_dict)
    user_id_dict.update(created_dict)

    logging.info('looked up User IDs %r', user_id_dict)
    return user_id_dict

  def LookupUserID(self, cnxn, email, autocreate=False, allowgroups=False):
    """Get one user ID for the given email address.

    Args:
      cnxn: connection to SQL database.
      email: string email address of the user to look up.
      autocreate: set to True to create users that were not found.
      allowgroups: set to True to allow non-email user name for group
      creation.

    Returns:
      The int user ID of the specified user.

    Raises:
      NoSuchUserException if the user was not found and autocreate is False.
    """
    email = email.lower()
    email_dict = self.LookupUserIDs(
        cnxn, [email], autocreate=autocreate, allowgroups=allowgroups)
    if email not in email_dict:
      raise NoSuchUserException('%r not found' % email)
    return email_dict[email]

  ### Retrieval of user objects: with preferences, action limits, and cues

  def GetUsersByIDs(self, cnxn, user_ids, use_cache=True):
    """Return a dictionary of retrieved User PBs.

    Args:
      cnxn: connection to SQL database.
      user_ids: list of user IDs to fetch.
      use_cache: set to False to ignore cache and force DB lookup.

    Returns:
      A dict {user_id: user_pb} for each specified user ID.  For any user ID
      that is not fount in the DB, a default User PB is created on-the-fly.
    """
    # Check the RAM cache and memcache, as appropriate.
    result_dict, missed_ids = self.user_2lc.GetAll(
        cnxn, user_ids, use_cache=use_cache)

    # Provide default values for any user ID that was not found.
    result_dict.update(
        (user_id, user_pb2.MakeUser(user_id))
        for user_id in missed_ids)

    return result_dict

  def GetUser(self, cnxn, user_id):
    """Load the specified user from the user details table."""
    return self.GetUsersByIDs(cnxn, [user_id])[user_id]

  ### Updating user objects

  def UpdateUser(self, cnxn, user_id, user):
    """Store a user PB in the database.

    Args:
      cnxn: connection to SQL database.
      user_id: int user ID of the user to update.
      user: User PB to store.

    Returns:
      Nothing.
    """
    if not user_id:
      raise NoSuchUserException('Cannot update anonymous user')

    delta = {
        'is_site_admin': user.is_site_admin,
        'notify_issue_change': user.notify_issue_change,
        'notify_starred_issue_change': user.notify_starred_issue_change,
        'email_compact_subject': user.email_compact_subject,
        'email_view_widget': user.email_view_widget,
        'banned': user.banned,
        'after_issue_update': str(user.after_issue_update or 'UP_TO_LIST'),
        'keep_people_perms_open': user.keep_people_perms_open,
        'preview_on_hover': user.preview_on_hover,
        'ignore_action_limits': user.ignore_action_limits,
        'obscure_email': user.obscure_email,
        'last_visit_timestamp': user.last_visit_timestamp,
        'email_bounce_timestamp': user.email_bounce_timestamp,
        'vacation_message': user.vacation_message,
        }
    # Start sending UPDATE statements, but don't COMMIT until the end.
    self.user_tbl.Update(cnxn, delta, user_id=user_id, commit=False)

    # Add rows for any ActionLimits that are defined for this user.
    al_rows = []
    if user.get_assigned_value('project_creation_limit'):
      al_rows.append(_ActionLimitToRow(
          user_id, 'project_creation', user.project_creation_limit))
    if user.get_assigned_value('issue_comment_limit'):
      al_rows.append(_ActionLimitToRow(
          user_id, 'issue_comment', user.issue_comment_limit))
    if user.get_assigned_value('issue_attachment_limit'):
      al_rows.append(_ActionLimitToRow(
          user_id, 'issue_attachment', user.issue_attachment_limit))
    if user.get_assigned_value('issue_bulk_edit_limit'):
      al_rows.append(_ActionLimitToRow(
          user_id, 'issue_bulk_edit', user.issue_bulk_edit_limit))
    if user.get_assigned_value('api_request_limit'):
      al_rows.append(_ActionLimitToRow(
          user_id, 'api_request', user.api_request_limit))

    self.actionlimit_tbl.Delete(cnxn, user_id=user_id, commit=False)
    self.actionlimit_tbl.InsertRows(
        cnxn, ACTIONLIMIT_COLS, al_rows, commit=False)

    # Rewrite all the DismissedCues rows.
    cues_rows = [(user_id, cue) for cue in user.dismissed_cues]
    self.dismissedcues_tbl.Delete(cnxn, user_id=user_id, commit=False)
    self.dismissedcues_tbl.InsertRows(
        cnxn, DISMISSEDCUES_COLS, cues_rows, commit=False)

    cnxn.Commit()
    self.user_2lc.InvalidateKeys(cnxn, [user_id])

  def UpdateUserBan(
      self, cnxn, user_id, user,
      is_banned=None, banned_reason=None):
    if is_banned is not None:
      if is_banned:
        user.banned = banned_reason or 'No reason given'
      else:
        user.reset('banned')

    # Write the user settings to the database.
    self.UpdateUser(cnxn, user_id, user)

  def GetRecentlyVisitedHotlists(self, cnxn, user_id):
    recent_hotlist_rows = self.hotlistvisithistory_tbl.Select(
        cnxn, cols=['hotlist_id'], user_id=[user_id],
        order_by=[('viewed DESC')], limit=10)
    return [row[0] for row in recent_hotlist_rows]

  def AddVisitedHotlist(self, cnxn, user_id, hotlist_id, commit=True):
    self.hotlistvisithistory_tbl.Delete(
        cnxn, hotlist_id=hotlist_id, user_id=user_id, commit=False)
    self.hotlistvisithistory_tbl.InsertRows(
        cnxn, HOTLISTVISITHISTORY_COLS,
        [(hotlist_id, user_id, int(time.time()))],
        commit=commit)

  def TrimUserVisitedHotlists(self, cnxn, commit=True):
    user_id_rows = self.hotlistvisithistory_tbl.Select(
        cnxn, cols=['user_id'], group_by='user_id',
        having=[('COUNT(*) > %s', [10])], limit=1000)
    user_ids = list(set([row[0] for row in user_id_rows]))

    for user_id in user_ids:
       viewed_hotlist_rows = self.hotlistvisithistory_tbl.Select(
          cnxn, cols=[], user_id=user_id, order_by=[('viewed DESC', [])])
       if len(viewed_hotlist_rows) > 10:
         cut_off_date = viewed_hotlist_rows[9][2]
         self.hotlistvisithistory_tbl.Delete(
             cnxn, user_id=user_id, where=[('viewed < %s', [cut_off_date])],
             commit=commit)

  def UpdateUserSettings(
      self, cnxn, user_id, user, notify=None, notify_starred=None,
      email_compact_subject=None, email_view_widget=None,
      obscure_email=None, after_issue_update=None,
      is_site_admin=None, ignore_action_limits=None,
      is_banned=None, banned_reason=None, action_limit_updates=None,
      dismissed_cues=None, keep_people_perms_open=None, preview_on_hover=None,
      vacation_message=None):
    """Update the preferences of the specified user.

    Args:
      cnxn: connection to SQL database.
      user_id: int user ID of the user whose settings we are updating.
      user: User PB of user before changes are applied.
      keyword args: dictionary of setting names mapped to new values.

    Returns:
      The user's new User PB.
    """
    # notifications
    if notify is not None:
      user.notify_issue_change = notify
    if notify_starred is not None:
      user.notify_starred_issue_change = notify_starred
    if email_compact_subject is not None:
      user.email_compact_subject = email_compact_subject
    if email_view_widget is not None:
      user.email_view_widget = email_view_widget

    # display options
    if after_issue_update is not None:
      user.after_issue_update = user_pb2.IssueUpdateNav(after_issue_update)
    if preview_on_hover is not None:
      user.preview_on_hover = preview_on_hover
    if dismissed_cues:  # Note, we never set it back to [].
      user.dismissed_cues = dismissed_cues
    if keep_people_perms_open is not None:
      user.keep_people_perms_open = keep_people_perms_open

    # misc
    if obscure_email is not None:
      user.obscure_email = obscure_email

    # admin
    if is_site_admin is not None:
      user.is_site_admin = is_site_admin
    if ignore_action_limits is not None:
      user.ignore_action_limits = ignore_action_limits
    if is_banned is not None:
      if is_banned:
        user.banned = banned_reason or 'No reason given'
      else:
        user.reset('banned')

    # user availablity
    if vacation_message is not None:
      user.vacation_message = vacation_message

    # action limits
    if action_limit_updates:
      self._UpdateActionLimits(user, action_limit_updates)

    # Write the user settings to the database.
    self.UpdateUser(cnxn, user_id, user)

  def _UpdateActionLimits(self, user, action_limit_updates):
    """Apply action limit updates to a user's account."""
    for action, new_limit_tuple in action_limit_updates.iteritems():
      if action in actionlimit.ACTION_TYPE_NAMES:
        action_type = actionlimit.ACTION_TYPE_NAMES[action]
        if new_limit_tuple is None:
          actionlimit.ResetRecentActions(user, action_type)
        else:
          new_soft_limit, new_hard_limit, new_lifetime_limit = new_limit_tuple

          pb_getter = action + '_limit'
          old_lifetime_limit = getattr(user, pb_getter).lifetime_limit
          old_soft_limit = getattr(user, pb_getter).period_soft_limit
          old_hard_limit = getattr(user, pb_getter).period_hard_limit

          if ((new_lifetime_limit >= 0 and
               new_lifetime_limit != old_lifetime_limit) or
              (new_soft_limit >= 0 and new_soft_limit != old_soft_limit) or
              (new_hard_limit >= 0 and new_hard_limit != old_hard_limit)):
            actionlimit.CustomizeLimit(user, action_type, new_soft_limit,
                                       new_hard_limit, new_lifetime_limit)


def _ActionLimitToRow(user_id, action_kind, al):
  """Return a tuple for an SQL table row for an action limit."""
  return (user_id, action_kind, al.recent_count, al.reset_timestamp,
          al.lifetime_count, al.lifetime_limit, al.period_soft_limit,
          al.period_hard_limit)


class Error(Exception):
  """Base class for errors from this module."""
  pass


class NoSuchUserException(Error):
  """No user with the specified name exists."""
  pass
