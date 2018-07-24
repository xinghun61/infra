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
from api.api_proto import features_objects_pb2
from api.api_proto import issue_objects_pb2
from api.api_proto import project_objects_pb2
from framework import exceptions
from framework import filecontent
from framework import framework_constants
from tracker import attachment_helpers
from tracker import field_helpers
from tracker import tracker_bizobj
from tracker import tracker_helpers
from proto import tracker_pb2


# Convert and ingest objects in issue_objects.proto.


def ConvertApprovalValues(approval_values, phases, users_by_id, config):
  """Convert a list of ApprovalValue into protoc Approvals."""
  phases_by_id = {
    phase.phase_id: phase
    for phase in phases}
  result = [
    ConvertApproval(
      av, users_by_id, config, phase=phases_by_id.get(av.phase_id))
    for av in approval_values]
  return result


def ConvertApproval(approval_value, users_by_id, config, phase=None):
  """Use the given ApprovalValue to create a protoc Approval."""
  approval_name = ''
  fd = tracker_bizobj.FindFieldDefByID(approval_value.approval_id, config)
  if fd:
    approval_name = fd.field_name

  field_ref = ConvertFieldRef(
      approval_name, tracker_pb2.FieldTypes.APPROVAL_TYPE, None)
  approver_refs = ConvertUserRefs(approval_value.approver_ids, [], users_by_id)
  setter_ref = ConvertUserRef(approval_value.setter_id, None, users_by_id)

  status = ConvertApprovalStatus(approval_value.status)
  set_on = approval_value.set_on

  phase_ref = issue_objects_pb2.PhaseRef()
  if phase:
    phase_ref.phase_name = phase.name

  result = issue_objects_pb2.Approval(
      field_ref=field_ref, approver_refs=approver_refs,
      status=status, set_on=set_on, setter_ref=setter_ref,
      phase_ref=phase_ref)
  return result


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


def ConvertApprovalStatus(status):
  """Use the given protorpc ApprovalStatus to create a protoc ApprovalStatus"""
  return issue_objects_pb2.ApprovalStatus.Value(status.name)


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


def ConvertFieldValue(field_name, value, field_type, approval_name=None,
                      phase_name=None, is_derived=False):
  """Convert one field value view item into a protoc FieldValue."""
  fv = issue_objects_pb2.FieldValue(
      field_ref=ConvertFieldRef(field_name, field_type, approval_name),
      value=str(value),
      is_derived=is_derived)
  if phase_name:
    fv.phase_ref.phase_name = phase_name

  return fv


def ConvertFieldType(field_type):
  """Use the given protorpc FieldTypes enum to create a protoc FieldType."""
  return common_pb2.FieldType.Value(field_type.name)


def ConvertFieldRef(field_name, field_type, approval_name):
  """Convert a field name and protorpc FieldType into a protoc FieldRef."""
  return common_pb2.FieldRef(field_name=field_name,
                             type=ConvertFieldType(field_type),
                             approval_name=approval_name)


def ConvertFieldValues(
    config, labels, derived_labels, field_values, users_by_id, phases=None):
  """Convert lists of labels and field_values to protoc FieldValues."""
  fvs = []
  phase_names_by_id = {phase.phase_id: phase.name for phase in phases or []}
  fds_by_id = {fd.field_id:fd for fd in config.field_defs}
  enum_names_by_lower = {
      fd.field_name.lower(): fd.field_name for fd in config.field_defs
      if fd.field_type == tracker_pb2.FieldTypes.ENUM_TYPE}

  labels_by_prefix = tracker_bizobj.LabelsByPrefix(
      labels, enum_names_by_lower.keys())
  der_labels_by_prefix = tracker_bizobj.LabelsByPrefix(
      derived_labels, enum_names_by_lower.keys())

  for lower_field_name, values in labels_by_prefix.iteritems():
    field_name = enum_names_by_lower.get(lower_field_name)
    if not field_name:
      continue
    fvs.extend(
        [ConvertFieldValue(
            field_name, value, tracker_pb2.FieldTypes.ENUM_TYPE) for
         value in values])

  for lower_field_name, values in der_labels_by_prefix.iteritems():
    field_name = enum_names_by_lower.get(lower_field_name)
    if not field_name:
      continue
    fvs.extend(
        [ConvertFieldValue(
            field_name, value, tracker_pb2.FieldTypes.ENUM_TYPE,
            is_derived=True) for value in values])

  for fv in field_values:
    value = tracker_bizobj.GetFieldValue(fv, users_by_id)
    field_def = fds_by_id.get(fv.field_id)
    field_name = ''
    field_type = None
    approval_name = None
    if field_def:
      field_name = field_def.field_name
      field_type = field_def.field_type
      if field_def.approval_id is not None:
        approval_def = fds_by_id.get(field_def.approval_id)
        if approval_def:
          approval_name = approval_def.field_name

    fvs.append(ConvertFieldValue(
        field_name, value, field_type, approval_name=approval_name,
        phase_name=phase_names_by_id.get(fv.phase_id), is_derived=fv.derived))

  return fvs


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

  field_values = ConvertFieldValues(
      config, issue.labels, issue.derived_labels,
      issue.field_values, users_by_id, phases=issue.phases)
  approval_values = ConvertApprovalValues(
      issue.approval_values, issue.phases, users_by_id, config)
  reporter_ref = ConvertUserRef(issue.reporter_id, None, users_by_id)
  phases = [ConvertPhaseDef(phase) for phase in issue.phases]
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
      attachment_count=issue.attachment_count,
      approval_values=approval_values, phases=phases)
  return result


def ConvertPhaseDef(phase):
  """Convert a protorpc Phase to a protoc PhaseDef."""
  phase_def = issue_objects_pb2.PhaseDef(
      phase_ref=issue_objects_pb2.PhaseRef(phase_name=phase.name),
      rank=phase.rank)
  return phase_def


def ConvertAmendment(amendment, users_by_id):
  """Convert a protorpc Amendment to a protoc Amendment."""
  field_name = tracker_bizobj.GetAmendmentFieldName(amendment)
  new_value = tracker_bizobj.AmendmentString(amendment, users_by_id)
  result = issue_objects_pb2.Amendment(
      field_name=field_name, new_or_delta_value=new_value,
      old_value=amendment.oldvalue)
  return result


def ConvertAttachment(attach, project_name):
  """Convert a protorpc Attachment to a protoc Attachment."""
  size, thumbnail_url, view_url, download_url = None, None, None, None
  if not attach.deleted:
    size = attach.filesize
    download_url = attachment_helpers.GetDownloadURL(attach.attachment_id)
    view_url = attachment_helpers.GetViewURL(attach, download_url, project_name)
    thumbnail_url = attachment_helpers.GetThumbnailURL(attach, download_url)

  result = issue_objects_pb2.Attachment(
      attachment_id=attach.attachment_id, filename=attach.filename,
      size=size, content_type=attach.mimetype,
      is_deleted=attach.deleted, thumbnail_url=thumbnail_url,
      view_url=view_url, download_url=download_url)
  return result


def ConvertComment(
    issue, comment, users_by_id, config, description_nums,
    logged_in_user_id):
  """Convert a protorpc IssueComment to a protoc Comment."""
  # TODO(jrobbins): Refactor these permission checks into WE.
  is_deleted = bool(comment.deleted_by or users_by_id[comment.user_id].banned)
  deletable_by_me = comment.user_id == logged_in_user_id  # TODO: CanDelete().
  is_viewable = not is_deleted or deletable_by_me
  inbound_message_visible = comment.user_id == logged_in_user_id

  # TODO(jrobbins): Tell client which comments the current user can delete.
  result = issue_objects_pb2.Comment(
      project_name=issue.project_name,
      local_id=issue.local_id,
      sequence_num=comment.sequence,
      is_deleted=is_deleted,
      timestamp=comment.timestamp,
      is_spam=comment.is_spam)

  if is_viewable:
    result.commenter.CopyFrom(
        ConvertUserRef(comment.user_id, None, users_by_id))
    result.content = comment.content
    if inbound_message_visible and comment.inbound_message:
      result.inbound_message = comment.inbound_message
    result.amendments.extend([
        ConvertAmendment(amend, users_by_id)
        for amend in comment.amendments])
    result.attachments.extend([
        ConvertAttachment(attach, issue.project_name)
        for attach in comment.attachments])
    if comment.id in description_nums:
      result.description_num = description_nums[comment.id]

  fd = tracker_bizobj.FindFieldDefByID(comment.approval_id, config)
  if fd:
    result.approval_ref.field_name = fd.field_name

  return result


def ConvertCommentList(issue, comments, users_by_id, config, logged_in_user_id):
  """Convert a list of protorpc IssueComments to protoc Comments."""
  description_nums = {}
  for comment in comments:
    if comment.is_description:
      description_nums[comment.id] = len(description_nums) + 1

  result = [
    ConvertComment(
        issue, c, users_by_id, config, description_nums,
        logged_in_user_id)
    for c in comments]
  return result


def IngestUserRefs(cnxn, user_refs, user_service, autocreate=False):
  """Return IDs of specified users or raise NoSuchUserException."""
  # 1. Verify that all specified user IDs actually match existing users.
  user_ids_to_verify = [user_ref.user_id for user_ref in user_refs
                        if user_ref.user_id]
  user_service.LookupUserEmails(cnxn, user_ids_to_verify)

  # 2. Lookup or create any users that are specified by email address.
  needed_emails = [user_ref.display_name for user_ref in user_refs
                   if not user_ref.user_id and user_ref.display_name]
  emails_to_ids = user_service.LookupUserIDs(
      cnxn, needed_emails, autocreate=autocreate)

  # 3. Build the result.
  # Note: user_id can be specified as 0 to clear the issue owner.
  result = [emails_to_ids.get(user_ref.display_name, user_ref.user_id)
            for user_ref in user_refs]
  return result


def IngestComponentRefs(comp_refs, config):
  """Return IDs of specified components or raise NoSuchComponentException."""
  cids_by_path = {cd.path.lower(): cd.component_id
                  for cd in config.component_defs}
  result = []
  for comp_ref in comp_refs:
    cid = cids_by_path.get(comp_ref.path.lower())
    if cid:
      result.append(cid)
    else:
      raise exceptions.NoSuchComponentException()
  return result


def IngestFieldRefs(field_refs, config):
  """Return IDs of specified fields or raise NoSuchFieldDefException."""
  fids_by_name = {fd.field_name.lower(): fd.field_id
                  for fd in config.field_defs}
  result = []
  for field_ref in field_refs:
    fid = fids_by_name.get(field_ref.field_name.lower())
    if fid:
      result.append(fid)
    else:
      raise exceptions.NoSuchFieldDefException()
  return result


def IngestIssueRefs(cnxn, issue_refs, services):
  """Look up issue IDs for the specified issues."""
  project_names = set(ref.project_name for ref in issue_refs)
  project_names_to_id = services.project.LookupProjectIDs(cnxn, project_names)
  project_local_id_pairs = []
  for ref in issue_refs:
    if ref.project_name in project_names_to_id:
      pair = (project_names_to_id[ref.project_name], ref.local_id)
      project_local_id_pairs.append(pair)
    else:
      raise exceptions.NoSuchProjectException()
  issue_ids, misses = services.issue.LookupIssueIDs(
      cnxn, project_local_id_pairs)
  if misses:
    raise exceptions.NoSuchIssueException()
  return issue_ids


def IngestIssueDelta(cnxn, services, delta, config, phases):
  """Ingest a protoc IssueDelta and create a protorpc IssueDelta."""
  status = None
  if delta.HasField('status'):
    status = delta.status.value
  owner_id = None
  if delta.HasField('owner_ref'):
    owner_id = IngestUserRefs(cnxn, [delta.owner_ref], services.user)[0]
  summary = None
  if delta.HasField('summary'):
    summary = delta.summary.value

  cc_ids_add = IngestUserRefs(
      cnxn, delta.cc_refs_add, services.user, autocreate=True)
  cc_ids_remove = IngestUserRefs(cnxn, delta.cc_refs_remove, services.user)

  comp_ids_add = IngestComponentRefs(delta.comp_refs_add, config)
  comp_ids_remove = IngestComponentRefs(delta.comp_refs_remove, config)

  labels_add = [lab_ref.label for lab_ref in delta.label_refs_add]
  labels_remove = [lab_ref.label for lab_ref in delta.label_refs_remove]

  field_vals_add = IngestFieldValues(
      cnxn, services.user, delta.field_vals_add, config, phases=phases)
  field_vals_remove = IngestFieldValues(
      cnxn, services.user, delta.field_vals_remove, config, phases=phases)
  fields_clear = IngestFieldRefs(delta.fields_clear, config)

  blocked_on_add = IngestIssueRefs(
      cnxn, delta.blocked_on_refs_add, services)
  blocked_on_remove = IngestIssueRefs(
      cnxn, delta.blocked_on_refs_remove, services)
  blocking_add = IngestIssueRefs(
      cnxn, delta.blocking_refs_add, services)
  blocking_remove = IngestIssueRefs(
      cnxn, delta.blocking_refs_remove, services)
  merged_into = None
  if delta.HasField('merged_into_ref'):
    merged_into = IngestIssueRefs(cnxn, [delta.merged_into_ref], services)[0]

  result = tracker_bizobj.MakeIssueDelta(
      status, owner_id, cc_ids_add, cc_ids_remove, comp_ids_add,
      comp_ids_remove, labels_add, labels_remove, field_vals_add,
      field_vals_remove, fields_clear, blocked_on_add, blocked_on_remove,
      blocking_add, blocking_remove, merged_into, summary)
  return result

def IngestAttachmentUploads(attachment_uploads):
  """Ingest protoc AttachmentUpload objects as tuples."""
  result = []
  for up in attachment_uploads:
    if not up.filename:
      raise exceptions.InputException('Missing attachment name')
    if not up.content:
      raise exceptions.InputException('Missing attachment content')
    mimetype = filecontent.GuessContentTypeFromFilename(up.filename)
    attachment_tuple = (up.filename, up.content, mimetype)
    result.append(attachment_tuple)
  return result


def IngestApprovalDelta(cnxn, user_service, approval_delta, setter_id, config):
  """Ingest a protoc ApprovalDelta and create a protorpc ApprovalDelta."""
  fids_by_name = {fd.field_name.lower(): fd.field_id for
                       fd in config.field_defs}

  approver_ids_add = IngestUserRefs(
      cnxn, approval_delta.approver_refs_add, user_service)
  approver_ids_remove = IngestUserRefs(
      cnxn, approval_delta.approver_refs_remove, user_service)
  sub_fvs_add = IngestFieldValues(
      cnxn, user_service, approval_delta.field_vals_add, config)
  sub_fvs_remove = IngestFieldValues(
      cnxn, user_service, approval_delta.field_vals_remove, config)
  sub_fields_clear = [fids_by_name.get(clear.field_name.lower()) for
                      clear in approval_delta.fields_clear
                      if clear.field_name.lower() in fids_by_name]

  # protoc ENUMs default to the zero value (in this case: NOT_SET).
  # NOT_SET should only be allowed when an issue is first created.
  # Once a user changes it to something else, no one should be allowed
  # to set it back.
  status = None
  if approval_delta.status != issue_objects_pb2.NOT_SET:
    status = IngestApprovalStatus(approval_delta.status)

  return tracker_bizobj.MakeApprovalDelta(
      status, setter_id, approver_ids_add, approver_ids_remove,
      sub_fvs_add, sub_fvs_remove, sub_fields_clear)


def IngestApprovalStatus(approval_status):
  """Ingest a protoc ApprovalStatus and create a protorpc ApprovalStatus. """
  if approval_status == issue_objects_pb2.NOT_SET:
    return tracker_pb2.ApprovalStatus.NOT_SET
  return tracker_pb2.ApprovalStatus(approval_status)


def IngestFieldValues(cnxn, user_service, field_values, config, phases=None):
  """Ingest a list of protoc FieldValues and create protorpc FieldValues.

  Args:
    cnxn: connection to the DB.
    user_service: interface to user data storage.
    field_values: a list of protoc FieldValue used by the API.
    config: ProjectIssueConfig for this field_value's project.
    phases: a list of the issue's protorpc Phases.


  Returns: A protorpc FieldValue object.
  """
  fds_by_name = {fd.field_name.lower(): fd for fd in config.field_defs}
  phases_by_name = {phase.name: phase.phase_id for phase in phases or []}

  ejected_fvs = []
  for fv in field_values:
    fd = fds_by_name.get(fv.field_ref.field_name.lower())
    if fd:
      ejected_fv = field_helpers.ParseOneFieldValue(
          cnxn, user_service, fd, str(fv.value))
      if fd.is_phase_field:
        ejected_fv.phase_id = phases_by_name.get(fv.phase_ref.phase_name)
      ejected_fvs.append(ejected_fv)

  return ejected_fvs


# Convert and ingest objects in project_objects.proto.

def ConvertStatusDef(status_def, rank):
  """Convert a protorpc StatusDef into a protoc StatusDef."""
  return project_objects_pb2.StatusDef(
      status=status_def.status,
      means_open=status_def.means_open,
      rank=rank,
      docstring=status_def.status_docstring,
      deprecated=status_def.deprecated)


def ConvertLabelDef(label_def, rank):
  """Convert a protorpc LabelDef into a protoc LabelDef."""
  return project_objects_pb2.LabelDef(
      label=label_def.label,
      rank=rank,
      docstring=label_def.label_docstring,
      deprecated=label_def.deprecated)


def ConvertComponentDef(component_def, users_by_id, labels_by_id):
  """Convert a protorpc ComponentDef into a protoc ComponentDef."""
  admin_refs = ConvertUserRefs(component_def.admin_ids, [], users_by_id)
  cc_refs = ConvertUserRefs(component_def.cc_ids, [], users_by_id)
  labels = [labels_by_id[lid] for lid in component_def.label_ids]
  label_refs = ConvertLabels(labels, [])
  creator_ref = ConvertUserRef(component_def.creator_id, None, users_by_id)
  modifier_ref = ConvertUserRef(component_def.modifier_id, None, users_by_id)
  return project_objects_pb2.ComponentDef(
      path=component_def.path,
      docstring=component_def.docstring,
      admin_refs=admin_refs,
      cc_refs=cc_refs,
      deprecated=component_def.deprecated,
      created=component_def.created,
      creator_ref=creator_ref,
      modified=component_def.modified,
      modifier_ref=modifier_ref,
      label_refs=label_refs)


def ConvertFieldDef(field_def, users_by_id, config):
  """Convert a protorpc FieldDef into a protoc FieldDef."""
  parent_approval_name = None
  if field_def.approval_id:
    parent_fd = tracker_bizobj.FindFieldDefByID(field_def.approval_id, config)
    parent_approval_name = parent_fd.field_name
  field_ref = ConvertFieldRef(
      field_def.field_name, field_def.field_type, parent_approval_name)
  admin_refs = ConvertUserRefs(field_def.admin_ids, [], users_by_id)
  # TODO(jrobbins): validation, permission granting, and notification options.

  return project_objects_pb2.FieldDef(
      field_ref=field_ref,
      applicable_type=field_def.applicable_type,
      is_required=field_def.is_required,
      is_niche=field_def.is_niche,
      is_multivalued=field_def.is_multivalued,
      docstring=field_def.docstring,
      admin_refs=admin_refs,
      is_phase_field=field_def.is_phase_field)


def ConvertApprovalDef(approval_def, users_by_id, config):
  """Convert a protorpc ApprovalDef into a protoc ApprovalDef."""
  field_def = tracker_bizobj.FindFieldDefByID(approval_def.approval_id, config)
  field_ref = ConvertFieldRef(field_def.field_name, field_def.field_type, None)
  approver_refs = ConvertUserRefs(approval_def.approver_ids, [], users_by_id)
  return project_objects_pb2.ApprovalDef(
      field_ref=field_ref,
      approver_refs=approver_refs,
      survey=approval_def.survey)


def ConvertConfig(project, config, users_by_id, labels_by_id):
  """Convert a protorpc ProjectIssueConfig into a protoc Config."""
  status_defs = [
      ConvertStatusDef(sd, rank)
      for rank, sd in enumerate(config.well_known_statuses)]
  label_defs = [
      ConvertLabelDef(ld, rank)
      for rank, ld in enumerate(config.well_known_labels)]
  component_defs = [
      ConvertComponentDef(cd, users_by_id, labels_by_id)
      for cd in config.component_defs]
  field_defs = [
      ConvertFieldDef(fd, users_by_id, config)
      for fd in config.field_defs]
  approval_defs = [
      ConvertApprovalDef(ad, users_by_id, config)
      for ad in config.approval_defs]
  result = project_objects_pb2.Config(
      project_name=project.project_name,
      status_defs=status_defs,
      label_defs=label_defs,
      exclusive_label_prefixes=config.exclusive_label_prefixes,
      component_defs=component_defs,
      field_defs=field_defs,
      approval_defs=approval_defs)
  return result


def ConvertHotlist(hotlist, users_by_id):
  """Convert a protoprc Hotlist into a protoc Hotlist."""
  owner_ref = ConvertUserRef(
      hotlist.owner_ids[0], None, users_by_id)
  result = features_objects_pb2.Hotlist(
      owner_ref=owner_ref,
      name=hotlist.name,
      summary=hotlist.summary,
      description=hotlist.description)
  return result
