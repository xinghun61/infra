# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""The TemplateService class providing methods for template persistence."""

import collections
import logging

import settings

from framework import exceptions
from framework import sql
from proto import tracker_pb2
from services import caches
from services import project_svc
from tracker import tracker_bizobj
from tracker import tracker_constants


TEMPLATE_COLS = [
    'id', 'project_id', 'name', 'content', 'summary', 'summary_must_be_edited',
    'owner_id', 'status', 'members_only', 'owner_defaults_to_member',
    'component_required']
TEMPLATE2LABEL_COLS = ['template_id', 'label']
TEMPLATE2COMPONENT_COLS = ['template_id', 'component_id']
TEMPLATE2ADMIN_COLS = ['template_id', 'admin_id']
TEMPLATE2FIELDVALUE_COLS = [
    'template_id', 'field_id', 'int_value', 'str_value', 'user_id',
    'date_value', 'url_value']
ISSUEPHASEDEF_COLS = ['id', 'name', 'rank']
TEMPLATE2APPROVALVALUE_COLS = [
    'approval_id', 'template_id', 'phase_id', 'status']


TEMPLATE_TABLE_NAME = 'Template'
TEMPLATE2LABEL_TABLE_NAME = 'Template2Label'
TEMPLATE2ADMIN_TABLE_NAME = 'Template2Admin'
TEMPLATE2COMPONENT_TABLE_NAME = 'Template2Component'
TEMPLATE2FIELDVALUE_TABLE_NAME = 'Template2FieldValue'
ISSUEPHASEDEF_TABLE_NAME = 'IssuePhaseDef'
TEMPLATE2APPROVALVALUE_TABLE_NAME = 'Template2ApprovalValue'


class TemplateTwoLevelCache(caches.AbstractTwoLevelCache):
  """Class to manage RAM and memcache for templates.

  Holds a dictionary of {project_id: templateset} key value pairs,
  where a templateset is a list of all templates in a project.
  """

  def __init__(self, cache_manager, template_service):
    super(TemplateTwoLevelCache, self).__init__(
        cache_manager, 'project', memcache_prefix='templatesetprotos:',
        pb_class=tracker_pb2.TemplateSet)
    self.template_service = template_service

  def _MakeCache(self, cache_manager, kind, max_size=None):
    """Make the RAM cache and register it with the cache_manager."""
    return caches.RamCache(cache_manager, kind, max_size=max_size)

  def FetchItems(self, cnxn, keys):
    """On RAM and memcache miss, hit the database."""
    project_templates_dict = {}
    for key in keys:
      project_templates_dict.setdefault(key, [])

    # Fetch template rows and relations.
    for project_id in keys:
      template_rows = self.template_service.template_tbl.Select(
          cnxn, cols=TEMPLATE_COLS, project_id=project_id,
          order_by=[('name', [])])
      template_ids = [row[0] for row in template_rows]
      template2label_rows = self.template_service.\
          template2label_tbl.Select(
              cnxn, cols=TEMPLATE2LABEL_COLS, template_id=template_ids)
      template2component_rows = self.template_service.\
          template2component_tbl.Select(
              cnxn, cols=TEMPLATE2COMPONENT_COLS, template_id=template_ids)
      template2admin_rows = self.template_service.template2admin_tbl.Select(
          cnxn, cols=TEMPLATE2ADMIN_COLS, template_id=template_ids)
      template2fieldvalue_rows = self.template_service.\
          template2fieldvalue_tbl.Select(
              cnxn, cols=TEMPLATE2FIELDVALUE_COLS, template_id=template_ids)
      template2approvalvalue_rows = self.template_service.\
          template2approvalvalue_tbl.Select(
              cnxn, cols=TEMPLATE2APPROVALVALUE_COLS, template_id=template_ids)
      phase_ids = [av_row[2] for av_row in template2approvalvalue_rows]
      phase_rows = self.template_service.issuephasedef_tbl.Select(
          cnxn, cols=ISSUEPHASEDEF_COLS, id=list(set(phase_ids)))

      # Build TemplateDef with all related data.
      template_dict = {}
      for template_row in template_rows:
        template = UnpackTemplate(template_row)
        template_dict[template.template_id] = template

      for template2label_row in template2label_rows:
        template_id, label = template2label_row
        template = template_dict.get(template_id)
        if template:
          template.labels.append(label)

      for template2component_row in template2component_rows:
        template_id, component_id = template2component_row
        template = template_dict.get(template_id)
        if template:
          template.component_ids.append(component_id)

      for template2admin_row in template2admin_rows:
        template_id, admin_id = template2admin_row
        template = template_dict.get(template_id)
        if template:
          template.admin_ids.append(admin_id)

      for fv_row in template2fieldvalue_rows:
        (template_id, field_id, int_value, str_value, user_id,
         date_value, url_value) = fv_row
        fv = tracker_bizobj.MakeFieldValue(
            field_id, int_value, str_value, user_id, date_value, url_value,
            False)
        template = template_dict.get(template_id)
        if template:
          template.field_values.append(fv)

      phases_by_id = {}
      for phase_row in phase_rows:
        (phase_id, name, rank) = phase_row
        phase = tracker_pb2.Phase(
            phase_id=phase_id, name=name, rank=rank)
        phases_by_id[phase_id] = phase

      # Note: there is no templateapproval2approver_tbl.
      for av_row in template2approvalvalue_rows:
        (approval_id, template_id, phase_id, status) = av_row
        approval_value = tracker_pb2.ApprovalValue(
            approval_id=approval_id, phase_id=phase_id,
            status=tracker_pb2.ApprovalStatus(status.upper()))
        template = template_dict.get(template_id)
        if template:
          template.approval_values.append(approval_value)
          phase = phases_by_id.get(phase_id)
          if phase and phase not in template.phases:
            template_dict.get(template_id).phases.append(phase)

      project_templates_dict[project_id] = tracker_pb2.TemplateSet(
          templates=template_dict.values())

    return project_templates_dict


class TemplateService(object):

  def __init__(self, cache_manager):
    self.template_tbl = sql.SQLTableManager(TEMPLATE_TABLE_NAME)
    self.template2label_tbl = sql.SQLTableManager(TEMPLATE2LABEL_TABLE_NAME)
    self.template2component_tbl = sql.SQLTableManager(
        TEMPLATE2COMPONENT_TABLE_NAME)
    self.template2admin_tbl = sql.SQLTableManager(TEMPLATE2ADMIN_TABLE_NAME)
    self.template2fieldvalue_tbl = sql.SQLTableManager(
        TEMPLATE2FIELDVALUE_TABLE_NAME)
    self.issuephasedef_tbl = sql.SQLTableManager(
        ISSUEPHASEDEF_TABLE_NAME)
    self.template2approvalvalue_tbl = sql.SQLTableManager(
        TEMPLATE2APPROVALVALUE_TABLE_NAME)

    self.template_2lc = TemplateTwoLevelCache(cache_manager, self)

  def CreateDefaultProjectTemplates(self, cnxn, project_id):
    """Create the default templates for a project.

    Used only when creating a new project.

    Args:
      cnxn: A MonorailConnection instance.
      project_id: The project ID under which to create the templates.
    """
    for tpl in tracker_constants.DEFAULT_TEMPLATES:
      tpl = tracker_bizobj.ConvertDictToTemplate(tpl)
      self.CreateIssueTemplateDef(cnxn, project_id, tpl.name, tpl.content,
          tpl.summary, tpl.summary_must_be_edited, tpl.status, tpl.members_only,
          tpl.owner_defaults_to_member, tpl.component_required, tpl.owner_id,
          tpl.labels, tpl.component_ids, tpl.admin_ids, tpl.field_values,
          tpl.phases)

  def GetProjectTemplates(self, cnxn, project_id):
    """Gets all templates in a given project.

    Args:
      cnxn: A MonorailConnection instance.
      project_id: All templates for this project will be returned.

    Returns:
      A list of TemplateDefs.
    """
    result_dict, _ = self.template_2lc.GetAll(cnxn, [project_id])
    return result_dict[project_id]

  def TemplatesWithComponent(self, cnxn, component_id, config):
    """Returns all templates with the specified component.

    Args:
      cnxn: connection to SQL database.
      component_id: int component id.
      config: ProjectIssueConfig instance.

    Returns:
      A list of TemplateDefs.
    """
    template2component_rows = self.template2component_tbl.Select(
        cnxn, cols=['template_id'], component_id=component_id)
    template_ids = [r[0] for r in template2component_rows]

    # TODO(jeffcarp): Rewrite this method to join on project_id.
    template_set = self.GetProjectTemplates(cnxn, config.project_id)
    return [t for t in template_set.templates if t.template_id in template_ids]

  def CreateIssueTemplateDef(
      self, cnxn, project_id, name, content, summary, summary_must_be_edited,
      status, members_only, owner_defaults_to_member, component_required,
      owner_id=None, labels=None, component_ids=None, admin_ids=None,
      field_values=None, phases=None, approval_values=None):
    """Create a new issue template definition with the given info.

    Args:
      cnxn: connection to SQL database.
      project_id: int ID of the current project.
      name: name of the new issue template.
      content: string content of the issue template.
      summary: string summary of the issue template.
      summary_must_be_edited: True if the summary must be edited when this
          issue template is used to make a new issue.
      status: string default status of a new issue created with this template.
      members_only: True if only members can view this issue template.
      owner_defaults_to_member: True is issue owner should be set to member
          creating the issue.
      component_required: True if a component is required.
      owner_id: user_id of default owner, if any.
      labels: list of string labels for the new issue, if any.
      component_ids: list of component_ids, if any.
      admin_ids: list of admin_ids, if any.
      field_values: list of FieldValue PBs, if any.
      phases: list of Phase PBs, if any.
      approval_values: list of ApprovalValue PBs, if any.

    Returns:
      Integer template_id of the new issue template definition.
    """
    template_id = self.template_tbl.InsertRow(
        cnxn, project_id=project_id, name=name, content=content,
        summary=summary, summary_must_be_edited=summary_must_be_edited,
        owner_id=owner_id, status=status, members_only=members_only,
        owner_defaults_to_member=owner_defaults_to_member,
        component_required=component_required, commit=False)

    if labels:
      self.template2label_tbl.InsertRows(
          cnxn, TEMPLATE2LABEL_COLS, [(template_id, label) for label in labels],
          commit=False)
    if component_ids:
      self.template2component_tbl.InsertRows(
          cnxn, TEMPLATE2COMPONENT_COLS, [(template_id, c_id) for
                                          c_id in component_ids], commit=False)
    if admin_ids:
      self.template2admin_tbl.InsertRows(
          cnxn, TEMPLATE2ADMIN_COLS, [(template_id, admin_id) for
                                      admin_id in admin_ids], commit=False)
    if field_values:
      self.template2fieldvalue_tbl.InsertRows(
          cnxn, TEMPLATE2FIELDVALUE_COLS, [
              (template_id, fv.field_id, fv.int_value, fv.str_value, fv.user_id,
               fv.date_value, fv.url_value) for fv in field_values],
          commit=False)

    # current phase_ids in approval_values and phases are temporary and were
    # assigned based on the order of the phases. These temporary phase_ids are
    # used to keep track of which approvals belong to which phases and are
    # updated once all phases have their real phase_ids returned from InsertRow.
    phase_id_by_tmp = {}
    if phases:
      for phase in phases:
        phase_id = self.issuephasedef_tbl.InsertRow(
            cnxn, name=phase.name, rank=phase.rank, commit=False)
        phase_id_by_tmp[phase.phase_id] = phase_id

    if approval_values:
      self.template2approvalvalue_tbl.InsertRows(
          cnxn, TEMPLATE2APPROVALVALUE_COLS,
          [(av.approval_id, template_id,
            phase_id_by_tmp.get(av.phase_id), av.status.name.lower())
           for av in approval_values],
          commit=False)

    cnxn.Commit()
    self.template_2lc.InvalidateKeys(cnxn, [project_id])
    return template_id

  def UpdateIssueTemplateDef(
      self, cnxn, project_id, template_id, name=None, content=None,
      summary=None, summary_must_be_edited=None, status=None, members_only=None,
      owner_defaults_to_member=None, component_required=None, owner_id=None,
      labels=None, component_ids=None, admin_ids=None, field_values=None,
      phases=None, approval_values=None):
    """Update an existing issue template definition with the given info.

    Args:
      cnxn: connection to SQL database.
      project_id: int ID of the current project.
      template_id: int ID of the issue template to update.
      name: updated name of the new issue template.
      content: updated string content of the issue template.
      summary: updated string summary of the issue template.
      summary_must_be_edited: True if the summary must be edited when this
          issue template is used to make a new issue.
      status: updated string default status of a new issue created with this
          template.
      members_only: True if only members can view this issue template.
      owner_defaults_to_member: True is issue owner should be set to member
          creating the issue.
      component_required: True if a component is required.
      owner_id: updated user_id of default owner, if any.
      labels: updated list of string labels for the new issue, if any.
      component_ids: updated list of component_ids, if any.
      admin_ids: updated list of admin_ids, if any.
      field_values: updated list of FieldValue PBs, if any.
      phases: updated list of Phase PBs, if any.
      approval_values: updated list of ApprovalValue PBs, if any.
    """
    new_values = {}
    if name is not None:
      new_values['name'] = name
    if content is not None:
      new_values['content'] = content
    if summary is not None:
      new_values['summary'] = summary
    if summary_must_be_edited is not None:
      new_values['summary_must_be_edited'] = bool(summary_must_be_edited)
    if status is not None:
      new_values['status'] = status
    if members_only is not None:
      new_values['members_only'] = bool(members_only)
    if owner_defaults_to_member is not None:
      new_values['owner_defaults_to_member'] = bool(owner_defaults_to_member)
    if component_required is not None:
      new_values['component_required'] = bool(component_required)
    if owner_id is not None:
      new_values['owner_id'] = owner_id

    self.template_tbl.Update(cnxn, new_values, id=template_id, commit=False)

    if labels is not None:
      self.template2label_tbl.Delete(
          cnxn, template_id=template_id, commit=False)
      self.template2label_tbl.InsertRows(
          cnxn, TEMPLATE2LABEL_COLS, [(template_id, label) for label in labels],
          commit=False)
    if component_ids is not None:
      self.template2component_tbl.Delete(
          cnxn, template_id=template_id, commit=False)
      self.template2component_tbl.InsertRows(
          cnxn, TEMPLATE2COMPONENT_COLS, [(template_id, c_id) for
                                          c_id in component_ids],
          commit=False)
    if admin_ids is not None:
      self.template2admin_tbl.Delete(
          cnxn, template_id=template_id, commit=False)
      self.template2admin_tbl.InsertRows(
          cnxn, TEMPLATE2ADMIN_COLS, [(template_id, admin_id) for
                                      admin_id in admin_ids],
          commit=False)
    if field_values is not None:
      self.template2fieldvalue_tbl.Delete(
          cnxn, template_id=template_id, commit=False)
      self.template2fieldvalue_tbl.InsertRows(
          cnxn, TEMPLATE2FIELDVALUE_COLS, [
              (template_id, fv.field_id, fv.int_value, fv.str_value, fv.user_id,
               fv.date_value, fv.url_value) for fv in field_values],
          commit=False)

    phase_id_by_tmp = {}
    # TODO(jojwang): monorail:3756, when approval_values are separated from
    # phases, we need to keep track of tmp phase_ids created at the servlet.
    if phases is not None:
      self.template2approvalvalue_tbl.Delete(
          cnxn, template_id=template_id, commit=False)
      for phase in phases:
        phase_id = self.issuephasedef_tbl.InsertRow(
            cnxn, name=phase.name, rank=phase.rank, commit=False)
        phase_id_by_tmp[phase.phase_id] = phase_id

      self.template2approvalvalue_tbl.InsertRows(
          cnxn, TEMPLATE2APPROVALVALUE_COLS,
          [(av.approval_id, template_id,
            phase_id_by_tmp.get(av.phase_id), av.status.name.lower())
           for av in approval_values], commit=False)

    cnxn.Commit()
    self.template_2lc.InvalidateKeys(cnxn, [project_id])

  def DeleteIssueTemplateDef(self, cnxn, project_id, template_id):
    """Delete the specified issue template definition."""
    # TODO(jojwang): monorail:3241, soft delete may be required for launch
    # process templates
    self.template2label_tbl.Delete(cnxn, template_id=template_id, commit=False)
    self.template2component_tbl.Delete(
        cnxn, template_id=template_id, commit=False)
    self.template2admin_tbl.Delete(cnxn, template_id=template_id, commit=False)
    self.template2fieldvalue_tbl.Delete(
        cnxn, template_id=template_id, commit=False)
    self.template2approvalvalue_tbl.Delete(
        cnxn, template_id=template_id, commit=False)
    # We do not delete issuephasedef rows becuase these rows will be used by
    # issues that were created with this template. template2approvalvalue rows
    # can be deleted becuase those rows are copied over to issue2approvalvalue
    # during issue creation.
    self.template_tbl.Delete(cnxn, id=template_id, commit=False)

    cnxn.Commit()
    self.template_2lc.InvalidateKeys(cnxn, [project_id])

  def ExpungeProjectTemplates(self, cnxn, project_id):
    template_id_rows = self.template_tbl.Select(
        cnxn, cols=['id'], project_id=project_id)
    template_ids = [row[0] for row in template_id_rows]
    self.template2label_tbl.Delete(cnxn, template_id=template_ids)
    self.template2component_tbl.Delete(cnxn, template_id=template_ids)
    # TODO(3816): Delete all other relations here.
    self.template_tbl.Delete(cnxn, project_id=project_id)


def UnpackTemplate(template_row):
  """Partially construct a template object using info from a DB row."""
  (template_id, _project_id, name, content, summary,
   summary_must_be_edited, owner_id, status,
   members_only, owner_defaults_to_member, component_required) = template_row
  template = tracker_pb2.TemplateDef()
  template.template_id = template_id
  template.name = name
  template.content = content
  template.summary = summary
  template.summary_must_be_edited = bool(
      summary_must_be_edited)
  template.owner_id = owner_id or 0
  template.status = status
  template.members_only = bool(members_only)
  template.owner_defaults_to_member = bool(owner_defaults_to_member)
  template.component_required = bool(component_required)

  return template
