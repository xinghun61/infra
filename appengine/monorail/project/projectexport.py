# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Servlet to export a project's config in JSON format.
"""

import logging
import time

from third_party import ezt

from framework import permissions
from framework import jsonfeed
from framework import servlet
from project import project_helpers
from tracker import tracker_bizobj


class ProjectExport(servlet.Servlet):
  """Only site admins can export a project"""

  _PAGE_TEMPLATE = 'project/project-export-page.ezt'
  _MAIN_TAB_MODE = servlet.Servlet.MAIN_TAB_ADMIN

  def AssertBasePermission(self, mr):
    """Make sure that the logged in user has permission to view this page."""
    super(ProjectExport, self).AssertBasePermission(mr)
    if not mr.auth.user_pb.is_site_admin:
      raise permissions.PermissionException(
          'Only site admins may export project configuration')

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page."""

    return {
        'admin_tab_mode': None,
        'page_perms': self.MakePagePerms(mr, None, permissions.CREATE_ISSUE),
    }


class ProjectExportJSON(jsonfeed.JsonFeed):
  """ProjectExportJSON shows all configuration for a Project in JSON form."""

  # Pretty-print the JSON output.
  JSON_INDENT = 4

  def AssertBasePermission(self, mr):
    """Make sure that the logged in user has permission to view this page."""
    super(ProjectExportJSON, self).AssertBasePermission(mr)
    if not mr.auth.user_pb.is_site_admin:
      raise permissions.PermissionException(
          'Only site admins may export project configuration')

  def HandleRequest(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """
    project = self.services.project.GetProject(mr.cnxn, mr.project.project_id)
    user_id_set = project_helpers.UsersInvolvedInProject(project)

    config = self.services.config.GetProjectConfig(
        mr.cnxn, mr.project.project_id)
    template_set = self.services.template.GetProjectTemplates(
        mr.cnxn, config.project_id)
    involved_users = self.services.config.UsersInvolvedInConfig(
        config, template_set.templates)
    user_id_set.update(involved_users)

    # The value 0 indicates "no user", e.g., that an issue has no owner.
    # We don't need to create a User row to represent that.
    user_id_set.discard(0)
    email_dict = self.services.user.LookupUserEmails(mr.cnxn, user_id_set)

    project_json = self._MakeProjectJSON(project, email_dict)
    config_json = self._MakeConfigJSON(config, email_dict,
        template_set.templates)

    json_data = {
        'metadata': {
            'version': 1,
            'when': int(time.time()),
            'who': mr.auth.email,
        },
        'project': project_json,
        'config': config_json,
        # This list could be derived from the others, but we provide it for
        # ease of processing.
        'emails': email_dict.values(),
    }
    return json_data

  def _MakeProjectJSON(self, project, email_dict):
    project_json = {
      'name': project.project_name,
      'summary': project.summary,
      'description': project.description,
      'state': project.state.name,
      'access': project.access.name,
      'owners': [email_dict.get(user) for user in project.owner_ids],
      'committers': [email_dict.get(user) for user in project.committer_ids],
      'contributors': [
          email_dict.get(user) for user in project.contributor_ids],
      'perms': [self._MakePermJSON(perm, email_dict)
                for perm in project.extra_perms],
      'issue_notify_address': project.issue_notify_address,
      'attachment_bytes': project.attachment_bytes_used,
      'attachment_quota': project.attachment_quota,
      'recent_activity': project.recent_activity,
      'process_inbound_email': project.process_inbound_email,
      'only_owners_remove_restrictions':
          project.only_owners_remove_restrictions,
      'only_owners_see_contributors': project.only_owners_see_contributors,
      'revision_url_format': project.revision_url_format,
      'read_only_reason': project.read_only_reason,
    }
    return project_json

  def _MakePermJSON(self, perm, email_dict):
    perm_json = {
      'member': email_dict.get(perm.member_id),
      'perms': [p for p in perm.perms],
    }
    return perm_json

  def _MakeConfigJSON(self, config, email_dict, project_templates):
    config_json = {
      'statuses':
          [self._MakeStatusJSON(status)
           for status in config.well_known_statuses],
      'statuses_offer_merge':
          [status for status in config.statuses_offer_merge],
      'labels':
          [self._MakeLabelJSON(label) for label in config.well_known_labels],
      'exclusive_label_prefixes':
          [label for label in config.exclusive_label_prefixes],
      # TODO(agable): Export the projects FieldDefs (not yet used).
      'components':
          [self._MakeComponentJSON(component, email_dict)
           for component in config.component_defs],
      'templates':
          [self._MakeTemplateJSON(template, email_dict)
           for template in project_templates],
      'developer_template': config.default_template_for_developers,
      'user_template': config.default_template_for_users,
      'list_cols': config.default_col_spec,
      'list_spec': config.default_sort_spec,
      'grid_x': config.default_x_attr,
      'grid_y': config.default_y_attr,
      'only_known_values': config.restrict_to_known,
    }
    if config.custom_issue_entry_url:
      config_json.update({'issue_entry_url': config.custom_issue_entry_url})
    return config_json

  def _MakeTemplateJSON(self, template, email_dict):
    template_json = {
      'name': template.name,
      'summary': template.summary,
      'content': template.content,
      'summary_must_be_edited': template.summary_must_be_edited,
      'owner': email_dict.get(template.owner_id),
      'status': template.status,
      'labels': [label for label in template.labels],
      # TODO(agable): Export the template's default Fields (not yet used).
      'members_only': template.members_only,
      'owner_defaults_to_member': template.owner_defaults_to_member,
      'component_required': template.component_required,
      'admins': [email_dict(user) for user in template.admin_ids],
    }
    return template_json

  def _MakeStatusJSON(self, status):
    status_json = {
      'status': status.status,
      'open': status.means_open,
      'docstring': status.status_docstring,
    }
    return status_json

  def _MakeLabelJSON(self, label):
    label_json = {
      'label': label.label,
      'docstring': label.label_docstring,
    }
    return label_json

  def _MakeComponentJSON(self, component, email_dict):
    component_json = {
      'path': component.path,
      'docstring': component.docstring,
      'admins': [email_dict.get(user) for user in component.admin_ids],
      'ccs': [email_dict.get(user) for user in component.cc_ids],
    }
    return component_json
