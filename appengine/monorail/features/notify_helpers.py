# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Helper functions for email notifications of issue changes."""

import cgi
import json
import logging
import re

from django.utils.html import urlize
from third_party import ezt

from google.appengine.api import taskqueue

from features import filterrules_helpers
from features import savedqueries_helpers
from features import notify_reasons
from framework import emailfmt
from framework import framework_bizobj
from framework import framework_constants
from framework import framework_helpers
from framework import framework_views
from framework import jsonfeed
from framework import monorailrequest
from framework import permissions
from framework import template_helpers
from framework import urls
from proto import tracker_pb2
from search import query2ast
from search import searchpipeline
from tracker import tracker_bizobj


# Email tasks can get too large for AppEngine to handle. In order to prevent
# that, we set a maximum body size, and may truncate messages to that length.
# We set this value to 40k so that the total of 40k body + 40k html_body +
# metadata does not exceed AppEngine's limit of 100k.
MAX_EMAIL_BODY_SIZE = 40 * 1024

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


def _EnqueueOutboundEmail(message_dict):
  """Create a task to send one email message, all fields are in the dict.

  We use a separate task for each outbound email to isolate errors.

  Args:
    message_dict: dict with all needed info for the task.
  """
  # We use a JSON-encoded payload because it ensures that the task size is
  # effectively the same as the sum of the email bodies. Using params results
  # in the dict being urlencoded, which can (worst case) triple the size of
  # an email body containing many characters which need to be escaped.
  payload = json.dumps(message_dict)
  taskqueue.add(
    url=urls.OUTBOUND_EMAIL_TASK + '.do', payload=payload,
    queue_name='outboundemail')


def AddAllEmailTasks(tasks):
  """Add one GAE task for each email to be sent."""
  notified = []
  for task in tasks:
    _EnqueueOutboundEmail(task)
    notified.append(task['to'])

  return notified


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


def MakeBulletedEmailWorkItems(
    group_reason_list, issue, body_for_non_members, body_for_members,
    project, hostport, commenter_view, detail_url, seq_num=None,
    subject_prefix=None, compact_subject_prefix=None):
  """Make a list of dicts describing email-sending tasks to notify users.

  Args:
    group_reason_list: list of (addr_perm_list, reason) tuples.
    issue: Issue that was updated.
    body_for_non_members: string body of email to send to non-members.
    body_for_members: string body of email to send to members.
    project: Project that contains the issue.
    hostport: string hostname and port number for links to the site.
    commenter_view: UserView for the user who made the comment.
    detail_url: str direct link to the issue.
    seq_num: optional int sequence number of the comment.
    subject_prefix: optional string to customize the email subject line.
    compact_subject_prefix: optional string to customize the email subject line.

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
        seq_num=seq_num, subject_prefix=subject_prefix,
        compact_subject_prefix=compact_subject_prefix))

  return email_tasks


def _TruncateBody(body):
  """Truncate body string if it exceeds size limit."""
  if len(body) > MAX_EMAIL_BODY_SIZE:
    logging.info('Truncate body since its size %d exceeds limit', len(body))
    return body[:MAX_EMAIL_BODY_SIZE] + '...'
  return body


def _MakeEmailWorkItem(
    addr_perm, reasons, issue,
    body_for_non_members, body_for_members, project, hostport, commenter_view,
    detail_url, seq_num=None, subject_prefix=None, compact_subject_prefix=None):
  """Make one email task dict for one user, includes a detailed reason."""
  subject_format = (
      (subject_prefix or 'Issue ') +
      '%(local_id)d in %(project_name)s: %(summary)s')
  if addr_perm.user and addr_perm.user.email_compact_subject:
    subject_format = (
        (compact_subject_prefix or '') +
        '%(project_name)s:%(local_id)d: %(summary)s')

  subject = subject_format % {
    'local_id': issue.local_id,
    'project_name': issue.project_name,
    'summary': issue.summary,
    }

  footer = _MakeNotificationFooter(reasons, addr_perm.reply_perm, hostport)
  if isinstance(footer, unicode):
    footer = footer.encode('utf-8')
  if addr_perm.is_member:
    logging.info('got member %r, sending body for members', addr_perm.address)
    body = _TruncateBody(body_for_members) + footer
  else:
    logging.info(
        'got non-member %r, sending body for non-members', addr_perm.address)
    body = _TruncateBody(body_for_non_members) + footer
  logging.info('sending message footer:\n%r', footer)

  can_reply_to = (
      addr_perm.reply_perm != notify_reasons.REPLY_NOT_ALLOWED and
      project.process_inbound_email)
  from_addr = emailfmt.FormatFromAddr(
    project, commenter_view=commenter_view, reveal_addr=addr_perm.is_member,
    can_reply_to=can_reply_to)
  if can_reply_to:
    reply_to = '%s@%s' % (project.project_name, emailfmt.MailDomain())
  else:
    reply_to = emailfmt.NoReplyAddress()
  refs = emailfmt.GetReferences(
    addr_perm.address, subject, seq_num,
    '%s@%s' % (project.project_name, emailfmt.MailDomain()))
  # We use markup to display a convenient link that takes users directly to the
  # issue without clicking on the email.
  html_body = None
  # cgi.escape the body and additionally escape single quotes which are
  # occassionally used to contain HTML attributes and event handler
  # definitions.
  html_escaped_body = cgi.escape(body, quote=1).replace("'", '&#39;')
  template = HTML_BODY_WITH_GMAIL_ACTION_TEMPLATE
  if addr_perm.user and not addr_perm.user.email_view_widget:
    template = HTML_BODY_WITHOUT_GMAIL_ACTION_TEMPLATE
  html_body = template % {
      'url': detail_url,
      'body': _AddHTMLTags(html_escaped_body.decode('utf-8')),
      }
  return dict(
    to=addr_perm.address, subject=subject, body=body, html_body=html_body,
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

  if reply_perm == notify_reasons.REPLY_MAY_COMMENT:
    lines.extend(['', 'Reply to this email to add a comment.'])
  elif reply_perm == notify_reasons.REPLY_MAY_UPDATE:
    lines.extend(['', 'Reply to this email to add a comment or make updates.'])

  return '\n'.join(lines)


