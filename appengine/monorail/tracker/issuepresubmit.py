# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""JSON feed for issue presubmit warnings."""

import logging

from businesslogic import work_env
from features import filterrules_helpers
from framework import framework_views
from framework import jsonfeed
from framework import permissions
from proto import tracker_pb2
from tracker import field_helpers
from tracker import tracker_bizobj
from tracker import tracker_helpers
from services import issue_svc


class IssuePresubmitJSON(jsonfeed.JsonFeed):
  """JSON data for any warnings as the user edits an issue."""

  def AssertBasePermission(self, mr):
    """Make sure that the logged in user has permission to view this page."""
    super(IssuePresubmitJSON, self).AssertBasePermission(mr)
    if mr.local_id is None:
      return  # For issue creation, there is no existing issue.

    with work_env.WorkEnv(mr, self.services) as we:
      issue = we.GetIssueByLocalID(mr.project_id, mr.local_id)
      config = we.GetProjectConfig(mr.project_id)
    granted_perms = tracker_bizobj.GetGrantedPerms(
        issue, mr.auth.effective_ids, config)
    permit_view = permissions.CanViewIssue(
        mr.auth.effective_ids, mr.perms, mr.project, issue,
        granted_perms=granted_perms)
    if not permit_view:
      logging.warning('Issue is %r', issue)
      raise permissions.PermissionException(
          'User is not allowed to view this issue')

  def HandleRequest(self, mr):
    """Provide the UI with warning info as the user edits an issue.

    Args:
      mr: common information parsed from the HTTP request.

    Returns:
      Results dictionary in JSON format.
    """
    existing_issue = None
    if mr.local_id:
      with work_env.WorkEnv(mr, self.services) as we:
        existing_issue = we.GetIssueByLocalID(mr.project_id, mr.local_id)

    with mr.profiler.Phase('parsing request'):
      post_data = mr.request.POST
      parsed = tracker_helpers.ParseIssueRequest(
          mr.cnxn, post_data, self.services, mr.errors, mr.project_name)

    logging.info('parsed.users %r', parsed.users)

    with mr.profiler.Phase('making user views'):
      involved_user_ids = [parsed.users.owner_id]
      users_by_id = framework_views.MakeAllUserViews(
          mr.cnxn, self.services.user, involved_user_ids)
      proposed_owner_view = users_by_id[parsed.users.owner_id]

    with work_env.WorkEnv(mr, self.services) as we:
      config = we.GetProjectConfig(mr.project_id)
      component_ids = tracker_helpers.LookupComponentIDs(
          parsed.components.paths, config, mr.errors)

    with mr.profiler.Phase('initializing proposed_issue'):
      proposed_issue = self.MakeProposedIssue(
          mr, existing_issue, parsed, config, component_ids)

    with mr.profiler.Phase('applying rules'):
      _any_change, traces = filterrules_helpers.ApplyFilterRules(
          mr.cnxn, self.services, proposed_issue, config)
      logging.info('proposed_issue is now: %r', proposed_issue)
      logging.info('traces are: %r', traces)

    with mr.profiler.Phase('making derived user views'):
      derived_users_by_id = framework_views.MakeAllUserViews(
          mr.cnxn, self.services.user, [proposed_issue.derived_owner_id],
          proposed_issue.derived_cc_ids)

    with mr.profiler.Phase('pair derived values with rule explanations'):
      (derived_labels_and_why, derived_owner_and_why,
       derived_cc_and_why, warnings_and_why, errors_and_why
       ) = PairDerivedValuesWithRuleExplanations(
          proposed_issue, traces, derived_users_by_id)

    return {
        'owner_availability': proposed_owner_view.avail_message_short,
        'owner_avail_state': proposed_owner_view.avail_state,
        'derived_labels': derived_labels_and_why,
        'derived_owner_email': derived_owner_and_why,
        'derived_cc_emails': derived_cc_and_why,
        'warnings': warnings_and_why,
        'errors': errors_and_why,
        }

  def MakeProposedIssue(
      self, mr, existing_issue, parsed, config, component_ids):
    """Create an Issue in RAM as input to the filter rules."""
    field_helpers.ShiftEnumFieldsIntoLabels(
      parsed.labels, parsed.labels_remove,
      parsed.fields.vals, parsed.fields.vals_remove, config)
    field_values = field_helpers.ParseFieldValues(
      mr.cnxn, self.services.user, parsed.fields.vals, config)
    proposed_issue = tracker_pb2.Issue(
      project_id=mr.project_id, local_id=mr.local_id,
      summary=parsed.summary, status=parsed.status,
      owner_id=parsed.users.owner_id, labels=parsed.labels,
      component_ids=component_ids, project_name=mr.project_name,
      field_values=field_values)
    if existing_issue:
      proposed_issue.attachment_count = existing_issue.attachment_count
      proposed_issue.star_count = existing_issue.star_count
    return proposed_issue


def PairDerivedValuesWithRuleExplanations(
    proposed_issue, traces, derived_users_by_id):
  """Pair up values and explanations into JSON objects."""
  derived_labels_and_why = [
      {'value': lab,
       'why': traces.get((tracker_pb2.FieldID.LABELS, lab))}
      for lab in proposed_issue.derived_labels]
  derived_owner_and_why = []
  if proposed_issue.derived_owner_id:
    derived_owner_and_why = [{
        'value': derived_users_by_id[proposed_issue.derived_owner_id].email,
        'why': traces.get(
            (tracker_pb2.FieldID.OWNER, proposed_issue.derived_owner_id)),
        }]
  derived_cc_and_why = [
      {'value': derived_users_by_id[cc_id].email,
       'why': traces.get((tracker_pb2.FieldID.CC, cc_id))}
      for cc_id in proposed_issue.derived_cc_ids
      if cc_id in derived_users_by_id and derived_users_by_id[cc_id].email]

  warnings_and_why = [
      {'value': warning,
       'why': traces.get((tracker_pb2.FieldID.WARNING, warning))}
      for warning in proposed_issue.derived_warnings]

  errors_and_why = [
      {'value': error,
       'why': traces.get((tracker_pb2.FieldID.ERROR, error))}
      for error in proposed_issue.derived_errors]

  return (derived_labels_and_why, derived_owner_and_why, derived_cc_and_why,
          warnings_and_why, errors_and_why)
