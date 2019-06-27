# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""FLT task to be manually triggered to convert launch issues."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

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
UX_PREFIX = 'ux-'

PM_FIELD = 'pm'
TL_FIELD = 'tl'
TE_FIELD = 'te'
UX_FIELD = 'ux'
MTARGET_FIELD = 'm-target'
MAPPROVED_FIELD = 'm-approved'

CONVERSION_COMMENT = 'Automatic generating of FLT Launch data.'

BROWSER_APPROVALS_TO_LABELS = {
    'Chrome-Accessibility': 'Launch-Accessibility-',
    'Chrome-Leadership-Exp': 'Launch-Exp-Leadership-',
    'Chrome-Leadership-Full': 'Launch-Leadership-',
    'Chrome-Legal': 'Launch-Legal-',
    'Chrome-Privacy': 'Launch-Privacy-',
    'Chrome-Security': 'Launch-Security-',
    'Chrome-Test': 'Launch-Test-',
    'Chrome-UX': 'Launch-UI-',
    }

OS_APPROVALS_TO_LABELS = {
    'ChromeOS-Accessibility': 'Launch-Accessibility-',
    'ChromeOS-Leadership-Exp': 'Launch-Exp-Leadership-',
    'ChromeOS-Leadership-Full': 'Launch-Leadership-',
    'ChromeOS-Legal': 'Launch-Legal-',
    'ChromeOS-Privacy': 'Launch-Privacy-',
    'ChromeOS-Security': 'Launch-Security-',
    'ChromeOS-Test': 'Launch-Test-',
    'ChromeOS-UX': 'Launch-UI-',
    }

# 'NotReviewed' not included because this should be converted to
# the template approval's default value, eg NOT_SET OR NEEDS_REVIEW
VALUE_TO_STATUS = {
    'ReviewRequested': tracker_pb2.ApprovalStatus.REVIEW_REQUESTED,
    'NeedInfo': tracker_pb2.ApprovalStatus.NEED_INFO,
    'Yes': tracker_pb2.ApprovalStatus.APPROVED,
    'No': tracker_pb2.ApprovalStatus.NOT_APPROVED,
    'NA': tracker_pb2.ApprovalStatus.NA,
    # 'Started' is not a valid label value in the chromium project,
    # but for some reason, some labels have this value.
    'Started': tracker_pb2.ApprovalStatus.REVIEW_STARTED,
}

# This works in the Browser and OS process because
# BROWSER_APPROVALS_TO_LABELS and OS_APPROVALS_TO_LABELS have the same values.
# Adding '^' before each label prefix to ensure Blah-Launch-UI-Yes is ignored
REVIEW_LABELS_RE = re.compile('^' + '|^'.join(
    list(OS_APPROVALS_TO_LABELS.values())))

# Maps template phases to channel names in 'Launch-M-Target-80-[Channel]' labels
BROWSER_PHASE_MAP = {
    'beta': 'beta',
    'stable': 'stable',
    'stable-full': 'stable',
    'stable-exp': 'stable-exp',
    }

PHASE_PAT = '$|'.join(list(BROWSER_PHASE_MAP.values()))
# Matches launch milestone labels, eg. Launch-M-Target-70-Stable-Exp
BROWSER_M_LABELS_RE = re.compile(
    r'^Launch-M-(?P<type>Approved|Target)-(?P<m>\d\d)-'
    r'(?P<channel>%s$)' % PHASE_PAT,
    re.IGNORECASE)

OS_PHASE_MAP = {'feature freeze': '',
                 'branch': '',
                'stable': 'stable',
                'stable-full': 'stable',
                'stable-exp': 'stable-exp',}
# We only care about Launch-M-<type>-<m>-Stable|Stable-Exp labels for OS.
OS_M_LABELS_RE = re.compile(
    r'^Launch-M-(?P<type>Approved|Target)-(?P<m>\d\d)-'
    r'(?P<channel>Stable$|Stable-Exp$)', re.IGNORECASE)

CAN = 2  # Query for open issues only
# Ensure empty group_by_spec and sort_spec so issues are sorted by 'ID'.
GROUP_BY_SPEC = ''
SORT_SPEC = ''

CONVERT_NUM = 20
CONVERT_START = 0
VERIFY_NUM = 400

# Queries
QUERY_MAP = {
    'default':
    'Type=Launch Rollout-Type=Default OS=Windows,Mac,Linux,Android,iOS',
    'finch': 'Type=Launch Rollout-Type=Finch OS=Windows,Mac,Linux,Android,iOS',
    'os': 'Type=Launch OS=Chrome -OS=Windows,Mac,Linux,Android,iOS'
    ' Rollout-Type=Default',
    'os-finch': 'Type=Launch OS=Chrome -OS=Windows,Mac,Linux,Android,iOS'
    ' Rollout-Type=Finch'}

TEMPLATE_MAP = {
    'default': 'Chrome Launch - Default',
    'finch': 'Chrome Launch - Experimental',
    'os': 'Chrome OS Launch - Default',
    'os-finch': 'Chrome OS Launch - Experimental',
}

ProjectInfo = collections.namedtuple(
    'ProjectInfo', 'config, q, approval_values, phases, '
    'pm_fid, tl_fid, te_fid, ux_fid, m_target_id, m_approved_id, '
    'phase_map, approvals_to_labels, labels_re')


class FLTConvertTask(jsonfeed.InternalTask):
  """FLTConvert converts current Type=Launch issues into Type=FLT-Launch."""

  def AssertBasePermission(self, mr):
    super(FLTConvertTask, self).AssertBasePermission(mr)
    if not mr.auth.user_pb.is_site_admin:
      raise permissions.PermissionException(
          'Only site admins may trigger conversion job')

  def UndoConversion(self, mr):
    with work_env.WorkEnv(mr, self.services) as we:
      pipeline = we.ListIssues(
          'Type=FLT-Launch FLT=Conversion', ['chromium'], mr.auth.user_id,
          CONVERT_NUM, CONVERT_START, [], 2, GROUP_BY_SPEC, SORT_SPEC, False)

    project = self.services.project.GetProjectByName(mr.cnxn, 'chromium')
    config = self.services.config.GetProjectConfig(mr.cnxn, project.project_id)
    pm_id = tracker_bizobj.FindFieldDef('PM', config).field_id
    tl_id = tracker_bizobj.FindFieldDef('TL', config).field_id
    te_id = tracker_bizobj.FindFieldDef('TE', config).field_id
    ux_id = tracker_bizobj.FindFieldDef('UX', config).field_id
    for possible_stale_issue in pipeline.visible_results:
      issue = self.services.issue.GetIssue(
          mr.cnxn, possible_stale_issue.issue_id, use_cache=False)

      issue.approval_values = []
      issue.phases = []
      issue.field_values = [fv for fv in issue.field_values
                            if fv.phase_id is None]
      issue.field_values = [fv for fv in issue.field_values
                            if fv.field_id not in
                            [pm_id, tl_id, te_id, ux_id]]
      issue.labels.remove('Type-FLT-Launch')
      issue.labels.remove('FLT-Conversion')
      issue.labels.append('Type-Launch')

      self.services.issue._UpdateIssuesApprovals(mr.cnxn, issue)
      self.services.issue.UpdateIssue(mr.cnxn, issue)
    return {'deleting': [issue.local_id for issue in pipeline.visible_results],
            'num': len(pipeline.visible_results),
    }

  def VerifyConversion(self, mr):
    """Verify that all FLT-Conversion issues were converted correctly."""
    with work_env.WorkEnv(mr, self.services) as we:
      pipeline = we.ListIssues(
          'FLT=Conversion', ['chromium'], mr.auth.user_id,
          VERIFY_NUM, CONVERT_START, [], 2, GROUP_BY_SPEC, SORT_SPEC, False)

    project = self.services.project.GetProjectByName(mr.cnxn, 'chromium')
    config = self.services.config.GetProjectConfig(mr.cnxn, project.project_id)
    browser_approval_names = {fd.field_id: fd.field_name for fd
                              in config.field_defs if fd.field_name in
                              BROWSER_APPROVALS_TO_LABELS.keys()}
    os_approval_names = {fd.field_id: fd.field_name for fd in config.field_defs
                         if (fd.field_name in OS_APPROVALS_TO_LABELS.keys())
                         or fd.field_name == 'ChromeOS-Enterprise'}
    pm_id = tracker_bizobj.FindFieldDef('PM', config).field_id
    tl_id = tracker_bizobj.FindFieldDef('TL', config).field_id
    te_id = tracker_bizobj.FindFieldDef('TE', config).field_id
    ux_id = tracker_bizobj.FindFieldDef('UX', config).field_id
    mapproved_id = tracker_bizobj.FindFieldDef('M-Approved', config).field_id
    mtarget_id = tracker_bizobj.FindFieldDef('M-Target', config).field_id

    problems = []
    for possible_stale_issue in pipeline.allowed_results:
      issue = self.services.issue.GetIssue(
          mr.cnxn, possible_stale_issue.issue_id, use_cache=False)
      # Check correct template used
      approval_names = browser_approval_names
      approvals_to_labels = BROWSER_APPROVALS_TO_LABELS
      m_labels_re = BROWSER_M_LABELS_RE
      label_channel_to_phase_id = {
          phase.name.lower(): phase.phase_id for phase in issue.phases}
      if [l for l in issue.labels if l.startswith('OS-')] == ['OS-Chrome']:
        approval_names = os_approval_names
        m_labels_re = OS_M_LABELS_RE
        approvals_to_labels = OS_APPROVALS_TO_LABELS
        # OS default launch
        if 'Rollout-Type-Default' in issue.labels:
          if not all(phase.name in ['Feature Freeze', 'Branch', 'Stable']
                     for phase in issue.phases):
            problems.append((
                issue.local_id, 'incorrect phases for OS default launch.'))
        # OS finch launch
        elif 'Rollout-Type-Finch' in issue.labels:
          if not all(phase.name in (
              'Feature Freeze', 'Branch', 'Stable-Exp', 'Stable-Full')
                     for phase in issue.phases):
            problems.append((
                issue.local_id, 'incorrect phases for OS finch launch.'))
        else:
          problems.append((
              issue.local_id,
              'no rollout-type; should not have been converted'))
      # Browser default launch
      elif 'Rollout-Type-Default' in issue.labels:
        if not all(phase.name.lower() in ['beta', 'stable']
                   for phase in issue.phases):
          problems.append((
              issue.local_id, 'incorrect phases for Default rollout'))
      # Browser finch launch
      elif 'Rollout-Type-Finch' in issue.labels:
        if not all(phase.name.lower() in ['beta', 'stable-exp', 'stable-full']
                   for phase in issue.phases):
          problems.append((
              issue.local_id, 'incorrect phases for Finch rollout'))
      else:
        problems.append((
            issue.local_id,
            'no rollout-type; should not have been converted'))

      # Check approval_values
      for av in issue.approval_values:
        name = approval_names.get(av.approval_id)
        if name == 'ChromeOS-Enterprise':
          if av.status != tracker_pb2.ApprovalStatus.NEEDS_REVIEW:
            problems.append((issue.local_id, 'bad ChromeOS-Enterprise status'))
          continue
        label_pre = approvals_to_labels.get(name)
        if not label_pre:
          # either name was None or not found in APPROVALS_TO_LABELS
          problems.append((issue.local_id, 'approval %s not recognized' % name))
          continue
        label_value = next((l[len(label_pre):] for l in issue.labels
                            if l.startswith(label_pre)), None)
        if (not label_value or label_value == 'NotReviewed') and av.status in [
            tracker_pb2.ApprovalStatus.NOT_SET,
            tracker_pb2.ApprovalStatus.NEEDS_REVIEW]:
          continue
        if av.status is VALUE_TO_STATUS.get(label_value):
          continue
        # neither of the above ifs passed
        problems.append((issue.local_id,
                         'approval %s has status %r for label value %s' % (
                             name, av.status.name, label_value)))

      # Check people field_values
      expected_people_fvs = self.ConvertPeopleLabels(
          mr, issue.labels, pm_id, tl_id, te_id, ux_id)
      for people_fv in expected_people_fvs:
        if people_fv not in issue.field_values:
          if people_fv.field_id == tl_id:
            role = 'TL'
          elif people_fv.field_id == pm_id:
            role = 'PM'
          elif people_fv.field_id == ux_id:
            role = 'UX'
          else:
            role = 'TE'
          problems.append((issue.local_id, 'missing a field for %s' % role))

      # Check M phase field_values
      for label in issue.labels:
        match = re.match(m_labels_re, label)
        if match:
          channel = match.group('channel')
          if (channel.lower() == 'stable-exp'
              and 'Rollout-Type-Default' in issue.labels):
            # ignore stable-exp for default rollouts.
            continue
          milestone = match.group('m')
          m_type = match.group('type')
          m_id = mapproved_id if m_type == 'Approved' else mtarget_id
          phase_id = label_channel_to_phase_id.get(
              channel.lower(), label_channel_to_phase_id.get('stable-full'))
          if not next((
              fv for fv in issue.field_values
              if fv.phase_id == phase_id and fv.field_id == m_id and
              fv.int_value == int(milestone)), None):
            problems.append((
                issue.local_id, 'no phase field for label %s' % label))

    return {
        'problems found': ['issue %d: %s' % problem for problem in problems],
        'issues verified': ['issue %d' % issue.local_id for
                            issue in pipeline.allowed_results],
        'num': len(pipeline.allowed_results),
    }

  def HandleRequest(self, mr):
    """Convert Type=Launch issues to new Type=FLT-Launch issues."""
    launch = mr.GetParam('launch')
    if launch == 'delete':
      return self.UndoConversion(mr)
    if launch == 'verify':
      return self.VerifyConversion(mr)
    project_info = self.FetchAndAssertProjectInfo(mr)

    # Search for issues:
    with work_env.WorkEnv(mr, self.services) as we:
      pipeline = we.ListIssues(
          project_info.q, ['chromium'], mr.auth.user_id, CONVERT_NUM,
          CONVERT_START, [], 2, GROUP_BY_SPEC, SORT_SPEC, False)

    # Convert issues:
    for possible_stale_issue in pipeline.visible_results:
      # Note: These approval values and phases from templates will be used
      # and modified to create approval values and phases for each issue.
      # We need to create copies for each issue so changes are not carried
      # over to the conversion of the next issue in the loop.
      template_avs = self.CreateApprovalCopies(project_info.approval_values)
      template_phases = self.CreatePhasesCopies(project_info.phases)
      issue = self.services.issue.GetIssue(
          mr.cnxn, possible_stale_issue.issue_id, use_cache=False)
      new_approvals = ConvertLaunchLabels(
          issue.labels, template_avs,
          project_info.config.field_defs, project_info.approvals_to_labels)
      m_fvs = ConvertMLabels(
          issue.labels, template_phases,
          project_info.m_target_id, project_info.m_approved_id,
          project_info.labels_re, project_info.phase_map)
      people_fvs = self.ConvertPeopleLabels(
          mr, issue.labels,
          project_info.pm_fid, project_info.tl_fid, project_info.te_fid,
          project_info.ux_fid)
      amendments = self.ExecuteIssueChanges(
          project_info.config, issue, new_approvals,
          template_phases, m_fvs + people_fvs)
      logging.info(amendments)

    return {
        'converted_issues': [
            issue.local_id for issue in pipeline.visible_results],
        'num': len(pipeline.visible_results),
        }

  def CreateApprovalCopies(self, avs):
    return [
      tracker_pb2.ApprovalValue(
          approval_id=av.approval_id,
          status=av.status,
          setter_id=av.setter_id,
          set_on=av.set_on,
          phase_id=av.phase_id) for av in avs
    ]

  def CreatePhasesCopies(self, phases):
    return [
      tracker_pb2.Phase(
          phase_id=phase.phase_id,
          name=phase.name,
          rank=phase.rank) for phase in phases
        ]

  def FetchAndAssertProjectInfo(self, mr):
    # Get request details
    launch = mr.GetParam('launch')
    logging.info(launch)
    q = QUERY_MAP.get(launch)
    template_name = TEMPLATE_MAP.get(launch)
    assert q and template_name, 'bad launch type: %s' % launch

    phase_map = (
        OS_PHASE_MAP if launch in ['os', 'os-finch'] else BROWSER_PHASE_MAP)
    approvals_to_labels = (
        OS_APPROVALS_TO_LABELS if launch in ['os', 'os-finch']
        else BROWSER_APPROVALS_TO_LABELS)
    m_labels_re = (
        OS_M_LABELS_RE if launch in ['os', 'os-finch'] else BROWSER_M_LABELS_RE)

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
    assert all(phase.name.lower() in list(
        phase_map.keys()) for phase in phases), (
          'one or more phases not recognized')
    if launch in ['finch', 'os', 'os-finch']:
      assert all(
          av.status is tracker_pb2.ApprovalStatus.NEEDS_REVIEW
          for av in approval_values
      ), '%s template not set up correctly' % launch

    approval_fds = {fd.field_id: fd.field_name for fd in config.field_defs
                    if fd.field_type is tracker_pb2.FieldTypes.APPROVAL_TYPE}
    assert all(
        approval_fds.get(av.approval_id) in list(approvals_to_labels.keys())
        for av in approval_values
        if approval_fds.get(av.approval_id) != 'ChromeOS-Enterprise'), (
            'one or more approvals not recognized')
    approval_def_ids = [ad.approval_id for ad in config.approval_defs]
    assert all(av.approval_id in approval_def_ids for av in approval_values), (
        'one or more approvals not in config.approval_defs')

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
    ux_fid = user_fds.get(UX_FIELD)
    assert ux_fid, 'project has no FieldDef %s' % UX_FIELD

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
                       te_fid, ux_fid, m_target_id, m_approved_id, phase_map,
                       approvals_to_labels, m_labels_re)

  # TODO(jojwang): mr needs to be passed in as arg and
  # all self.mr should be changed to mr
  def ExecuteIssueChanges(self, config, issue, new_approvals, phases, new_fvs):
    # Apply Approval and phase changes
    approval_defs_by_id = {ad.approval_id: ad for ad in config.approval_defs}
    for av in new_approvals:
      ad = approval_defs_by_id.get(av.approval_id)
      if ad:
        av.approver_ids = ad.approver_ids
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
    issue.approval_values = new_approvals
    self.services.issue._UpdateIssuesApprovals(self.mr.cnxn, issue)

    # Apply field value changes
    issue.phases = phases
    delta = tracker_bizobj.MakeIssueDelta(
        None, None, [], [], [], [], ['Type-FLT-Launch', 'FLT-Conversion'],
        ['Type-Launch'], new_fvs, [], [], [], [], [], [], None, None)
    amendments, _ = self.services.issue.DeltaUpdateIssue(
        self.mr.cnxn, self.services, self.mr.auth.user_id, issue.project_id,
        config, issue, delta, comment=CONVERSION_COMMENT)

    return amendments

  def ConvertPeopleLabels(
      self, mr, labels, pm_field_id, tl_field_id, te_field_id, ux_field_id):
    field_values = []
    pm_ldap, tl_ldap, test_ldaps, ux_ldaps = ExtractLabelLDAPs(labels)

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

    for ux_ldap in ux_ldaps:
      ux_fv = self.CreateUserFieldValue(mr, ux_ldap, ux_field_id)
      if ux_fv:
        field_values.append(ux_fv)
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


def ConvertMLabels(
    labels, phases, m_target_id, m_approved_id, labels_re, phase_map):
  field_values = []
  for label in labels:
    match = re.match(labels_re, label)
    if match:
      milestone = match.group('m')
      m_type = match.group('type')
      channel = match.group('channel')
      for phase in phases:
        # We know get(phase) will return something because
        # we're checking before ConvertMLabels, that all phases
        # exist in BROWSER_PHASE_MAP or OS_PHASE_MAP
        if phase_map.get(phase.name.lower()) == channel.lower():
          field_id = m_target_id if (
              m_type.lower() == 'target') else m_approved_id
          field_values.append(tracker_bizobj.MakeFieldValue(
              field_id, int(milestone), None, None, None, None, False,
              phase_id=phase.phase_id))
          break  # exit phase loop if match is found.
  return field_values


def ConvertLaunchLabels(labels, approvals, project_fds, approvals_to_labels):
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
    old_prefix = approvals_to_labels.get(approval_name)
    label_value = label_values.get(old_prefix, '')
    # if label_value not found in VALUE_TO_STATUS, use current status.
    approval.status = VALUE_TO_STATUS.get(label_value, approval.status)

  return approvals


def ExtractLabelLDAPs(labels):
  """Extracts LDAPs from labels 'PM-', 'TL-', 'UX-', and 'test-'"""

  pm_ldap = None
  tl_ldap = None
  test_ldaps = []
  ux_ldaps = []
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
    elif label.startswith(UX_PREFIX):
      ldap = label[len(UX_PREFIX):]
      if ldap:
        ux_ldaps.append(ldap)
  return pm_ldap, tl_ldap, test_ldaps, ux_ldaps
