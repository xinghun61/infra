# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""FLT task to be manually triggered to convert launch issues."""
import re
import settings
import logging

from framework import permissions
from framework import exceptions
from framework import jsonfeed
from proto import tracker_pb2
from tracker import tracker_bizobj

PM_PREFIX = 'pm-'
TL_PREFIX = 'tl-'
TEST_PREFIX = 'test-'

CONVERSION_COMMENT = "Automatic generating of FLT Launch data."

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


    return {
        'app_id': settings.app_id,
        'is_site_admin': mr.auth.user_pb.is_site_admin,
        }

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
                is_description=True, approval_id=av.approval_id))
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
      self, mr, issue, pm_field_id, tl_field_id, te_field_id):
    field_values = []
    pm_ldap, tl_ldap, test_ldaps = ExtractLabelLDAPs(issue.labels)

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


# TODO(jojwang): before calling ConvertMLabels, check that all phases
# can be found in PHASE_MAP and M-Target and M-Approved are phase fields
# and multi-valued.
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


def ConvertLaunchLabels(issue, approvals, project_fds):
  """Converts 'Launch-[Review]' values into statuses for given approvals."""
  label_values = {}
  for label in issue.labels:
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
