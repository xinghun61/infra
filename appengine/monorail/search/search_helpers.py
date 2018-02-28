# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

RESTRICT_VIEW_PATTERN = 'restrict-view-%'


def GetPersonalAtRiskLabelIDs(
  cnxn, _user, config_svc, effective_ids, project, perms):
  """Return list of label_ids for restriction labels that user can't view.

  Args:
    cnxn: An instance of MonorailConnection.
    _user: Unused.
    config_svc: An instance of ConfigService.
    effective_ids: The effective IDs of the current user.
    project: A project object for the current project.
    perms: A PermissionSet for the current user.
  Returns:
    A list of LabelDef IDs the current user is forbidden to access.
  """
  at_risk_label_ids = []
  label_def_rows = config_svc.GetLabelDefRowsAnyProject(
    cnxn, where=[('LOWER(label) LIKE %s', [RESTRICT_VIEW_PATTERN])])

  for label_id, _pid, _rank, label, _docstring, _hidden in label_def_rows:
    label_lower = label.lower()
    needed_perm = label_lower.split('-', 1)[-1]
    needed_perm = needed_perm.replace('-', '')

    if not perms.CanUsePerm(needed_perm, effective_ids, project, []):
      at_risk_label_ids.append(label_id)

  return at_risk_label_ids
