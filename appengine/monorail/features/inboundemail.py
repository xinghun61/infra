# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Handler to process inbound email with issue comments and commands."""

import email
import logging
import os
import re
import time
import urllib

from third_party import ezt

from google.appengine.api import mail
from google.appengine.ext.webapp.mail_handlers import BounceNotificationHandler

import webapp2

import settings
from businesslogic import work_env
from features import commitlogcommands
from features import notify_helpers
from framework import authdata
from framework import emailfmt
from framework import framework_constants
from framework import monorailrequest
from framework import permissions
from framework import sql
from framework import template_helpers
from proto import project_pb2
from services import issue_svc
from services import user_svc


TEMPLATE_PATH_BASE = framework_constants.TEMPLATE_PATH

MSG_TEMPLATES = {
    'banned': 'features/inboundemail-banned.ezt',
    'body_too_long': 'features/inboundemail-body-too-long.ezt',
    'project_not_found': 'features/inboundemail-project-not-found.ezt',
    'not_a_reply': 'features/inboundemail-not-a-reply.ezt',
    'no_account': 'features/inboundemail-no-account.ezt',
    'no_artifact': 'features/inboundemail-no-artifact.ezt',
    'no_perms': 'features/inboundemail-no-perms.ezt',
    'replies_disabled': 'features/inboundemail-replies-disabled.ezt',
    }


class InboundEmail(webapp2.RequestHandler):
  """Servlet to handle inbound email messages."""

  def __init__(self, request, response, services=None, *args, **kwargs):
    super(InboundEmail, self).__init__(request, response, *args, **kwargs)
    self.services = services or self.app.config.get('services')
    self._templates = {}
    for name, template_path in MSG_TEMPLATES.iteritems():
      self._templates[name] = template_helpers.MonorailTemplate(
          TEMPLATE_PATH_BASE + template_path,
          compress_whitespace=False, base_format=ezt.FORMAT_RAW)

  def get(self, project_addr=None):
    logging.info('\n\n\nGET for InboundEmail and project_addr is %r',
                 project_addr)
    self.Handler(mail.InboundEmailMessage(self.request.body),
                 urllib.unquote(project_addr))

  def post(self, project_addr=None):
    logging.info('\n\n\nPOST for InboundEmail and project_addr is %r',
                 project_addr)
    self.Handler(mail.InboundEmailMessage(self.request.body),
                 urllib.unquote(project_addr))

  def Handler(self, inbound_email_message, project_addr):
    """Process an inbound email message."""
    msg = inbound_email_message.original
    email_tasks = self.ProcessMail(msg, project_addr)

    if email_tasks:
      notify_helpers.AddAllEmailTasks(email_tasks)

  def ProcessMail(self, msg, project_addr):
    """Process an inbound email message."""
    # TODO(jrobbins): If the message is HUGE, don't even try to parse
    # it. Silently give up.

    (from_addr, to_addrs, cc_addrs, references, incident_id, subject,
     body) = emailfmt.ParseEmailMessage(msg)

    logging.info('Proj addr:   %r', project_addr)
    logging.info('From addr:   %r', from_addr)
    logging.info('Subject:     %r', subject)
    logging.info('To:          %r', to_addrs)
    logging.info('Cc:          %r', cc_addrs)
    logging.info('References:  %r', references)
    logging.info('Incident Id: %r', incident_id)
    logging.info('Body:        %r', body)

    # If message body is very large, reject it and send an error email.
    if emailfmt.IsBodyTooBigToParse(body):
      return _MakeErrorMessageReplyTask(
          project_addr, from_addr, self._templates['body_too_long'])

    # Make sure that the project reply-to address is in the To: line.
    if not emailfmt.IsProjectAddressOnToLine(project_addr, to_addrs):
      return None

    project_name, verb = emailfmt.IdentifyProjectAndVerb(project_addr)

    is_alert = bool(verb and verb.lower() == 'alert')
    error_addr = from_addr
    local_id = None
    author_addr = from_addr

    if is_alert:
      error_addr = settings.alert_escalation_email
      author_addr = settings.alert_service_account
    else:
      local_id = emailfmt.IdentifyIssue(project_name, subject)
      if not local_id:
        logging.info('Could not identify issue: %s %s', project_addr, subject)
        # No error message, because message was probably not intended for us.
        return None

    cnxn = sql.MonorailConnection()
    if self.services.cache_manager:
      self.services.cache_manager.DoDistributedInvalidation(cnxn)

    project = self.services.project.GetProjectByName(cnxn, project_name)

    # TODO(zhangtiff): Add separate email templates for alert error cases.
    if not project or project.state != project_pb2.ProjectState.LIVE:
      return _MakeErrorMessageReplyTask(
          project_addr, error_addr, self._templates['project_not_found'])

    if not project.process_inbound_email:
      return _MakeErrorMessageReplyTask(
          project_addr, error_addr, self._templates['replies_disabled'],
          project_name=project_name)

    # Verify that this is a reply to a notification that we could have sent.
    is_development = os.environ['SERVER_SOFTWARE'].startswith('Development')
    if not (is_alert or is_development):
      for ref in references:
        if emailfmt.ValidateReferencesHeader(ref, project, from_addr, subject):
          break  # Found a message ID that we could have sent.
      else: # for-else: if loop completes with no valid reference found.
        return _MakeErrorMessageReplyTask(
            project_addr, from_addr, self._templates['not_a_reply'])

    # Authenticate the author_addr and perm check.
    # Note: If the issue summary line is changed, a new thread is created,
    # and replies to the old thread will no longer work because the subject
    # line hash will not match, which seems reasonable.
    try:
      auth = authdata.AuthData.FromEmail(
          cnxn, author_addr, self.services, autocreate=is_alert)
      author_id = auth.user_id
    except user_svc.NoSuchUserException:
      author_id = None
    if not author_id:
      return _MakeErrorMessageReplyTask(
          project_addr, error_addr, self._templates['no_account'])

    if auth.user_pb.banned:
      logging.info('Banned user %s tried to post to %s',
                   from_addr, project_addr)
      return _MakeErrorMessageReplyTask(
          project_addr, error_addr, self._templates['banned'])

    perms = permissions.GetPermissions(
        auth.user_pb, auth.effective_ids, project)

    # If the email is an alert, switch to the alert handling path.
    if is_alert:
        self.ProcessAlert(cnxn, project, project_addr, from_addr, author_addr,
            author_id, subject, body, incident_id)
        return None

    # This email is a response to an email about a comment.
    self.ProcessIssueReply(
        cnxn, project, local_id, project_addr, from_addr, author_id,
        auth.effective_ids, perms, body)

    return None


  def ProcessAlert(
      self, cnxn, project, project_addr, from_addr, author_addr,
      author_id, subject, body, incident_id, owner_email=None):
    """Examine an an alert issue email and create an issue based on the email.

    Args:
      cnxn: connection to SQL database.
      project: Project PB for the project containing the issue.
      project_addr: string email address the alert email was sent to.
      from_addr: string email address of the user who sent the alert email
          to our server.
      author_addr: string email address of the user who will file the
          alert issue.
      author_id: int user ID of user who will file the alert issue.
      body: string email body text of the reply email.
      incident_id: string containing an optional unique incident used to
          de-dupe alert issues.
      owner_email: string email address of the user the bug will be assigned to.

    Returns:
      A list of follow-up work items, e.g., to notify other users of
      the new comment, or to notify the user that their reply was not
      processed.

    Side-effect:
      Adds a new comment to the issue, if no error is reported.
    """
    # Make sure the email address is whitelisted.
    if not from_addr.endswith(settings.alert_whitelisted_suffixes):
      logging.info('Unauthorized %s tried to send alert to %s',
                     from_addr, project_addr)
      return None

    # Create the actual issue from the email data.
    # TODO(zhangtiff): Set labels, components, etc based on email content.
    cc_ids = []
    status = 'Available'

    labels = ['Infra-Troopers-Alerts', 'Restrict-View-Google', 'Pri-2']
    field_values = []
    component_ids = []
    formatted_body = 'Filed by %s on behalf of %s\n\n%s' % (
        author_addr, from_addr, body)

    mr = monorailrequest.MonorailRequestBase(
        services=self.services, user_id=author_id, cnxn=cnxn)
    with work_env.WorkEnv(mr, self.services) as we:
      updated_issue = None
      owner_id = None
      if owner_email:
        owner_id = self.services.user.LookupUserID(cnxn, owner_email,
            autocreate=True)
        status = 'Assigned'

      if incident_id:
        incident_label = 'Incident-Id-' + incident_id
        labels.append(incident_label)

        label_id = self.services.config.LookupLabelID(
            cnxn, project.project_id, incident_label)

        if label_id:
          issue_ids = self.services.issue.GetIIDsByLabelIDs(
              cnxn, [label_id], project.project_id, None)

          issues, _ = self.services.issue.GetOpenAndClosedIssues(
              cnxn, issue_ids)

          latest_issue = None
          # Find the most recently modified open issue.
          for issue in issues:
            if not latest_issue:
              latest_issue = issue
            elif issue.modified_timestamp > latest_issue.modified_timestamp:
              latest_issue = issue

          if latest_issue:
            updated_issue = latest_issue
            # Find all comments on the issue by the current user.
            comments = self.services.issue.GetComments(cnxn,
                issue_id=[updated_issue.issue_id], commenter_id=[author_id])

            # Timestamp for 24 hours ago in seconds from epoch.
            yesterday = int(time.time()) - 24 * 60 * 60

            for comment in comments:
              # Stop early if we find a comment created in the last 24 hours.
              if comment.timestamp > yesterday:
                  logging.info('Alert fired again with incident id: %s',
                      incident_id)
                  return None

            # Add a reply to the existing issue for this incident.
            self.services.issue.CreateIssueComment(
                cnxn, updated_issue, author_id, formatted_body)

      if not updated_issue:
        updated_issue = we.CreateIssue(
            project.project_id, subject, status, owner_id,
            cc_ids, labels, field_values, component_ids, formatted_body)

      # Update issue using commads.
      lines = body.strip().split('\n')
      uia = commitlogcommands.UpdateIssueAction(updated_issue.local_id)
      uia.Parse(cnxn, project.project_name, author_id, lines, self.services,
                strip_quoted_lines=True)
      uia.Run(cnxn, self.services, allow_edit=True)


  def ProcessIssueReply(
      self, cnxn, project, local_id, project_addr, from_addr, author_id,
      effective_ids, perms, body):
    """Examine an issue reply email body and add a comment to the issue.

    Args:
      cnxn: connection to SQL database.
      project: Project PB for the project containing the issue.
      local_id: int ID of the issue being replied to.
      project_addr: string email address used for outbound emails from
          that project.
      from_addr: string email address of the user who sent the email
          reply to our server.
      author_id: int user ID of user who sent the reply email.
      effective_ids: set of int user IDs for the user (including any groups),
          or an empty set if user is not signed in.
      perms: PermissionSet for the user who sent the reply email.
      body: string email body text of the reply email.

    Returns:
      A list of follow-up work items, e.g., to notify other users of
      the new comment, or to notify the user that their reply was not
      processed.

    Side-effect:
      Adds a new comment to the issue, if no error is reported.
    """
    try:
      issue = self.services.issue.GetIssueByLocalID(
          cnxn, project.project_id, local_id)
    except issue_svc.NoSuchIssueException:
      issue = None

    if not issue or issue.deleted:
      # The referenced issue was not found, e.g., it might have been
      # deleted, or someone messed with the subject line.  Reject it.
      return _MakeErrorMessageReplyTask(
          project_addr, from_addr, self._templates['no_artifact'],
          artifact_phrase='issue %d' % local_id,
          project_name=project.project_name)

    can_view = perms.CanUsePerm(
        permissions.VIEW, effective_ids, project,
        permissions.GetRestrictions(issue))
    can_comment = perms.CanUsePerm(
        permissions.ADD_ISSUE_COMMENT, effective_ids, project,
        permissions.GetRestrictions(issue))
    if not can_view or not can_comment:
      return _MakeErrorMessageReplyTask(
          project_addr, from_addr, self._templates['no_perms'],
          artifact_phrase='issue %d' % local_id,
          project_name=project.project_name)
    allow_edit = permissions.CanEditIssue(
        effective_ids, perms, project, issue)
    # TODO(jrobbins): if the user does not have EDIT_ISSUE and the inbound
    # email tries to make an edit, send back an error message.

    lines = body.strip().split('\n')
    uia = commitlogcommands.UpdateIssueAction(local_id)
    uia.Parse(cnxn, project.project_name, author_id, lines, self.services,
              strip_quoted_lines=True)
    uia.Run(cnxn, self.services, allow_edit=allow_edit)


def _MakeErrorMessageReplyTask(
    project_addr, sender_addr, template, **callers_page_data):
  """Return a new task to send an error message email.

  Args:
    project_addr: string email address that the inbound email was delivered to.
    sender_addr: string email address of user who sent the email that we could
        not process.
    template: EZT template used to generate the email error message.  The
        first line of this generated text will be used as the subject line.
    callers_page_data: template data dict for body of the message.

  Returns:
    A list with a single Email task that can be enqueued to
    actually send the email.

  Raises:
    ValueError: if the template does begin with a "Subject:" line.
  """
  email_data = {
      'project_addr': project_addr,
      'sender_addr': sender_addr
      }
  email_data.update(callers_page_data)

  generated_lines = template.GetResponse(email_data)
  subject, body = generated_lines.split('\n', 1)
  if subject.startswith('Subject: '):
    subject = subject[len('Subject: '):]
  else:
    raise ValueError('Email template does not begin with "Subject:" line.')

  email_task = dict(to=sender_addr, subject=subject, body=body,
                    from_addr=emailfmt.NoReplyAddress())
  logging.info('sending email error reply: %r', email_task)

  return [email_task]


BAD_WRAP_RE = re.compile('=\r\n')
BAD_EQ_RE = re.compile('=3D')

class BouncedEmail(BounceNotificationHandler):
  """Handler to notice when email to given user is bouncing."""

  # For docs on AppEngine's bounce email handling, see:
  # https://cloud.google.com/appengine/docs/python/mail/bounce
  # Source code is in file:
  # google_appengine/google/appengine/ext/webapp/mail_handlers.py

  def post(self):
    try:
      super(BouncedEmail, self).post()
    except AttributeError:
      # Work-around for
      # https://code.google.com/p/googleappengine/issues/detail?id=13512
      raw_message = self.request.POST.get('raw-message')
      logging.info('raw_message %r', raw_message)
      raw_message = BAD_WRAP_RE.sub('', raw_message)
      raw_message = BAD_EQ_RE.sub('=', raw_message)
      logging.info('fixed raw_message %r', raw_message)
      mime_message = email.message_from_string(raw_message)
      logging.info('get_payload gives %r', mime_message.get_payload())
      self.request.POST['raw-message'] = mime_message
      super(BouncedEmail, self).post()  # Retry with mime_message


  def receive(self, bounce_message):
    email_addr = bounce_message.original.get('to')
    logging.info('Bounce was sent to: %r', email_addr)

    app_config = webapp2.WSGIApplication.app.config
    services = app_config['services']
    cnxn = sql.MonorailConnection()

    try:
      user_id = services.user.LookupUserID(cnxn, email_addr)
      user = services.user.GetUser(cnxn, user_id)
      user.email_bounce_timestamp = int(time.time())
      services.user.UpdateUser(cnxn, user_id, user)
    except user_svc.NoSuchUserException:
      logging.info('User %r not found, ignoring', email_addr)
      logging.info('Received bounce post ... [%s]', self.request)
      logging.info('Bounce original: %s', bounce_message.original)
      logging.info('Bounce notification: %s', bounce_message.notification)
