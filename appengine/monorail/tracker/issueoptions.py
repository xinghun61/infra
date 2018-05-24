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
from framework import framework_helpers
from framework import framework_views
from framework import jsonfeed
from framework import permissions
from project import project_helpers
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
    (members_def_list, visible_member_views,
        visible_member_email_list) = GetMemberOptions(mr, self.services)
    fields = GetFieldOptions(mr, self.services, config,
        visible_member_views, visible_member_email_list)

    return {
      'fields': fields,
      'members': members_def_list
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
  # TODO(jrobbins): omit fields that they don't have permission to view.
  field_def_views = [
      tracker_views.FieldDefView(fd, config)
      for fd in config.field_defs
      if not fd.is_deleted]
  fields = [
      dict(field_name=fdv.field_name, field_type=fdv.field_type,
           field_id=fdv.field_id, needs_perm=fdv.needs_perm,
           is_required=fdv.is_required, is_multivalued=fdv.is_multivalued,
           choices=[dict(name=c.name, doc=c.docstring) for c in fdv.choices],
           docstring=fdv.docstring)
      for fdv in field_def_views]

  user_indexes = {email: idx
                  for idx, email in enumerate(visible_member_email_list)}

  for field_dict in fields:
    needed_perm = field_dict['needs_perm']
    if needed_perm:
      qualified_user_indexes = []
      for uv in visible_member_views:
        # TODO(jrobbins): Similar code occurs in field_helpers.py.
        user = services.user.GetUser(mr.cnxn, uv.user_id)
        auth = authdata.AuthData.FromUserID(
            mr.cnxn, uv.user_id, services)
        user_perms = permissions.GetPermissions(
            user, auth.effective_ids, mr.project)
        has_perm = user_perms.CanUsePerm(
            needed_perm, auth.effective_ids, mr.project, [])
        if has_perm:
          qualified_user_indexes.append(user_indexes[uv.email])

      field_dict['user_indexes'] = sorted(set(qualified_user_indexes))
  return fields


def GetMemberOptions(mr, services):
  member_data = project_helpers.BuildProjectMembers(
      mr.cnxn, mr.project, services.user)
  owner_views = member_data['owners']
  committer_views = member_data['committers']
  contributor_views = member_data['contributors']

  all_group_ids = services.usergroup.DetermineWhichUserIDsAreGroups(
      mr.cnxn, [mem.user_id for mem in member_data['all_members']])

  (ac_exclusion_ids, no_expand_ids
   ) = services.project.GetProjectAutocompleteExclusion(
      mr.cnxn, mr.project_id)
  group_ids_to_expand = [
    gid for gid in all_group_ids if gid not in no_expand_ids]

  # TODO(jrobbins): Normally, users will be allowed view the members
  # of any user group if the project From: email address is listed
  # as a group member, as well as any group that they are personally
  # members of.
  member_ids, owner_ids = services.usergroup.LookupVisibleMembers(
      mr.cnxn, group_ids_to_expand, mr.perms, mr.auth.effective_ids, services)
  indirect_ids = set()
  for gid in all_group_ids:
    indirect_ids.update(member_ids.get(gid, []))
    indirect_ids.update(owner_ids.get(gid, []))
  indirect_user_ids = list(indirect_ids)
  indirect_member_views = framework_views.MakeAllUserViews(
      mr.cnxn, services.user, indirect_user_ids).values()

  visible_member_views = _FilterMemberData(
      mr, owner_views, committer_views, contributor_views,
      indirect_member_views)
  # Filter out service accounts
  visible_member_views = [m for m in visible_member_views
                          if not framework_helpers.IsServiceAccount(m.email)
                          and not m.user_id in ac_exclusion_ids]
  visible_member_email_list = sorted(set(
      uv.email for uv in visible_member_views))
  visible_members_dict = {}
  for uv in visible_member_views:
    visible_members_dict[uv.email] = uv.user_id
  all_visible_group_ids = set(services.usergroup.DetermineWhichUserIDsAreGroups(
      mr.cnxn, visible_members_dict.values()))

  members_def_list = [
    dict(name=email, doc='')
    for email in visible_member_email_list
  ]
  for md in members_def_list:
    md_id = visible_members_dict[md['name']]
    if md_id in all_visible_group_ids:
      md['is_group'] = True

  return (members_def_list, visible_member_views,
      visible_member_email_list)


def _FilterMemberData(
    mr, owner_views, committer_views, contributor_views,
    indirect_member_views):
  """Return a filtered list of members that the user can view.

  In most projects, everyone can view the entire member list.  But,
  some projects are configured to only allow project owners to see
  all members. In those projects, committers and contributors do not
  see any contributors.  Regardless of how the project is configured
  or the role that the user plays in the current project, we include
  any indirect members through user groups that the user has access
  to view.

  Args:
    mr: Commonly used info parsed from the HTTP request.
    owner_views: list of UserViews for project owners.
    committer_views: list of UserViews for project committers.
    contributor_views: list of UserViews for project contributors.
    indirect_member_views: list of UserViews for users who have
        an indirect role in the project via a user group, and that the
        logged in user is allowed to see.

  Returns:
    A list of owners, committer and visible indirect members if the user is not
    signed in.  If the project is set to display contributors to non-owners or
    the signed in user has necessary permissions then additionally a list of
    contributors.
  """
  visible_members = []

  # Everyone can view owners and committers
  visible_members.extend(owner_views)
  visible_members.extend(committer_views)

  # The list of indirect members is already limited to ones that the user
  # is allowed to see according to user group settings.
  visible_members.extend(indirect_member_views)

  # If the user is allowed to view the list of contributors, add those too.
  if permissions.CanViewContributorList(mr):
    visible_members.extend(contributor_views)

  return visible_members


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
