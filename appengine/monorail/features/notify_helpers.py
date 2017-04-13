# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Helper functions for email notifications of issue changes."""

import cgi
import logging
import re

from django.utils.html import urlize
from third_party import ezt

from features import filterrules_helpers
from features import savedqueries_helpers
from framework import emailfmt
from framework import framework_bizobj
from framework import framework_constants
from framework import framework_helpers
from framework import jsonfeed
from framework import monorailrequest
from framework import permissions
from framework import template_helpers
from framework import urls
from proto import tracker_pb2
from search import query2ast
from search import searchpipeline
from tracker import component_helpers
from tracker import tracker_bizobj


# Email tasks can get too large for AppEngine to handle. In order to prevent
# that, we set a maximum body size, and may truncate messages to that length.
# We set this value to 40k so that the total of 40k body + 40k html_body +
# metadata does not exceed AppEngine's limit of 100k.
MAX_EMAIL_BODY_SIZE = 40 * 1024

# When sending change notification emails, choose the reply-to header and
# footer message based on three levels of the recipient's permissions
# for that issue.
REPLY_NOT_ALLOWED = 'REPLY_NOT_ALLOWED'
REPLY_MAY_COMMENT = 'REPLY_MAY_COMMENT'
REPLY_MAY_UPDATE = 'REPLY_MAY_UPDATE'

# This HTML template adds mark up which enables Gmail/Inbox to display a
# convenient link that takes users to the CL directly from the inbox without
# having to click on the email.
# Documentation for this schema.org markup is here:
#   https://developers.google.com/gmail/markup/reference/go-to-action
HTML_BODY_WITH_GMAIL_ACTION_TEMPLATE = """
<html>
<body>
<script type="application/ld+json">
{
  "@context": "http://schema.org",
  "@type": "EmailMessage",
  "potentialAction": {
    "@type": "ViewAction",
    "name": "View Issue",
    "url": "%(url)s"
  },
  "description": ""
}
</script>

<div style="font-family: arial, sans-serif">%(body)s</div>
</body>
</html>
"""

HTML_BODY_WITHOUT_GMAIL_ACTION_TEMPLATE = """
<html>
<body>
<div style="font-family: arial, sans-serif">%(body)s</div>
</body>
</html>
"""


class NotifyTaskBase(jsonfeed.InternalTask):
  """Abstract base class for notification task handler."""

  _EMAIL_TEMPLATE = None  # Subclasses must override this.

  CHECK_SECURITY_TOKEN = False

  def __init__(self, *args, **kwargs):
    super(NotifyTaskBase, self).__init__(*args, **kwargs)

    if not self._EMAIL_TEMPLATE:
      raise Exception('Subclasses must override _EMAIL_TEMPLATE.'
                      ' This class must not be called directly.')
    # We use FORMAT_RAW for emails because they are plain text, not HTML.
    # TODO(jrobbins): consider sending HTML formatted emails someday.
    self.email_template = template_helpers.MonorailTemplate(
        framework_constants.TEMPLATE_PATH + self._EMAIL_TEMPLATE,
        compress_whitespace=False, base_format=ezt.FORMAT_RAW)


def ComputeIssueChangeAddressPermList(
    cnxn, ids_to_consider, project, issue, services, omit_addrs,
    users_by_id, pref_check_function=lambda u: u.notify_issue_change):
  """Return a list of user email addresses to notify of an issue change.

  User email addresses are determined by looking up the given user IDs
  in the given users_by_id dict.

  Args:
    cnxn: connection to SQL database.
    ids_to_consider: list of user IDs for users interested in this issue.
    project: Project PB for the project contianing containing this issue.
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
    A list of tuples: [(recipient_is_member, address, user, reply_perm), ...]
    where reply_perm is one of REPLY_NOT_ALLOWED, REPLY_MAY_COMMENT,
    REPLY_MAY_UPDATE.
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

    memb_addr_perm_list.append((recipient_is_member, addr, user, reply_perm))

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
      memb_addr_perm_list.append((False, ml_addr, None, REPLY_NOT_ALLOWED))

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
      addr_perm_list.append((False, addr, None, REPLY_NOT_ALLOWED))

  return addr_perm_list


def MakeBulletedEmailWorkItems(
    group_reason_list, issue, body_for_non_members, body_for_members,
    project, hostport, commenter_view, detail_url, seq_num=None):
  """Make a list of dicts describing email-sending tasks to notify users.

  Args:
    group_reason_list: list of (is_memb, addr_perm, reason) tuples.
    issue: Issue that was updated.
    body_for_non_members: string body of email to send to non-members.
    body_for_members: string body of email to send to members.
    project: Project that contains the issue.
    hostport: string hostname and port number for links to the site.
    commenter_view: UserView for the user who made the comment.
    detail_url: str direct link to the issue.
    seq_num: optional int sequence number of the comment.

  Returns:
    A list of dictionaries, each with all needed info to send an individual
    email to one user.  Each email contains a footer that lists all the
    reasons why that user received the email.
  """
  logging.info('group_reason_list is %r', group_reason_list)
  addr_reasons_dict = {}
  for group, reason in group_reason_list:
    for memb_addr_perm in group:
      addr_reasons_dict.setdefault(memb_addr_perm, []).append(reason)

  email_tasks = []
  for memb_addr_perm, reasons in addr_reasons_dict.iteritems():
    email_tasks.append(_MakeEmailWorkItem(
        memb_addr_perm, reasons, issue, body_for_non_members,
        body_for_members, project, hostport, commenter_view, detail_url,
        seq_num=seq_num))

  return email_tasks


def _TruncateBody(body):
  """Truncate body string if it exceeds size limit."""
  if len(body) > MAX_EMAIL_BODY_SIZE:
    logging.info('Truncate body since its size %d exceeds limit', len(body))
    return body[:MAX_EMAIL_BODY_SIZE] + '...'
  return body


def _MakeEmailWorkItem(
    (recipient_is_member, to_addr, user, reply_perm), reasons, issue,
    body_for_non_members, body_for_members, project, hostport, commenter_view,
     detail_url, seq_num=None):
  """Make one email task dict for one user, includes a detailed reason."""
  subject_format = 'Issue %(local_id)d in %(project_name)s: %(summary)s'
  if user and user.email_compact_subject:
    subject_format = '%(project_name)s:%(local_id)d: %(summary)s'

  subject = subject_format % {
    'local_id': issue.local_id,
    'project_name': issue.project_name,
    'summary': issue.summary,
    }

  footer = _MakeNotificationFooter(reasons, reply_perm, hostport)
  if isinstance(footer, unicode):
    footer = footer.encode('utf-8')
  if recipient_is_member:
    logging.info('got member %r, sending body for members', to_addr)
    body = _TruncateBody(body_for_members) + footer
  else:
    logging.info('got non-member %r, sending body for non-members', to_addr)
    body = _TruncateBody(body_for_non_members) + footer
  logging.info('sending message footer:\n%r', footer)

  can_reply_to = (
      reply_perm != REPLY_NOT_ALLOWED and project.process_inbound_email)
  from_addr = emailfmt.FormatFromAddr(
    project, commenter_view=commenter_view, reveal_addr=recipient_is_member,
    can_reply_to=can_reply_to)
  if can_reply_to:
    reply_to = '%s@%s' % (project.project_name, emailfmt.MailDomain())
  else:
    reply_to = emailfmt.NoReplyAddress()
  refs = emailfmt.GetReferences(
    to_addr, subject, seq_num,
    '%s@%s' % (project.project_name, emailfmt.MailDomain()))
  # We use markup to display a convenient link that takes users directly to the
  # issue without clicking on the email.
  html_body = None
  # cgi.escape the body and additionally escape single quotes which are
  # occassionally used to contain HTML attributes and event handler
  # definitions.
  html_escaped_body = cgi.escape(body, quote=1).replace("'", '&#39;')
  template = HTML_BODY_WITH_GMAIL_ACTION_TEMPLATE
  if user and not user.email_view_widget:
    template = HTML_BODY_WITHOUT_GMAIL_ACTION_TEMPLATE
  html_body = template % {
      'url': detail_url,
      'body': _AddHTMLTags(html_escaped_body.decode('utf-8')),
      }
  return dict(to=to_addr, subject=subject, body=body, html_body=html_body,
              from_addr=from_addr, reply_to=reply_to, references=refs)


def _AddHTMLTags(body):
  """Adds HMTL tags in the specified email body.

  Specifically does the following:
  * Detects links and adds <a href>s around the links.
  * Substitutes <br/> for all occurrences of "\n".

  See crbug.com/582463 for context.
  """
  # Convert all URLs into clickable links.
  body = urlize(body)
  # The above step converts
  #   '&lt;link.com&gt;' into '&lt;<a href="link.com&gt">link.com&gt</a>;' and
  #   '&lt;x@y.com&gt;' into '&lt;<a href="mailto:x@y.com&gt">x@y.com&gt</a>;'
  # The below regex fixes this specific problem. See
  # https://bugs.chromium.org/p/monorail/issues/detail?id=1007 for more details.
  body = re.sub(r'&lt;<a href="(|mailto:)(.*?)&gt">(.*?)&gt</a>;',
                r'&lt;<a href="\1\2">\3</a>&gt;', body)

  # Fix incorrectly split &quot; by urlize
  body = re.sub(r'<a href="(.*?)&quot">(.*?)&quot</a>;',
                r'<a href="\1&quot;">\2&quot;</a>', body)

  # Convert all "\n"s into "<br/>"s.
  body = body.replace('\r\n', '<br/>')
  body = body.replace('\n', '<br/>')
  return body


def _MakeNotificationFooter(reasons, reply_perm, hostport):
  """Make an informative footer for a notification email.

  Args:
    reasons: a list of strings to be used as the explanation.  Empty if no
        reason is to be given.
    reply_perm: string which is one of REPLY_NOT_ALLOWED, REPLY_MAY_COMMENT,
        REPLY_MAY_UPDATE.
    hostport: string with domain_name:port_number to be used in linking to
        the user preferences page.

  Returns:
    A string to be used as the email footer.
  """
  if not reasons:
    return ''

  domain_port = hostport.split(':')
  domain_port[0] = framework_helpers.GetPreferredDomain(domain_port[0])
  hostport = ':'.join(domain_port)

  prefs_url = 'https://%s%s' % (hostport, urls.USER_SETTINGS)
  lines = ['-- ']
  lines.append('You received this message because:')
  lines.extend('  %d. %s' % (idx + 1, reason)
               for idx, reason in enumerate(reasons))

  lines.extend(['', 'You may adjust your notification preferences at:',
                prefs_url])

  if reply_perm == REPLY_MAY_COMMENT:
    lines.extend(['', 'Reply to this email to add a comment.'])
  elif reply_perm == REPLY_MAY_UPDATE:
    lines.extend(['', 'Reply to this email to add a comment or make updates.'])

  return '\n'.join(lines)


def GetNonOmittedSubscriptions(cnxn, services, project_ids, omit_addrs):
  """Get a dict of users w/ subscriptions in those projects."""
  users_to_queries = services.features.GetSubscriptionsInProjects(
      cnxn, project_ids)
  user_emails = services.user.LookupUserEmails(cnxn, users_to_queries.keys())
  for user_id, email in user_emails.iteritems():
    if email in omit_addrs:
      del users_to_queries[user_id]

  return users_to_queries


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
      cond = searchpipeline.ReplaceKeywordsWithUserID(uid, cond)
      cond_ast = query2ast.ParseUserQuery(
        cond, '', query2ast.BUILTIN_ISSUE_FIELDS, config)

      if filterrules_helpers.EvalPredicate(
          cnxn, services, cond_ast, issue, label_set, config,
          tracker_bizobj.GetOwnerId(issue), tracker_bizobj.GetCcIds(issue),
          tracker_bizobj.GetStatus(issue)):
        subscribers_to_notify.append(uid)
        break  # Don't bother looking at the user's other saved quereies.

  return subscribers_to_notify


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
  """Return [(addr_perm, reason), ...] for users auto-cc'd by components."""
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
