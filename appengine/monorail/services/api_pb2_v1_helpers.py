# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Convert Monorail PB objects to API PB objects"""

import datetime
import logging
import time

from businesslogic import work_env
from framework import exceptions
from framework import framework_constants
from framework import framework_helpers
from framework import framework_views
from framework import permissions
from framework import timestr
from proto import api_pb2_v1
from proto import project_pb2
from proto import tracker_pb2
from services import issue_svc
from services import project_svc
from services import user_svc
from tracker import field_helpers
from tracker import tracker_bizobj
from tracker import tracker_helpers


def convert_project(project, config, role):
  """Convert Monorail Project PB to API ProjectWrapper PB."""

  return api_pb2_v1.ProjectWrapper(
      kind='monorail#project',
      name=project.project_name,
      externalId=project.project_name,
      htmlLink='/p/%s/' % project.project_name,
      summary=project.summary,
      description=project.description,
      role=role,
      issuesConfig=convert_project_config(config))


def convert_project_config(config):
  """Convert Monorail ProjectIssueConfig PB to API ProjectIssueConfig PB."""

  return api_pb2_v1.ProjectIssueConfig(
      kind='monorail#projectIssueConfig',
      restrictToKnown=config.restrict_to_known,
      defaultColumns=config.default_col_spec.split(),
      defaultSorting=config.default_sort_spec.split(),
      statuses=[convert_status(s) for s in config.well_known_statuses],
      labels=[convert_label(l) for l in config.well_known_labels],
      prompts=[convert_template(t) for t in config.templates],
      defaultPromptForMembers=config.default_template_for_developers,
      defaultPromptForNonMembers=config.default_template_for_users)


def convert_status(status):
  """Convert Monorail StatusDef PB to API Status PB."""

  return api_pb2_v1.Status(
      status=status.status,
      meansOpen=status.means_open,
      description=status.status_docstring)


def convert_label(label):
  """Convert Monorail LabelDef PB to API Label PB."""

  return api_pb2_v1.Label(
      label=label.label,
      description=label.label_docstring)


def convert_template(template):
  """Convert Monorail TemplateDef PB to API Prompt PB."""

  return api_pb2_v1.Prompt(
      name=template.name,
      title=template.summary,
      description=template.content,
      titleMustBeEdited=template.summary_must_be_edited,
      status=template.status,
      labels=template.labels,
      membersOnly=template.members_only,
      defaultToMember=template.owner_defaults_to_member,
      componentRequired=template.component_required)


def convert_person(user_id, cnxn, services, trap_exception=False):
  """Convert user id to API AtomPerson PB."""

  if not user_id:
    return None
  try:
    user = services.user.GetUser(cnxn, user_id)
  except user_svc.NoSuchUserException as ex:
    if trap_exception:
      logging.warning(str(ex))
      return None
    else:
      raise ex

  days_ago = None
  if user.last_visit_timestamp:
    secs_ago = int(time.time()) - user.last_visit_timestamp
    days_ago = secs_ago / framework_constants.SECS_PER_DAY
  return api_pb2_v1.AtomPerson(
      kind='monorail#issuePerson',
      name=user.email,
      htmlLink='https://%s/u/%d' % (framework_helpers.GetHostPort(), user_id),
      last_visit_days_ago=days_ago,
      email_bouncing=bool(user.email_bounce_timestamp),
      vacation_message=user.vacation_message)


def convert_issue_ids(issue_ids, mar, services):
  """Convert global issue ids to API IssueRef PB."""

  # missed issue ids are filtered out.
  issues = services.issue.GetIssues(mar.cnxn, issue_ids)
  result = []
  for issue in issues:
    issue_ref = api_pb2_v1.IssueRef(
      issueId=issue.local_id,
      projectId=issue.project_name,
      kind='monorail#issueRef')
    result.append(issue_ref)
  return result


def convert_issueref_pbs(issueref_pbs, mar, services):
  """Convert API IssueRef PBs to global issue ids."""

  if issueref_pbs:
    result = []
    for ir in issueref_pbs:
      project_id = mar.project_id
      if ir.projectId:
        project = services.project.GetProjectByName(
          mar.cnxn, ir.projectId)
        if project:
          project_id = project.project_id
      try:
        issue = services.issue.GetIssueByLocalID(
            mar.cnxn, project_id, ir.issueId)
        result.append(issue.issue_id)
      except issue_svc.NoSuchIssueException:
        logging.warning(
            'Issue (%s:%d) does not exist.' % (ir.projectId, ir.issueId))
    return result
  else:
    return None


def convert_issue(cls, issue, mar, services):
  """Convert Monorail Issue PB to API IssuesGetInsertResponse."""

  config = services.config.GetProjectConfig(mar.cnxn, issue.project_id)
  granted_perms = tracker_bizobj.GetGrantedPerms(
      issue, mar.auth.effective_ids, config)
  issue_project = services.project.GetProject(mar.cnxn, issue.project_id)
  component_list = []
  for cd in config.component_defs:
    cid = cd.component_id
    if cid in issue.component_ids:
      component_list.append(cd.path)
  cc_list = [convert_person(p, mar.cnxn, services) for p in issue.cc_ids]
  cc_list = [p for p in cc_list if p is not None]
  field_values_list = []
  field_id_dict = {
      fd.field_id: fd.field_name for fd in config.field_defs}
  for fv in issue.field_values:
    field_name = field_id_dict.get(fv.field_id)
    if not field_name:
      logging.warning('Custom field %d of project %s does not exist',
                      fv.field_id, issue_project.project_name)
      continue
    val = None
    if fv.user_id:
      val = _get_user_email(
          services.user, mar.cnxn, fv.user_id)
    else:
      val = str(tracker_bizobj.GetFieldValue(fv, {}))
    new_fv = api_pb2_v1.FieldValue(
        fieldName=field_name,
        fieldValue=val,
        derived=fv.derived)
    field_values_list.append(new_fv)
  with work_env.WorkEnv(mar, services) as we:
    starred = we.IsIssueStarred(issue)
  resp = cls(
      kind='monorail#issue',
      id=issue.local_id,
      title=issue.summary,
      summary=issue.summary,
      projectId=issue_project.project_name,
      stars=issue.star_count,
      starred=starred,
      status=issue.status,
      state=(api_pb2_v1.IssueState.open if
             tracker_helpers.MeansOpenInProject(
                 tracker_bizobj.GetStatus(issue), config)
             else api_pb2_v1.IssueState.closed),
      labels=issue.labels,
      components=component_list,
      author=convert_person(issue.reporter_id, mar.cnxn, services),
      owner=convert_person(issue.owner_id, mar.cnxn, services),
      cc=cc_list,
      updated=datetime.datetime.fromtimestamp(issue.modified_timestamp),
      published=datetime.datetime.fromtimestamp(issue.opened_timestamp),
      blockedOn=convert_issue_ids(issue.blocked_on_iids, mar, services),
      blocking=convert_issue_ids(issue.blocking_iids, mar, services),
      canComment=permissions.CanCommentIssue(
          mar.auth.effective_ids, mar.perms, issue_project, issue,
          granted_perms=granted_perms),
      canEdit=permissions.CanEditIssue(
          mar.auth.effective_ids, mar.perms, issue_project, issue,
          granted_perms=granted_perms),
      fieldValues=field_values_list)
  if issue.closed_timestamp > 0:
    resp.closed = datetime.datetime.fromtimestamp(issue.closed_timestamp)
  if issue.merged_into:
    resp.mergedInto=convert_issue_ids([issue.merged_into], mar, services)[0]
  if issue.owner_modified_timestamp:
    resp.owner_modified = datetime.datetime.fromtimestamp(
        issue.owner_modified_timestamp)
  if issue.status_modified_timestamp:
    resp.status_modified = datetime.datetime.fromtimestamp(
        issue.status_modified_timestamp)
  if issue.component_modified_timestamp:
    resp.component_modified = datetime.datetime.fromtimestamp(
        issue.component_modified_timestamp)
  return resp


def convert_comment(issue, comment, mar, services, granted_perms):
  """Convert Monorail IssueComment PB to API IssueCommentWrapper."""

  can_delete = permissions.CanDelete(
      mar.auth.user_id, mar.auth.effective_ids, mar.perms,
      comment.deleted_by, comment.user_id, mar.project,
      permissions.GetRestrictions(issue), granted_perms=granted_perms)

  return api_pb2_v1.IssueCommentWrapper(
      attachments=[convert_attachment(a) for a in comment.attachments],
      author=convert_person(comment.user_id, mar.cnxn, services,
                            trap_exception=True),
      canDelete=can_delete,
      content=comment.content,
      deletedBy=convert_person(comment.deleted_by, mar.cnxn, services,
                               trap_exception=True),
      id=comment.sequence,
      published=datetime.datetime.fromtimestamp(comment.timestamp),
      updates=convert_amendments(issue, comment.amendments, mar, services),
      kind='monorail#issueComment',
      is_description=comment.is_description)


def convert_attachment(attachment):
  """Convert Monorail Attachment PB to API Attachment."""

  return api_pb2_v1.Attachment(
      attachmentId=attachment.attachment_id,
      fileName=attachment.filename,
      fileSize=attachment.filesize,
      mimetype=attachment.mimetype,
      isDeleted=attachment.deleted)


def convert_amendments(issue, amendments, mar, services):
  """Convert a list of Monorail Amendment PBs to API Update."""
  amendments_user_ids = tracker_bizobj.UsersInvolvedInAmendments(amendments)
  users_by_id = framework_views.MakeAllUserViews(
      mar.cnxn, services.user, amendments_user_ids)
  framework_views.RevealAllEmailsToMembers(mar, users_by_id)

  result = api_pb2_v1.Update(kind='monorail#issueCommentUpdate')
  for amendment in amendments:
    if amendment.field == tracker_pb2.FieldID.SUMMARY:
      result.summary = amendment.newvalue
    elif amendment.field == tracker_pb2.FieldID.STATUS:
      result.status = amendment.newvalue
    elif amendment.field == tracker_pb2.FieldID.OWNER:
      if len(amendment.added_user_ids) == 0:
        result.owner = framework_constants.NO_USER_NAME
      else:
        result.owner = _get_user_email(
            services.user, mar.cnxn, amendment.added_user_ids[0])
    elif amendment.field == tracker_pb2.FieldID.LABELS:
      result.labels = amendment.newvalue.split()
    elif amendment.field == tracker_pb2.FieldID.CC:
      for user_id in amendment.added_user_ids:
        user_email = _get_user_email(
            services.user, mar.cnxn, user_id)
        result.cc.append(user_email)
      for user_id in amendment.removed_user_ids:
        user_email = _get_user_email(
            services.user, mar.cnxn, user_id)
        result.cc.append('-%s' % user_email)
    elif amendment.field == tracker_pb2.FieldID.BLOCKEDON:
      result.blockedOn = _append_project(
          amendment.newvalue, issue.project_name)
    elif amendment.field == tracker_pb2.FieldID.BLOCKING:
      result.blocking = _append_project(
          amendment.newvalue, issue.project_name)
    elif amendment.field == tracker_pb2.FieldID.MERGEDINTO:
      result.mergedInto = amendment.newvalue
    elif amendment.field == tracker_pb2.FieldID.COMPONENTS:
      result.components = amendment.newvalue.split()
    elif amendment.field == tracker_pb2.FieldID.CUSTOM:
      fv = api_pb2_v1.FieldValue()
      fv.fieldName = amendment.custom_field_name
      fv.fieldValue = tracker_bizobj.AmendmentString(amendment, users_by_id)
      result.fieldValues.append(fv)

  return result


def _get_user_email(user_service, cnxn, user_id):
  """Get user email."""

  try:
    user_email = user_service.LookupUserEmail(
            cnxn, user_id)
    if not user_email:
      user_email = framework_constants.DELETED_USER_NAME
  except user_svc.NoSuchUserException:
    user_email = framework_constants.DELETED_USER_NAME
  return user_email


def _append_project(issue_ids, project_name):
  """Append project name to convert <id> to <project>:<id> format."""

  result = []
  id_list = issue_ids.split()
  for id_str in id_list:
    if ':' in id_str:
      result.append(id_str)
    # '-' means this issue is being removed
    elif id_str.startswith('-'):
      result.append('-%s:%s' % (project_name, id_str[1:]))
    else:
      result.append('%s:%s' % (project_name, id_str))
  return result


def split_remove_add(item_list):
  """Split one list of items into two: items to add and items to remove."""

  list_to_add = []
  list_to_remove = []

  for item in item_list:
    if item.startswith('-'):
      list_to_remove.append(item[1:])
    else:
      list_to_add.append(item)

  return list_to_add, list_to_remove


# TODO(sheyang): batch the SQL queries to fetch projects/issues.
def issue_global_ids(project_local_id_pairs, project_id, mar, services):
  """Find global issues ids given <project_name>:<issue_local_id> pairs."""

  result = []
  for pair in project_local_id_pairs:
    issue_project_id = None
    local_id = None
    if ':' in pair:
      pair_ary = pair.split(':')
      project_name = pair_ary[0]
      local_id = int(pair_ary[1])
      project = services.project.GetProjectByName(mar.cnxn, project_name)
      if not project:
        raise exceptions.NoSuchProjectException(
            'Project %s does not exist' % project_name)
      issue_project_id = project.project_id
    else:
      issue_project_id = project_id
      local_id = int(pair)
    result.append(
        services.issue.LookupIssueID(mar.cnxn, issue_project_id, local_id))

  return result


def convert_group_settings(group_name, setting):
  """Convert UserGroupSettings to UserGroupSettingsWrapper."""
  return api_pb2_v1.UserGroupSettingsWrapper(
      groupName=group_name,
      who_can_view_members=setting.who_can_view_members,
      ext_group_type=setting.ext_group_type,
      last_sync_time=setting.last_sync_time)


def convert_component_def(cd, mar, services):
  """Convert ComponentDef PB to Component PB."""
  project_name = services.project.LookupProjectNames(
      mar.cnxn, [cd.project_id])[cd.project_id]
  user_ids = set()
  user_ids.update(
      cd.admin_ids + cd.cc_ids + [cd.creator_id] + [cd.modifier_id])
  user_names_dict = services.user.LookupUserEmails(mar.cnxn, list(user_ids))
  component = api_pb2_v1.Component(
      componentId=cd.component_id,
      projectName=project_name,
      componentPath=cd.path,
      description=cd.docstring,
      admin=sorted([user_names_dict[uid] for uid in cd.admin_ids]),
      cc=sorted([user_names_dict[uid] for uid in cd.cc_ids]),
      deprecated=cd.deprecated)
  if cd.created:
    component.created = datetime.datetime.fromtimestamp(cd.created)
    component.creator = user_names_dict[cd.creator_id]
  if cd.modified:
    component.modified = datetime.datetime.fromtimestamp(cd.modified)
    component.modifier = user_names_dict[cd.modifier_id]
  return component


def convert_component_ids(config, component_names):
  """Convert a list of component names to ids."""
  component_names_lower = [name.lower() for name in component_names]
  result = []
  for cd in config.component_defs:
    cpath = cd.path
    if cpath.lower() in component_names_lower:
      result.append(cd.component_id)
  return result


def convert_field_values(field_values, mar, services):
  """Convert user passed in field value list to FieldValue PB, or labels."""
  fv_list_add = []
  fv_list_remove = []
  fv_list_clear = []
  label_list_add = []
  label_list_remove = []
  field_name_dict = {
      fd.field_name: fd for fd in mar.config.field_defs}

  for fv in field_values:
    field_def = field_name_dict.get(fv.fieldName)
    if not field_def:
      logging.warning('Custom field %s of does not exist', fv.fieldName)
      continue

    if fv.operator == api_pb2_v1.FieldValueOperator.clear:
      fv_list_clear.append(field_def.field_id)
      continue

    # Enum fields are stored as labels
    if field_def.field_type == tracker_pb2.FieldTypes.ENUM_TYPE:
      raw_val = '%s-%s' % (fv.fieldName, fv.fieldValue)
      if fv.operator == api_pb2_v1.FieldValueOperator.remove:
        label_list_remove.append(raw_val)
      elif fv.operator == api_pb2_v1.FieldValueOperator.add:
        label_list_add.append(raw_val)
      else:  # pragma: no cover
        logging.warning('Unsupported field value operater %s', fv.operator)
    else:
      new_fv = field_helpers.ParseOneFieldValue(
          mar.cnxn, services.user, field_def, fv.fieldValue)
      if fv.operator == api_pb2_v1.FieldValueOperator.remove:
        fv_list_remove.append(new_fv)
      elif fv.operator == api_pb2_v1.FieldValueOperator.add:
        fv_list_add.append(new_fv)
      else:  # pragma: no cover
        logging.warning('Unsupported field value operater %s', fv.operator)

  return (fv_list_add, fv_list_remove, fv_list_clear,
          label_list_add, label_list_remove)
