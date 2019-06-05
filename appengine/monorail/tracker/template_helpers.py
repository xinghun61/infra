# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Helper functions for issue template servlets"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import collections
import logging

from framework import authdata
from framework import exceptions
from framework import framework_bizobj
from framework import framework_helpers
from tracker import field_helpers
from tracker import tracker_bizobj
from tracker import tracker_constants
from tracker import tracker_helpers
from proto import tracker_pb2

MAX_NUM_PHASES = 6

PHASE_INPUTS = [
    'phase_0', 'phase_1', 'phase_2', 'phase_3', 'phase_4', 'phase_5']

_NO_PHASE_VALUE = 'no_phase'

ParsedTemplate = collections.namedtuple(
    'ParsedTemplate', 'name, members_only, summary, summary_must_be_edited, '
    'content, status, owner_str, labels, field_val_strs, component_paths, '
    'component_required, owner_defaults_to_member, admin_str, add_approvals, '
    'phase_names, approvals_to_phase_idx, required_approval_ids')


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

  add_approvals = post_data.get('add_approvals') == 'on'
  phase_names = [post_data.get(phase_input, '') for phase_input in PHASE_INPUTS]

  required_approval_ids = []
  approvals_to_phase_idx = {}

  for approval_def in config.approval_defs:
    phase_num = post_data.get('approval_%d' % approval_def.approval_id, '')
    if phase_num == _NO_PHASE_VALUE:
      approvals_to_phase_idx[approval_def.approval_id] = None
    else:
      try:
        idx = PHASE_INPUTS.index(phase_num)
        approvals_to_phase_idx[approval_def.approval_id] = idx
      except ValueError:
        logging.info('approval %d was omitted' % approval_def.approval_id)
    required_name = 'approval_%d_required' % approval_def.approval_id
    if (post_data.get(required_name) == 'on'):
      required_approval_ids.append(approval_def.approval_id)

  return ParsedTemplate(
      name, members_only, summary, summary_must_be_edited, content, status,
      owner_str, labels, field_val_strs, component_paths, component_required,
      owner_defaults_to_member, admin_str, add_approvals, phase_names,
      approvals_to_phase_idx, required_approval_ids)


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

  # TODO(jojwang): monorail:4678 Process phase field values.
  phase_field_val_strs = {}
  field_values = field_helpers.ParseFieldValues(
      mr.cnxn, services.user, parsed.field_val_strs,
      phase_field_val_strs, config)
  for fv in field_values:
    logging.info('field_value is %r: %r',
                 fv.field_id, tracker_bizobj.GetFieldValue(fv, {}))

  phases = []
  approvals = []
  if parsed.add_approvals:
    phases, approvals = _GetPhasesAndApprovalsFromParsed(
        mr, parsed.phase_names, parsed.approvals_to_phase_idx,
        parsed.required_approval_ids)

  return admin_ids, owner_id, component_ids, field_values, phases, approvals


def _GetPhasesAndApprovalsFromParsed(
    mr, phase_names, approvals_to_phase_idx, required_approval_ids):
  """Get Phase PBs from a parsed phase_names and approvals_by_phase_idx."""

  phases = []
  approvals = []
  valid_phase_names = []

  for name in phase_names:
    if name:
      if not tracker_constants.PHASE_NAME_RE.match(name):
        mr.errors.phase_approvals = 'Invalid gate name(s).'
        return phases, approvals
      valid_phase_names.append(name)
  if len(valid_phase_names) != len(
      set(name.lower() for name in valid_phase_names)):
    mr.errors.phase_approvals = 'Duplicate gate names.'
    return phases, approvals
  valid_phase_idxs = [idx for idx, name in enumerate(phase_names) if name]
  if set(valid_phase_idxs) != set(
      [idx for idx in approvals_to_phase_idx.values() if idx is not None]):
    mr.errors.phase_approvals = 'Defined gates must have assigned approvals.'
    return phases, approvals

  # Distributing the ranks over a wider range is not necessary since
  # any edits to template phases will cause a complete rewrite.
  # phase_id is temporarily the idx for keeping track of which approvals
  # belong to which phases.
  for idx, phase_name in enumerate(phase_names):
    if phase_name:
      phase = tracker_pb2.Phase(name=phase_name, rank=idx, phase_id=idx)
      phases.append(phase)

  for approval_id, phase_idx in approvals_to_phase_idx.iteritems():
    av = tracker_pb2.ApprovalValue(
        approval_id=approval_id, phase_id=phase_idx)
    if approval_id in required_approval_ids:
      av.status = tracker_pb2.ApprovalStatus.NEEDS_REVIEW
    approvals.append(av)

  return phases, approvals


def FilterApprovalsAndPhases(approval_values, phases, config):
  """Return lists without deleted approvals and empty phases."""
  deleted_approval_ids = [fd.field_id for fd in config.field_defs if
                          fd.is_deleted and
                          fd.field_type is tracker_pb2.FieldTypes.APPROVAL_TYPE]
  filtered_avs = [av for av in approval_values if
                     av.approval_id not in deleted_approval_ids]

  av_phase_ids = list(set([av.phase_id for av in filtered_avs]))
  filtered_phases = [phase for phase in phases if
                     phase.phase_id in av_phase_ids]
  return filtered_avs, filtered_phases


def GatherApprovalsPageData(approval_values, tmpl_phases, config):
  """Create the page data necessary for filling in the launch-gates-table."""
  filtered_avs, filtered_phases = FilterApprovalsAndPhases(
      approval_values, tmpl_phases, config)
  filtered_phases.sort(key=lambda phase: phase.rank)

  required_approval_ids = []
  prechecked_approvals = []

  phase_idx_by_id = {
        phase.phase_id:idx for idx, phase in enumerate(filtered_phases)}
  for av in filtered_avs:
    # approval is part of a phase and that phase can be found.
    if phase_idx_by_id.get(av.phase_id) is not None:
      idx = phase_idx_by_id.get(av.phase_id)
      prechecked_approvals.append(
          '%d_phase_%d' % (av.approval_id, idx))
    else:
      prechecked_approvals.append('%d' % av.approval_id)
    if av.status is tracker_pb2.ApprovalStatus.NEEDS_REVIEW:
      required_approval_ids.append(av.approval_id)

  num_phases = len(filtered_phases)
  filtered_phases.extend([tracker_pb2.Phase()] * (
      MAX_NUM_PHASES - num_phases))
  return prechecked_approvals, required_approval_ids, filtered_phases


def GetCheckedApprovalsFromParsed(approvals_to_phase_idx):
  checked_approvals = []
  for approval_id, phs_idx in approvals_to_phase_idx.iteritems():
    if phs_idx is not None:
      checked_approvals.append('%d_phase_%d' % (approval_id, phs_idx))
    else:
      checked_approvals.append('%d' % approval_id)
  return checked_approvals
