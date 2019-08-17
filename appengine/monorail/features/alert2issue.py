# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Handlers to process alert notification messages."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import itertools
import logging
import rfc822

import settings
from businesslogic import work_env
from features import commitlogcommands
from framework import monorailcontext
from framework import emailfmt
from tracker import tracker_helpers

AlertEmailHeader = emailfmt.AlertEmailHeader


def IsWhitelisted(email_addr):
  """Returns whether a given email is from one of the whitelisted domains."""
  return email_addr.endswith(settings.alert_whitelisted_suffixes)


def FindAlertIssue(services, cnxn, project_id, incident_label):
  """Find the existing issue with the incident_label."""
  if not incident_label:
    return None

  label_id = services.config.LookupLabelID(
      cnxn, project_id, incident_label)
  if not label_id:
    return None

  # If a new notification is sent with an existing incident ID, then it
  # should be added as a new comment into the existing issue.
  #
  # If there are more than one issues with a given incident ID, then
  # it's either
  # - there is a bug in this module,
  # - the issues were manually updated with the same incident ID, OR
  # - an issue auto update program updated the issues with the same
  #  incident ID, which also sounds like a bug.
  #
  # In any cases, the latest issue should be used, whichever status it has.
  # - The issue of an ongoing incident can be mistakenly closed by
  # engineers.
  # - A closed incident can be reopened, and, therefore, the issue also
  # needs to be re-opened.
  issue_ids = services.issue.GetIIDsByLabelIDs(
      cnxn, [label_id], project_id, None)
  issues = services.issue.GetIssues(cnxn, issue_ids)
  if issues:
    return max(issues, key=lambda issue: issue.modified_timestamp)
  return None


def GetAlertProperties(services, cnxn, project_id, incident_id, trooper_queue,
                       body, msg):
  """Create a dict of issue property values for the alert to be created with.

  Args:
    cnxn: connection to SQL database.
    project_id: the ID of the Monorail project, in which the alert should
      be created in.
    incident_id: string containing an optional unique incident used to
      de-dupe alert issues.
    trooper_queue: the label specifying the trooper queue to add an issue into.
    body: the body text of the alert notification message.
    msg: the email.Message object containing the alert notification.

  Returns:
    A dict of issue property values to be used for issue creation.
  """
  proj_config = services.config.GetProjectConfig(cnxn, project_id)
  user_svc = services.user
  known_labels = set(wkl.label.lower() for wkl in proj_config.well_known_labels)

  props = dict(
      owner_id=_GetOwnerID(user_svc, cnxn, msg.get(AlertEmailHeader.OWNER)),
      cc_ids=_GetCCIDs(user_svc, cnxn, msg.get(AlertEmailHeader.CC)),
      component_ids=_GetComponentIDs(
          proj_config, body, msg.get(AlertEmailHeader.COMPONENT)),

      # Props that are added as labels.
      trooper_queue=(trooper_queue or 'Infra-Troopers-Alerts'),
      incident_label=_GetIncidentLabel(incident_id),
      priority=_GetPriority(known_labels, msg.get(AlertEmailHeader.PRIORITY)),
      oses=_GetOSes(known_labels, msg.get(AlertEmailHeader.OS)),
      issue_type=_GetIssueType(known_labels, msg.get(AlertEmailHeader.TYPE)),

      field_values=[],
  )

  # Props that depend on other props.
  props.update(
      status=_GetStatus(proj_config, props['owner_id'],
                        msg.get(AlertEmailHeader.STATUS)),
      labels=_GetLabels(props['trooper_queue'], props['incident_label'],
                        props['priority'], props['issue_type'], props['oses']),
  )

  return props


def ProcessEmailNotification(
    services, cnxn, project, project_addr, from_addr, auth, subject, body,
    incident_id, msg, trooper_queue=None):
  """Process an alert notification email to create or update issues.""

  Args:
    cnxn: connection to SQL database.
    project: Project PB for the project containing the issue.
    project_addr: string email address the alert email was sent to.
    from_addr: string email address of the user who sent the alert email
        to our server.
    auth: AuthData object with user_id and email address of the user who
        will file the alert issue.
    subject: the subject of the email message
    body: the body text of the email message
    incident_id: string containing an optional unique incident used to
        de-dupe alert issues.
    msg: the email.Message object that the notification was delivered via.
    trooper_queue: the label specifying the trooper queue that the alert
      notification was sent to. If not given, the notification is sent to
      Infra-Troopers-Alerts.

  Side-effect:
    Creates an issue or issue comment, if no error was reported.
  """
  # Make sure the email address is whitelisted.
  if not IsWhitelisted(from_addr):
    logging.info('Unauthorized %s tried to send alert to %s',
                 from_addr, project_addr)
    return

  formatted_body = 'Filed by %s on behalf of %s\n\n%s' % (
      auth.email, from_addr, body)

  mc = monorailcontext.MonorailContext(services, auth=auth, cnxn=cnxn)
  mc.LookupLoggedInUserPerms(project)
  with work_env.WorkEnv(mc, services) as we:
    alert_props = GetAlertProperties(
        services, cnxn, project.project_id, incident_id, trooper_queue, body,
        msg)
    alert_issue = FindAlertIssue(
        services, cnxn, project.project_id, alert_props['incident_label'])

    if alert_issue:
      # Add a reply to the existing issue for this incident.
      services.issue.CreateIssueComment(
          cnxn, alert_issue, auth.user_id, formatted_body)
    else:
      # Create a new issue for this incident.
      alert_issue, _ = we.CreateIssue(
          project.project_id, subject,
          alert_props['status'], alert_props['owner_id'],
          alert_props['cc_ids'], alert_props['labels'],
          alert_props['field_values'], alert_props['component_ids'],
          formatted_body)

    # Update issue using commands.
    lines = body.strip().split('\n')
    uia = commitlogcommands.UpdateIssueAction(alert_issue.local_id)
    commands_found = uia.Parse(
        cnxn, project.project_name, auth.user_id, lines,
        services, strip_quoted_lines=True)

    if commands_found:
      uia.Run(cnxn, services, allow_edit=True)


def _GetComponentIDs(proj_config, body, components):
  # TODO(crbug/807064): Remove this special casing once components can be set
  # via the email header
  comps = ['Infra']
  if 'codesearch' in body:
    comps = ['Infra>Codesearch']
  elif components:
    comps = components.split(',')

  return tracker_helpers.LookupComponentIDs(comps, proj_config)


def _GetIncidentLabel(incident_id):
  return 'Incident-Id-%s' % incident_id if incident_id else ''


def _GetLabels(trooper_queue, incident_label, priority, issue_type, oses):
  labels = set(['Restrict-View-Google'])
  labels.update(
      label for label in itertools.chain(
          [trooper_queue, incident_label, priority, issue_type], oses)
      if label
  )
  return list(labels)


def _GetOwnerID(user_svc, cnxn, owner_email):
  if not owner_email:
    return None
  emails = [addr for _, addr in rfc822.AddressList(owner_email)]
  return user_svc.LookupExistingUserIDs(cnxn, emails).get(owner_email)


def _GetCCIDs(user_svc, cnxn, cc_emails):
  if not cc_emails:
    return []
  emails = [addr for _, addr in rfc822.AddressList(cc_emails)]
  return [userID for _, userID
          in user_svc.LookupExistingUserIDs(cnxn, emails).iteritems()
          if userID is not None]


def _GetPriority(known_labels, priority):
  priority_label = ('Pri-%s' % priority).lower()
  if priority:
    if priority_label in known_labels:
      return priority_label
    logging.info('invalid priority %s for alerts; default to pri-2', priority)

  # XXX: what if 'Pri-2' doesn't exist in known_labels?
  return 'pri-2'


def _GetStatus(proj_config, owner_id, status):
  # XXX: what if assigned and available are not in known_statuses?
  if owner_id:
    # If there is an owner, the status must be 'Assigned'.
    if status and status.lower() != 'assigned':
      logging.info(
          'invalid status %s for an alert with an owner; default to assigned',
          status)
    return 'assigned'

  if status:
    if tracker_helpers.MeansOpenInProject(status, proj_config):
      return status
    logging.info('invalid status %s for an alert; default to available', status)

  return 'available'


def _GetOSes(known_labels, oses):
  if not oses:
    return []

  os_labels_to_lookup = {('OS-%s' % os).lower() for os in oses.split(',') if os}
  os_labels_to_return = os_labels_to_lookup & known_labels
  invalid_os_labels = os_labels_to_lookup - os_labels_to_return
  if invalid_os_labels:
    logging.info('invalid OSes %s', ','.join(invalid_os_labels))

  return list(os_labels_to_return)


def _GetIssueType(known_labels, issue_type):
  if not issue_type:
    return None

  issue_type_label = ('Type-%s' % issue_type).lower()
  if issue_type_label in known_labels:
    return issue_type_label

  logging.info('invalid type %s for an alert; default to None', issue_type)
  return None
