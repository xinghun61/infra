# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Handlers to process alert notification messages."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging

import settings
from businesslogic import work_env
from features import commitlogcommands
from framework import monorailcontext
from tracker import tracker_helpers

def IsWhitelisted(email_addr):
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
                       body):
  """Create a dict of issue property values for the alert to be created with.

  Args:
    cnxn: connection to SQL database.
    project_id: the ID of the Monorail project, in which the alert should
      be created in.
    incident_id: string containing an optional unique incident used to
      de-dupe alert issues.
    trooper_queue: the label specifying the trooper queue to add an issue into.
    body: the body text of the alert notification message.

  Returns:
    A dict of issue property values to be used for issue creation.
  """
  # TODO(crbug/807064) - parse and get property values from email headers.
  proj_config = services.config.GetProjectConfig(cnxn, project_id)
  props = {
      'owner_id': None,
      'cc_ids': [],
      'component_ids': _GetComponentIDs(proj_config, body),
      'field_values': [],
      'status': 'Available',

      # Props that are added as labels.
      'incident_label': _GetIncidentLabel(incident_id),
      'priority': 'Pri-2',
      'trooper_queue': trooper_queue or 'Infra-Troopers-Alerts',
  }

  props['labels'] = _GetLabels(
      props['incident_label'], props['priority'], props['trooper_queue'])

  return props

def ProcessEmailNotification(
    services, cnxn, project, project_addr, from_addr, auth, subject, body,
    incident_id, label=None):
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
    label: the label to be added to the issue.

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
        services, cnxn, project.project_id, incident_id, label, body)
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


def _GetComponentIDs(proj_config, body):
  # TODO(crbug/807064): Remove this special casing once components can be set
  # via the email header
  return tracker_helpers.LookupComponentIDs(
      ['Infra>Codesearch' if 'codesearch' in body else 'Infra'], proj_config)


def _GetIncidentLabel(incident_id):
  return 'Incident-Id-%s' % incident_id if incident_id else ''


def _GetLabels(incident_label, priority, trooper_queue):
  labels = set(['Restrict-View-Google'])
  labels.update(label for label in [incident_label, priority, trooper_queue]
                if label)
  return list(labels)
