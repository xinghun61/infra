# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Functions that convert protorpc business objects into protoc objects.

Monorail uses protorpc objects internally, whereas the API uses protoc
objects.  The difference is not just the choice of protobuf library, there
will always be a need for conversion because out internal objects may have
field that we do not want to expose externally, or the format of some fields
may be different than how we want to expose them.
"""

import logging

from api.api_proto import common_pb2
from api.api_proto import issue_objects_pb2
from framework import framework_constants
from tracker import tracker_bizobj
from tracker import tracker_helpers
from tracker import tracker_views


def ConvertStatusRef(explicit_status, derived_status, config):
  """Use the given status strings to create a StatusRef."""
  status = explicit_status or derived_status
  is_derived = not explicit_status
  if not status:
    return common_pb2.StatusRef(
        status=framework_constants.NO_VALUES, is_derived=False, means_open=True)

  return common_pb2.StatusRef(
      status=status,
      is_derived=is_derived,
      means_open=tracker_helpers.MeansOpenInProject(status, config))


def ConvertUserRef(explicit_user_id, derived_user_id, users_by_id):
  """Use the given user IDs to create a UserRef."""
  user_id = explicit_user_id or derived_user_id
  is_derived = not explicit_user_id
  if not user_id:
    return common_pb2.UserRef(
        user_id=0, display_name=framework_constants.NO_USER_NAME)

  return common_pb2.UserRef(
      user_id=user_id,
      is_derived=is_derived,
      display_name=users_by_id[user_id].display_name)


def ConvertUserRefs(explicit_user_ids, derived_user_ids, users_by_id):
  """Use the given user ID lists to create a list of UserRef."""
  result = []
  for user_id in explicit_user_ids:
    result.append(common_pb2.UserRef(
      user_id=user_id,
      is_derived=False,
      display_name=users_by_id[user_id].display_name))
  for user_id in derived_user_ids:
    result.append(common_pb2.UserRef(
      user_id=user_id,
      is_derived=True,
      display_name=users_by_id[user_id].display_name))
  return result


def ConvertLabels(explicit_labels, derived_labels):
  """Combine the given explicit and derived lists into LabelRefs."""
  explicit_refs = [common_pb2.LabelRef(label=lab, is_derived=False)
                   for lab in explicit_labels]
  derived_refs = [common_pb2.LabelRef(label=lab, is_derived=True)
                  for lab in derived_labels]
  return explicit_refs + derived_refs


def ConvertComponents(explicit_component_ids, derived_component_ids, config):
  """Make a ComponentRef for each component_id."""
  result = []
  for cid in explicit_component_ids:
    cd = tracker_bizobj.FindComponentDefByID(cid, config)
    result.append(common_pb2.ComponentRef(path=cd.path, is_derived=False))
  for cid in derived_component_ids:
    cd = tracker_bizobj.FindComponentDefByID(cid, config)
    result.append(common_pb2.ComponentRef(path=cd.path, is_derived=True))
  return result


def ConvertIssueRef(issue_ref_pair):
  """Convert (project_name, local_id) to an IssueRef protoc object."""
  project_name, local_id = issue_ref_pair
  return common_pb2.IssueRef(project_name=project_name, local_id=local_id)


def ConvertIssueRefs(issue_ids, related_refs_dict):
  """Convert a list of iids to IssueRef protoc objects."""
  return [ConvertIssueRef(related_refs_dict[iid]) for iid in issue_ids]


def ConvertFieldValueItem(field_name, value, is_derived=False):
  """Convert one field value view item into a protoc FieldValue."""
  fv = issue_objects_pb2.FieldValue(
      field_ref=common_pb2.FieldRef(field_name=field_name),
      value=str(value.val),
      is_derived=is_derived)
  return fv


# TODO(jrobbins): Refactor this to avoid needing to use view objects.
def ConvertFieldValueViews(field_value_views):
  """Convert FieldValueView objects to protoc FieldValue objects."""
  result = []
  for fvv in field_value_views:
    result.extend([ConvertFieldValueItem(fvv.field_name, item)
                   for item in fvv.values])
    result.extend([ConvertFieldValueItem(fvv.field_name, item, is_derived=True)
                   for item in fvv.derived_values])
  return result


def ConvertIssue(issue, users_by_id, related_refs, config):
  """Convert our protorpc Issue to a protoc Issue.

  Args:
    issue: protorpc issue used by monorail internally.
    users_by_id: dict {user_id: UserViews} for all users mentioned in issue.
    related_refs: dict {issue_id: (project_name, local_id)} of all blocked-on,
        blocking, or merged-into issues referenced from this issue, regardless
        of perms.
    config: ProjectIssueConfig for this issue.

  Returns: A protoc Issue object.
  """
  status_ref = ConvertStatusRef(issue.status, issue.derived_status, config)
  owner_ref = ConvertUserRef(
      issue.owner_id, issue.derived_owner_id, users_by_id)
  cc_refs = ConvertUserRefs(
      issue.cc_ids, issue.derived_cc_ids, users_by_id)
  labels, derived_labels = tracker_bizobj.ExplicitAndDerivedNonMaskedLabels(
      issue, config)
  label_refs = ConvertLabels(labels, derived_labels)
  component_refs = ConvertComponents(
      issue.component_ids, issue.derived_component_ids, config)
  blocked_on_issue_refs = ConvertIssueRefs(
      issue.blocked_on_iids, related_refs)
  blocking_issue_refs = ConvertIssueRefs(
      issue.blocking_iids, related_refs)
  merged_into_issue_ref = None
  if issue.merged_into:
    merged_into_issue_ref = ConvertIssueRef(related_refs[issue.merged_into])

  field_value_views = tracker_views.MakeAllFieldValueViews(
      config, issue.labels, issue.derived_labels, issue.field_values,
      users_by_id)
  field_values = ConvertFieldValueViews(field_value_views)

  # TODO(jrobbins): approvals
  reporter_ref = ConvertUserRef(issue.reporter_id, None, users_by_id)
  result = issue_objects_pb2.Issue(
      project_name=issue.project_name, local_id=issue.local_id,
      summary=issue.summary, status_ref=status_ref, owner_ref=owner_ref,
      cc_refs=cc_refs, label_refs=label_refs, component_refs=component_refs,
      blocked_on_issue_refs=blocked_on_issue_refs,
      blocking_issue_refs=blocking_issue_refs,
      merged_into_issue_ref=merged_into_issue_ref, field_values=field_values,
      is_deleted=issue.deleted, reporter_ref=reporter_ref,
      opened_timestamp=issue.opened_timestamp,
      closed_timestamp=issue.closed_timestamp,
      modified_timestamp=issue.modified_timestamp,
      star_count=issue.star_count, is_spam=issue.is_spam,
      attachment_count=issue.attachment_count)
  return result
