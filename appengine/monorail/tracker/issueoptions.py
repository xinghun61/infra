# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""JSON feeds for issue autocomplete options.

These are split into distinct endpoints to reduce the payload size
for large projects.
"""

import logging
from third_party import ezt

from framework import authdata
from framework import framework_bizobj
from framework import framework_helpers
from framework import framework_views
from framework import jsonfeed
from framework import permissions
from project import project_helpers
from tracker import field_helpers
from tracker import tracker_helpers
from tracker import tracker_views


# Here are some restriction labels to help people do the most common things
# that they might want to do with restrictions.
_FREQUENT_ISSUE_RESTRICTIONS = [
    (permissions.VIEW, permissions.EDIT_ISSUE,
     'Only users who can edit the issue may access it'),
    (permissions.ADD_ISSUE_COMMENT, permissions.EDIT_ISSUE,
     'Only users who can edit the issue may add comments'),
    ]


# These issue restrictions should be offered as examples whenever the project
# does not have any custom permissions in use already.
_EXAMPLE_ISSUE_RESTRICTIONS = [
    (permissions.VIEW, 'CoreTeam',
     'Custom permission CoreTeam is needed to access'),
    ]


class IssueStatusLabelOptionsJSON(jsonfeed.JsonFeed):
  """JSON data describing all issue statuses and labels."""

  def HandleRequest(self, mr):
    """Provide the UI with info used in auto-completion.

    Args:
      mr: common information parsed from the HTTP request.

    Returns:
      Results dictionary in JSON format
    """
    # Issue options data can be cached separately in each user's browser.  When
    # the project changes, a new cached_content_timestamp is set and it will
    # cause new requests to use a new URL.
    self.SetCacheHeaders(self.response)

    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    open_statuses, closed_statuses = GetStatusOptions(config)
    components = GetComponentOptions(config)
    custom_permissions = permissions.GetCustomPermissions(mr.project)
    labels = GetLabelOptions(mr, config, custom_permissions)
    exclusive_prefixes = [
      prefix.lower()
      for prefix in config.exclusive_label_prefixes
    ]
    hotlists = GetHotlistOptions(mr, self.services)
    return {
      'open': open_statuses,
      'closed': closed_statuses,
      'statuses_offer_merge': config.statuses_offer_merge,
      'components': components,
      'labels': labels,
      'excl_prefixes': exclusive_prefixes,
      'strict': ezt.boolean(config.restrict_to_known),
      'custom_permissions': custom_permissions,
      'hotlists': hotlists,
    }


class IssueMembersOptionsJSON(jsonfeed.JsonFeed):
  """JSON data describing all issue member & custom field options."""

  def HandleRequest(self, mr):
    """Provide the UI with info used in auto-completion.

    Args:
      mr: common information parsed from the HTTP request.

    Returns:
      Results dictionary in JSON format
    """
    # Issue options data can be cached separately in each user's browser.  When
    # the project changes, a new cached_content_timestamp is set and it will
    # cause new requests to use a new URL.
    self.SetCacheHeaders(self.response)

    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)

    member_views = tracker_helpers.GetVisibleMembers(
        mr, mr.project, self.services).values()
    member_emails = sorted(set(uv.email for uv in member_views))
    group_emails = sorted(set(uv.email for uv in member_views if uv.is_group))

    fields = GetFieldOptions(mr, self.services, config, member_views,
                             member_emails)

    return {
      'fields': fields,
      'members': member_emails,
      'group_emails': group_emails,
    }


def GetStatusOptions(config):
  open_statuses = []
  closed_statuses = []
  for wks in config.well_known_statuses:
    if not wks.deprecated:
      item = dict(name=wks.status, doc=wks.status_docstring)
      if wks.means_open:
        open_statuses.append(item)
      else:
        closed_statuses.append(item)

  return open_statuses, closed_statuses


def GetComponentOptions(config):
  """Prepares component options for autocomplete."""
  # TODO(jrobbins): restrictions on component definitions?
  return [
    {'name': cd.path, 'doc': cd.docstring}
    for cd in config.component_defs if not cd.deprecated
  ]


def GetLabelOptions(mr, config, custom_permissions):
  """Prepares label options for autocomplete."""
  labels = []
  field_names = [
    fd.field_name
    for fd in config.field_defs
    if not fd.is_deleted
  ]
  non_masked_labels = tracker_helpers.LabelsNotMaskedByFields(
      config, field_names)
  for wkl in non_masked_labels:
    if not wkl.commented:
      item = {'name': wkl.name, 'doc': wkl.docstring}
      labels.append(item)

  frequent_restrictions = _FREQUENT_ISSUE_RESTRICTIONS[:]
  if not custom_permissions:
    frequent_restrictions.extend(_EXAMPLE_ISSUE_RESTRICTIONS)

  labels.extend(_BuildRestrictionChoices(
      mr.project, frequent_restrictions,
      permissions.STANDARD_ISSUE_PERMISSIONS))

  return labels


def GetHotlistOptions(mr, services):
  """Fetches Hotlist options for autocomplete."""
  hotlist_pbs = services.features.GetHotlistsByUserID(
      mr.cnxn, mr.auth.user_id)

  seen = set()
  ambiguous_names = set()
  for hpb in hotlist_pbs:
    if hpb.name in seen:
      ambiguous_names.add(hpb.name)
    seen.add(hpb.name)

  hotlists = list()
  ambiguous_owners_ids = {hpb.owner_ids[0] for hpb in hotlist_pbs
      if hpb.name in ambiguous_names}
  ambiguous_owners_ids_to_emails = services.user.LookupUserEmails(
      mr.cnxn, ambiguous_owners_ids)
  for hpb in hotlist_pbs:
    if hpb.name in ambiguous_names:
      ref_str = ':'.join([ambiguous_owners_ids_to_emails[hpb.owner_ids[0]],
                         hpb.name])
    else:
      ref_str = hpb.name
    hotlists.append({'ref_str': ref_str, 'summary': hpb.summary})
  return hotlists


def GetFieldOptions(mr, services, config, visible_member_views,
                    visible_member_email_list):
  """Fetches custom field options for autocomplete."""
  user_indexes = {email: idx
                  for idx, email in enumerate(visible_member_email_list)}

  # TODO(jrobbins): omit fields that they don't have permission to view.
  fields = []
  for fd in config.field_defs:
    if fd.is_deleted:
      continue

    qualified_users = []
    if fd.needs_perm:
      qualified_users = field_helpers.FilterValidFieldValues(
          mr, mr.project, services, fd, visible_member_views)

    fdv = tracker_views.FieldDefView(fd, config)
    fields.append(dict(
        field_name=fdv.field_name, field_type=fdv.field_type,
        field_id=fdv.field_id, needs_perm=fdv.needs_perm,
        is_required=fdv.is_required, is_multivalued=fdv.is_multivalued,
        choices=[dict(name=c.name, doc=c.docstring) for c in fdv.choices],
        user_indexes=sorted(user_indexes[uv.email] for uv in qualified_users),
        docstring=fdv.docstring))

  return sorted(fields, key=lambda field: field['field_name'])


def _BuildRestrictionChoices(project, freq_restrictions, actions):
  """Return a list of autocompletion choices for restriction labels.

  Args:
    project: Project PB for the current project.
    freq_restrictions: list of (action, perm, doc) tuples for restrictions
        that are frequently used.
    actions: list of strings for actions that are relevant to the current
      artifact.

  Returns:
    A list of dictionaries [{'name': 'perm name', 'doc': 'docstring'}, ...]
    suitable for use in a JSON feed to our JS autocompletion functions.
  """
  custom_permissions = permissions.GetCustomPermissions(project)
  choices = []

  for action, perm, doc in freq_restrictions:
    choices.append({
        'name': 'Restrict-%s-%s' % (action, perm),
        'doc': doc,
        })

  for action in actions:
    for perm in custom_permissions:
      choices.append({
          'name': 'Restrict-%s-%s' % (action, perm),
          'doc': 'Permission %s needed to use %s' % (perm, action),
          })

  return choices
