# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""JSON feed for issue presubmit warningins."""

import logging

from features import filterrules_helpers
from framework import framework_views
from framework import jsonfeed
from framework import permissions
from proto import tracker_pb2
from tracker import tracker_bizobj
from tracker import tracker_helpers
from services import issue_svc


class IssuePresubmitJSON(jsonfeed.JsonFeed):
  """JSON data for any warnings as the user edits an issue."""

  def AssertBasePermission(self, mr):
    """Make sure that the logged in user has permission to view this page."""
    super(IssuePresubmitJSON, self).AssertBasePermission(mr)
    issue = self._GetIssue(mr)
    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    granted_perms = tracker_bizobj.GetGrantedPerms(
        issue, mr.auth.effective_ids, config)
    permit_view = permissions.CanViewIssue(
        mr.auth.effective_ids, mr.perms, mr.project, issue,
        granted_perms=granted_perms)
    if not permit_view:
      logging.warning('Issue is %r', issue)
      raise permissions.PermissionException(
          'User is not allowed to view this issue')

  def _GetIssue(self, mr):
    """Retrive the requested issue."""
    if mr.local_id is None:
      logging.info('issue not specified')
      self.abort(404, 'issue not specified')

    try:
      issue = self.services.issue.GetIssueByLocalID(
          mr.cnxn, mr.project_id, mr.local_id)
    except issue_svc.NoSuchIssueException:
      logging.info('issue not found')
      self.abort(404, 'issue not found')

    return issue

  def HandleRequest(self, mr):
    """Provide the UI with warning info as the user edits an issue.

    Args:
      mr: common information parsed from the HTTP request.

    Returns:
      Results dictionary in JSON format.
    """
    with self.profiler.Phase('parsing request'):
      post_data = mr.request.POST
      parsed = tracker_helpers.ParseIssueRequest(
          mr.cnxn, post_data, self.services, mr.errors, mr.project_name)

    logging.info('parsed.users %r', parsed.users)

    with self.profiler.Phase('making user views'):
      involved_user_ids = [parsed.users.owner_id]
      users_by_id = framework_views.MakeAllUserViews(
          mr.cnxn, self.services.user, involved_user_ids)
      proposed_owner_view = users_by_id[parsed.users.owner_id]

    with self.profiler.Phase('getting config and components'):
      config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
      component_ids = tracker_helpers.LookupComponentIDs(
          parsed.components.paths, config, mr.errors)

    with self.profiler.Phase('applying rules'):
      proposed_issue = tracker_pb2.Issue(
          project_id=mr.project_id, local_id=mr.local_id,
          summary=parsed.summary, status=parsed.status,
          owner_id=parsed.users.owner_id, labels=parsed.labels,
          component_ids=component_ids, project_name=mr.project_name)
      # TODO(jrobbins): also check for process warnings.
      filterrules_helpers.ApplyFilterRules(
          mr.cnxn, self.services, proposed_issue, config)
      logging.info('proposed_issue is now: %r', proposed_issue)

    with self.profiler.Phase('making derived user views'):
      derived_users_by_id = framework_views.MakeAllUserViews(
          mr.cnxn, self.services.user, [proposed_issue.derived_owner_id],
          proposed_issue.derived_cc_ids)
      derived_owner_email = None
      if proposed_issue.derived_owner_id:
        derived_owner_email = (
            derived_users_by_id[proposed_issue.derived_owner_id].email)
      derived_cc_emails = [
          derived_users_by_id[cc_id].email
          for cc_id in proposed_issue.derived_cc_ids
          if derived_users_by_id[cc_id].email]

    return {
        'owner_availability': proposed_owner_view.avail_message_short,
        'owner_avail_state': proposed_owner_view.avail_state,
        'derived_labels': proposed_issue.derived_labels,
        'derived_owner_email': derived_owner_email,
        'derived_cc_emails': derived_cc_emails,
        }
