# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Servlets for issue tracker configuration.

These classes implement the Statuses, Labels and fields, Components, Rules, and
Views subtabs under the Process tab.  Unlike most servlet modules, this single
file holds a base class and several related servlet classes.
"""

import collections
import itertools
import logging
import time

from third_party import ezt

from features import filterrules_helpers
from features import filterrules_views
from features import savedqueries_helpers
from framework import authdata
from framework import framework_bizobj
from framework import framework_constants
from framework import framework_helpers
from framework import framework_views
from framework import monorailrequest
from framework import permissions
from framework import servlet
from framework import urls
from tracker import field_helpers
from tracker import tracker_bizobj
from tracker import tracker_constants
from tracker import tracker_helpers
from tracker import tracker_views


class IssueAdminBase(servlet.Servlet):
  """Base class for servlets allowing project owners to configure tracker."""

  _MAIN_TAB_MODE = servlet.Servlet.MAIN_TAB_PROCESS
  _PROCESS_SUBTAB = None  # specified in subclasses

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """
    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    config_view = tracker_views.ConfigView(mr, self.services, config)
    return {
        'admin_tab_mode': self._PROCESS_SUBTAB,
        'config': config_view,
        }

  def ProcessFormData(self, mr, post_data):
    """Validate and store the contents of the issues tracker admin page.

    Args:
      mr: commonly used info parsed from the request.
      post_data: HTML form data from the request.

    Returns:
      String URL to redirect the user to, or None if response was already sent.
    """
    page_url = self.ProcessSubtabForm(post_data, mr)

    if mr.errors.AnyErrors():
      self.PleaseCorrect(mr)  # TODO(jrobbins): echo more user-entered text.
    else:
      return framework_helpers.FormatAbsoluteURL(
          mr, page_url, saved=1, ts=int(time.time()))


class AdminStatuses(IssueAdminBase):
  """Servlet allowing project owners to configure well-known statuses."""

  _PAGE_TEMPLATE = 'tracker/admin-statuses-page.ezt'
  _PROCESS_SUBTAB = servlet.Servlet.PROCESS_TAB_STATUSES

  def ProcessSubtabForm(self, post_data, mr):
    """Process the status definition section of the admin page.

    Args:
      post_data: HTML form data for the HTTP request being processed.
      mr: commonly used info parsed from the request.

    Returns:
      The URL of the page to show after processing.
    """
    if not self.CheckPerm(mr, permissions.EDIT_PROJECT):
      raise permissions.PermissionException(
          'Only project owners may edit the status definitions')

    wks_open_text = post_data.get('predefinedopen', '')
    wks_open_matches = framework_constants.IDENTIFIER_DOCSTRING_RE.findall(
        wks_open_text)
    wks_open_tuples = [
        (status.lstrip('#'), docstring.strip(), True, status.startswith('#'))
        for status, docstring in wks_open_matches]

    wks_closed_text = post_data.get('predefinedclosed', '')
    wks_closed_matches = framework_constants.IDENTIFIER_DOCSTRING_RE.findall(
        wks_closed_text)
    wks_closed_tuples = [
        (status.lstrip('#'), docstring.strip(), False, status.startswith('#'))
        for status, docstring in wks_closed_matches]

    statuses_offer_merge_text = post_data.get('statuses_offer_merge', '')
    statuses_offer_merge = framework_constants.IDENTIFIER_RE.findall(
        statuses_offer_merge_text)

    if not mr.errors.AnyErrors():
      self.services.config.UpdateConfig(
          mr.cnxn, mr.project, statuses_offer_merge=statuses_offer_merge,
          well_known_statuses=wks_open_tuples + wks_closed_tuples)

    # TODO(jrobbins): define a "strict" mode that affects only statuses.

    return urls.ADMIN_STATUSES


class AdminLabels(IssueAdminBase):
  """Servlet allowing project owners to labels and fields."""

  _PAGE_TEMPLATE = 'tracker/admin-labels-page.ezt'
  _PROCESS_SUBTAB = servlet.Servlet.PROCESS_TAB_LABELS

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """
    page_data = super(AdminLabels, self).GatherPageData(mr)
    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    field_def_views = [
        tracker_views.FieldDefView(fd, config)
        # TODO(jrobbins): future field-level view restrictions.
        for fd in config.field_defs
        if not fd.is_deleted]
    page_data.update({
        'field_defs': field_def_views,
        })
    return page_data

  def ProcessSubtabForm(self, post_data, mr):
    """Process changes to labels and custom field definitions.

    Args:
      post_data: HTML form data for the HTTP request being processed.
      mr: commonly used info parsed from the request.

    Returns:
      The URL of the page to show after processing.
    """
    if not self.CheckPerm(mr, permissions.EDIT_PROJECT):
      raise permissions.PermissionException(
          'Only project owners may edit the label definitions')

    wkl_text = post_data.get('predefinedlabels', '')
    wkl_matches = framework_constants.IDENTIFIER_DOCSTRING_RE.findall(wkl_text)
    wkl_tuples = [
        (label.lstrip('#'), docstring.strip(), label.startswith('#'))
        for label, docstring in wkl_matches]

    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    field_names = [fd.field_name for fd in config.field_defs
                   if not fd.is_deleted]
    masked_labels = tracker_helpers.LabelsMaskedByFields(config, field_names)
    wkl_tuples.extend([
        (masked.name, masked.docstring, False) for masked in masked_labels])

    excl_prefix_text = post_data.get('excl_prefixes', '')
    excl_prefixes = framework_constants.IDENTIFIER_RE.findall(excl_prefix_text)

    if not mr.errors.AnyErrors():
      self.services.config.UpdateConfig(
          mr.cnxn, mr.project,
          well_known_labels=wkl_tuples, excl_label_prefixes=excl_prefixes)

    # TODO(jrobbins): define a "strict" mode that affects only labels.

    return urls.ADMIN_LABELS


class AdminTemplates(IssueAdminBase):
  """Servlet allowing project owners to configure templates."""

  _PAGE_TEMPLATE = 'tracker/admin-templates-page.ezt'
  _PROCESS_SUBTAB = servlet.Servlet.PROCESS_TAB_TEMPLATES

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """
    return super(AdminTemplates, self).GatherPageData(mr)

  def ProcessSubtabForm(self, post_data, mr):
    """Process changes to new issue templates.

    Args:
      post_data: HTML form data for the HTTP request being processed.
      mr: commonly used info parsed from the request.

    Returns:
      The URL of the page to show after processing.
    """
    if not self.CheckPerm(mr, permissions.EDIT_PROJECT):
      raise permissions.PermissionException(
          'Only project owners may edit the default templates')

    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)

    template_set = self.services.template.GetProjectTemplates(mr.cnxn,
        config.project_id)
    default_template_id_for_developers, default_template_id_for_users = (
        self._ParseDefaultTemplateSelections(post_data, template_set.templates))
    if default_template_id_for_developers or default_template_id_for_users:
      self.services.config.UpdateConfig(
          mr.cnxn, mr.project,
          default_template_for_developers=default_template_id_for_developers,
          default_template_for_users=default_template_id_for_users)

    return urls.ADMIN_TEMPLATES

  def _ParseDefaultTemplateSelections(self, post_data, templates):
    """Parse the input for the default templates to offer users."""
    def GetSelectedTemplateID(name):
      """Find the ID of the template specified in post_data[name]."""
      if name not in post_data:
        return None
      selected_template_name = post_data[name]
      for template in templates:
        if selected_template_name == template.name:
          return template.template_id

      logging.error('User somehow selected an invalid template: %r',
                    selected_template_name)
      return None

    return (GetSelectedTemplateID('default_template_for_developers'),
            GetSelectedTemplateID('default_template_for_users'))


class AdminComponents(IssueAdminBase):
  """Servlet allowing project owners to view the list of components."""

  _PAGE_TEMPLATE = 'tracker/admin-components-page.ezt'
  _PROCESS_SUBTAB = servlet.Servlet.PROCESS_TAB_COMPONENTS

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """
    page_data = super(AdminComponents, self).GatherPageData(mr)
    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    users_by_id = framework_views.MakeAllUserViews(
        mr.cnxn, self.services.user,
        *[list(cd.admin_ids) + list(cd.cc_ids)
          for cd in config.component_defs])
    framework_views.RevealAllEmailsToMembers(mr.auth, mr.project, users_by_id)
    component_def_views = [
        tracker_views.ComponentDefView(mr.cnxn, self.services, cd, users_by_id)
        # TODO(jrobbins): future component-level view restrictions.
        for cd in config.component_defs]
    for cd in component_def_views:
      if mr.auth.email in [user.email for user in cd.admins]:
        cd.classes += 'myadmin '
      if mr.auth.email in [user.email for user in cd.cc]:
        cd.classes += 'mycc '

    page_data.update({
        'component_defs': component_def_views,
        'failed_perm': mr.GetParam('failed_perm'),
        'failed_subcomp': mr.GetParam('failed_subcomp'),
        'failed_templ': mr.GetParam('failed_templ'),
        })
    return page_data

  def _GetComponentDefs(self, _mr, post_data, config):
    """Get the config and component definitions from the request."""
    component_defs = []
    component_paths = post_data.get('delete_components').split(',')
    for component_path in component_paths:
      component_def = tracker_bizobj.FindComponentDef(component_path, config)
      component_defs.append(component_def)
    return component_defs

  def _ProcessDeleteComponent(self, mr, component_def):
    """Delete the specified component and its references."""
    self.services.issue.DeleteComponentReferences(
        mr.cnxn, component_def.component_id)
    self.services.config.DeleteComponentDef(
        mr.cnxn, mr.project_id, component_def.component_id)

  def ProcessFormData(self, mr, post_data):
    """Processes a POST command to delete components.

    Args:
      mr: commonly used info parsed from the request.
      post_data: HTML form data from the request.

    Returns:
      String URL to redirect the user to, or None if response was already sent.
    """
    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    component_defs = self._GetComponentDefs(mr, post_data, config)
    # Reverse the component_defs so that we start deleting from subcomponents.
    component_defs.reverse()

    # Collect errors.
    perm_errors = []
    subcomponents_errors = []
    templates_errors = []
    # Collect successes.
    deleted_components = []

    for component_def in component_defs:
      allow_edit = permissions.CanEditComponentDef(
          mr.auth.effective_ids, mr.perms, mr.project, component_def, config)
      if not allow_edit:
        perm_errors.append(component_def.path)

      subcomponents = tracker_bizobj.FindDescendantComponents(
          config, component_def)
      if subcomponents:
        subcomponents_errors.append(component_def.path)

      templates = self.services.template.TemplatesWithComponent(
          mr.cnxn, component_def.component_id, config)
      if templates:
        templates_errors.append(component_def.path)

      allow_delete = allow_edit and not subcomponents and not templates
      if allow_delete:
        self._ProcessDeleteComponent(mr, component_def)
        deleted_components.append(component_def.path)
        # Refresh project config after the component deletion.
        config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)

    return framework_helpers.FormatAbsoluteURL(
        mr, urls.ADMIN_COMPONENTS, ts=int(time.time()),
        failed_perm=','.join(perm_errors),
        failed_subcomp=','.join(subcomponents_errors),
        failed_templ=','.join(templates_errors),
        deleted=','.join(deleted_components))


class AdminViews(IssueAdminBase):
  """Servlet for project owners to set default columns, axes, and sorting."""

  _PAGE_TEMPLATE = 'tracker/admin-views-page.ezt'
  _PROCESS_SUBTAB = servlet.Servlet.PROCESS_TAB_VIEWS

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """
    page_data = super(AdminViews, self).GatherPageData(mr)
    with mr.profiler.Phase('getting canned queries'):
      canned_queries = self.services.features.GetCannedQueriesByProjectID(
          mr.cnxn, mr.project_id)

    page_data.update({
        'new_query_indexes': range(
            len(canned_queries) + 1, savedqueries_helpers.MAX_QUERIES + 1),
        'issue_notify': mr.project.issue_notify_address,
        'max_queries': savedqueries_helpers.MAX_QUERIES,
        })
    return page_data

  def ProcessSubtabForm(self, post_data, mr):
    """Process the Views subtab.

    Args:
      post_data: HTML form data for the HTTP request being processed.
      mr: commonly used info parsed from the request.

    Returns:
      The URL of the page to show after processing.
    """
    if not self.CheckPerm(mr, permissions.EDIT_PROJECT):
      raise permissions.PermissionException(
          'Only project owners may edit the default views')
    existing_queries = savedqueries_helpers.ParseSavedQueries(
        mr.cnxn, post_data, self.services.project)
    added_queries = savedqueries_helpers.ParseSavedQueries(
        mr.cnxn, post_data, self.services.project, prefix='new_')
    canned_queries = existing_queries + added_queries

    list_prefs = _ParseListPreferences(post_data)

    if not mr.errors.AnyErrors():
      self.services.config.UpdateConfig(
          mr.cnxn, mr.project, list_prefs=list_prefs)
      self.services.features.UpdateCannedQueries(
          mr.cnxn, mr.project_id, canned_queries)

    return urls.ADMIN_VIEWS


def _ParseListPreferences(post_data):
  """Parse the part of a project admin form about artifact list preferences."""
  default_col_spec = ''
  if 'default_col_spec' in post_data:
    default_col_spec = post_data['default_col_spec']
  # Don't allow empty colum spec
  if not default_col_spec:
    default_col_spec = tracker_constants.DEFAULT_COL_SPEC
  col_spec_words = monorailrequest.ParseColSpec(
      default_col_spec, max_parts=framework_constants.MAX_COL_PARTS)
  col_spec = ' '.join(word for word in col_spec_words)

  default_sort_spec = ''
  if 'default_sort_spec' in post_data:
    default_sort_spec = post_data['default_sort_spec']
  sort_spec_words = monorailrequest.ParseColSpec(default_sort_spec)
  sort_spec = ' '.join(sort_spec_words)

  x_attr_str = ''
  if 'default_x_attr' in post_data:
    x_attr_str = post_data['default_x_attr']
  x_attr_words = monorailrequest.ParseColSpec(x_attr_str)
  x_attr = ''
  if x_attr_words:
    x_attr = x_attr_words[0]

  y_attr_str = ''
  if 'default_y_attr' in post_data:
    y_attr_str = post_data['default_y_attr']
  y_attr_words = monorailrequest.ParseColSpec(y_attr_str)
  y_attr = ''
  if y_attr_words:
    y_attr = y_attr_words[0]

  member_default_query = ''
  if 'member_default_query' in post_data:
    member_default_query = post_data['member_default_query']

  return col_spec, sort_spec, x_attr, y_attr, member_default_query


class AdminRules(IssueAdminBase):
  """Servlet allowing project owners to configure filter rules."""

  _PAGE_TEMPLATE = 'tracker/admin-rules-page.ezt'
  _PROCESS_SUBTAB = servlet.Servlet.PROCESS_TAB_RULES

  def AssertBasePermission(self, mr):
    """Check whether the user has any permission to visit this page.

    Args:
      mr: commonly used info parsed from the request.
    """
    super(AdminRules, self).AssertBasePermission(mr)
    if not self.CheckPerm(mr, permissions.EDIT_PROJECT):
      raise permissions.PermissionException(
          'User is not allowed to administer this project')

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """
    page_data = super(AdminRules, self).GatherPageData(mr)
    rules = self.services.features.GetFilterRules(
        mr.cnxn, mr.project_id)
    users_by_id = framework_views.MakeAllUserViews(
        mr.cnxn, self.services.user,
        [rule.default_owner_id for rule in rules],
        *[rule.add_cc_ids for rule in rules])
    framework_views.RevealAllEmailsToMembers(mr.auth, mr.project, users_by_id)
    rule_views = [filterrules_views.RuleView(rule, users_by_id)
                  for rule in rules]

    for idx, rule_view in enumerate(rule_views):
      rule_view.idx = idx + 1  # EZT has no loop index, so we set idx.

    page_data.update({
        'rules': rule_views,
        'new_rule_indexes': (
            range(len(rules) + 1, filterrules_helpers.MAX_RULES + 1)),
        'max_rules': filterrules_helpers.MAX_RULES,
        })
    return page_data

  def ProcessSubtabForm(self, post_data, mr):
    """Process the Rules subtab.

    Args:
      post_data: HTML form data for the HTTP request being processed.
      mr: commonly used info parsed from the request.

    Returns:
      The URL of the page to show after processing.
    """
    old_rules = self.services.features.GetFilterRules(mr.cnxn, mr.project_id)
    rules = filterrules_helpers.ParseRules(
        mr.cnxn, post_data, self.services.user, mr.errors)
    new_rules = filterrules_helpers.ParseRules(
        mr.cnxn, post_data, self.services.user, mr.errors, prefix='new_')
    rules.extend(new_rules)

    if not mr.errors.AnyErrors():
      config = self.services.features.UpdateFilterRules(
          mr.cnxn, mr.project_id, rules)

      if old_rules != rules:
        logging.info('recomputing derived fields')
        config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
        filterrules_helpers.RecomputeAllDerivedFields(
            mr.cnxn, self.services, mr.project, config)

    return urls.ADMIN_RULES
