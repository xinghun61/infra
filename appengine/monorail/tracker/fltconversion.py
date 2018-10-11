# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""FLT task to be manually triggered to convert launch issues."""
import re
import settings

from framework import permissions
from framework import exceptions
from framework import jsonfeed
from proto import tracker_pb2

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


class FLTConvertTask(jsonfeed.InternalTask):
  """FLTConvert converts current Type=Launch issues into Type=FLT-Launch."""


  def AssertBasePermission(self, mr):
    super(FLTConvertTask, self).AssertBasePermission(mr)
    if not mr.auth.user_pb.is_site_admin:
      raise permissions.PermissionException(
          'Only site admins may trigger conversion job')
    if settings.app_id != 'monorail-staging':
      raise exceptions.ActionNotSupported(
          'Launch issues conversion only allowed in staging.')

  def HandleRequest(self, mr):
    """Convert Type=Launch issues to new Type=FLT-Launch issues."""


    return {
        'app_id': settings.app_id,
        'is_site_admin': mr.auth.user_pb.is_site_admin,
        }


def ConvertLaunchLabels(issue, approvals, project_fds):
  """Converts 'Launch-[Review]' values into statuses for given approvals."""
  label_values = {}
  for label in issue.labels:
    launch_match = REVIEW_LABELS_RE.match(label)
    if launch_match:
      prefix = launch_match.group()
      value = label.split(prefix, 1)[1]  # returns 'Yes' from 'Launch-UI-Yes'
      label_values[prefix] = value

  field_names_dict = {fd.field_id: fd.field_name for fd in project_fds}
  for approval in approvals:
    approval_name = field_names_dict.get(approval.approval_id, '')
    old_prefix = APPROVALS_TO_LABELS.get(approval_name)
    label_value = label_values.get(old_prefix, '')
    # if label_value not found in VALUE_TO_STATUS, use current status.
    approval.status = VALUE_TO_STATUS.get(label_value, approval.status)

  return approvals
