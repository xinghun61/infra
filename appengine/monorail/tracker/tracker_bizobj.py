# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Business objects for the Monorail issue tracker.

These are classes and functions that operate on the objects that
users care about in the issue tracker: e.g., issues, and the issue
tracker configuration.
"""

import logging

from framework import framework_bizobj
from framework import framework_constants
from framework import framework_helpers
from framework import timestr
from framework import urls
from proto import tracker_pb2
from tracker import tracker_constants


def GetOwnerId(issue):
  """Get the owner of an issue, whether it is explicit or derived."""
  return (issue.owner_id or issue.derived_owner_id or
          framework_constants.NO_USER_SPECIFIED)


def GetStatus(issue):
  """Get the status of an issue, whether it is explicit or derived."""
  return issue.status or issue.derived_status or  ''


def GetCcIds(issue):
  """Get the Cc's of an issue, whether they are explicit or derived."""
  return issue.cc_ids + issue.derived_cc_ids


def GetLabels(issue):
  """Get the labels of an issue, whether explicit or derived."""
  return issue.labels + issue.derived_labels


def MakeProjectIssueConfig(
    project_id, well_known_statuses, statuses_offer_merge, well_known_labels,
    excl_label_prefixes, templates, col_spec):
  """Return a ProjectIssueConfig with the given values."""
  # pylint: disable=multiple-statements
  if not well_known_statuses: well_known_statuses = []
  if not statuses_offer_merge: statuses_offer_merge = []
  if not well_known_labels: well_known_labels = []
  if not excl_label_prefixes: excl_label_prefixes = []
  if not templates: templates = []
  if not col_spec: col_spec = ' '

  project_config = tracker_pb2.ProjectIssueConfig()
  if project_id:  # There is no ID for harmonized configs.
    project_config.project_id = project_id

  SetConfigStatuses(project_config, well_known_statuses)
  project_config.statuses_offer_merge = statuses_offer_merge
  SetConfigLabels(project_config, well_known_labels)
  SetConfigTemplates(project_config, templates)
  project_config.exclusive_label_prefixes = excl_label_prefixes

  # ID 0 means that nothing has been specified, so use hard-coded defaults.
  project_config.default_template_for_developers = 0
  project_config.default_template_for_users = 0

  project_config.default_col_spec = col_spec

  # Note: default project issue config has no filter rules.

  return project_config


def UsersInvolvedInConfig(config):
  """Return a set of all user IDs referenced in the ProjectIssueConfig."""
  result = set()
  for template in config.templates:
    if template.owner_id:
      result.add(template.owner_id)
    result.update(template.admin_ids)
  for field in config.field_defs:
    result.update(field.admin_ids)
  # TODO(jrobbins): add component owners, auto-cc, and admins.
  return result


def FindFieldDef(field_name, config):
  """Find the specified field, or return None."""
  if not field_name:
    return None
  field_name_lower = field_name.lower()
  for fd in config.field_defs:
    if fd.field_name.lower() == field_name_lower:
      return fd

  return None


def FindFieldDefByID(field_id, config):
  """Find the specified field, or return None."""
  for fd in config.field_defs:
    if fd.field_id == field_id:
      return fd

  return None


def GetGrantedPerms(issue, effective_ids, config):
  """Return a set of permissions granted by user-valued fields in an issue."""
  granted_perms = set()
  for field_value in issue.field_values:
    if field_value.user_id in effective_ids:
      field_def = FindFieldDefByID(field_value.field_id, config)
      if field_def and field_def.grants_perm:
        # TODO(jrobbins): allow comma-separated list in grants_perm
        granted_perms.add(field_def.grants_perm.lower())

  return granted_perms


def LabelIsMaskedByField(label, field_names):
  """If the label should be displayed as a field, return the field name.

  Args:
    label: string label to consider.
    field_names: a list of field names in lowercase.

  Returns:
    If masked, return the lowercase name of the field, otherwise None.  A label
    is masked by a custom field if the field name "Foo" matches the key part of
    a key-value label "Foo-Bar".
  """
  if '-' not in label:
    return None

  for field_name_lower in field_names:
    if label.lower().startswith(field_name_lower + '-'):
      return field_name_lower

  return None


def NonMaskedLabels(labels, field_names):
  """Return only those labels that are not masked by custom fields."""
  return [lab for lab in labels
          if not LabelIsMaskedByField(lab, field_names)]


def MakeFieldDef(
    field_id, project_id, field_name, field_type_int, applic_type, applic_pred,
    is_required, is_niche, is_multivalued, min_value, max_value, regex,
    needs_member, needs_perm, grants_perm, notify_on, date_action, docstring,
    is_deleted):
  """Make a FieldDef PB for the given FieldDef table row tuple."""
  if isinstance(date_action, basestring):
    date_action = date_action.upper()
  fd = tracker_pb2.FieldDef(
      field_id=field_id, project_id=project_id, field_name=field_name,
      field_type=field_type_int, is_required=bool(is_required),
      is_niche=bool(is_niche),
      is_multivalued=bool(is_multivalued), docstring=docstring,
      is_deleted=bool(is_deleted), applicable_type=applic_type or '',
      applicable_predicate=applic_pred or '',
      needs_member=bool(needs_member), grants_perm=grants_perm or '',
      notify_on=tracker_pb2.NotifyTriggers(notify_on or 0),
      date_action=tracker_pb2.DateAction(date_action or 0))
  if min_value is not None:
    fd.min_value = min_value
  if max_value is not None:
    fd.max_value = max_value
  if regex is not None:
    fd.regex = regex
  if needs_perm is not None:
    fd.needs_perm = needs_perm
  return fd


def MakeFieldValue(
    field_id, int_value, str_value, user_id, date_value, url_value, derived):
  """Make a FieldValue based on the given information."""
  fv = tracker_pb2.FieldValue(field_id=field_id, derived=derived)
  if int_value is not None:
    fv.int_value = int_value
  elif str_value is not None:
    fv.str_value = str_value
  elif user_id is not None:
    fv.user_id = user_id
  elif date_value is not None:
    fv.date_value = date_value
  elif url_value is not None:
    fv.url_value = url_value
  else:
    raise ValueError('Unexpected field value')
  return fv


def GetFieldValueWithRawValue(field_type, field_value, users_by_id, raw_value):
  """Find and return the field value of the specified field type.

  If the specified field_value is None or is empty then the raw_value is
  returned. When the field type is USER_TYPE the raw_value is used as a key to
  lookup users_by_id.

  Args:
    field_type: tracker_pb2.FieldTypes type.
    field_value: tracker_pb2.FieldValue type.
    users_by_id: Dict mapping user_ids to UserViews.
    raw_value: String to use if field_value is not specified.

  Returns:
    Value of the specified field type.
  """
  ret_value = GetFieldValue(field_value, users_by_id)
  if ret_value:
    return ret_value
  # Special case for user types.
  if field_type == tracker_pb2.FieldTypes.USER_TYPE:
    if raw_value in users_by_id:
      return users_by_id[raw_value].email
  return raw_value


def GetFieldValue(fv, users_by_id):
  """Return the value of this field.  Give emails for users in users_by_id."""
  if fv is None:
    return None
  elif fv.int_value is not None:
    return fv.int_value
  elif fv.str_value is not None:
    return fv.str_value
  elif fv.user_id is not None:
    if fv.user_id in users_by_id:
      return users_by_id[fv.user_id].email
    else:
      logging.info('Failed to lookup user %d when getting field', fv.user_id)
      return fv.user_id
  elif fv.date_value is not None:
    return timestr.TimestampToDateWidgetStr(fv.date_value)
  else:
    return None


def FindComponentDef(path, config):
  """Find the specified component, or return None."""
  path_lower = path.lower()
  for cd in config.component_defs:
    if cd.path.lower() == path_lower:
      return cd

  return None


def FindMatchingComponentIDs(path, config, exact=True):
  """Return a list of components that match the given path."""
  component_ids = []
  path_lower = path.lower()

  if exact:
    for cd in config.component_defs:
      if cd.path.lower() == path_lower:
        component_ids.append(cd.component_id)
  else:
    path_lower_delim = path.lower() + '>'
    for cd in config.component_defs:
      target_delim = cd.path.lower() + '>'
      if target_delim.startswith(path_lower_delim):
        component_ids.append(cd.component_id)

  return component_ids


def FindComponentDefByID(component_id, config):
  """Find the specified component, or return None."""
  for cd in config.component_defs:
    if cd.component_id == component_id:
      return cd

  return None


def FindAncestorComponents(config, component_def):
  """Return a list of all components the given component is under."""
  path_lower = component_def.path.lower()
  return [cd for cd in config.component_defs
          if path_lower.startswith(cd.path.lower() + '>')]


def GetIssueComponentsAndAncestors(issue, config):
  """Return a list of all the components that an issue is in."""
  result = set()
  for component_id in issue.component_ids:
    cd = FindComponentDefByID(component_id, config)
    if cd is None:
      logging.error('Tried to look up non-existent component %r' % component_id)
      continue
    ancestors = FindAncestorComponents(config, cd)
    result.add(cd)
    result.update(ancestors)

  return sorted(result, key=lambda cd: cd.path)


def FindDescendantComponents(config, component_def):
  """Return a list of all nested components under the given component."""
  path_plus_delim = component_def.path.lower() + '>'
  return [cd for cd in config.component_defs
          if cd.path.lower().startswith(path_plus_delim)]


def MakeComponentDef(
    component_id, project_id, path, docstring, deprecated, admin_ids, cc_ids,
    created, creator_id, modified=None, modifier_id=None, label_ids=None):
  """Make a ComponentDef PB for the given FieldDef table row tuple."""
  cd = tracker_pb2.ComponentDef(
      component_id=component_id, project_id=project_id, path=path,
      docstring=docstring, deprecated=bool(deprecated),
      admin_ids=admin_ids, cc_ids=cc_ids, created=created,
      creator_id=creator_id, modified=modified, modifier_id=modifier_id,
      label_ids=label_ids or [])
  return cd


def MakeSavedQuery(
    query_id, name, base_query_id, query, subscription_mode=None,
    executes_in_project_ids=None):
  """Make SavedQuery PB for the given info."""
  saved_query = tracker_pb2.SavedQuery(
      name=name, base_query_id=base_query_id, query=query)
  if query_id is not None:
    saved_query.query_id = query_id
  if subscription_mode is not None:
    saved_query.subscription_mode = subscription_mode
  if executes_in_project_ids is not None:
    saved_query.executes_in_project_ids = executes_in_project_ids
  return saved_query


def SetConfigStatuses(project_config, well_known_statuses):
  """Internal method to set the well-known statuses of ProjectIssueConfig."""
  project_config.well_known_statuses = []
  for status, docstring, means_open, deprecated in well_known_statuses:
    canonical_status = framework_bizobj.CanonicalizeLabel(status)
    project_config.well_known_statuses.append(tracker_pb2.StatusDef(
        status_docstring=docstring, status=canonical_status,
        means_open=means_open, deprecated=deprecated))


def SetConfigLabels(project_config, well_known_labels):
  """Internal method to set the well-known labels of a ProjectIssueConfig."""
  project_config.well_known_labels = []
  for label, docstring, deprecated in well_known_labels:
    canonical_label = framework_bizobj.CanonicalizeLabel(label)
    project_config.well_known_labels.append(tracker_pb2.LabelDef(
        label=canonical_label, label_docstring=docstring,
        deprecated=deprecated))


def SetConfigTemplates(project_config, template_dict_list):
  """Internal method to set the templates of a ProjectIssueConfig."""
  templates = [ConvertDictToTemplate(template_dict)
               for template_dict in template_dict_list]
  project_config.templates = templates


def ConvertDictToTemplate(template_dict):
  """Construct a Template PB with the values from template_dict.

  Args:
    template_dict: dictionary with fields corresponding to the Template
        PB fields.

  Returns:
    A Template protocol buffer thatn can be stored in the
    project's ProjectIssueConfig PB.
  """
  return MakeIssueTemplate(
      template_dict.get('name'), template_dict.get('summary'),
      template_dict.get('status'), template_dict.get('owner_id'),
      template_dict.get('content'), template_dict.get('labels'), [], [],
      template_dict.get('components'),
      summary_must_be_edited=template_dict.get('summary_must_be_edited'),
      owner_defaults_to_member=template_dict.get('owner_defaults_to_member'),
      component_required=template_dict.get('component_required'),
      members_only=template_dict.get('members_only'))


def MakeIssueTemplate(
    name, summary, status, owner_id, content, labels, field_values, admin_ids,
    component_ids, summary_must_be_edited=None, owner_defaults_to_member=None,
    component_required=None, members_only=None):
  """Make an issue template PB."""
  template = tracker_pb2.TemplateDef()
  template.name = name
  if summary:
    template.summary = summary
  if status:
    template.status = status
  if owner_id:
    template.owner_id = owner_id
  template.content = content
  template.field_values = field_values
  template.labels = labels or []
  template.admin_ids = admin_ids
  template.component_ids = component_ids or []

  if summary_must_be_edited is not None:
    template.summary_must_be_edited = summary_must_be_edited
  if owner_defaults_to_member is not None:
    template.owner_defaults_to_member = owner_defaults_to_member
  if component_required is not None:
    template.component_required = component_required
  if members_only is not None:
    template.members_only = members_only

  return template


def MakeDefaultProjectIssueConfig(project_id):
  """Return a ProjectIssueConfig with use by projects that don't have one."""
  return MakeProjectIssueConfig(
      project_id,
      tracker_constants.DEFAULT_WELL_KNOWN_STATUSES,
      tracker_constants.DEFAULT_STATUSES_OFFER_MERGE,
      tracker_constants.DEFAULT_WELL_KNOWN_LABELS,
      tracker_constants.DEFAULT_EXCL_LABEL_PREFIXES,
      tracker_constants.DEFAULT_TEMPLATES,
      tracker_constants.DEFAULT_COL_SPEC)


def HarmonizeConfigs(config_list):
  """Combine several ProjectIssueConfigs into one for cross-project sorting.

  Args:
    config_list: a list of ProjectIssueConfig PBs with labels and statuses
        among other fields.

  Returns:
    A new ProjectIssueConfig with just the labels and status values filled
    in to be a logical union of the given configs.  Specifically, the order
    of the combined status and label lists should be maintained.
  """
  if not config_list:
    return MakeDefaultProjectIssueConfig(None)

  harmonized_status_names = _CombineOrderedLists(
      [[stat.status for stat in config.well_known_statuses]
       for config in config_list])
  harmonized_label_names = _CombineOrderedLists(
      [[lab.label for lab in config.well_known_labels]
       for config in config_list])
  harmonized_default_sort_spec = ' '.join(
      config.default_sort_spec for config in config_list)
  # This col_spec is probably not what the user wants to view because it is
  # too much information.  We join all the col_specs here so that we are sure
  # to lookup all users needed for sorting, even if it is more than needed.
  # xxx we need to look up users based on colspec rather than sortspec?
  harmonized_default_col_spec = ' '.join(
      config.default_col_spec for config in config_list)

  result_config = tracker_pb2.ProjectIssueConfig()
  # The combined config is only used during sorting, never stored.
  result_config.default_col_spec = harmonized_default_col_spec
  result_config.default_sort_spec = harmonized_default_sort_spec

  for status_name in harmonized_status_names:
    result_config.well_known_statuses.append(tracker_pb2.StatusDef(
        status=status_name, means_open=True))

  for label_name in harmonized_label_names:
    result_config.well_known_labels.append(tracker_pb2.LabelDef(
        label=label_name))

  for config in config_list:
    result_config.field_defs.extend(config.field_defs)
    result_config.component_defs.extend(config.component_defs)

  return result_config


def HarmonizeLabelOrStatusRows(def_rows):
  """Put the given label defs into a logical global order."""
  ranked_defs_by_project = {}
  oddball_defs = []
  for row in def_rows:
    def_id, project_id, rank, label = row[0], row[1], row[2], row[3]
    if rank is not None:
      ranked_defs_by_project.setdefault(project_id, []).append(
          (def_id, rank, label))
    else:
      oddball_defs.append((def_id, rank, label))

  oddball_defs.sort(reverse=True, key=lambda def_tuple: def_tuple[2].lower())
  # Compose the list-of-lists in a consistent order by project_id.
  list_of_lists = [ranked_defs_by_project[pid]
                   for pid in sorted(ranked_defs_by_project.keys())]
  harmonized_ranked_defs = _CombineOrderedLists(
      list_of_lists, include_duplicate_keys=True,
      key=lambda def_tuple: def_tuple[2])

  return oddball_defs + harmonized_ranked_defs


def _CombineOrderedLists(
    list_of_lists, include_duplicate_keys=False, key=lambda x: x):
  """Combine lists of items while maintaining their desired order.

  Args:
    list_of_lists: a list of lists of strings.
    include_duplicate_keys: Pass True to make the combined list have the
        same total number of elements as the sum of the input lists.
    key: optional function to choose which part of the list items hold the
        string used for comparison.  The result will have the whole items.

  Returns:
    A single list of items containing one copy of each of the items
    in any of the original list, and in an order that maintains the original
    list ordering as much as possible.
  """
  combined_items = []
  combined_keys = []
  seen_keys_set = set()
  for one_list in list_of_lists:
    _AccumulateCombinedList(
        one_list, combined_items, combined_keys, seen_keys_set, key=key,
        include_duplicate_keys=include_duplicate_keys)

  return combined_items


def _AccumulateCombinedList(
    one_list, combined_items, combined_keys, seen_keys_set,
    include_duplicate_keys=False, key=lambda x: x):
  """Accumulate strings into a combined list while its maintaining ordering.

  Args:
    one_list: list of strings in a desired order.
    combined_items: accumulated list of items in the desired order.
    combined_keys: accumulated list of key strings in the desired order.
    seen_keys_set: set of strings that are already in combined_list.
    include_duplicate_keys: Pass True to make the combined list have the
        same total number of elements as the sum of the input lists.
    key: optional function to choose which part of the list items hold the
        string used for comparison.  The result will have the whole items.

  Returns:
    Nothing.  But, combined_items is modified to mix in all the items of
    one_list at appropriate points such that nothing in combined_items
    is reordered, and the ordering of items from one_list is maintained
    as much as possible.  Also, seen_keys_set is modified to add any keys
    for items that were added to combined_items.

  Also, any strings that begin with "#" are compared regardless of the "#".
  The purpose of such strings is to guide the final ordering.
  """
  insert_idx = 0
  for item in one_list:
    s = key(item).lower()
    if s in seen_keys_set:
      item_idx = combined_keys.index(s)  # Need parallel list of keys
      insert_idx = max(insert_idx, item_idx + 1)

    if s not in seen_keys_set or include_duplicate_keys:
      combined_items.insert(insert_idx, item)
      combined_keys.insert(insert_idx, s)
      insert_idx += 1

    seen_keys_set.add(s)


def GetBuiltInQuery(query_id):
  """If the given query ID is for a built-in query, return that string."""
  return tracker_constants.DEFAULT_CANNED_QUERY_CONDS.get(query_id, '')


def UsersInvolvedInAmendments(amendments):
  """Return a set of all user IDs mentioned in the given Amendments."""
  user_id_set = set()
  for amendment in amendments:
    user_id_set.update(amendment.added_user_ids)
    user_id_set.update(amendment.removed_user_ids)

  return user_id_set


def _AccumulateUsersInvolvedInComment(comment, user_id_set):
  """Build up a set of all users involved in an IssueComment.

  Args:
    comment: an IssueComment PB.
    user_id_set: a set of user IDs to build up.

  Returns:
    The same set, but modified to have the user IDs of user who
    entered the comment, and all the users mentioned in any amendments.
  """
  user_id_set.add(comment.user_id)
  user_id_set.update(UsersInvolvedInAmendments(comment.amendments))

  return user_id_set


def UsersInvolvedInComment(comment):
  """Return a set of all users involved in an IssueComment.

  Args:
    comment: an IssueComment PB.

  Returns:
    A set with the user IDs of user who entered the comment, and all the
    users mentioned in any amendments.
  """
  return _AccumulateUsersInvolvedInComment(comment, set())


def UsersInvolvedInCommentList(comments):
  """Return a set of all users involved in a list of IssueComments.

  Args:
    comments: a list of IssueComment PBs.

  Returns:
    A set with the user IDs of user who entered the comment, and all the
    users mentioned in any amendments.
  """
  result = set()
  for c in comments:
    _AccumulateUsersInvolvedInComment(c, result)

  return result


def UsersInvolvedInIssues(issues):
  """Return a set of all user IDs referenced in the issues' metadata."""
  result = set()
  for issue in issues:
    result.update([issue.reporter_id, issue.owner_id, issue.derived_owner_id])
    result.update(issue.cc_ids)
    result.update(issue.derived_cc_ids)
    result.update(fv.user_id for fv in issue.field_values if fv.user_id)

  return result


def MakeAmendment(
    field, new_value, added_ids, removed_ids, custom_field_name=None,
    old_value=None):
  """Utility function to populate an Amendment PB.

  Args:
    field: enum for the field being updated.
    new_value: new string value of that field.
    added_ids: list of user IDs being added.
    removed_ids: list of user IDs being removed.
    custom_field_name: optional name of a custom field.
    old_value: old string value of that field.

  Returns:
    An instance of Amendment.
  """
  amendment = tracker_pb2.Amendment()
  amendment.field = field
  amendment.newvalue = new_value
  amendment.added_user_ids.extend(added_ids)
  amendment.removed_user_ids.extend(removed_ids)

  if old_value is not None:
    amendment.oldvalue = old_value

  if custom_field_name is not None:
    amendment.custom_field_name = custom_field_name

  return amendment


def _PlusMinusString(added_items, removed_items):
  """Return a concatenation of the items, with a minus on removed items.

  Args:
    added_items: list of string items added.
    removed_items: list of string items removed.

  Returns:
    A unicode string with all the removed items first (preceeded by minus
    signs) and then the added items.
  """
  assert all(isinstance(item, basestring)
             for item in added_items + removed_items)
  # TODO(jrobbins): this is not good when values can be negative ints.
  return ' '.join(
      ['-%s' % item.strip()
       for item in removed_items if item] +
      ['%s' % item for item in added_items if item])


def _PlusMinusAmendment(
    field, added_items, removed_items, custom_field_name=None):
  """Make an Amendment PB with the given added/removed items."""
  return MakeAmendment(
      field, _PlusMinusString(added_items, removed_items), [], [],
      custom_field_name=custom_field_name)


def _PlusMinusRefsAmendment(
    field, added_refs, removed_refs, default_project_name=None):
  """Make an Amendment PB with the given added/removed refs."""
  return _PlusMinusAmendment(
      field,
      [FormatIssueRef(r, default_project_name=default_project_name)
       for r in added_refs if r],
      [FormatIssueRef(r, default_project_name=default_project_name)
       for r in removed_refs if r])


def MakeSummaryAmendment(new_summary, old_summary):
  """Make an Amendment PB for a change to the summary."""
  return MakeAmendment(
      tracker_pb2.FieldID.SUMMARY, new_summary, [], [], old_value=old_summary)


def MakeStatusAmendment(new_status, old_status):
  """Make an Amendment PB for a change to the status."""
  return MakeAmendment(
      tracker_pb2.FieldID.STATUS, new_status, [], [], old_value=old_status)


def MakeOwnerAmendment(new_owner_id, old_owner_id):
  """Make an Amendment PB for a change to the owner."""
  return MakeAmendment(
      tracker_pb2.FieldID.OWNER, '', [new_owner_id], [old_owner_id])


def MakeCcAmendment(added_cc_ids, removed_cc_ids):
  """Make an Amendment PB for a change to the Cc list."""
  return MakeAmendment(
      tracker_pb2.FieldID.CC, '', added_cc_ids, removed_cc_ids)


def MakeLabelsAmendment(added_labels, removed_labels):
  """Make an Amendment PB for a change to the labels."""
  return _PlusMinusAmendment(
      tracker_pb2.FieldID.LABELS, added_labels, removed_labels)


def DiffValueLists(new_list, old_list):
  """Give an old list and a new list, return the added and removed items."""
  if not old_list:
    return new_list, []
  if not new_list:
    return [], old_list

  added = []
  removed = old_list[:]  # Assume everything was removed, then narrow that down
  for val in new_list:
    if val in removed:
      removed.remove(val)
    else:
      added.append(val)

  return added, removed


def MakeFieldAmendment(field_id, config, new_values, old_values=None):
  """Return an amendment showing how an issue's field changed.

  Args:
    field_id: int field ID of a built-in or custom issue field.
    config: config info for the current project, including field_defs.
    new_values: list of strings representing new values of field.
    old_values: list of strings representing old values of field.

  Returns:
    A new Amemdnent object.

  Raises:
    ValueError: if the specified field was not found.
  """
  fd = FindFieldDefByID(field_id, config)

  if fd is None:
    raise ValueError('field %r vanished mid-request', field_id)

  if fd.is_multivalued:
    old_values = old_values or []
    added, removed = DiffValueLists(new_values, old_values)
    if fd.field_type == tracker_pb2.FieldTypes.USER_TYPE:
      return MakeAmendment(
          tracker_pb2.FieldID.CUSTOM, '', added, removed,
          custom_field_name=fd.field_name)
    else:
      return _PlusMinusAmendment(
          tracker_pb2.FieldID.CUSTOM,
          ['%s' % item for item in added],
          ['%s' % item for item in removed],
          custom_field_name=fd.field_name)

  else:
    if fd.field_type == tracker_pb2.FieldTypes.USER_TYPE:
      return MakeAmendment(
          tracker_pb2.FieldID.CUSTOM, '', new_values, [],
          custom_field_name=fd.field_name)

    if new_values:
      new_str = ', '.join('%s' % item for item in new_values)
    else:
      new_str = '----'

    return MakeAmendment(
        tracker_pb2.FieldID.CUSTOM, new_str, [], [],
        custom_field_name=fd.field_name)


def MakeFieldClearedAmendment(field_id, config):
  fd = FindFieldDefByID(field_id, config)

  if fd is None:
    raise ValueError('field %r vanished mid-request', field_id)

  return MakeAmendment(
      tracker_pb2.FieldID.CUSTOM, '----', [], [],
      custom_field_name=fd.field_name)


def MakeComponentsAmendment(added_comp_ids, removed_comp_ids, config):
  """Make an Amendment PB for a change to the components."""
  # TODO(jrobbins): record component IDs as ints and display them with
  # lookups (and maybe permission checks in the future).  But, what
  # about history that references deleleted components?
  added_comp_paths = []
  for comp_id in added_comp_ids:
    cd = FindComponentDefByID(comp_id, config)
    if cd:
      added_comp_paths.append(cd.path)

  removed_comp_paths = []
  for comp_id in removed_comp_ids:
    cd = FindComponentDefByID(comp_id, config)
    if cd:
      removed_comp_paths.append(cd.path)

  return _PlusMinusAmendment(
      tracker_pb2.FieldID.COMPONENTS,
      added_comp_paths, removed_comp_paths)


def MakeBlockedOnAmendment(
    added_refs, removed_refs, default_project_name=None):
  """Make an Amendment PB for a change to the blocked on issues."""
  return _PlusMinusRefsAmendment(
      tracker_pb2.FieldID.BLOCKEDON, added_refs, removed_refs,
      default_project_name=default_project_name)


def MakeBlockingAmendment(added_refs, removed_refs, default_project_name=None):
  """Make an Amendment PB for a change to the blocking issues."""
  return _PlusMinusRefsAmendment(
      tracker_pb2.FieldID.BLOCKING, added_refs, removed_refs,
      default_project_name=default_project_name)


def MakeMergedIntoAmendment(added_ref, removed_ref, default_project_name=None):
  """Make an Amendment PB for a change to the merged-into issue."""
  return _PlusMinusRefsAmendment(
      tracker_pb2.FieldID.MERGEDINTO, [added_ref], [removed_ref],
      default_project_name=default_project_name)


def MakeProjectAmendment(new_project_name):
  """Make an Amendment PB for a change to an issue's project."""
  return MakeAmendment(
      tracker_pb2.FieldID.PROJECT, new_project_name, [], [])


def AmendmentString(amendment, users_by_id):
  """Produce a displayable string for an Amendment PB.

  Args:
    amendment: Amendment PB to display.
    users_by_id: dict {user_id: user_view, ...} including all users
      mentioned in amendment.

  Returns:
    A string that could be displayed on a web page or sent in email.
  """
  if amendment.newvalue:
    return amendment.newvalue

  # Display new owner only
  if amendment.field == tracker_pb2.FieldID.OWNER:
    if amendment.added_user_ids and amendment.added_user_ids[0] > 0:
      uid = amendment.added_user_ids[0]
      result = users_by_id[uid].display_name
    else:
      result = framework_constants.NO_USER_NAME
  else:
    result = _PlusMinusString(
        [users_by_id[uid].display_name for uid in amendment.added_user_ids
         if uid in users_by_id],
        [users_by_id[uid].display_name for uid in amendment.removed_user_ids
         if uid in users_by_id])

  return result


def AmendmentLinks(amendment, users_by_id, project_name):
  """Produce a list of value/url pairs for an Amendment PB.

  Args:
    amendment: Amendment PB to display.
    users_by_id: dict {user_id: user_view, ...} including all users
      mentioned in amendment.
    project_nme: Name of project the issue/comment/amendment is in.

  Returns:
    A list of dicts with 'value' and 'url' keys. 'url' may be None.
  """
  # Display both old and new summary
  if amendment.field == tracker_pb2.FieldID.SUMMARY:
    result = amendment.newvalue
    if amendment.oldvalue:
      result += ' (was: %s)' % amendment.oldvalue
    return [{'value': result, 'url': None}]
  # Display new owner only
  elif amendment.field == tracker_pb2.FieldID.OWNER:
    if amendment.added_user_ids and amendment.added_user_ids[0] > 0:
      uid = amendment.added_user_ids[0]
      return [{'value': users_by_id[uid].display_name, 'url': None}]
    else:
      return [{'value': framework_constants.NO_USER_NAME, 'url': None}]
  elif amendment.field in (tracker_pb2.FieldID.BLOCKEDON,
                           tracker_pb2.FieldID.BLOCKING,
                           tracker_pb2.FieldID.MERGEDINTO):
    values = amendment.newvalue.split()
    bug_refs = [_SafeParseIssueRef(v.strip()) for v in values]
    issue_urls = [FormatIssueURL(ref, default_project_name=project_name)
                  for ref in bug_refs]
    # TODO(jrobbins): Permission checks on referenced issues to allow
    # showing summary on hover.
    return [{'value': v, 'url': u} for (v, u) in zip(values, issue_urls)]
  elif amendment.newvalue:
    # Catchall for everything except user-valued fields.
    return [{'value': v, 'url': None} for v in amendment.newvalue.split()]
  else:
    # Applies to field==CC or CUSTOM with user type.
    values = _PlusMinusString(
        [users_by_id[uid].display_name for uid in amendment.added_user_ids
         if uid in users_by_id],
        [users_by_id[uid].display_name for uid in amendment.removed_user_ids
         if uid in users_by_id])
    return [{'value': v.strip(), 'url': None} for v in values.split()]


def GetAmendmentFieldName(amendment):
  """Get user-visible name for an amendment to a built-in or custom field."""
  if amendment.custom_field_name:
    return amendment.custom_field_name
  else:
    field_name = str(amendment.field)
    return field_name.capitalize()


def MakeDanglingIssueRef(project_name, issue_id):
  """Create a DanglingIssueRef pb."""
  ret = tracker_pb2.DanglingIssueRef()
  ret.project = project_name
  ret.issue_id = issue_id
  return ret


def FormatIssueURL(issue_ref_tuple, default_project_name=None):
  """Format an issue url from an issue ref."""
  if issue_ref_tuple is None:
    return ''
  project_name, local_id = issue_ref_tuple
  project_name = project_name or default_project_name
  url = framework_helpers.FormatURL(
    None, '/p/%s%s' % (project_name, urls.ISSUE_DETAIL), id=local_id)
  return url


def FormatIssueRef(issue_ref_tuple, default_project_name=None):
  """Format an issue reference for users: e.g., 123, or projectname:123."""
  if issue_ref_tuple is None:
    return ''
  project_name, local_id = issue_ref_tuple
  if project_name and project_name != default_project_name:
    return '%s:%d' % (project_name, local_id)
  else:
    return str(local_id)


def ParseIssueRef(ref_str):
  """Parse an issue ref string: e.g., 123, or projectname:123 into a tuple.

  Raises ValueError if the ref string exists but can't be parsed.
  """
  if not ref_str.strip():
    return None

  if ':' in ref_str:
    project_name, id_str = ref_str.split(':', 1)
    project_name = project_name.strip().lstrip('-')
  else:
    project_name = None
    id_str = ref_str

  id_str = id_str.lstrip('-')

  return project_name, int(id_str)


def _SafeParseIssueRef(ref_str):
  """Same as ParseIssueRef, but catches ValueError and returns None instead."""
  try:
    return ParseIssueRef(ref_str)
  except ValueError:
    return None


def MergeFields(field_values, fields_add, fields_remove, field_defs):
  """Merge the fields to add/remove into the current field values.

  Args:
    field_values: list of current FieldValue PBs.
    fields_add: list of FieldValue PBs to add to field_values.  If any of these
        is for a single-valued field, it replaces all previous values for the
        same field_id in field_values.
    fields_remove: list of FieldValues to remove from field_values, if found.
    field_defs: list of FieldDef PBs from the issue's project's config.

  Returns:
    A 3-tuple with the merged field values, the specific values that added
    or removed.  The actual added or removed might be fewer than the requested
    ones if the issue already had one of the values-to-add or lacked one of the
    values-to-remove.
  """
  is_multi = {fd.field_id: fd.is_multivalued for fd in field_defs}
  merged_fvs = list(field_values)
  fvs_added = []
  for fv_consider in fields_add:
    consider_value = GetFieldValue(fv_consider, {})
    for old_fv in field_values:
      if (fv_consider.field_id == old_fv.field_id and
          GetFieldValue(old_fv, {}) == consider_value):
        break
    else:
      # Drop any existing values for non-multi fields.
      if not is_multi.get(fv_consider.field_id):
        merged_fvs = [fv for fv in merged_fvs
                      if fv.field_id != fv_consider.field_id]
      fvs_added.append(fv_consider)
      merged_fvs.append(fv_consider)

  fvs_removed = []
  for fv_consider in fields_remove:
    consider_value = GetFieldValue(fv_consider, {})
    for old_fv in field_values:
      if (fv_consider.field_id == old_fv.field_id and
          GetFieldValue(old_fv, {}) == consider_value):
        fvs_removed.append(fv_consider)
        merged_fvs.remove(old_fv)

  return merged_fvs, fvs_added, fvs_removed


def SplitBlockedOnRanks(issue, target_iid, split_above, open_iids):
  """Splits issue relation rankings by some target issue's rank

  Args:
    issue: Issue PB for the issue considered.
    target_iid: the global ID of the issue to split rankings about.
    split_above: False to split below the target issue, True to split above.
    open_iids: a list of global IDs of open and visible issues blocking
      the considered issue.

  Returns:
    A tuple (lower, higher) where both are lists of
    [(blocker_iid, rank),...] of issues in rank order. If split_above is False
    the target issue is included in higher, otherwise it is included in lower
  """
  issue_rank_pairs = [(dst_iid, rank)
      for (dst_iid, rank) in zip(issue.blocked_on_iids, issue.blocked_on_ranks)
      if dst_iid in open_iids]
  # blocked_on_iids is sorted high-to-low, we need low-to-high
  issue_rank_pairs.reverse()
  offset = int(split_above)
  for i, (dst_iid, _) in enumerate(issue_rank_pairs):
    if dst_iid == target_iid:
      return issue_rank_pairs[:i + offset], issue_rank_pairs[i + offset:]

  logging.error('Target issue %r was not found in blocked_on_iids of %r',
                target_iid, issue)
  return issue_rank_pairs, []
