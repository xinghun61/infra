# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Helper functions for issue template servlets"""

import collections
import logging

from framework import authdata
from framework import exceptions
from framework import framework_bizobj
from framework import framework_helpers
from tracker import field_helpers
from tracker import tracker_bizobj
from tracker import tracker_helpers
from proto import tracker_pb2


PHASE_INPUTS = [
    'phase_0', 'phase_1', 'phase_2', 'phase_3', 'phase_4', 'phase_5']


ParsedTemplate = collections.namedtuple(
    'ParsedTemplate', 'name, members_only, summary, summary_must_be_edited, '
    'content, status, owner_str, labels, field_val_strs, component_paths, '
    'component_required, owner_defaults_to_member, admin_str, add_phases, '
    'phase_names, approvals_by_phase_idx, required_approval_ids')


def ParseTemplateRequest(post_data, config):
  """Parse an issue template."""

  name = post_data.get('name', '')
  members_only = (post_data.get('members_only') == 'on')
  summary = post_data.get('summary', '')
  summary_must_be_edited = (
      post_data.get('summary_must_be_edited') == 'on')
  content = post_data.get('content', '')
  content = framework_helpers.WordWrapSuperLongLines(content, max_cols=75)
  status = post_data.get('status', '')
  owner_str = post_data.get('owner', '')
  labels = post_data.getall('label')
  field_val_strs = collections.defaultdict(list)
  for fd in config.field_defs:
    field_value_key = 'custom_%d' % fd.field_id
    if post_data.get(field_value_key):
      field_val_strs[fd.field_id].append(post_data[field_value_key])

  component_paths = []
  if post_data.get('components'):
    for component_path in post_data.get('components').split(','):
      if component_path.strip() not in component_paths:
        component_paths.append(component_path.strip())
  component_required = post_data.get('component_required') == 'on'

  owner_defaults_to_member = post_data.get('owner_defaults_to_member') == 'on'

  admin_str = post_data.get('admin_names', '')

  add_phases = post_data.get('add_phases') == 'on'
  phase_names = [post_data.get(phase_input, '') for phase_input in PHASE_INPUTS]

  required_approval_ids = []
  approvals_by_phase_idx = collections.defaultdict(list)
  for approval_def in config.approval_defs:
    phase_num = post_data.get('approval_%d' % approval_def.approval_id, '')
    try:
      idx = PHASE_INPUTS.index(phase_num)
      approvals_by_phase_idx[idx].append(approval_def.approval_id)
      required_name = 'approval_%d_required' % approval_def.approval_id
      if (post_data.get(required_name) == 'on'):
        required_approval_ids.append(approval_def.approval_id)
    except ValueError:
      logging.info('approval %d was omitted' % approval_def.approval_id)

  return ParsedTemplate(
      name, members_only, summary, summary_must_be_edited, content, status,
      owner_str, labels, field_val_strs, component_paths, component_required,
      owner_defaults_to_member, admin_str, add_phases, phase_names,
      approvals_by_phase_idx, required_approval_ids)


def GetTemplateInfoFromParsed(mr, services, parsed, config):
  """Get Template field info and PBs from a ParsedTemplate."""

  admin_ids, _ = tracker_helpers.ParseAdminUsers(
      mr.cnxn, parsed.admin_str, services.user)

  owner_id = 0
  if parsed.owner_str:
    try:
      user_id = services.user.LookupUserID(mr.cnxn, parsed.owner_str)
      auth = authdata.AuthData.FromUserID(mr.cnxn, user_id, services)
      if framework_bizobj.UserIsInProject(mr.project, auth.effective_ids):
        owner_id = user_id
      else:
        mr.errors.owner = 'User is not a member of this project.'
    except exceptions.NoSuchUserException:
      mr.errors.owner = 'Owner not found.'

  component_ids = tracker_helpers.LookupComponentIDs(
      parsed.component_paths, config, mr.errors)

  field_values = field_helpers.ParseFieldValues(
      mr.cnxn, services.user, parsed.field_val_strs, config)
  for fv in field_values:
    logging.info('field_value is %r: %r',
                 fv.field_id, tracker_bizobj.GetFieldValue(fv, {}))

  phases = []
  if parsed.add_phases:
    phases = _GetPhasesFromParsed(
        mr, parsed.phase_names, parsed.approvals_by_phase_idx,
        parsed.required_approval_ids)

  return admin_ids, owner_id, component_ids, field_values, phases


def _GetPhasesFromParsed(mr, phase_names, approvals_by_phase_idx, required_approval_ids):
  """Get Phase PBs from a parsed phase_names and approvals_by_phase_idx."""

  phases = []

  valid_phase_names = [name for name in phase_names if name]
  if len(valid_phase_names) != len(
      set(name.lower() for name in valid_phase_names)):
    mr.errors.phase_approvals = 'Duplicate gate names.'
    return phases
  valid_phase_idxs = [idx for idx, name in enumerate(phase_names) if name]
  if set(valid_phase_idxs) != set(approvals_by_phase_idx.keys()):
    mr.errors.phase_approvals = 'Defined gates must have assigned approvals.'
    return phases

  for idx in approvals_by_phase_idx:
    approval_ids = approvals_by_phase_idx[idx]
    phase_name = phase_names[idx]

    # Distributing the ranks over a wider range is not necessary since
    # any edits to template phases will cause a complete rewrite
    phase = tracker_pb2.Phase(name=phase_name, rank=idx)
    phases.append(phase)
    for approval_id in approval_ids:
      av = tracker_pb2.ApprovalValue(
          approval_id=approval_id)
      if approval_id in required_approval_ids:
        av.status = tracker_pb2.ApprovalStatus.NEEDS_REVIEW
      # TODO(jojwang): monorail:3655, add default sub_field_values
      # TODO(jojwang): monorail:3656, add option for default approvers
      # per template
      phase.approval_values.append(av)

  return phases
