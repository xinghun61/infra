# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A set of functions that provide persistence for users.

Business objects are described in user_pb2.py.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import time

import settings
from framework import exceptions
from framework import framework_bizobj
from framework import framework_constants
from framework import framework_helpers
from framework import sql
from framework import validate
from proto import user_pb2
from services import caches


USER_TABLE_NAME = 'User'
USERPREFS_TABLE_NAME = 'UserPrefs'
DISMISSEDCUES_TABLE_NAME = 'DismissedCues'
HOTLISTVISITHISTORY_TABLE_NAME = 'HotlistVisitHistory'
LINKEDACCOUNT_TABLE_NAME = 'LinkedAccount'
LINKEDACCOUNTINVITE_TABLE_NAME = 'LinkedAccountInvite'

USER_COLS = [
    'user_id', 'email', 'is_site_admin', 'notify_issue_change',
    'notify_starred_issue_change', 'email_compact_subject', 'email_view_widget',
    'notify_starred_ping',
    'banned', 'after_issue_update', 'keep_people_perms_open',
    'preview_on_hover', 'obscure_email',
    'last_visit_timestamp', 'email_bounce_timestamp', 'vacation_message']
USERPREFS_COLS = ['user_id', 'name', 'value']
DISMISSEDCUES_COLS = ['user_id', 'cue']
HOTLISTVISITHISTORY_COLS = ['hotlist_id', 'user_id', 'viewed']
LINKEDACCOUNT_COLS = ['parent_id', 'child_id']
LINKEDACCOUNTINVITE_COLS = ['parent_id', 'child_id']


class UserTwoLevelCache(caches.AbstractTwoLevelCache):
  """Class to manage RAM and memcache for User PBs."""

  def __init__(self, cache_manager, user_service):
    super(UserTwoLevelCache, self).__init__(
        cache_manager, 'user', 'user:', user_pb2.User,
        max_size=settings.user_cache_max_size)
    self.user_service = user_service

  def _DeserializeUsersByID(
      self, user_rows, dismissedcue_rows, linkedaccount_rows):
    """Convert database row tuples into User PBs.

    Args:
      user_rows: rows from the User DB table.
      dismissedcue_rows: rows from the DismissedCues DB table.
      linkedaccount_rows: rows from the LinkedAccount DB table.

    Returns:
      A dict {user_id: user_pb} for all the users referenced in user_rows.
    """
    result_dict = {}

    # Make one User PB for each row in user_rows.
    for row in user_rows:
      (user_id, email, is_site_admin,
       notify_issue_change, notify_starred_issue_change,
       email_compact_subject, email_view_widget, notify_starred_ping, banned,
       after_issue_update, keep_people_perms_open, preview_on_hover,
       obscure_email, last_visit_timestamp,
       email_bounce_timestamp, vacation_message) = row
      user = user_pb2.MakeUser(
          user_id, email=email, obscure_email=obscure_email)
      user.is_site_admin = bool(is_site_admin)
      user.notify_issue_change = bool(notify_issue_change)
      user.notify_starred_issue_change = bool(notify_starred_issue_change)
      user.email_compact_subject = bool(email_compact_subject)
      user.email_view_widget = bool(email_view_widget)
      user.notify_starred_ping = bool(notify_starred_ping)
      if banned:
        user.banned = banned
      if after_issue_update:
        user.after_issue_update = user_pb2.IssueUpdateNav(
            after_issue_update.upper())
      user.keep_people_perms_open = bool(keep_people_perms_open)
      user.preview_on_hover = bool(preview_on_hover)
      user.last_visit_timestamp = last_visit_timestamp or 0
      user.email_bounce_timestamp = email_bounce_timestamp or 0
      if vacation_message:
        user.vacation_message = vacation_message
      result_dict[user_id] = user

    # Build up a list of dismissed "cue card" help items for the users.
    for user_id, cue in dismissedcue_rows:
      if user_id not in result_dict:
        logging.error('Found dismissed cues for missing user %r', user_id)
        continue
      result_dict[user_id].dismissed_cues.append(cue)

    # Put in any linked accounts.
    for parent_id, child_id in linkedaccount_rows:
      if parent_id in result_dict:
        result_dict[parent_id].linked_child_ids.append(child_id)
      if child_id in result_dict:
        result_dict[child_id].linked_parent_id = parent_id

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
    dismissedcues_rows = self.user_service.dismissedcues_tbl.Select(
        cnxn, cols=DISMISSEDCUES_COLS, user_id=keys)
    linkedaccount_rows = self.user_service.linkedaccount_tbl.Select(
        cnxn, cols=LINKEDACCOUNT_COLS, parent_id=keys, child_id=keys,
        or_where_conds=True)
    return self._DeserializeUsersByID(
        user_rows, dismissedcues_rows, linkedaccount_rows)


class UserPrefsTwoLevelCache(caches.AbstractTwoLevelCache):
  """Class to manage RAM and memcache for UserPrefs PBs."""

  def __init__(self, cache_manager, user_service):
    super(UserPrefsTwoLevelCache, self).__init__(
        cache_manager, 'user', 'userprefs:', user_pb2.UserPrefs,
        max_size=settings.user_cache_max_size)
    self.user_service = user_service

  def _DeserializeUserPrefsByID(self, userprefs_rows):
    """Convert database row tuples into UserPrefs PBs.

    Args:
      userprefs_rows: rows from the UserPrefs DB table.

    Returns:
      A dict {user_id: userprefs} for all the users in userprefs_rows.
    """
    result_dict = {}

    # Make one UserPrefs PB for each row in userprefs_rows.
    for row in userprefs_rows:
      (user_id, name, value) = row
      if user_id not in result_dict:
        userprefs = user_pb2.UserPrefs(user_id=user_id)
        result_dict[user_id] = userprefs
      else:
        userprefs = result_dict[user_id]
      userprefs.prefs.append(user_pb2.UserPrefValue(name=name, value=value))

    return result_dict

  def FetchItems(self, cnxn, keys):
    """On RAM and memcache miss, retrieve UserPrefs objects from the database.

    Args:
      cnxn: connection to SQL database.
      keys: list of user IDs to retrieve.

    Returns:
      A dict {user_id: userprefs} for each user.
    """
    userprefs_rows = self.user_service.userprefs_tbl.Select(
        cnxn, cols=USERPREFS_COLS, user_id=keys)
    return self._DeserializeUserPrefsByID(userprefs_rows)


class UserService(object):
  """The persistence layer for all user data."""

  def __init__(self, cache_manager):
    """Constructor.

    Args:
      cache_manager: local cache with distributed invalidation.
    """
    self.user_tbl = sql.SQLTableManager(USER_TABLE_NAME)
    self.userprefs_tbl = sql.SQLTableManager(USERPREFS_TABLE_NAME)
    self.dismissedcues_tbl = sql.SQLTableManager(DISMISSEDCUES_TABLE_NAME)
    self.hotlistvisithistory_tbl = sql.SQLTableManager(
        HOTLISTVISITHISTORY_TABLE_NAME)
    self.linkedaccount_tbl = sql.SQLTableManager(LINKEDACCOUNT_TABLE_NAME)
    self.linkedaccountinvite_tbl = sql.SQLTableManager(
        LINKEDACCOUNTINVITE_TABLE_NAME)

    # Like a dictionary {user_id: email}
    self.email_cache = caches.RamCache(cache_manager, 'user', max_size=50000)

    # Like a dictionary {email: user_id}.
    # This will never invaidate, and it doesn't need to.
    self.user_id_cache = caches.RamCache(cache_manager, 'user', max_size=50000)

    # Like a dictionary {user_id: user_pb}
    self.user_2lc = UserTwoLevelCache(cache_manager, self)

    # Like a dictionary {user_id: userprefs}
    self.userprefs_2lc = UserPrefsTwoLevelCache(cache_manager, self)

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

  def LookupUserEmails(self, cnxn, user_ids, ignore_missed=False):
    """Return a dict of email addresses for the given user IDs.

    Args:
      cnxn: connection to SQL database.
      user_ids: list of int user IDs to look up.
      ignore_missed: if True, does not throw NoSuchUserException, when there
        are users not found for some user_ids.

    Returns:
      A dict {user_id: email_addr} for all the requested IDs.

    Raises:
      exceptions.NoSuchUserException: if any requested user cannot be found
         and ignore_missed is False.
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
      if ignore_missed:
        logging.info('No email addresses found for users %r' % nonexist_ids)
      else:
        raise exceptions.NoSuchUserException(
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
      exceptions.NoSuchUserException: if no email address was found for that
      user.
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
      exceptions.NoSuchUserException: if some users were not found and
          autocreate is False.
    """
    # Skip any addresses that look like "--" or are empty,
    # because that means "no user".
    # Also, make sure all email addresses are lower case.
    needed_emails = [email.lower() for email in emails
                     if email
                     and not framework_constants.NO_VALUE_RE.match(email)]

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
      raise exceptions.NoSuchUserException('%r' % nonexist_emails)

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
      exceptions.NoSuchUserException if the user was not found and autocreate
          is False.
    """
    email = email.lower()
    email_dict = self.LookupUserIDs(
        cnxn, [email], autocreate=autocreate, allowgroups=allowgroups)
    if email not in email_dict:
      raise exceptions.NoSuchUserException('%r not found' % email)
    return email_dict[email]

  ### Retrieval of user objects: with preferences and cues

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
      raise exceptions.NoSuchUserException('Cannot update anonymous user')

    delta = {
        'is_site_admin': user.is_site_admin,
        'notify_issue_change': user.notify_issue_change,
        'notify_starred_issue_change': user.notify_starred_issue_change,
        'email_compact_subject': user.email_compact_subject,
        'email_view_widget': user.email_view_widget,
        'notify_starred_ping': user.notify_starred_ping,
        'banned': user.banned,
        'after_issue_update': str(user.after_issue_update or 'UP_TO_LIST'),
        'keep_people_perms_open': user.keep_people_perms_open,
        'preview_on_hover': user.preview_on_hover,
        'obscure_email': user.obscure_email,
        'last_visit_timestamp': user.last_visit_timestamp,
        'email_bounce_timestamp': user.email_bounce_timestamp,
        'vacation_message': user.vacation_message,
        }
    # Start sending UPDATE statements, but don't COMMIT until the end.
    self.user_tbl.Update(cnxn, delta, user_id=user_id, commit=False)

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
        order_by=[('viewed DESC', [])], limit=10)
    return [row[0] for row in recent_hotlist_rows]

  def AddVisitedHotlist(self, cnxn, user_id, hotlist_id, commit=True):
    self.hotlistvisithistory_tbl.Delete(
        cnxn, hotlist_id=hotlist_id, user_id=user_id, commit=False)
    self.hotlistvisithistory_tbl.InsertRows(
        cnxn, HOTLISTVISITHISTORY_COLS,
        [(hotlist_id, user_id, int(time.time()))],
        commit=commit)

  def ExpungeHotlistsFromHistory(self, cnxn, hotlist_ids, commit=True):
    self.hotlistvisithistory_tbl.Delete(
        cnxn, hotlist_id=hotlist_ids, commit=commit)

  def ExpungeUsersHotlistsHistory(self, cnxn, user_ids, commit=True):
    self.hotlistvisithistory_tbl.Delete(cnxn, user_id=user_ids, commit=commit)

  def TrimUserVisitedHotlists(self, cnxn, commit=True):
    """For any user who has visited more than 10 hotlists, trim history."""
    user_id_rows = self.hotlistvisithistory_tbl.Select(
        cnxn, cols=['user_id'], group_by=['user_id'],
        having=[('COUNT(*) > %s', [10])], limit=1000)

    for user_id in [row[0] for row in user_id_rows]:
       viewed_hotlist_rows = self.hotlistvisithistory_tbl.Select(
          cnxn, cols=['viewed'], user_id=user_id,
          order_by=[('viewed DESC', [])])
       if len(viewed_hotlist_rows) > 10:
         cut_off_date = viewed_hotlist_rows[9][0]
         self.hotlistvisithistory_tbl.Delete(
             cnxn, user_id=user_id, where=[('viewed < %s', [cut_off_date])],
             commit=commit)

  ### Linked account invites

  def GetPendingLinkedInvites(self, cnxn, user_id):
    """Return lists of accounts that have invited this account."""
    if not user_id:
      return [], []
    invite_rows = self.linkedaccountinvite_tbl.Select(
        cnxn, cols=LINKEDACCOUNTINVITE_COLS, parent_id=user_id,
        child_id=user_id, or_where_conds=True)
    invite_as_parent = [row[1] for row in invite_rows
                        if row[0] == user_id]
    invite_as_child = [row[0] for row in invite_rows
                       if row[1] == user_id]
    return invite_as_parent, invite_as_child

  def _AssertNotAlreadyLinked(self, cnxn, parent_id, child_id):
    """Check constraints on our linked account graph."""
    # Our linked account graph should be no more than one level deep.
    parent_is_already_a_child = self.linkedaccount_tbl.Select(
        cnxn, cols=LINKEDACCOUNT_COLS, child_id=parent_id)
    if parent_is_already_a_child:
      raise exceptions.InputException('Parent account is already a child')
    child_is_already_a_parent = self.linkedaccount_tbl.Select(
        cnxn, cols=LINKEDACCOUNT_COLS, parent_id=child_id)
    if child_is_already_a_parent:
      raise exceptions.InputException('Child account is already a parent')

    # A child account can only be linked to one parent.
    child_is_already_a_child = self.linkedaccount_tbl.Select(
        cnxn, cols=LINKEDACCOUNT_COLS, child_id=child_id)
    if child_is_already_a_child:
      raise exceptions.InputException('Child account is already linked')

  def InviteLinkedParent(self, cnxn, parent_id, child_id):
    """Child stores an invite for the proposed parent user to consider."""
    if not parent_id:
      raise exceptions.InputException('Parent account is missing')
    if not child_id:
      raise exceptions.InputException('Child account is missing')
    self._AssertNotAlreadyLinked(cnxn, parent_id, child_id)
    self.linkedaccountinvite_tbl.InsertRow(
        cnxn, parent_id=parent_id, child_id=child_id)

  def AcceptLinkedChild(self, cnxn, parent_id, child_id):
    """Parent accepts an invite from a child account."""
    if not parent_id:
      raise exceptions.InputException('Parent account is missing')
    if not child_id:
      raise exceptions.InputException('Child account is missing')
    # Check that the child has previously created an invite for this parent.
    invite_rows = self.linkedaccountinvite_tbl.Select(
        cnxn, cols=LINKEDACCOUNTINVITE_COLS,
        parent_id=parent_id, child_id=child_id)
    if not invite_rows:
      raise exceptions.InputException('No such invite')

    self._AssertNotAlreadyLinked(cnxn, parent_id, child_id)

    self.linkedaccount_tbl.InsertRow(
        cnxn, parent_id=parent_id, child_id=child_id)
    self.linkedaccountinvite_tbl.Delete(
        cnxn, parent_id=parent_id, child_id=child_id)
    self.user_2lc.InvalidateKeys(cnxn, [parent_id, child_id])

  def UnlinkAccounts(self, cnxn, parent_id, child_id):
    """Delete a linked-account relationship."""
    if not parent_id:
      raise exceptions.InputException('Parent account is missing')
    if not child_id:
      raise exceptions.InputException('Child account is missing')
    self.linkedaccount_tbl.Delete(
        cnxn, parent_id=parent_id, child_id=child_id)
    self.user_2lc.InvalidateKeys(cnxn, [parent_id, child_id])

  ### User settings
  # Settings are details about a user account that are usually needed
  # every time that user is displayed to another user.

  # TODO(jrobbins): Move most of these into UserPrefs.
  def UpdateUserSettings(
      self, cnxn, user_id, user, notify=None, notify_starred=None,
      email_compact_subject=None, email_view_widget=None,
      notify_starred_ping=None, obscure_email=None, after_issue_update=None,
      is_site_admin=None, is_banned=None, banned_reason=None,
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
    if notify_starred_ping is not None:
      user.notify_starred_ping = notify_starred_ping
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
    if is_banned is not None:
      if is_banned:
        user.banned = banned_reason or 'No reason given'
      else:
        user.reset('banned')

    # user availability
    if vacation_message is not None:
      user.vacation_message = vacation_message

    # Write the user settings to the database.
    self.UpdateUser(cnxn, user_id, user)

  ### User preferences
  # These are separate from settings in the User objects because they are
  # only needed for the currently signed in user.

  def GetUsersPrefs(self, cnxn, user_ids, use_cache=True):
    """Return {user_id: userprefs} for the requested user IDs."""
    prefs_dict, misses = self.userprefs_2lc.GetAll(
        cnxn, user_ids, use_cache=use_cache)
    # Make sure that every user is represented in the result.
    for user_id in misses:
      prefs_dict[user_id] = user_pb2.UserPrefs(user_id=user_id)
    return prefs_dict

  def GetUserPrefs(self, cnxn, user_id, use_cache=True):
    """Return a UserPrefs PB for the requested user ID."""
    prefs_dict = self.GetUsersPrefs(cnxn, [user_id], use_cache=use_cache)
    return prefs_dict[user_id]

  def GetUserPrefsByEmail(self, cnxn, email, use_cache=True):
    """Return a UserPrefs PB for the requested email, or an empty UserPrefs."""
    try:
      user_id = self.LookupUserID(cnxn, email)
      user_prefs = self.GetUserPrefs(cnxn, user_id, use_cache=use_cache)
    except exceptions.NoSuchUserException:
      user_prefs = user_pb2.UserPrefs()
    return user_prefs

  def SetUserPrefs(self, cnxn, user_id, pref_values):
    """Store the given list of UserPrefValues."""
    userprefs_rows = [(user_id, upv.name, upv.value) for upv in pref_values]
    self.userprefs_tbl.InsertRows(
        cnxn, USERPREFS_COLS, userprefs_rows, replace=True)
    self.userprefs_2lc.InvalidateKeys(cnxn, [user_id])

  ### Expunge all User Data from DB

  def ExpungeUsers(self, cnxn, user_ids):
    """Completely wipes user data from User DB tables for given users.

    This method will not commit the operation. This method will not make
    changes to in-memory data.
    NOTE: This method ends with an operation that deletes user rows. If
    appropriate methods that remove references to the User table rows are
    not called before, the commit will fail. See work_env.ExpungeUsers
    for more info.

    Args:
      cnxn: connection to SQL database.
      user_ids: list of user_ids for users we want to delete.
    """
    self.linkedaccount_tbl.Delete(cnxn, parent_id=user_ids, commit=False)
    self.linkedaccount_tbl.Delete(cnxn, child_id=user_ids, commit=False)
    self.linkedaccountinvite_tbl.Delete(cnxn, parent_id=user_ids, commit=False)
    self.linkedaccountinvite_tbl.Delete(cnxn, child_id=user_ids, commit=False)
    self.dismissedcues_tbl.Delete(cnxn, user_id=user_ids, commit=False)
    self.userprefs_tbl.Delete(cnxn, user_id=user_ids, commit=False)
    self.user_tbl.Delete(cnxn, user_id=user_ids, commit=False)

  def TotalUsersCount(self, cnxn):
    """Returns the total number of rows in the User table.

    The dummy User reserved for representing deleted users within Monorail
    will not be counted.
    """
    # Subtract one so we don't count the deleted user with
    # with user_id = framework_constants.DELETED_USER_ID
    return (self.user_tbl.SelectValue(cnxn, col='COUNT(*)')) - 1

  def GetAllUserEmailsBatch(self, cnxn, limit=1000, offset=0):
    """Returns a list of user emails.

    This method can be used for listing all user emails in Monorail's DB.
    The list will contain at most [limit] emails, and be ordered by
    user_id. The list will start at the given offset value. The email for
    the dummy User reserved for representing deleted users within Monorail
    will never be returned.

    Args:
      cnxn: connection to SQL database.
      limit: limit on the number of emails returned, defaults to 1000.
      offset: starting index of the list, defaults to 0.

    """
    rows = self.user_tbl.Select(
        cnxn, cols=['email'],
        limit=limit,
        offset=offset,
        where=[('user_id != %s', [framework_constants.DELETED_USER_ID])],
        order_by=[('user_id ASC', [])])
    return [row[0] for row in rows]
