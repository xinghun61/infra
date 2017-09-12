# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Helper functions for deciding who to notify and why.."""

import collections
import logging

import settings
from features import filterrules_helpers
from features import savedqueries_helpers
from framework import framework_bizobj
from framework import framework_constants
from framework import framework_helpers
from framework import framework_views
from framework import monorailrequest
from framework import permissions
from proto import tracker_pb2
from search import query2ast
from search import searchpipeline
from tracker import component_helpers
from tracker import tracker_bizobj

# When sending change notification emails, choose the reply-to header and
# footer message based on three levels of the recipient's permissions
# for that issue.
REPLY_NOT_ALLOWED = 'REPLY_NOT_ALLOWED'
REPLY_MAY_COMMENT = 'REPLY_MAY_COMMENT'
REPLY_MAY_UPDATE = 'REPLY_MAY_UPDATE'

# These are strings describing the various reasons that we send notifications.
REASON_REPORTER = 'You reported this issue'
REASON_OWNER = 'You are the owner of the issue'
REASON_OLD_OWNER = 'You were the issue owner before this change'
REASON_DEFAULT_OWNER = 'A rule made you owner of the issue'
REASON_CCD = 'You were specifically CC\'d on the issue'
REASON_DEFAULT_CCD = 'A rule CC\'d you on the issue'
REASON_STARRER = 'You starred the issue'
REASON_SUBSCRIBER = 'Your saved query matched the issue'
REASON_ALSO_NOTIFY = 'A rule was set up to notify you'
REASON_ALL_NOTIFICATIONS = (
    'The project was configured to send all issue notifications '
    'to this address')


# An AddrPerm is how we represent our decision to notify a given
# email address, which version of the email body to send to them, and
# whether to offer them the option to reply to the notification.  Many
# of the functions in this file pass around AddrPerm lists (an "APL").
# is_member is a boolean
# address is a string email address
# user is a User PB, including user preference fields.
# reply_perm is one of REPLY_NOT_ALLOWED, REPLY_MAY_COMMENT,
# REPLY_MAY_UPDATE.
AddrPerm = collections.namedtuple(
    'AddrPerm', 'is_member, address, user, reply_perm')



def ComputeIssueChangeAddressPermList(
    cnxn, ids_to_consider, project, issue, services, omit_addrs,
    users_by_id, pref_check_function=lambda u: u.notify_issue_change):
  """Return a list of user email addresses to notify of an issue change.

  User email addresses are determined by looking up the given user IDs
  in the given users_by_id dict.

  Args:
    cnxn: connection to SQL database.
    ids_to_consider: list of user IDs for users interested in this issue.
    project: Project PB for the project containing this issue.
    issue: Issue PB for the issue that was updated.
    services: Services.
    omit_addrs: set of strings for email addresses to not notify because
        they already know.
    users_by_id: dict {user_id: user_view} user info.
    pref_check_function: optional function to use to check if a certain
        User PB has a preference set to receive the email being sent.  It
        defaults to "If I am in the issue's owner or cc field", but it
        can be set to check "If I starred the issue."

  Returns:
    A list of AddrPerm objects.
  """
  memb_addr_perm_list = []
  logging.info('Considering %r ', ids_to_consider)
  for user_id in ids_to_consider:
    if user_id == framework_constants.NO_USER_SPECIFIED:
      continue
    user = services.user.GetUser(cnxn, user_id)
    # Notify people who have a pref set, or if they have no User PB
    # because the pref defaults to True.
    if user and not pref_check_function(user):
      logging.info('Not notifying %r: user preference', user.email)
      continue
    # TODO(jrobbins): doing a bulk operation would reduce DB load.
    auth = monorailrequest.AuthData.FromUserID(cnxn, user_id, services)
    perms = permissions.GetPermissions(user, auth.effective_ids, project)
    config = services.config.GetProjectConfig(cnxn, project.project_id)
    granted_perms = tracker_bizobj.GetGrantedPerms(
        issue, auth.effective_ids, config)

    if not permissions.CanViewIssue(
        auth.effective_ids, perms, project, issue,
        granted_perms=granted_perms):
      logging.info('Not notifying %r: user cannot view issue', user.email)
      continue

    addr = users_by_id[user_id].email
    if addr in omit_addrs:
      logging.info('Not notifying %r: user already knows', user.email)
      continue

    recipient_is_member = bool(framework_bizobj.UserIsInProject(
        project, auth.effective_ids))

    reply_perm = REPLY_NOT_ALLOWED
    if project.process_inbound_email:
      if permissions.CanEditIssue(auth.effective_ids, perms, project, issue):
        reply_perm = REPLY_MAY_UPDATE
      elif permissions.CanCommentIssue(
          auth.effective_ids, perms, project, issue):
        reply_perm = REPLY_MAY_COMMENT

    memb_addr_perm_list.append(
      AddrPerm(recipient_is_member, addr, user, reply_perm))

  logging.info('For %s %s, will notify: %r',
               project.project_name, issue.local_id, memb_addr_perm_list)

  return memb_addr_perm_list


def ComputeProjectNotificationAddrList(
    project, contributor_could_view, omit_addrs):
  """Return a list of non-user addresses to notify of an issue change.

  The non-user addresses are specified by email address strings, not
  user IDs.  One such address can be specified in the project PB.
  It is not assumed to have permission to see all issues.

  Args:
    project: Project PB containing the issue that was updated.
    contributor_could_view: True if any project contributor should be able to
        see the notification email, e.g., in a mailing list archive or feed.
    omit_addrs: set of strings for email addresses to not notify because
        they already know.

  Returns:
    A list of tuples: [(False, email_addr, None, reply_permission_level), ...],
    where reply_permission_level is always REPLY_NOT_ALLOWED for now.
  """
  memb_addr_perm_list = []
  if contributor_could_view:
    ml_addr = project.issue_notify_address
    if ml_addr and ml_addr not in omit_addrs:
      memb_addr_perm_list.append(
          AddrPerm(False, ml_addr, None, REPLY_NOT_ALLOWED))

  return memb_addr_perm_list


def ComputeIssueNotificationAddrList(issue, omit_addrs):
  """Return a list of non-user addresses to notify of an issue change.

  The non-user addresses are specified by email address strings, not
  user IDs.  They can be set by filter rules with the "Also notify" action.
  "Also notify" addresses are assumed to have permission to see any issue,
  even a restricted one.

  Args:
    issue: Issue PB for the issue that was updated.
    omit_addrs: set of strings for email addresses to not notify because
        they already know.

  Returns:
    A list of tuples: [(False, email_addr, None, reply_permission_level), ...],
    where reply_permission_level is always REPLY_NOT_ALLOWED for now.
  """
  addr_perm_list = []
  for addr in issue.derived_notify_addrs:
    if addr not in omit_addrs:
      addr_perm_list.append(
          AddrPerm(False, addr, None, REPLY_NOT_ALLOWED))

  return addr_perm_list


def _GetSubscribersAddrPermList(
    cnxn, services, issue, project, config, omit_addrs, users_by_id):
  """Lookup subscribers, evaluate their saved queries, and decide to notify."""
  users_to_queries = GetNonOmittedSubscriptions(
      cnxn, services, [project.project_id], omit_addrs)
  # TODO(jrobbins): need to pass through the user_id to use for "me".
  subscribers_to_notify = EvaluateSubscriptions(
      cnxn, issue, users_to_queries, services, config)
  # TODO(jrobbins): expand any subscribers that are user groups.
  subs_needing_user_views = [
      uid for uid in subscribers_to_notify if uid not in users_by_id]
  users_by_id.update(framework_views.MakeAllUserViews(
      cnxn, services.user, subs_needing_user_views))
  sub_addr_perm_list = ComputeIssueChangeAddressPermList(
      cnxn, subscribers_to_notify, project, issue, services, omit_addrs,
      users_by_id, pref_check_function=lambda *args: True)

  return sub_addr_perm_list


def EvaluateSubscriptions(
    cnxn, issue, users_to_queries, services, config):
  """Determine subscribers who have subs that match the given issue."""
  # Note: unlike filter rule, subscriptions see explicit & derived values.
  lower_labels = [lab.lower() for lab in tracker_bizobj.GetLabels(issue)]
  label_set = set(lower_labels)

  subscribers_to_notify = []
  for uid, saved_queries in users_to_queries.iteritems():
    for sq in saved_queries:
      if sq.subscription_mode != 'immediate':
        continue
      if issue.project_id not in sq.executes_in_project_ids:
        continue
      cond = savedqueries_helpers.SavedQueryToCond(sq)
      logging.info('evaluating query %s: %r', sq.name, cond)
      cond, _warnings = searchpipeline.ReplaceKeywordsWithUserID(uid, cond)
      cond_ast = query2ast.ParseUserQuery(
        cond, '', query2ast.BUILTIN_ISSUE_FIELDS, config)

      if filterrules_helpers.EvalPredicate(
          cnxn, services, cond_ast, issue, label_set, config,
          tracker_bizobj.GetOwnerId(issue), tracker_bizobj.GetCcIds(issue),
          tracker_bizobj.GetStatus(issue)):
        subscribers_to_notify.append(uid)
        break  # Don't bother looking at the user's other saved quereies.

  return subscribers_to_notify


def GetNonOmittedSubscriptions(cnxn, services, project_ids, omit_addrs):
  """Get a dict of users w/ subscriptions in those projects."""
  users_to_queries = services.features.GetSubscriptionsInProjects(
      cnxn, project_ids)
  user_emails = services.user.LookupUserEmails(cnxn, users_to_queries.keys())
  for user_id, email in user_emails.iteritems():
    if email in omit_addrs:
      del users_to_queries[user_id]
  return users_to_queries


def ComputeCustomFieldAddrPerms(
    cnxn, config, issue, project, services, omit_addrs, users_by_id):
  """Check the reasons to notify users named in custom fields."""
  group_reason_list = []
  for fd in config.field_defs:
    named_user_ids = ComputeNamedUserIDsToNotify(issue, fd)
    if named_user_ids:
      named_addr_perms = ComputeIssueChangeAddressPermList(
          cnxn, named_user_ids, project, issue, services, omit_addrs,
          users_by_id, pref_check_function=lambda u: True)
      group_reason_list.append(
          (named_addr_perms, 'You are named in the %s field' % fd.field_name))

  return group_reason_list


def ComputeNamedUserIDsToNotify(issue, fd):
  """Give a list of user IDs to notify because they're in a field."""
  if (fd.field_type == tracker_pb2.FieldTypes.USER_TYPE and
      fd.notify_on == tracker_pb2.NotifyTriggers.ANY_COMMENT):
    return [fv.user_id for fv in issue.field_values
            if fv.field_id == fd.field_id]

  return []


def ComputeComponentFieldAddrPerms(
    cnxn, config, issue, project, services, omit_addrs, users_by_id):
  """Return [(addr_perm_list, reason),...] for users auto-cc'd by components."""
  component_ids = set(issue.component_ids)
  group_reason_list = []
  for cd in config.component_defs:
    if cd.component_id in component_ids:
      cc_ids = component_helpers.GetCcIDsForComponentAndAncestors(config, cd)
      comp_addr_perms = ComputeIssueChangeAddressPermList(
          cnxn, cc_ids, project, issue, services, omit_addrs,
          users_by_id, pref_check_function=lambda u: True)
      group_reason_list.append(
          (comp_addr_perms,
           'You are auto-CC\'d on all issues in component %s' % cd.path))

  return group_reason_list


def ComputeGroupReasonList(
    cnxn, services, project, issue, config, users_by_id, omit_addrs,
    contributor_could_view, starrer_ids=None, noisy=False,
    old_owner_id=None, commenter_in_project=True, include_subscribers=True,
    include_notify_all=True,
    starrer_pref_check_function=lambda u: u.notify_starred_issue_change):
  """Return a list [(addr_perm_list, reason),...] of addrs to notify."""
  # Get the transitive set of owners and Cc'd users, and their UserViews.
  starrer_ids = starrer_ids or []
  reporter = [issue.reporter_id] if issue.reporter_id in starrer_ids else []
  if old_owner_id:
    old_direct_owners, old_transitive_owners = (
        services.usergroup.ExpandAnyUserGroups(cnxn, [old_owner_id]))
  else:
    old_direct_owners, old_transitive_owners = [], []

  direct_owners, transitive_owners = (
      services.usergroup.ExpandAnyUserGroups(cnxn, [issue.owner_id]))
  der_direct_owners, der_transitive_owners = (
      services.usergroup.ExpandAnyUserGroups(
          cnxn, [issue.derived_owner_id]))
  direct_comp, trans_comp = services.usergroup.ExpandAnyUserGroups(
      cnxn, component_helpers.GetComponentCcIDs(issue, config))
  direct_ccs, transitive_ccs = services.usergroup.ExpandAnyUserGroups(
      cnxn, list(issue.cc_ids))
  # TODO(jrobbins): This will say that the user was cc'd by a rule when it
  # was really added to the derived_cc_ids by a component.
  der_direct_ccs, der_transitive_ccs = (
      services.usergroup.ExpandAnyUserGroups(
          cnxn, list(issue.derived_cc_ids)))
  users_by_id.update(framework_views.MakeAllUserViews(
      cnxn, services.user, transitive_owners, der_transitive_owners,
      direct_comp, trans_comp, transitive_ccs, der_transitive_ccs))

  # Notify interested people according to the reason for their interest:
  # owners, component auto-cc'd users, cc'd users, starrers, and
  # other notification addresses.
  reporter_addr_perm_list = ComputeIssueChangeAddressPermList(
      cnxn, reporter, project, issue, services, omit_addrs, users_by_id)
  owner_addr_perm_list = ComputeIssueChangeAddressPermList(
      cnxn, direct_owners + transitive_owners, project, issue,
      services, omit_addrs, users_by_id)
  old_owner_addr_perm_list = ComputeIssueChangeAddressPermList(
      cnxn, old_direct_owners + old_transitive_owners, project, issue,
      services, omit_addrs, users_by_id)
  owner_addr_perm_set = set(owner_addr_perm_list)
  old_owner_addr_perm_list = [ap for ap in old_owner_addr_perm_list
                              if ap not in owner_addr_perm_set]
  der_owner_addr_perm_list = ComputeIssueChangeAddressPermList(
      cnxn, der_direct_owners + der_transitive_owners, project, issue,
      services, omit_addrs, users_by_id)
  cc_addr_perm_list = ComputeIssueChangeAddressPermList(
      cnxn, direct_ccs + transitive_ccs, project, issue,
      services, omit_addrs, users_by_id)
  der_cc_addr_perm_list = ComputeIssueChangeAddressPermList(
      cnxn, der_direct_ccs + der_transitive_ccs, project, issue,
      services, omit_addrs, users_by_id)

  starrer_addr_perm_list = []
  sub_addr_perm_list = []
  if not noisy or commenter_in_project:
    # Avoid an OOM by only notifying a number of starrers that we can handle.
    # And, we really should limit the number of emails that we send anyway.
    max_starrers = settings.max_starrers_to_notify
    starrer_ids = starrer_ids[-max_starrers:]
    # Note: starrers can never be user groups.
    starrer_addr_perm_list = (
        ComputeIssueChangeAddressPermList(
            cnxn, starrer_ids, project, issue,
            services, omit_addrs, users_by_id,
            pref_check_function=starrer_pref_check_function))

    if include_subscribers:
      sub_addr_perm_list = _GetSubscribersAddrPermList(
          cnxn, services, issue, project, config, omit_addrs,
          users_by_id)

  # Get the list of addresses to notify based on filter rules.
  issue_notify_addr_list = ComputeIssueNotificationAddrList(
      issue, omit_addrs)
  # Get the list of addresses to notify based on project settings.
  proj_notify_addr_list = []
  if include_notify_all:
    proj_notify_addr_list = ComputeProjectNotificationAddrList(
        project, contributor_could_view, omit_addrs)

  group_reason_list = [
    (reporter_addr_perm_list, REASON_REPORTER),
    (owner_addr_perm_list, REASON_OWNER),
    (old_owner_addr_perm_list, REASON_OLD_OWNER),
    (der_owner_addr_perm_list, REASON_DEFAULT_OWNER),
    (cc_addr_perm_list, REASON_CCD),
    (der_cc_addr_perm_list, REASON_DEFAULT_CCD),
    ]
  group_reason_list.extend(ComputeComponentFieldAddrPerms(
      cnxn, config, issue, project, services, omit_addrs,
      users_by_id))
  group_reason_list.extend(ComputeCustomFieldAddrPerms(
      cnxn, config, issue, project, services, omit_addrs,
      users_by_id))
  group_reason_list.extend([
      (starrer_addr_perm_list, REASON_STARRER),
      (sub_addr_perm_list, REASON_SUBSCRIBER),
      (issue_notify_addr_list, REASON_ALSO_NOTIFY),
      (proj_notify_addr_list, REASON_ALL_NOTIFICATIONS),
      ])
  return group_reason_list
