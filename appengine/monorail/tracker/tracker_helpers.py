# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Helper functions and classes used by the Monorail Issue Tracker pages.

This module has functions that are reused in multiple servlets or
other modules.
"""

import collections
import logging
import re
import urllib

import settings

from framework import authdata
from framework import filecontent
from framework import framework_bizobj
from framework import framework_constants
from framework import framework_helpers
from framework import framework_views
from framework import permissions
from framework import sorting
from framework import template_helpers
from framework import urls
from tracker import tracker_bizobj
from tracker import tracker_constants


# HTML input field names for blocked on and blocking issue refs.
BLOCKED_ON = 'blocked_on'
BLOCKING = 'blocking'

# This string is used in HTML form element names to identify custom fields.
# E.g., a value for a custom field with field_id 12 would be specified in
# an HTML form element with name="custom_12".
_CUSTOM_FIELD_NAME_PREFIX = 'custom_'

# When the attachment quota gets within 1MB of the limit, stop offering
# users the option to attach files.
_SOFT_QUOTA_LEEWAY = 1024 * 1024

# Accessors for sorting built-in fields.
SORTABLE_FIELDS = {
    'project': lambda issue: issue.project_name,
    'id': lambda issue: issue.local_id,
    'owner': tracker_bizobj.GetOwnerId,  # And postprocessor
    'reporter': lambda issue: issue.reporter_id,  # And postprocessor
    'component': lambda issue: issue.component_ids,
    'cc': tracker_bizobj.GetCcIds,  # And postprocessor
    'summary': lambda issue: issue.summary.lower(),
    'stars': lambda issue: issue.star_count,
    'attachments': lambda issue: issue.attachment_count,
    'opened': lambda issue: issue.opened_timestamp,
    'closed': lambda issue: issue.closed_timestamp,
    'modified': lambda issue: issue.modified_timestamp,
    'status': tracker_bizobj.GetStatus,
    'blocked': lambda issue: bool(issue.blocked_on_iids),
    'blockedon': lambda issue: issue.blocked_on_iids or sorting.MAX_STRING,
    'blocking': lambda issue: issue.blocking_iids or sorting.MAX_STRING,
    'mergedinto': lambda issue: issue.merged_into or sorting.MAX_STRING,
    'ownermodified': lambda issue: issue.owner_modified_timestamp,
    'statusmodified': lambda issue: issue.status_modified_timestamp,
    'componentmodified': lambda issue: issue.component_modified_timestamp,
    'ownerlastvisit': tracker_bizobj.GetOwnerId,  # And postprocessor
    }

# Some fields take a user ID from the issue and then use that to index
# into a dictionary of user views, and then get a field of the user view
# as the value to sort key.
SORTABLE_FIELDS_POSTPROCESSORS = {
    'owner': lambda user_view: user_view.email,
    'reporter': lambda user_view: user_view.email,
    'cc': lambda user_view: user_view.email,
    'ownerlastvisit': lambda user_view: -user_view.user.last_visit_timestamp,
    }

# Namedtuples that hold data parsed from post_data.
ParsedComponents = collections.namedtuple(
    'ParsedComponents', 'entered_str, paths, paths_remove')
ParsedFields = collections.namedtuple(
    'ParsedFields', 'vals, vals_remove, fields_clear')
ParsedUsers = collections.namedtuple(
    'ParsedUsers', 'owner_username, owner_id, cc_usernames, '
    'cc_usernames_remove, cc_ids, cc_ids_remove')
ParsedBlockers = collections.namedtuple(
    'ParsedBlockers', 'entered_str, iids, dangling_refs')
ParsedHotlistRef = collections.namedtuple(
    'ParsedHotlistRef', 'user_email, hotlist_name')
ParsedHotlists = collections.namedtuple(
    'ParsedHotlists', 'entered_str, hotlist_refs')
ParsedIssue = collections.namedtuple(
    'ParsedIssue', 'summary, comment, is_description, status, users, labels, '
    'labels_remove, components, fields, template_name, attachments, '
    'kept_attachments, blocked_on, blocking, hotlists')


def ParseIssueRequest(cnxn, post_data, services, errors, default_project_name):
  """Parse all the possible arguments out of the request.

  Args:
    cnxn: connection to SQL database.
    post_data: HTML form information.
    services: Connections to persistence layer.
    errors: object to accumulate validation error info.
    default_project_name: name of the project that contains the issue.

  Returns:
    A namedtuple with all parsed information.  User IDs are looked up, but
    also the strings are returned to allow bouncing the user back to correct
    any errors.
  """
  summary = post_data.get('summary', '')
  comment = post_data.get('comment', '')
  is_description = bool(post_data.get('description', ''))
  status = post_data.get('status', '')
  template_name = post_data.get('template_name', '')
  component_str = post_data.get('components', '')
  label_strs = post_data.getall('label')

  comp_paths, comp_paths_remove = _ClassifyPlusMinusItems(
      re.split('[,;\s]+', component_str))
  parsed_components = ParsedComponents(
      component_str, comp_paths, comp_paths_remove)
  labels, labels_remove = _ClassifyPlusMinusItems(label_strs)
  parsed_fields = _ParseIssueRequestFields(post_data)
  # TODO(jrobbins): change from numbered fields to a multi-valued field.
  attachments = _ParseIssueRequestAttachments(post_data)
  kept_attachments = _ParseIssueRequestKeptAttachments(post_data)
  parsed_users = _ParseIssueRequestUsers(cnxn, post_data, services)
  parsed_blocked_on = _ParseBlockers(
      cnxn, post_data, services, errors, default_project_name, BLOCKED_ON)
  parsed_blocking = _ParseBlockers(
      cnxn, post_data, services, errors, default_project_name, BLOCKING)
  parsed_hotlists = _ParseHotlists(post_data)

  parsed_issue = ParsedIssue(
      summary, comment, is_description, status, parsed_users, labels,
      labels_remove, parsed_components, parsed_fields, template_name,
      attachments, kept_attachments, parsed_blocked_on, parsed_blocking,
      parsed_hotlists)
  return parsed_issue


def _ClassifyPlusMinusItems(add_remove_list):
  """Classify the given plus-or-minus items into add and remove lists."""
  add_remove_set = {s.strip() for s in add_remove_list}
  add_strs = [s for s in add_remove_set if s and not s.startswith('-')]
  remove_strs = [s[1:] for s in add_remove_set if s[1:] and s.startswith('-')]
  return add_strs, remove_strs


def _ParseHotlists(post_data):
  entered_str = post_data.get('hotlists', '').strip()
  hotlist_refs = []
  for ref_str in re.split('[,;\s]+', entered_str):
    if not ref_str:
      continue
    if ':' in ref_str:
      if ref_str.split(':')[0]:
        # E-mail isn't empty; full reference.
        hotlist_refs.append(ParsedHotlistRef(*ref_str.split(':', 1)))
      else:
        # Short reference.
        hotlist_refs.append(ParsedHotlistRef(None, ref_str.split(':', 1)[1]))
    else:
      # Short reference
      hotlist_refs.append(ParsedHotlistRef(None, ref_str))
  parsed_hotlists = ParsedHotlists(entered_str, hotlist_refs)
  return parsed_hotlists


def _ParseIssueRequestFields(post_data):
  """Iterate over post_data and return custom field values found in it."""
  field_val_strs = {}
  field_val_strs_remove = {}
  for key in post_data.keys():
    if key.startswith(_CUSTOM_FIELD_NAME_PREFIX):
      val_strs = [v for v in post_data.getall(key) if v]
      if val_strs:
        field_id = int(key[len(_CUSTOM_FIELD_NAME_PREFIX):])
        if post_data.get('op_' + key) == 'remove':
          field_val_strs_remove[field_id] = val_strs
        else:
          field_val_strs[field_id] = val_strs

  fields_clear = []
  op_prefix = 'op_' + _CUSTOM_FIELD_NAME_PREFIX
  for op_key in post_data.keys():
    if op_key.startswith(op_prefix):
      if post_data.get(op_key) == 'clear':
        field_id = int(op_key[len(op_prefix):])
        fields_clear.append(field_id)

  return ParsedFields(field_val_strs, field_val_strs_remove, fields_clear)


def _ParseIssueRequestAttachments(post_data):
  """Extract and clean-up any attached files from the post data.

  Args:
    post_data: dict w/ values from the user's HTTP POST form data.

  Returns:
    [(filename, filecontents, mimetype), ...] with items for each attachment.
  """
  # TODO(jrobbins): change from numbered fields to a multi-valued field.
  attachments = []
  for i in xrange(1, 16):
    if 'file%s' % i in post_data:
      item = post_data['file%s' % i]
      if isinstance(item, basestring):
        continue
      if '\\' in item.filename:  # IE insists on giving us the whole path.
        item.filename = item.filename[item.filename.rindex('\\') + 1:]
      if not item.filename:
        continue  # Skip any FILE fields that were not filled in.
      attachments.append((
          item.filename, item.value,
          filecontent.GuessContentTypeFromFilename(item.filename)))

  return attachments


def _ParseIssueRequestKeptAttachments(post_data):
  """Extract attachment ids for attachments kept when updating description

  Args:
    post_data: dict w/ values from the user's HTTP POST form data.

  Returns:
    a list of attachment ids for kept attachments
  """
  kept_attachments = post_data.getall('keep-attachment')
  return [int(aid) for aid in kept_attachments]


def _ParseIssueRequestUsers(cnxn, post_data, services):
  """Extract usernames from the POST data, categorize them, and look up IDs.

  Args:
    cnxn: connection to SQL database.
    post_data: dict w/ data from the HTTP POST.
    services: Services.

  Returns:
    A namedtuple (owner_username, owner_id, cc_usernames, cc_usernames_remove,
    cc_ids, cc_ids_remove), containing:
      - issue owner's name and user ID, if any
      - the list of all cc'd usernames
      - the user IDs to add or remove from the issue CC list.
    Any of these user IDs may be  None if the corresponding username
    or email address is invalid.
  """
  # Get the user-entered values from post_data.
  cc_username_str = post_data.get('cc', '').lower()
  owner_email = post_data.get('owner', '').strip().lower()

  cc_usernames, cc_usernames_remove = _ClassifyPlusMinusItems(
      re.split('[,;\s]+', cc_username_str))

  # Figure out the email addresses to lookup and do the lookup.
  emails_to_lookup = cc_usernames + cc_usernames_remove
  if owner_email:
    emails_to_lookup.append(owner_email)
  all_user_ids = services.user.LookupUserIDs(
      cnxn, emails_to_lookup, autocreate=True)
  if owner_email:
    owner_id = all_user_ids.get(owner_email)
  else:
    owner_id = framework_constants.NO_USER_SPECIFIED

  # Lookup the user IDs of the Cc addresses to add or remove.
  cc_ids = [all_user_ids.get(cc) for cc in cc_usernames]
  cc_ids_remove = [all_user_ids.get(cc) for cc in cc_usernames_remove]

  return ParsedUsers(owner_email, owner_id, cc_usernames, cc_usernames_remove,
                     cc_ids, cc_ids_remove)


def _ParseBlockers(cnxn, post_data, services, errors, default_project_name,
                   field_name):
  """Parse input for issues that the current issue is blocking/blocked on.

  Args:
    cnxn: connection to SQL database.
    post_data: dict w/ values from the user's HTTP POST.
    services: connections to backend services.
    errors: object to accumulate validation error info.
    default_project_name: name of the project that contains the issue.
    field_name: string HTML input field name, e.g., BLOCKED_ON or BLOCKING.

  Returns:
    A namedtuple with the user input string, and a list of issue IDs.
  """
  entered_str = post_data.get(field_name, '').strip()
  blocker_iids = []
  dangling_ref_tuples = []

  issue_ref = None
  for ref_str in re.split('[,;\s]+', entered_str):
    try:
      issue_ref = tracker_bizobj.ParseIssueRef(ref_str)
    except ValueError:
      setattr(errors, field_name, 'Invalid issue ID %s' % ref_str.strip())
      break

    if not issue_ref:
      continue

    blocker_project_name, blocker_issue_id = issue_ref
    if not blocker_project_name:
      blocker_project_name = default_project_name

    # Detect and report if the same issue was specified.
    current_issue_id = int(post_data.get('id')) if post_data.get('id') else -1
    if (blocker_issue_id == current_issue_id and
        blocker_project_name == default_project_name):
      setattr(errors, field_name, 'Cannot be %s the same issue' % field_name)
      break

    ref_projects = services.project.GetProjectsByName(
        cnxn, set([blocker_project_name]))
    blocker_iid, _misses = services.issue.ResolveIssueRefs(
        cnxn, ref_projects, default_project_name, [issue_ref])
    if not blocker_iid:
      if blocker_project_name in settings.recognized_codesite_projects:
        # We didn't find the issue, but it had a explicitly-specified project
        # which we know is on Codesite. Allow it as a dangling reference.
        dangling_ref_tuples.append(issue_ref)
        continue
      else:
        # Otherwise, it doesn't exist, so report it.
        setattr(errors, field_name, 'Invalid issue ID %s' % ref_str.strip())
        break
    if blocker_iid[0] not in blocker_iids:
      blocker_iids.extend(blocker_iid)

  blocker_iids.sort()
  dangling_ref_tuples.sort()
  return ParsedBlockers(entered_str, blocker_iids, dangling_ref_tuples)


def IsValidIssueOwner(cnxn, project, owner_id, services):
  """Return True if the given user ID can be an issue owner.

  Args:
    cnxn: connection to SQL database.
    project: the current Project PB.
    owner_id: the user ID of the proposed issue owner.
    services: connections to backends.

  It is OK to have 0 for the owner_id, that simply means that the issue is
  unassigned.

  Returns:
    A pair (valid, err_msg).  valid is True if the given user ID can be an
    issue owner. err_msg is an error message string to display to the user
    if valid == False, and is None if valid == True.
  """
  # An issue is always allowed to have no owner specified.
  if owner_id == framework_constants.NO_USER_SPECIFIED:
    return True, None

  auth = authdata.AuthData.FromUserID(cnxn, owner_id, services)
  if not framework_bizobj.UserIsInProject(project, auth.effective_ids):
    return False, 'Issue owner must be a project member'

  group_ids = services.usergroup.DetermineWhichUserIDsAreGroups(
      cnxn, [owner_id])
  if owner_id in group_ids:
    return False, 'Issue owner cannot be a user group'

  return True, None


def GetAllowedOpenedAndClosedIssues(mr, issue_ids, services):
  """Get filtered lists of open and closed issues identified by issue_ids.

  The function then filters the results to only the issues that the user
  is allowed to view.  E.g., we only auto-link to issues that the user
  would be able to view if he/she clicked the link.

  Args:
    mr: commonly used info parsed from the request.
    issue_ids: list of int issue IDs for the target issues.
    services: connection to issue, config, and project persistence layers.

  Returns:
    Two lists of issues that the user is allowed to view: one for open
    issues and one for closed issues.
  """
  open_issues, closed_issues = services.issue.GetOpenAndClosedIssues(
      mr.cnxn, issue_ids)
  project_dict = GetAllIssueProjects(
      mr.cnxn, open_issues + closed_issues, services.project)
  config_dict = services.config.GetProjectConfigs(mr.cnxn, project_dict.keys())
  allowed_open_issues = FilterOutNonViewableIssues(
      mr.auth.effective_ids, mr.auth.user_pb, project_dict, config_dict,
      open_issues)
  allowed_closed_issues = FilterOutNonViewableIssues(
      mr.auth.effective_ids, mr.auth.user_pb, project_dict, config_dict,
      closed_issues)

  return allowed_open_issues, allowed_closed_issues


def GetAllowedOpenAndClosedRelatedIssues(services, mr, issue):
  """Retrieve the issues that the given issue references.

  Related issues are the blocked on, blocking, and merged-into issues.
  This function also filters the results to only the issues that the
  user is allowed to view.

  Args:
    services: connection to issue, config, and project persistence layers.
    mr: commonly used info parsed from the request.
    issue: the Issue PB being viewed.

  Returns:
    Two dictionaries of issues that the user is allowed to view: one for open
    issues and one for closed issues.
  """
  related_issue_iids = list(issue.blocked_on_iids) + list(issue.blocking_iids)
  if issue.merged_into:
    related_issue_iids.append(issue.merged_into)
  open_issues, closed_issues = GetAllowedOpenedAndClosedIssues(
      mr, related_issue_iids, services)
  open_dict = {issue.issue_id: issue for issue in open_issues}
  closed_dict = {issue.issue_id: issue for issue in closed_issues}
  return open_dict, closed_dict


def MakeViewsForUsersInIssues(cnxn, issue_list, user_service, omit_ids=None):
  """Lookup all the users involved in any of the given issues.

  Args:
    cnxn: connection to SQL database.
    issue_list: list of Issue PBs from a result query.
    user_service: Connection to User backend storage.
    omit_ids: a list of user_ids to omit, e.g., because we already have them.

  Returns:
    A dictionary {user_id: user_view,...} for all the users involved
    in the given issues.
  """
  issue_participant_id_set = tracker_bizobj.UsersInvolvedInIssues(issue_list)
  if omit_ids:
    issue_participant_id_set.difference_update(omit_ids)

  # TODO(jrobbins): consider caching View objects as well.
  users_by_id = framework_views.MakeAllUserViews(
      cnxn, user_service, issue_participant_id_set)

  return users_by_id


def FormatIssueListURL(
    mr, config, absolute=True, project_names=None, **kwargs):
  """Format a link back to list view as configured by user."""
  if project_names is None:
    project_names = [mr.project_name]
  if not tracker_constants.JUMP_RE.match(mr.query):
    kwargs['q'] = mr.query
    if mr.can and mr.can != 2:
      kwargs['can'] = mr.can
  def_col_spec = config.default_col_spec
  if mr.col_spec and mr.col_spec != def_col_spec:
    kwargs['colspec'] = mr.col_spec
  if mr.sort_spec:
    kwargs['sort'] = mr.sort_spec
  if mr.group_by_spec:
    kwargs['groupby'] = mr.group_by_spec
  if mr.start:
    kwargs['start'] = mr.start
  if mr.num != tracker_constants.DEFAULT_RESULTS_PER_PAGE:
    kwargs['num'] = mr.num

  if len(project_names) == 1:
    url = '/p/%s%s' % (project_names[0], urls.ISSUE_LIST)
  else:
    url = urls.ISSUE_LIST
    kwargs['projects'] = ','.join(sorted(project_names))

  param_strings = ['%s=%s' % (k, urllib.quote((u'%s' % v).encode('utf-8')))
                   for k, v in kwargs.iteritems()]
  if param_strings:
    url += '?' + '&'.join(sorted(param_strings))
  if absolute:
    url = '%s://%s%s' % (mr.request.scheme, mr.request.host, url)

  return url


def FormatRelativeIssueURL(project_name, path, **kwargs):
  """Format a URL to get to an issue in the named project.

  Args:
    project_name: string name of the project containing the issue.
    path: string servlet path, e.g., from framework/urls.py.
    **kwargs: additional query-string parameters to include in the URL.

  Returns:
    A URL string.
  """
  return framework_helpers.FormatURL(
      None, '/p/%s%s' % (project_name, path), **kwargs)


def ComputeNewQuotaBytesUsed(project, attachments):
  """Add the given attachments to the project's attachment quota usage.

  Args:
    project: Project PB  for the project being updated.
    attachments: a list of attachments being added to an issue.

  Returns:
    The new number of bytes used.

  Raises:
    OverAttachmentQuota: If project would go over quota.
  """
  total_attach_size = 0L
  for _filename, content, _mimetype in attachments:
    total_attach_size += len(content)

  new_bytes_used = project.attachment_bytes_used + total_attach_size
  quota = (project.attachment_quota or
           tracker_constants.ISSUE_ATTACHMENTS_QUOTA_HARD)
  if new_bytes_used > quota:
    raise OverAttachmentQuota(new_bytes_used - quota)
  return new_bytes_used


def IsUnderSoftAttachmentQuota(project):
  """Check the project's attachment quota against the soft quota limit.

  If there is a custom quota on the project, this will check against
  that instead of the system-wide default quota.

  Args:
    project: Project PB for the project to examine

  Returns:
    True if the project is under quota, false otherwise.
  """
  quota = tracker_constants.ISSUE_ATTACHMENTS_QUOTA_SOFT
  if project.attachment_quota:
    quota = project.attachment_quota - _SOFT_QUOTA_LEEWAY

  return project.attachment_bytes_used < quota


def GetAllIssueProjects(cnxn, issues, project_service):
  """Get all the projects that the given issues belong to.

  Args:
    cnxn: connection to SQL database.
    issues: list of issues, which may come from different projects.
    project_service: connection to project persistence layer.

  Returns:
    A dictionary {project_id: project} of all the projects that
    any of the given issues belongs to.
  """
  needed_project_ids = {issue.project_id for issue in issues}
  project_dict = project_service.GetProjects(cnxn, needed_project_ids)
  return project_dict


def GetPermissionsInAllProjects(user, effective_ids, projects):
  """Look up the permissions for the given user in each project."""
  return {
      project.project_id:
      permissions.GetPermissions(user, effective_ids, project)
      for project in projects}


def FilterOutNonViewableIssues(
    effective_ids, user, project_dict, config_dict, issues):
  """Return a filtered list of issues that the user can view."""
  perms_dict = GetPermissionsInAllProjects(
      user, effective_ids, project_dict.values())

  denied_project_ids = {
      pid for pid, p in project_dict.iteritems()
      if not permissions.CanView(effective_ids, perms_dict[pid], p, [])}

  results = []
  for issue in issues:
    if issue.deleted or issue.project_id in denied_project_ids:
      continue

    if not permissions.HasRestrictions(issue):
      may_view = True
    else:
      perms = perms_dict[issue.project_id]
      project = project_dict[issue.project_id]
      config = config_dict.get(issue.project_id, config_dict.get('harmonized'))
      granted_perms = tracker_bizobj.GetGrantedPerms(
          issue, effective_ids, config)
      may_view = permissions.CanViewRestrictedIssueInVisibleProject(
          effective_ids, perms, project, issue, granted_perms=granted_perms)

    if may_view:
      results.append(issue)

  return results


def MeansOpenInProject(status, config):
  """Return true if this status means that the issue is still open.

  Args:
    status: issue status string. E.g., 'New'.
    config: the config of the current project.

  Returns:
    Boolean True if the status means that the issue is open.
  """
  status_lower = status.lower()

  # iterate over the list of known statuses for this project
  # return true if we find a match that declares itself to be open
  for wks in config.well_known_statuses:
    if wks.status.lower() == status_lower:
      return wks.means_open

  # if we didn't find a matching status we consider the status open
  return True


def IsNoisy(num_comments, num_starrers):
  """Return True if this is a "noisy" issue that would send a ton of emails.

  The rule is that a very active issue with a large number of comments
  and starrers will only send notification when a comment (or change)
  is made by a project member.

  Args:
    num_comments: int number of comments on issue so far.
    num_starrers: int number of users who starred the issue.

  Returns:
    True if we will not bother starrers with an email notification for
    changes made by non-members.
  """
  return (num_comments >= tracker_constants.NOISY_ISSUE_COMMENT_COUNT and
          num_starrers >= tracker_constants.NOISY_ISSUE_STARRER_COUNT)


def MergeCCsAndAddComment(
    services, mr, issue, merge_into_project, merge_into_issue):
  """Modify the CC field of the target issue and add a comment to it."""
  return MergeCCsAndAddCommentMultipleIssues(
      services, mr, [issue], merge_into_project, merge_into_issue)


def MergeCCsAndAddCommentMultipleIssues(
    services, mr, issues, merge_into_project, merge_into_issue):
  """Modify the CC field of the target issue and add a comment to it."""
  merge_into_restricts = permissions.GetRestrictions(merge_into_issue)
  merge_comment = ''
  source_cc = set()
  for issue in issues:
    if issue.project_name == merge_into_issue.project_name:
      issue_ref_str = '%d' % issue.local_id
    else:
      issue_ref_str = '%s:%d' % (issue.project_name, issue.local_id)
    if merge_comment:
      merge_comment += '\n'
    merge_comment += 'Issue %s has been merged into this issue.' % issue_ref_str

    if permissions.HasRestrictions(issue, perm='View'):
      restricts = permissions.GetRestrictions(issue)
      # Don't leak metadata from a restricted issue.
      if (issue.project_id != merge_into_issue.project_id or
          set(restricts) != set(merge_into_restricts)):
        # TODO(jrobbins): user option to choose to merge CC or not.
        # TODO(jrobbins): add a private comment rather than nothing
        continue

    source_cc.update(issue.cc_ids)
    if issue.owner_id:  # owner_id == 0 means no owner
      source_cc.update([issue.owner_id])

  target_cc = merge_into_issue.cc_ids
  add_cc = [user_id for user_id in source_cc if user_id not in target_cc]

  services.issue.ApplyIssueComment(
      mr.cnxn, services, mr.auth.user_id,
      merge_into_project.project_id, merge_into_issue.local_id,
      merge_into_issue.summary, merge_into_issue.status,
      merge_into_issue.owner_id, list(target_cc) + list(add_cc),
      merge_into_issue.labels, merge_into_issue.field_values,
      merge_into_issue.component_ids, merge_into_issue.blocked_on_iids,
      merge_into_issue.blocking_iids, merge_into_issue.dangling_blocked_on_refs,
      merge_into_issue.dangling_blocking_refs, merge_into_issue.merged_into,
      index_now=False, comment=merge_comment)

  return merge_comment


def GetAttachmentIfAllowed(mr, services):
  """Retrieve the requested attachment, or raise an appropriate exception.

  Args:
    mr: commonly used info parsed from the request.
    services: connections to backend services.

  Returns:
    The requested Attachment PB, and the Issue that it belongs to.

  Raises:
    NoSuchAttachmentException: attachment was not found or was marked deleted.
    NoSuchIssueException: issue that contains attachment was not found.
    PermissionException: the user is not allowed to view the attachment.
  """
  attachment = None

  attachment, cid, issue_id = services.issue.GetAttachmentAndContext(
      mr.cnxn, mr.aid)

  issue = services.issue.GetIssue(mr.cnxn, issue_id)
  config = services.config.GetProjectConfig(mr.cnxn, issue.project_id)
  granted_perms = tracker_bizobj.GetGrantedPerms(
      issue, mr.auth.effective_ids, config)
  permit_view = permissions.CanViewIssue(
      mr.auth.effective_ids, mr.perms, mr.project, issue,
      granted_perms=granted_perms)
  if not permit_view:
    raise permissions.PermissionException('Cannot view attachment\'s issue')

  comment = services.issue.GetComment(mr.cnxn, cid)
  can_delete = False
  if mr.auth.user_id and mr.project:
    can_delete = permissions.CanDelete(
        mr.auth.user_id, mr.auth.effective_ids, mr.perms,
        comment.deleted_by, comment.user_id, mr.project,
        permissions.GetRestrictions(issue), granted_perms=granted_perms)
  if comment.deleted_by and not can_delete:
    raise permissions.PermissionException('Cannot view attachment\'s comment')

  return attachment, issue


def LabelsMaskedByFields(config, field_names, trim_prefix=False):
  """Return a list of EZTItems for labels that would be masked by fields."""
  return _LabelsMaskedOrNot(config, field_names, trim_prefix=trim_prefix)


def LabelsNotMaskedByFields(config, field_names, trim_prefix=False):
  """Return a list of EZTItems for labels that would not be masked."""
  return _LabelsMaskedOrNot(
      config, field_names, invert=True, trim_prefix=trim_prefix)


def _LabelsMaskedOrNot(config, field_names, invert=False, trim_prefix=False):
  """Return EZTItems for labels that'd be masked. Or not, when invert=True."""
  field_names = [fn.lower() for fn in field_names]
  result = []
  for wkl in config.well_known_labels:
    masked_by = tracker_bizobj.LabelIsMaskedByField(wkl.label, field_names)
    if (masked_by and not invert) or (not masked_by and invert):
      display_name = wkl.label
      if trim_prefix:
        display_name = display_name[len(masked_by) + 1:]
      result.append(template_helpers.EZTItem(
          name=display_name,
          name_padded=display_name.ljust(20),
          commented='#' if wkl.deprecated else '',
          docstring=wkl.label_docstring,
          docstring_short=template_helpers.FitUnsafeText(
              wkl.label_docstring, 40),
          idx=len(result)))

  return result


def LookupComponentIDs(component_paths, config, errors):
  """Look up the IDs of the specified components in the given config."""
  component_ids = []
  for path in component_paths:
    if not path:
      continue
    cd = tracker_bizobj.FindComponentDef(path, config)
    if cd:
      component_ids.append(cd.component_id)
    else:
      errors.components = 'Unknown component %s' % path

  return component_ids


def ParseAdminUsers(cnxn, admins_str, user_service):
  """Parse all the usernames of component, field, or template admins."""
  admins, _remove = _ClassifyPlusMinusItems(
      re.split('[,;\s]+', admins_str))
  all_user_ids = user_service.LookupUserIDs(cnxn, admins, autocreate=True)
  admin_ids = [all_user_ids[username] for username in admins]
  return admin_ids, admins_str


def FilterIssueTypes(config):
  """Return a list of well-known issue types."""
  well_known_issue_types = []
  for wk_label in config.well_known_labels:
    if wk_label.label.lower().startswith('type-'):
      _, type_name = wk_label.label.split('-', 1)
      well_known_issue_types.append(type_name)

  return well_known_issue_types


def ParseMergeFields(
    cnxn, services, project_name, post_data, status, config, issue, errors):
  """Parse info that identifies the issue to merge into, if any."""
  merge_into_text = ''
  merge_into_ref = None
  merge_into_issue = None

  if status not in config.statuses_offer_merge:
    return '', None

  merge_into_text = post_data.get('merge_into', '')
  if merge_into_text:
    try:
      merge_into_ref = tracker_bizobj.ParseIssueRef(merge_into_text)
    except ValueError:
      logging.info('merge_into not an int: %r', merge_into_text)
      errors.merge_into_id = 'Please enter a valid issue ID'

  if not merge_into_ref:
    errors.merge_into_id = 'Please enter an issue ID'
    return merge_into_text, None

  merge_into_project_name, merge_into_id = merge_into_ref
  if (merge_into_id == issue.local_id and
      (merge_into_project_name == project_name or
       not merge_into_project_name)):
    logging.info('user tried to merge issue into itself: %r', merge_into_ref)
    errors.merge_into_id = 'Cannot merge issue into itself'
    return merge_into_text, None

  project = services.project.GetProjectByName(
      cnxn, merge_into_project_name or project_name)
  try:
    # Because we will modify this issue, load from DB rather than cache.
    merge_into_issue = services.issue.GetIssueByLocalID(
        cnxn, project.project_id, merge_into_id, use_cache=False)
  except Exception:
    logging.info('merge_into issue not found: %r', merge_into_ref)
    errors.merge_into_id = 'No such issue'
    return merge_into_text, None

  return merge_into_text, merge_into_issue


def GetNewIssueStarrers(cnxn, services, issue_id, merge_into_iid):
  """Get starrers of current issue who have not starred the target issue."""
  source_starrers = services.issue_star.LookupItemStarrers(cnxn, issue_id)
  target_starrers = services.issue_star.LookupItemStarrers(
      cnxn, merge_into_iid)
  return set(source_starrers) - set(target_starrers)


def AddIssueStarrers(
    cnxn, services, mr, merge_into_iid, merge_into_project, new_starrers):
  """Merge all the starrers for the current issue into the target issue."""
  project = merge_into_project or mr.project
  config = services.config.GetProjectConfig(mr.cnxn, project.project_id)
  services.issue_star.SetStarsBatch(
      cnxn, services, config, merge_into_iid, new_starrers, True)


def IsMergeAllowed(merge_into_issue, mr, services):
  """Check to see if user has permission to merge with specified issue."""
  merge_into_project = services.project.GetProjectByName(
      mr.cnxn, merge_into_issue.project_name)
  merge_into_config = services.config.GetProjectConfig(
      mr.cnxn, merge_into_project.project_id)
  merge_granted_perms = tracker_bizobj.GetGrantedPerms(
      merge_into_issue, mr.auth.effective_ids, merge_into_config)

  merge_view_allowed = mr.perms.CanUsePerm(
      permissions.VIEW, mr.auth.effective_ids,
      merge_into_project, permissions.GetRestrictions(merge_into_issue),
      granted_perms=merge_granted_perms)
  merge_edit_allowed = mr.perms.CanUsePerm(
      permissions.EDIT_ISSUE, mr.auth.effective_ids,
      merge_into_project, permissions.GetRestrictions(merge_into_issue),
      granted_perms=merge_granted_perms)

  return merge_view_allowed and merge_edit_allowed


class Error(Exception):
  """Base class for errors from this module."""


class OverAttachmentQuota(Error):
  """Project will exceed quota if the current operation is allowed."""
