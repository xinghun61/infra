# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""FLT task to be manually triggered to convert launch issues."""

import collections
import logging
import re
import settings
import time

from businesslogic import work_env
from framework import permissions
from framework import exceptions
from framework import jsonfeed
from proto import tracker_pb2
from tracker import template_helpers
from tracker import tracker_bizobj

PM_PREFIX = 'pm-'
TL_PREFIX = 'tl-'
TEST_PREFIX = 'test-'

PM_FIELD = 'pm'
TL_FIELD = 'tl'
TE_FIELD = 'te'
MTARGET_FIELD = 'm-target'
MAPPROVED_FIELD = 'm-approved'

CONVERSION_COMMENT = 'Automatic generating of FLT Launch data.'

APPROVALS_TO_LABELS = {
    'Chrome-Accessibility': 'Launch-Accessibility-',
    'Chrome-Leadership-Exp': 'Launch-Exp-Leadership-',
    'Chrome-Leadership-Full': 'Launch-Leadership-',
    'Chrome-Legal': 'Launch-Legal-',
    'Chrome-Privacy': 'Launch-Privacy-',
    'Chrome-Security': 'Launch-Security-',
    'Chrome-Test': 'Launch-Test-',
    'Chrome-UX': 'Launch-UI-',
    }

# 'NotReviewed' not included because this should be converted to
# the template approval's default value, eg NOT_SET OR NEEDS_REVIEW
VALUE_TO_STATUS = {
    'ReviewRequested': tracker_pb2.ApprovalStatus.REVIEW_REQUESTED,
    'NeedInfo': tracker_pb2.ApprovalStatus.NEED_INFO,
    'Yes': tracker_pb2.ApprovalStatus.APPROVED,
    'No': tracker_pb2.ApprovalStatus.NOT_APPROVED,
    'NA': tracker_pb2.ApprovalStatus.NA,
}
# Adding '^' before each label prefix to ensure Blah-Launch-UI-Yes is ignored
REVIEW_LABELS_RE = re.compile('^' + '|^'.join(APPROVALS_TO_LABELS.values()))

# Maps template phases to channel names in 'Launch-M-Target-80-[Channel]' labels
PHASE_MAP = {
    'beta': 'beta',
    'stable': 'stable',
    'stable-full': 'stable',
    'stable-exp': 'stable-exp',
    }

PHASE_PAT = '$|'.join(PHASE_MAP.values())
# Matches launch milestone labels, eg. Launch-M-Target-70-Stable-Exp
M_LABELS_RE = re.compile(
    r'^Launch-M-(?P<type>Approved|Target)-(?P<m>\d\d)-'
    r'(?P<channel>%s$)' % PHASE_PAT,
    re.IGNORECASE)

CAN = 2  # Query for open issues only
# Ensure empty group_by_spec and sort_spec so issues are sorted by 'ID'.
GROUP_BY_SPEC = ''
SORT_SPEC = ''

# TODO(jojwang): set CONVERT_NUM this to 300
CONVERT_NUM = 1
CONVERT_START = 0

# Queries
QUERY_MAP = {
    'default':
    'Type=Launch Rollout-Type=Default OS=Windows,Mac,Linux,Android,iOS',
    'finch': 'Type=Launch Rollout-Type=Finch OS=Windows,Mac,Linux,Android,iOS'}
TEMPLATE_MAP = {
    'default': 'Chrome Default Launch',
    'finch': 'Chrome Finch Launch'}

ProjectInfo = collections.namedtuple(
    'ProjectInfo', 'config, q, approval_values, phases, '
    'pm_fid, tl_fid, te_fid, m_target_id, m_approved_id')

# TODO(jojwang): PM, TL, TE user fields are project members in bugs-staging
# assert trying to add non-project members won't cause problems


class FLTConvertTask(jsonfeed.InternalTask):
  """FLTConvert converts current Type=Launch issues into Type=FLT-Launch."""

  def AssertBasePermission(self, mr):
    super(FLTConvertTask, self).AssertBasePermission(mr)
    if not mr.auth.user_pb.is_site_admin:
      raise permissions.PermissionException(
          'Only site admins may trigger conversion job')
    # TODO(BEFORE-LAUNCH): REMOVE 'monotail-staging' check
    if settings.app_id != 'monorail-staging':
      raise exceptions.ActionNotSupported(
          'Launch issues conversion only allowed in staging.')

  def HandleRequest(self, mr):
    """Convert Type=Launch issues to new Type=FLT-Launch issues."""
    project_info = self.FetchAndAssertProjectInfo(mr)

    # Search for issues:
    with work_env.WorkEnv(mr, self.services) as we:
      pipeline = we.ListIssues(
          project_info.q, ['chromium'], mr.auth.user_id, CONVERT_NUM,
          CONVERT_START, [], 2, GROUP_BY_SPEC, SORT_SPEC, False)

    # Convert issues:
    # TODO(jojwang): BEFORE LAUNCH change to pipeline.allowed_results
    for possible_stale_issue in pipeline.visible_results:
      issue = self.services.issue.GetIssue(
          mr.cnxn, possible_stale_issue.issue_id, use_cache=False)
      new_approvals = ConvertLaunchLabels(
          issue.labels, project_info.approval_values,
          project_info.config.field_defs)
      m_fvs = ConvertMLabels(
          issue.labels, project_info.phases,
          project_info.m_target_id, project_info.m_approved_id)
      people_fvs = self.ConvertPeopleLabels(
          mr, issue.labels,
          project_info.pm_fid, project_info.tl_fid, project_info.te_fid)
      amendments = self.ExecuteIssueChanges(
          project_info.config, issue, new_approvals,
          project_info.phases, m_fvs + people_fvs)
      logging.info('SUCCESSFULLY CONVERTED ISSUE: %s' % issue.local_id)
      logging.info('amendments %r', amendments)

    return {
        'converted_issues': [
            issue.local_id for issue in pipeline.visible_results],
        }

  def FetchAndAssertProjectInfo(self, mr):
    # Get request details
    launch = mr.GetParam('launch')
    logging.info(launch)
    q = QUERY_MAP.get(launch)
    template_name = TEMPLATE_MAP.get(launch)
    assert q and template_name, 'bad launch type: %s' % launch

    # Get project, config, template, assert template in project
    project = self.services.project.GetProjectByName(mr.cnxn, 'chromium')
    config = self.services.config.GetProjectConfig(mr.cnxn, project.project_id)
    template = self.services.template.GetTemplateByName(
        mr.cnxn, template_name, project.project_id)
    assert template, 'template %s not found in chromium project' % template_name

    # Get template approval_values/phases and assert they are expected
    approval_values, phases = template_helpers.FilterApprovalsAndPhases(
        template.approval_values, template.phases, config)
    assert approval_values and phases, (
        'no approvals or phases in %s' % template_name)
    assert all(phase.name.lower() in PHASE_MAP.keys() for phase in phases), (
        'one or more phases not recognized')

    approval_fds = {fd.field_id: fd.field_name for fd in config.field_defs
                    if fd.field_type is tracker_pb2.FieldTypes.APPROVAL_TYPE}
    assert all(
        approval_fds.get(av.approval_id) in APPROVALS_TO_LABELS.keys()
        for av in approval_values
        if approval_fds.get(av.approval_id) != 'Chrome-Enterprise'), (
            'one or more approvals not recognized')
    approval_def_ids = [ad.approval_id for ad in config.approval_defs]
    assert all(av.approval_id in approval_def_ids for av in approval_values), (
        'one or more approvals no in config.approval_defs')

    # Get relevant USER_TYPE FieldDef ids and assert they exist
    user_fds = {fd.field_name.lower(): fd.field_id for fd in config.field_defs
                    if fd.field_type is tracker_pb2.FieldTypes.USER_TYPE}
    logging.info('project USER_TYPE FieldDefs: %s' % user_fds)
    pm_fid = user_fds.get(PM_FIELD)
    assert pm_fid, 'project has no FieldDef %s' % PM_FIELD
    tl_fid = user_fds.get(TL_FIELD)
    assert tl_fid, 'project has no FieldDef %s' % TL_FIELD
    te_fid = user_fds.get(TE_FIELD)
    assert te_fid, 'project has no FieldDef %s' % TE_FIELD

    # Get relevant M Phase INT_TYPE FieldDef ids and assert they exist
    phase_int_fds = {fd.field_name.lower(): fd.field_id
                     for fd in config.field_defs
                     if fd.field_type is tracker_pb2.FieldTypes.INT_TYPE
                     and fd.is_phase_field and fd.is_multivalued}
    logging.info(
        'project Phase INT_TYPE multivalued FieldDefs: %s' % phase_int_fds)
    m_target_id = phase_int_fds.get(MTARGET_FIELD)
    assert m_target_id, 'project has no FieldDef %s' % MTARGET_FIELD
    m_approved_id = phase_int_fds.get(MAPPROVED_FIELD)
    assert m_approved_id, 'project has no FieldDef %s' % MAPPROVED_FIELD

    return ProjectInfo(config, q, approval_values, phases, pm_fid, tl_fid,
                       te_fid, m_target_id, m_approved_id)

  # TODO(jojwang): mr needs to be passed in as arg and
  # all self.mr should be changed to mr
  def ExecuteIssueChanges(self, config, issue, new_approvals, phases, new_fvs):
    # Apply Approval and phase changes
    issue.approval_values = new_approvals
    issue.phases = phases
    approval_defs_by_id = {ad.approval_id: ad for ad in config.approval_defs}
    for av in new_approvals:
      ad = approval_defs_by_id.get(av.approval_id)
      if ad:
        survey = ''
        if ad.survey:
          questions = ad.survey.split('\n')
          survey = '\n'.join(['<b>' + q + '</b>' for q in questions])
        self.services.issue.InsertComment(
            self.mr.cnxn, tracker_pb2.IssueComment(
                issue_id=issue.issue_id, project_id=issue.project_id,
                user_id=self.mr.auth.user_id, content=survey,
                is_description=True, approval_id=av.approval_id,
                timestamp=int(time.time())))
      else:
        logging.info(
            'ERROR: ApprovalDef %r for ApprovalValue %r not valid', ad, av)
    self.services.issue._UpdateIssuesApprovals(self.mr.cnxn, issue)

    # Apply field value changes
    delta = tracker_bizobj.MakeIssueDelta(
        None, None, [], [], [], [], ['Type-FLT-Launch', 'FLT-Conversion'],
        ['Type-Launch'], new_fvs, [], [], [], [], [], [], None, None)
    amendments, _ = self.services.issue.DeltaUpdateIssue(
        self.mr.cnxn, self.services, self.mr.auth.user_id, issue.project_id,
        config, issue, delta, comment=CONVERSION_COMMENT)

    return amendments

  def ConvertPeopleLabels(
      self, mr, labels, pm_field_id, tl_field_id, te_field_id):
    field_values = []
    pm_ldap, tl_ldap, test_ldaps = ExtractLabelLDAPs(labels)

    pm_fv = self.CreateUserFieldValue(mr, pm_ldap, pm_field_id)
    if pm_fv:
      field_values.append(pm_fv)

    tl_fv = self.CreateUserFieldValue(mr, tl_ldap, tl_field_id)
    if tl_fv:
      field_values.append(tl_fv)

    for test_ldap in test_ldaps:
      te_fv = self.CreateUserFieldValue(mr, test_ldap, te_field_id)
      if te_fv:
        field_values.append(te_fv)
    return field_values

  def CreateUserFieldValue(self, mr, ldap, field_id):
    if ldap is None:
      return None
    try:
      user_id = self.services.user.LookupUserID(mr.cnxn, ldap+'@chromium.org')
    except exceptions.NoSuchUserException:
      try:
        user_id = self.services.user.LookupUserID(mr.cnxn, ldap+'@google.com')
      except exceptions.NoSuchUserException:
        logging.info('No chromium.org or google.com accound found for %s', ldap)
        return None
    return tracker_bizobj.MakeFieldValue(
        field_id, None, None, user_id, None, None, False)


def ConvertMLabels(labels, phases, m_target_id, m_approved_id):
  field_values = []
  for label in labels:
    match = re.match(M_LABELS_RE, label)
    if match:
      milestone = match.group('m')
      m_type = match.group('type')
      channel = match.group('channel')
      for phase in phases:
        # We know get(phase) will return something because
        # we're checking before ConvertMLabels, that all phases
        # exist in PHASE_MAP
        if PHASE_MAP.get(phase.name.lower()) == channel.lower():
          field_id = m_target_id if (
              m_type.lower() == 'target') else m_approved_id
          field_values.append(tracker_bizobj.MakeFieldValue(
              field_id, int(milestone), None, None, None, None, False,
              phase_id=phase.phase_id))
          break  # exit phase loop if match is found.
  return field_values


def ConvertLaunchLabels(labels, approvals, project_fds):
  """Converts 'Launch-[Review]' values into statuses for given approvals."""
  label_values = {}
  for label in labels:
    launch_match = REVIEW_LABELS_RE.match(label)
    if launch_match:
      prefix = launch_match.group()
      value = label[len(prefix):]  # returns 'Yes' from 'Launch-UI-Yes'
      label_values[prefix] = value

  field_names_dict = {fd.field_id: fd.field_name for fd in project_fds}
  for approval in approvals:
    approval_name = field_names_dict.get(approval.approval_id, '')
    old_prefix = APPROVALS_TO_LABELS.get(approval_name)
    label_value = label_values.get(old_prefix, '')
    # if label_value not found in VALUE_TO_STATUS, use current status.
    approval.status = VALUE_TO_STATUS.get(label_value, approval.status)

  return approvals


def ExtractLabelLDAPs(labels):
  """Extracts LDAPs from labels 'PM-', 'TL-', and 'test-'"""

  pm_ldap = None
  tl_ldap = None
  test_ldaps = []
  for label in labels:
    label = label.lower()
    if label.startswith(PM_PREFIX):
      pm_ldap = label[len(PM_PREFIX):]
    elif label.startswith(TL_PREFIX):
      tl_ldap = label[len(TL_PREFIX):]
    elif label.startswith(TEST_PREFIX):
      ldap = label[len(TEST_PREFIX):]
      if ldap:
        test_ldaps.append(ldap)
  return pm_ldap, tl_ldap, test_ldaps
