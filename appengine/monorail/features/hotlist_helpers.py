# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Helper functions and classes used by the hotlist pages."""

import logging
import collections

from features import features_constants
from framework import framework_views
from framework import framework_helpers
from framework import sorting
from framework import table_view_helpers
from framework import timestr
from framework import paginate
from framework import permissions
from framework import urls
from tracker import tracker_bizobj
from tracker import tracker_constants
from tracker import tracker_helpers
from tracker import tablecell


# Type to hold a HotlistRef
HotlistRef = collections.namedtuple('HotlistRef', 'user_id, hotlist_name')


def GetSortedHotlistIssues(
    mr, hotlist_issues, issues_list, harmonized_config, services):
  with mr.profiler.Phase('Checking issue permissions and getting ranks'):

    allowed_issues = FilterIssues(mr, issues_list, services)
    allowed_iids = [issue.issue_id for issue in allowed_issues]
    # The values for issues in a hotlist are specific to the hotlist
    # (rank, adder, added) without invalidating the keys, an issue will retain
    # the rank value it has in one hotlist when navigating to another hotlist.
    sorting.InvalidateArtValuesKeys(
        mr.cnxn, [issue.issue_id for issue in allowed_issues])
    sorted_ranks = sorted(
        [hotlist_issue.rank for hotlist_issue in hotlist_issues if
         hotlist_issue.issue_id in allowed_iids])
    friendly_ranks = {
        rank: friendly for friendly, rank in enumerate(sorted_ranks, 1)}
    issue_adders = framework_views.MakeAllUserViews(
        mr.cnxn, services.user, [hotlist_issue.adder_id for
                                 hotlist_issue in hotlist_issues])
    hotlist_issues_context = {
        hotlist_issue.issue_id: {'issue_rank':
                                 friendly_ranks[hotlist_issue.rank],
                                 'adder_id': hotlist_issue.adder_id,
                                 'date_added': timestr.FormatAbsoluteDate(
                                     hotlist_issue.date_added),
                                 'note': hotlist_issue.note}
        for hotlist_issue in hotlist_issues if
        hotlist_issue.issue_id in allowed_iids}

  with mr.profiler.Phase('Making user views'):
    issues_users_by_id = framework_views.MakeAllUserViews(
        mr.cnxn, services.user,
        tracker_bizobj.UsersInvolvedInIssues(allowed_issues or []))
    issues_users_by_id.update(issue_adders)

  with mr.profiler.Phase('Sorting issues'):
    sortable_fields = tracker_helpers.SORTABLE_FIELDS.copy()
    sortable_fields.update(
        {'rank': lambda issue: hotlist_issues_context[
            issue.issue_id]['issue_rank'],
         'adder': lambda issue: hotlist_issues_context[
             issue.issue_id]['adder_id'],
         'added': lambda issue: hotlist_issues_context[
             issue.issue_id]['date_added'],
         'note': lambda issue: hotlist_issues_context[
             issue.issue_id]['note']})
    sortable_postproc = tracker_helpers.SORTABLE_FIELDS_POSTPROCESSORS.copy()
    sortable_postproc.update(
        {'adder': lambda user_view: user_view.email,
        })
    if not mr.sort_spec:
      mr.sort_spec = 'rank'
    sorted_issues = sorting.SortArtifacts(
        mr, allowed_issues, harmonized_config, sortable_fields,
        sortable_postproc,
        users_by_id=issues_users_by_id, tie_breakers=['rank', 'id'])
    return sorted_issues, hotlist_issues_context, issues_users_by_id


def CreateHotlistTableData(mr, hotlist_issues, services):
  """Creates the table data for the hotlistissues table."""
  with mr.profiler.Phase('getting stars'):
    starred_iid_set = set(services.issue_star.LookupStarredItemIDs(
        mr.cnxn, mr.auth.user_id))

  with mr.profiler.Phase('Computing col_spec'):
    mr.ComputeColSpec(mr.hotlist)

  issues_list = services.issue.GetIssues(
        mr.cnxn,
        [hotlist_issue.issue_id for hotlist_issue in hotlist_issues])
  with mr.profiler.Phase('Getting config'):
    hotlist_issues_project_ids = GetAllProjectsOfIssues(
        [issue for issue in issues_list])
    is_cross_project = len(hotlist_issues_project_ids) > 1
    config_list = GetAllConfigsOfProjects(
        mr.cnxn, hotlist_issues_project_ids, services)
    harmonized_config = tracker_bizobj.HarmonizeConfigs(config_list)

  (sorted_issues, hotlist_issues_context,
   issues_users_by_id) = GetSortedHotlistIssues(
       mr, hotlist_issues, issues_list, harmonized_config, services)

  with mr.profiler.Phase("getting related issues"):
    related_iids = set()
    results_needing_related = sorted_issues
    lower_cols = mr.col_spec.lower().split()
    for issue in results_needing_related:
      if 'blockedon' in lower_cols:
        related_iids.update(issue.blocked_on_iids)
      if 'blocking' in lower_cols:
        related_iids.update(issue.blocking_iids)
      if 'mergedinto' in lower_cols:
        related_iids.add(issue.merged_into)
    related_issues_list = services.issue.GetIssues(
        mr.cnxn, list(related_iids))
    related_issues = {issue.issue_id: issue for issue in related_issues_list}

  with mr.profiler.Phase('building table'):
    context_for_all_issues = {
        issue.issue_id: hotlist_issues_context[issue.issue_id]
                              for issue in sorted_issues}

    column_values = table_view_helpers.ExtractUniqueValues(
        mr.col_spec.lower().split(), sorted_issues, issues_users_by_id,
        harmonized_config, related_issues,
        hotlist_context_dict=context_for_all_issues)
    unshown_columns = table_view_helpers.ComputeUnshownColumns(
        sorted_issues, mr.col_spec.split(), harmonized_config,
        features_constants.OTHER_BUILT_IN_COLS)
    pagination = paginate.ArtifactPagination(
        mr, sorted_issues, mr.num,
        GetURLOfHotlist(mr.cnxn, mr.hotlist, services.user), len(sorted_issues))

    sort_spec = '%s %s %s' % (
        mr.group_by_spec, mr.sort_spec, harmonized_config.default_sort_spec)

    table_data = _MakeTableData(
        pagination.visible_results, starred_iid_set,
        mr.col_spec.lower().split(), mr.group_by_spec.lower().split(),
        issues_users_by_id, tablecell.CELL_FACTORIES, related_issues,
        harmonized_config, context_for_all_issues, mr.hotlist_id, sort_spec)

  table_related_dict = {
      'column_values': column_values, 'unshown_columns': unshown_columns,
      'pagination': pagination, 'is_cross_project': is_cross_project }
  return table_data, table_related_dict


def _MakeTableData(issues, starred_iid_set, lower_columns,
                   lower_group_by, users_by_id, cell_factories,
                   related_issues, config, context_for_all_issues,
                   hotlist_id, sort_spec):
  """Returns data from MakeTableData after adding additional information."""
  table_data = table_view_helpers.MakeTableData(
      issues, starred_iid_set, lower_columns, lower_group_by,
      users_by_id, cell_factories, lambda issue: issue.issue_id,
      related_issues, config, context_for_all_issues)

  for row, art in zip(table_data, issues):
    row.issue_id = art.issue_id
    row.local_id = art.local_id
    row.project_name = art.project_name
    row.project_url = framework_helpers.FormatURL(
        None, '/p/%s' % row.project_name)
    row.issue_ref = '%s:%d' % (art.project_name, art.local_id)
    row.issue_clean_url = tracker_helpers.FormatRelativeIssueURL(
        art.project_name, urls.ISSUE_DETAIL, id=art.local_id)
    row.issue_ctx_url = tracker_helpers.FormatRelativeIssueURL(
        art.project_name, urls.ISSUE_DETAIL,
        id=art.local_id, sort=sort_spec, hotlist_id=hotlist_id)

  return table_data


def FilterIssues(mr, issues, services):
  """Return a list of issues that the user is allowed to view."""
  allowed_issues = []
  project_ids = GetAllProjectsOfIssues(issues)
  issue_projects = services.project.GetProjects(mr.cnxn, project_ids)
  configs_by_project_id = services.config.GetProjectConfigs(
      mr.cnxn, project_ids)
  perms_by_project_id = {
      pid: permissions.GetPermissions(
          mr.auth.user_pb, mr.auth.effective_ids, p)
      for pid, p in issue_projects.items()}
  for issue in issues:
    if (mr.can == 1) or not issue.closed_timestamp:
      issue_project = issue_projects[issue.project_id]
      config = configs_by_project_id[issue.project_id]
      perms = perms_by_project_id[issue.project_id]
      granted_perms = tracker_bizobj.GetGrantedPerms(
          issue, mr.auth.effective_ids, config)
      permit_view = permissions.CanViewIssue(
          mr.auth.effective_ids, perms,
          issue_project, issue, granted_perms=granted_perms)
      if permit_view:
        allowed_issues.append(issue)

  return allowed_issues


def GetAllConfigsOfProjects(cnxn, project_ids, services):
  """Returns a list of configs for the given list of projects."""
  config_dict = services.config.GetProjectConfigs(cnxn, project_ids)
  config_list = [config_dict[project_id] for project_id in project_ids]
  return config_list


def GetAllProjectsOfIssues(issues):
  """Returns a list of all projects that the given issues are in."""
  project_ids = set()
  for issue in issues:
    project_ids.add(issue.project_id)
  return project_ids


def MembersWithoutGivenIDs(hotlist, exclude_ids):
  """Return three lists of member user IDs, with exclude_ids not in them."""
  owner_ids = [user_id for user_id in hotlist.owner_ids
               if user_id not in exclude_ids]
  editor_ids = [user_id for user_id in hotlist.editor_ids
                   if user_id not in exclude_ids]
  follower_ids = [user_id for user_id in hotlist.follower_ids
                     if user_id not in exclude_ids]

  return owner_ids, editor_ids, follower_ids


def MembersWithGivenIDs(hotlist, new_member_ids, role):
  """Return three lists of member IDs with the new IDs in the right one.

  Args:
    hotlist: Hotlist PB for the project to get current members from.
    new_member_ids: set of user IDs for members being added.
    role: string name of the role that new_member_ids should be granted.

  Returns:
    Three lists of member IDs with new_member_ids added to the appropriate
    list and removed from any other role.

  Raises:
    ValueError: if the role is not one of owner, committer, or contributor.
  """
  owner_ids, editor_ids, follower_ids = MembersWithoutGivenIDs(
      hotlist, new_member_ids)

  if role == 'owner':
    owner_ids.extend(new_member_ids)
  elif role == 'editor':
    editor_ids.extend(new_member_ids)
  elif role == 'follower':
    follower_ids.extend(new_member_ids)
  else:
    raise ValueError()

  return owner_ids, editor_ids, follower_ids


def GetURLOfHotlist(cnxn, hotlist, user_service, url_for_token=False):
    """Determines the url to be used to access the given hotlist.

    Args:
      cnxn: connection to SQL database
      hotlist: the hotlist_pb
      user_service: interface to user data storage
      url_for_token: if true, url returned will use user's id
        regardless of their user settings, for tokenization.

    Returns:
      The string url to be used when accessing this hotlist.
    """
    if not hotlist.owner_ids:  # Should never happen.
      logging.error('Unowned Hotlist: id:%r, name:%r', hotlist.hotlist_id,
                                                       hotlist.name)
      return ''
    owner_id = hotlist.owner_ids[0]  # only one owner allowed
    owner = user_service.GetUser(cnxn, owner_id)
    if owner.obscure_email or url_for_token:
      return '/u/%d/hotlists/%s' % (owner_id, hotlist.name)
    return (
        '/u/%s/hotlists/%s' % (
            owner.email, hotlist.name))


def RemoveHotlist(cnxn, hotlist_id, services):
  """Removes the given hotlist from the database.
    Args:
      hotlist_id: the id of the hotlist to be removed.
      services: interfaces to data storage.
  """
  services.hotlist_star.ExpungeStars(cnxn, hotlist_id)
  services.user.DeleteHotlistFromHistory(cnxn, hotlist_id)
  services.features.DeleteHotlist(cnxn, hotlist_id)


# The following are used by issueentry.

def InvalidParsedHotlistRefsNames(parsed_hotlist_refs, user_hotlist_pbs):
  """Find and return all names without a corresponding hotlist so named.

  Args:
    parsed_hotlist_refs: a list of ParsedHotlistRef objects
    user_hotlist_pbs: the hotlist protobuf objects of all hotlists
      belonging to the user

  Returns:
    a list of invalid names; if none are found, the empty list
  """
  user_hotlist_names = {hotlist.name for hotlist in user_hotlist_pbs}
  invalid_names = list()
  for parsed_ref in parsed_hotlist_refs:
    if parsed_ref.hotlist_name not in user_hotlist_names:
      invalid_names.append(parsed_ref.hotlist_name)
  return invalid_names


def AmbiguousShortrefHotlistNames(short_refs, user_hotlist_pbs):
  """Find and return ambiguous hotlist shortrefs' hotlist names.

  A hotlist shortref is ambiguous iff there exists more than
  hotlist with that name in the user's hotlists.

  Args:
    short_refs: a list of ParsedHotlistRef object specifying only
      a hotlist name (user_email being none)
    user_hotlist_pbs: the hotlist protobuf objects of all hotlists
      belonging to the user

  Returns:
    a list of ambiguous hotlist names; if none are found, the empty list
  """
  ambiguous_names = set()
  seen = set()
  for hotlist in user_hotlist_pbs:
    if hotlist.name in seen:
      ambiguous_names.add(hotlist.name)
    seen.add(hotlist.name)
  ambiguous_from_refs = list()
  for ref in short_refs:
    if ref.hotlist_name in ambiguous_names:
      ambiguous_from_refs.append(ref.hotlist_name)
  return ambiguous_from_refs


def InvalidParsedHotlistRefsEmails(full_refs, user_hotlist_emails_to_owners):
  """Find and return invalid e-mails in hotlist full refs.

  Args:
    full_refs: a list of ParsedHotlistRef object specifying both
      user_email and hotlist_name
    user_hotlist_emails_to_owners: a dictionary having for its keys only
      the e-mails of the owners of the hotlists the user had edit permission
      over. (Could also be a set containing these e-mails.)

  Returns:
    A list of invalid e-mails; if none are found, the empty list.
  """
  parsed_emails = [pref.user_email for pref in full_refs]
  invalid_emails = list()
  for email in parsed_emails:
    if email not in user_hotlist_emails_to_owners:
      invalid_emails.append(email)
  return invalid_emails


def GetHotlistsOfParsedHotlistFullRefs(
    full_refs, user_hotlist_emails_to_owners, user_hotlist_refs_to_pbs):
  """Check that all full refs are valid.

  A ref is 'invalid' if it doesn't specify one of the user's hotlists.

  Args:
    full_refs: a list of ParsedHotlistRef object specifying both
      user_email and hotlist_name
    user_hotlist_emails_to_owners: a dictionary having for its keys only
      the e-mails of the owners of the hotlists the user had edit permission
      over.
    user_hotlist_refs_to_pbs: a dictionary mapping HotlistRefs
      (owner_id, hotlist_name) to the corresponding hotlist protobuf object for
      the user's hotlists

  Returns:
    A two-tuple: (list of valid refs' corresponding hotlist protobuf objects,
                  list of invalid refs)

  """
  invalid_refs = list()
  valid_pbs = list()
  for parsed_ref in full_refs:
    hotlist_ref = HotlistRef(
        user_hotlist_emails_to_owners[parsed_ref.user_email],
        parsed_ref.hotlist_name)
    if hotlist_ref not in user_hotlist_refs_to_pbs:
      invalid_refs.append(parsed_ref)
    else:
      valid_pbs.append(user_hotlist_refs_to_pbs[hotlist_ref])
  return valid_pbs, invalid_refs
