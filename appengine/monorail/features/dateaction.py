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

from features import notify_helpers
from framework import framework_constants
from framework import framework_helpers
from framework import jsonfeed
from framework import urls


TEMPLATE_PATH = framework_constants.TEMPLATE_PATH


class DateActionCron(jsonfeed.InternalTask):

  """Find and process issues with date-type values that arrived today."""

  def HandleRequest(self, mr):
    """Find issues with date-type-fields that arrived and spawn tasks."""
    highest_iid_so_far = 0
    capped = True
    now = int(time.time())
    timestamp_min = (now / framework_constants.SECS_PER_DAY *
                     framework_constants.SECS_PER_DAY)
    timestamp_max = timestamp_min + framework_constants.SECS_PER_DAY
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
    logging.info('TODO(jrobbins): process date action for %r %r',
                 hostport, issue)
