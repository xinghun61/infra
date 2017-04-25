# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Cron and task handlers for email notifications of issue date value arrival.

If an issue has a date-type custom field, and that custom field is configured
to perform an action when that date arrives, then this cron handler and the
associated tasks carry out those actions on that issue.
"""

import logging
import time

from google.appengine.api import taskqueue

import settings

from features import notify_helpers
from features import notify_reasons
from framework import framework_constants
from framework import framework_helpers
from framework import framework_views
from framework import jsonfeed
from framework import permissions
from framework import timestr
from framework import urls
from proto import tracker_pb2
from tracker import tracker_bizobj
from tracker import tracker_views


TEMPLATE_PATH = framework_constants.TEMPLATE_PATH

class DateActionCron(jsonfeed.InternalTask):

  """Find and process issues with date-type values that arrived today."""

  def HandleRequest(self, mr):
    """Find issues with date-type-fields that arrived and spawn tasks."""
    highest_iid_so_far = 0
    capped = True
    timestamp_min, timestamp_max = _GetTimestampRange(int(time.time()))
    left_joins = [
        ('Issue2FieldValue ON Issue.id = Issue2FieldValue.issue_id', []),
        ('FieldDef ON Issue2FieldValue.field_id = FieldDef.id', []),
        ]
    where = [
        ('FieldDef.field_type = %s', ['date_type']),
        ('FieldDef.date_action IN (%s,%s)',
         ['ping_owner_only', 'ping_participants']),
        ('Issue2FieldValue.date_value >= %s', [timestamp_min]),
        ('Issue2FieldValue.date_value < %s', [timestamp_max]),
        ]
    order_by = [
        ('Issue.id', []),
        ]
    while capped:
        chunk_issue_ids, capped = self.services.issue.RunIssueQuery(
            mr.cnxn, left_joins,
            where + [('Issue.id > %s', [highest_iid_so_far])],
            order_by)
        if chunk_issue_ids:
            logging.info('chunk_issue_ids = %r', chunk_issue_ids)
            highest_iid_so_far = max(highest_iid_so_far, max(chunk_issue_ids))
            for issue_id in chunk_issue_ids:
                self.EnqueueDateAction(issue_id)

  def EnqueueDateAction(self, issue_id):
      """Create a task to notify users that an issue's date has arrived.

      Args:
        issue_id: int ID of the issue that was changed.

      Returns nothing.
      """
      params = {'issue_id': issue_id}
      logging.info('adding date-action task with params %r', params)
      taskqueue.add(url=urls.ISSUE_DATE_ACTION_TASK + '.do', params=params)


def _GetTimestampRange(now):
    timestamp_min = (now / framework_constants.SECS_PER_DAY *
                     framework_constants.SECS_PER_DAY)
    timestamp_max = timestamp_min + framework_constants.SECS_PER_DAY
    return timestamp_min, timestamp_max


class IssueDateActionTask(notify_helpers.NotifyTaskBase):
  """JSON servlet that notifies appropriate users after an issue change."""

  _EMAIL_TEMPLATE = 'features/auto-ping-email.ezt'

  def HandleRequest(self, mr):
    """Process the task to notify users after an issue change.

    Args:
      mr: common information parsed from the HTTP request.

    Returns:
      Results dictionary in JSON format which is useful just for debugging.
      The main goal is the side-effect of sending emails.
    """
    issue_id = mr.GetPositiveIntParam('issue_id')
    hostport = framework_helpers.GetHostPort()
    issue = self.services.issue.GetIssue(mr.cnxn, issue_id)
    project = self.services.project.GetProject(mr.cnxn, issue.project_id)
    config = self.services.config.GetProjectConfig(mr.cnxn, issue.project_id)
    pings = self._CalculateIssuePings(mr.cnxn, issue)
    if not pings:
      logging.warning('Issue %r has no dates to ping afterall?', issue_id)
      return
    content = '\n'.join(self._FormatPingLine(ping) for ping in pings)
    author_email_addr = '%s@%s' % (settings.date_action_ping_author, hostport)
    date_action_user_id = self.services.user.LookupUserID(
        mr.cnxn, author_email_addr, autocreate=True)
    comment = self.services.issue.CreateIssueComment(
        mr.cnxn, issue.project_id, issue.local_id, date_action_user_id, content)

    users_by_id = framework_views.MakeAllUserViews(
        mr.cnxn, self.services.user,
        tracker_bizobj.UsersInvolvedInIssues([issue]),
        [comment.user_id])
    logging.info('users_by_id is %r', users_by_id)
    tasks = self._MakeEmailTasks(
      mr.cnxn, issue, project, config, comment, hostport, users_by_id)

    notified = notify_helpers.AddAllEmailTasks(tasks)
    return {
        'notified': notified,
        }

  def _MakeEmailTasks(
      self, cnxn, issue, project, config, comment, hostport, users_by_id):
    """Return a list of dicts for tasks to notify people."""
    detail_url = framework_helpers.IssueCommentURL(
        hostport, project, issue.local_id, seq_num=comment.sequence)
    email_data = {
        'issue': tracker_views.IssueView(issue, users_by_id, config),
        'summary': issue.summary,
        'ping_comment_content': comment.content,
        'detail_url': detail_url,
        }

    # TODO(jrobbins): when we include the context of the comments that
    # set the date values, we will need to generate member and non-member
    # body text so that only members see all the emails revealed.
    body = self.email_template.GetResponse(email_data)
    logging.info('body for members and non-members is:\n%r' % body)
    contributor_could_view = permissions.CanViewIssue(
        set(), permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET,
        project, issue)
    # Note: We never notify the reporter of any issue just because they
    # reported it, only if they star it.
    # TODO(jrobbins): add an pref for starrers.
    starrer_ids = []

    # TODO(jrobbins): consider IsNoisy() when we support notifying starrers.
    group_reason_list = notify_reasons.ComputeGroupReasonList(
        cnxn, self.services, project, issue, config, users_by_id,
        [], contributor_could_view, starrer_ids=starrer_ids,
        commenter_in_project=True)

    commenter_view = users_by_id[comment.user_id]
    email_tasks = notify_helpers.MakeBulletedEmailWorkItems(
        group_reason_list, issue, body, body,
        project, hostport, commenter_view, detail_url, seq_num=comment.sequence,
        subject_prefix='Ping on issue ', compact_subject_prefix='Ping ')

    return email_tasks

  def _CalculateIssuePings(self, cnxn, issue):
    """Return a list of (field, timestamp) pairs for dates that should ping."""
    project_id = issue.project_id
    timestamp_min, timestamp_max = _GetTimestampRange(int(time.time()))
    arrived_dates_by_field_id = {
        fv.field_id: fv.date_value
        for fv in issue.field_values
        if timestamp_min <= fv.date_value < timestamp_max}
    logging.info('arrived_dates_by_field_id = %r', arrived_dates_by_field_id)
    # TODO(jrobbins): Lookup field defs regardless of project_id to better
    # handle foreign fields in issues that have been moved between projects.
    config = self.services.config.GetProjectConfig(cnxn, project_id)
    pings = [
      (field, arrived_dates_by_field_id[field.field_id])
      for field in config.field_defs
      if (field.field_id in arrived_dates_by_field_id and
          field.date_action in (tracker_pb2.DateAction.PING_OWNER_ONLY,
                                tracker_pb2.DateAction.PING_PARTICIPANTS))]
    pings = sorted(pings, key=lambda (field, timestamp): field.field_name)
    return pings

  def _FormatPingLine(self, ping):
    field, timestamp = ping
    date_str = timestr.TimestampToDateWidgetStr(timestamp)
    return 'The %s date has arrived: %s' % (field.field_name, date_str)
