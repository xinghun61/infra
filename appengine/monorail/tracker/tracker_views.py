# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""View objects to help display tracker business objects in templates."""

import collections
import logging
import re
import time
import urllib

from google.appengine.api import app_identity
from third_party import ezt

from framework import filecontent
from framework import framework_constants
from framework import framework_helpers
from framework import framework_views
from framework import gcs_helpers
from framework import permissions
from framework import template_helpers
from framework import timestr
from framework import urls
from proto import tracker_pb2
from services import user_svc
from tracker import tracker_bizobj
from tracker import tracker_constants
from tracker import tracker_helpers


class IssueView(template_helpers.PBProxy):
  """Wrapper class that makes it easier to display an Issue via EZT."""

  def __init__(
      self, issue, users_by_id, config, open_related=None,
      closed_related=None, all_related=None):
    """Store relevant values for later display by EZT.

    Args:
      issue: An Issue protocol buffer.
      users_by_id: dict {user_id: UserViews} for all users mentioned in issue.
      config: ProjectIssueConfig for this issue.
      open_related: dict of visible open issues that are related to this issue.
      closed_related: dict {issue_id: issue} of visible closed issues that
          are related to this issue.
      all_related: optional dict {issue_id: issue} of all blocked-on, blocking,
          or merged-into issues referenced from this issue, regardless of
          perms.
    """
    super(IssueView, self).__init__(issue)

    # The users involved in this issue must be present in users_by_id if
    # this IssueView is to be used on the issue detail or peek pages. But,
    # they can be absent from users_by_id if the IssueView is used as a
    # tile in the grid view.
    self.owner = users_by_id.get(issue.owner_id)
    self.derived_owner = users_by_id.get(issue.derived_owner_id)
    self.cc = [users_by_id.get(cc_id) for cc_id in issue.cc_ids
               if cc_id]
    self.derived_cc = [users_by_id.get(cc_id)
                       for cc_id in issue.derived_cc_ids
                       if cc_id]
    self.status = framework_views.StatusView(issue.status, config)
    self.derived_status = framework_views.StatusView(
        issue.derived_status, config)
    # If we don't have a config available, we don't need to access is_open, so
    # let it be True.
    self.is_open = ezt.boolean(
        not config or
        tracker_helpers.MeansOpenInProject(
            tracker_bizobj.GetStatus(issue), config))

    self.components = sorted(
        [ComponentValueView(component_id, config, False)
         for component_id in issue.component_ids
         if tracker_bizobj.FindComponentDefByID(component_id, config)] +
        [ComponentValueView(component_id, config, True)
         for component_id in issue.derived_component_ids
         if tracker_bizobj.FindComponentDefByID(component_id, config)],
        key=lambda cvv: cvv.path)

    self.fields = [
        MakeFieldValueView(
            fd, config, issue.labels, issue.derived_labels, issue.field_values,
            users_by_id)
        # TODO(jrobbins): field-level view restrictions, display options
        for fd in config.field_defs
        if not fd.is_deleted]
    self.fields = sorted(
        self.fields, key=lambda f: (f.applicable_type, f.field_name))

    field_names = [fd.field_name.lower() for fd in config.field_defs
                   if not fd.is_deleted]  # TODO(jrobbins): restricts
    self.labels = [
        framework_views.LabelView(label, config)
        for label in tracker_bizobj.NonMaskedLabels(issue.labels, field_names)]
    self.derived_labels = [
        framework_views.LabelView(label, config)
        for label in issue.derived_labels
        if not tracker_bizobj.LabelIsMaskedByField(label, field_names)]
    self.restrictions = _RestrictionsView(issue)

    # TODO(jrobbins): sort by order of labels in project config

    self.short_summary = issue.summary[:tracker_constants.SHORT_SUMMARY_LENGTH]

    if issue.closed_timestamp:
      self.closed = timestr.FormatAbsoluteDate(issue.closed_timestamp)
    else:
      self.closed = ''

    blocked_on_iids = issue.blocked_on_iids
    blocking_iids = issue.blocking_iids

    # Note that merged_into_str and blocked_on_str includes all issue
    # references, even those referring to issues that the user can't view,
    # so open_related and closed_related cannot be used.
    if all_related is not None:
      all_blocked_on_refs = [
          (all_related[ref_iid].project_name, all_related[ref_iid].local_id)
          for ref_iid in issue.blocked_on_iids]
      all_blocked_on_refs.extend([
          (r.project, r.issue_id) for r in issue.dangling_blocked_on_refs])
      self.blocked_on_str = ', '.join(
          tracker_bizobj.FormatIssueRef(
              ref, default_project_name=issue.project_name)
          for ref in all_blocked_on_refs)
      all_blocking_refs = [
          (all_related[ref_iid].project_name, all_related[ref_iid].local_id)
          for ref_iid in issue.blocking_iids]
      all_blocking_refs.extend([
          (r.project, r.issue_id) for r in issue.dangling_blocking_refs])
      self.blocking_str = ', '.join(
          tracker_bizobj.FormatIssueRef(
              ref, default_project_name=issue.project_name)
          for ref in all_blocking_refs)
      if issue.merged_into:
        merged_issue = all_related[issue.merged_into]
        merged_into_ref = merged_issue.project_name, merged_issue.local_id
      else:
        merged_into_ref = None
      self.merged_into_str = tracker_bizobj.FormatIssueRef(
          merged_into_ref, default_project_name=issue.project_name)

    self.blocked_on = []
    self.has_dangling = ezt.boolean(self.dangling_blocked_on_refs)
    self.blocking = []
    current_project_name = issue.project_name

    if (open_related is not None and closed_related is not None
        and all_related is not None):
      self.merged_into = IssueRefView(
          current_project_name, all_related.get(issue.merged_into),
          open_related, closed_related)

      self.blocked_on = [
          IssueRefView(
              current_project_name, all_related.get(iid),
              open_related, closed_related)
          for iid in blocked_on_iids]
      self.blocked_on.extend(
          [DanglingIssueRefView(ref.project, ref.issue_id)
           for ref in issue.dangling_blocked_on_refs])
      # TODO(jrobbins): sort by irv project_name and local_id

      self.blocking = [
          IssueRefView(
              current_project_name, all_related.get(iid),
              open_related, closed_related)
          for iid in blocking_iids]
      self.blocking.extend(
          [DanglingIssueRefView(ref.project, ref.issue_id)
           for ref in issue.dangling_blocking_refs])
      # TODO(jrobbins): sort by irv project_name and local_id

    visible_open_blocked_on = [
        irv for irv in self.blocked_on
        if (not irv.is_dangling and
            open_related and irv.issue_id in open_related)]
    self.multiple_blocked_on = ezt.boolean(len(visible_open_blocked_on) >= 2)
    self.detail_relative_url = tracker_helpers.FormatRelativeIssueURL(
        issue.project_name, urls.ISSUE_DETAIL, id=issue.local_id)


class _RestrictionsView(object):
  """An EZT object for the restrictions associated with an issue."""

  # Restrict label fragments that correspond to known permissions.
  _VIEW = permissions.VIEW.lower()
  _EDIT = permissions.EDIT_ISSUE.lower()
  _ADD_COMMENT = permissions.ADD_ISSUE_COMMENT.lower()
  _KNOWN_ACTION_KINDS = {_VIEW, _EDIT, _ADD_COMMENT}

  def __init__(self, issue):
    # List of restrictions that don't map to a known action kind.
    self.other = []

    restrictions_by_action = collections.defaultdict(list)
    # We can't use GetRestrictions here, as we prefer to preserve
    # the case of the label when showing restrictions in the UI.
    for label in tracker_bizobj.GetLabels(issue):
      if permissions.IsRestrictLabel(label):
        _kw, action_kind, needed_perm = label.split('-', 2)
        action_kind = action_kind.lower()
        if action_kind in self._KNOWN_ACTION_KINDS:
          restrictions_by_action[action_kind].append(needed_perm)
        else:
          self.other.append(label)

    self.view = ' and '.join(restrictions_by_action[self._VIEW])
    self.add_comment = ' and '.join(restrictions_by_action[self._ADD_COMMENT])
    self.edit = ' and '.join(restrictions_by_action[self._EDIT])

    self.has_restrictions = ezt.boolean(
        self.view or self.add_comment or self.edit or self.other)


class IssueRefView(object):
  """A simple object to easily display links to issues in EZT."""

  def __init__(
      self, current_project_name, related_issue, open_dict, closed_dict):
    """Make a simple object to display a link to a referenced issue.

    Args:
      current_project_name: string name of the current project.
      related_issue: issue PB of the target issue.
      open_dict: dict {issue_id: issue} of pre-fetched open issues that the
          user is allowed to view.
      closed_dict: dict of pre-fetched closed issues that the user is
          allowed to view.

    Note, the target issue may be a member of either open_dict or
    closed_dict, or neither one.  If neither, nothing is displayed.
    """
    if not related_issue:
      # Issue not found, so don't link to it.
      self.visible = ezt.boolean(False)
      self.url = None
      self.display_name = 'missing issue'
      self.issue_ref = None
      return

    self.issue_id = related_issue.issue_id
    self.visible = ezt.boolean(
        self.issue_id in open_dict or self.issue_id in closed_dict)
    self.is_open = ezt.boolean(self.issue_id in open_dict)

    if current_project_name == related_issue.project_name:
      self.url = 'detail?id=%s' % related_issue.local_id
      self.display_name = 'issue %s' % related_issue.local_id
      self.issue_ref = related_issue.local_id
    else:
      self.url = '/p/%s%s?id=%s' % (
          related_issue.project_name, urls.ISSUE_DETAIL,
          related_issue.local_id)
      self.display_name = 'issue %s:%s' % (
          related_issue.project_name, related_issue.local_id)
      self.issue_ref = self.display_name[6:]

    if self.visible:
      self.summary = related_issue.summary
    else:
      self.summary = None
      self.url = None

    self.is_dangling = ezt.boolean(False)

  def DebugString(self):
    if not self.visible:
      return 'IssueRefView(not visible)'

    return 'IssueRefView(%s)' % self.display_name


class DanglingIssueRefView(object):

  def __init__(self, project_name, issue_id):
    """Makes a simple object to display a link to an issue still in Codesite.

    Satisfies the same API and internal data members as IssueRefView,
    excpet for the arguments to __init__.

    Args:
      project_name: The name of the project on Codesite
      issue_id: The local id of the issue in that project
    """
    self.visible = True
    self.is_open = True  # TODO(agable) Make a call to Codesite to set this?
    self.url = 'https://code.google.com/p/%s/issues/detail?id=%d' % (
        project_name, issue_id)
    self.display_name = 'issue %s:%d' % (project_name, issue_id)
    self.short_name = 'issue %s:%d' % (project_name, issue_id)
    self.summary = 'Issue %d in %s.' % (issue_id, project_name)
    self.issue_ref = self.display_name[6:]
    self.is_dangling = ezt.boolean(True)

  def DebugString(self):
    return 'DanglingIssueRefView(%s)' % self.display_name


class IssueCommentView(template_helpers.PBProxy):
  """Wrapper class that makes it easier to display an IssueComment via EZT."""

  def __init__(
      self, project_name, comment_pb, users_by_id, autolink,
      all_referenced_artifacts, mr, issue, effective_ids=None):
    """Get IssueComment PB and make its fields available as attrs.

    Args:
      project_name: Name of the project this issue belongs to.
      comment_pb: Comment protocol buffer.
      users_by_id: dict mapping user_ids to UserViews, including
          the user that entered the comment, and any changed participants.
      autolink: utility object for automatically linking to other
        issues, git revisions, etc.
      all_referenced_artifacts: opaque object with details of referenced
        artifacts that is needed by autolink.
      mr: common information parsed from the HTTP request.
      issue: Issue PB for the issue that this comment is part of.
      effective_ids: optional set of int user IDs for the comment author.
    """
    super(IssueCommentView, self).__init__(comment_pb)

    self.id = comment_pb.id
    self.creator = users_by_id[comment_pb.user_id]

    # TODO(jrobbins): this should be based on the issue project, not the
    # request project for non-project views and cross-project.
    if mr.project:
      self.creator_role = framework_helpers.GetRoleName(
          effective_ids or {self.creator.user_id}, mr.project)
    else:
      self.creator_role = None

    time_tuple = time.localtime(comment_pb.timestamp)
    self.date_string = timestr.FormatAbsoluteDate(
        comment_pb.timestamp, old_format=timestr.MONTH_DAY_YEAR_FMT)
    self.date_relative = timestr.FormatRelativeDate(comment_pb.timestamp)
    self.date_tooltip = time.asctime(time_tuple)
    self.date_yyyymmdd = timestr.FormatAbsoluteDate(
        comment_pb.timestamp, recent_format=timestr.MONTH_DAY_YEAR_FMT,
        old_format=timestr.MONTH_DAY_YEAR_FMT)
    self.text_runs = _ParseTextRuns(comment_pb.content)
    if autolink:
      self.text_runs = autolink.MarkupAutolinks(
          mr, self.text_runs, all_referenced_artifacts)

    self.attachments = [AttachmentView(attachment, project_name)
                        for attachment in comment_pb.attachments]
    self.amendments = sorted([
        AmendmentView(amendment, users_by_id, mr.project_name)
        for amendment in comment_pb.amendments],
        key=lambda amendment: amendment.field_name.lower())
    # Treat comments from banned users as being deleted.
    self.is_deleted = (comment_pb.deleted_by or
                       (self.creator and self.creator.banned))
    self.can_delete = False
    if mr.auth.user_id and mr.project:
      # TODO(jrobbins): pass through config, then I can do:
      # granted_perms = tracker_bizobj.GetGrantedPerms(
      # issue, mr.auth.effective_ids, config)
      self.can_delete = permissions.CanDelete(
          mr.auth.user_id, mr.auth.effective_ids, mr.perms,
          comment_pb.deleted_by, comment_pb.user_id,
          mr.project, permissions.GetRestrictions(issue))

      # Prevent spammers from undeleting their own comments, but
      # allow people with permission to undelete their own comments.
      if comment_pb.is_spam and comment_pb.user_id == mr.auth.user_id:
        self.can_delete = mr.perms.HasPerm(permissions.MODERATE_SPAM,
            mr.auth.user_id, mr.project)

    self.visible = self.can_delete or not self.is_deleted


_TEMPLATE_TEXT_RE = re.compile('^(<b>[^<]+</b>)', re.MULTILINE)


def _ParseTextRuns(content):
  """Convert the user's comment to a list of TextRun objects."""
  chunks = _TEMPLATE_TEXT_RE.split(content)
  runs = [_ChunkToRun(chunk) for chunk in chunks]
  return runs


def _ChunkToRun(chunk):
  """Convert a substring of the user's comment to a TextRun object."""
  if chunk.startswith('<b>') and chunk.endswith('</b>'):
    return template_helpers.TextRun(chunk[3:-4], tag='b')
  else:
    return template_helpers.TextRun(chunk)


VIEWABLE_IMAGE_TYPES = [
    'image/jpeg', 'image/gif', 'image/png', 'image/x-png', 'image/webp',
    ]
VIEWABLE_VIDEO_TYPES = [
    'video/ogg', 'video/mp4', 'video/mpg', 'video/mpeg', 'video/webm',
    ]
MAX_PREVIEW_FILESIZE = 15 * 1024 * 1024  # 15 MB


class LogoView(template_helpers.PBProxy):
  """Wrapper class to make it easier to display project logos via EZT."""

  def __init__(self, project_pb):
    if (not project_pb or
        not project_pb.logo_gcs_id or
        not project_pb.logo_file_name):
      self.thumbnail_url = ''
      self.viewurl = ''
      return

    object_path = ('/' + app_identity.get_default_gcs_bucket_name() +
                   project_pb.logo_gcs_id)
    self.filename = project_pb.logo_file_name
    self.mimetype = filecontent.GuessContentTypeFromFilename(self.filename)

    self.thumbnail_url = gcs_helpers.SignUrl(object_path + '-thumbnail')
    self.viewurl = (
        gcs_helpers.SignUrl(object_path) + '&' + urllib.urlencode(
            {'response-content-displacement':
                ('attachment; filename=%s' % self.filename)}))


class AttachmentView(template_helpers.PBProxy):
  """Wrapper class to make it easier to display issue attachments via EZT."""

  def __init__(self, attach_pb, project_name):
    """Get IssueAttachmentContent PB and make its fields available as attrs.

    Args:
      attach_pb: Attachment part of IssueComment protocol buffer.
      project_name: string Name of the current project.
    """
    super(AttachmentView, self).__init__(attach_pb)
    self.filesizestr = template_helpers.BytesKbOrMb(attach_pb.filesize)
    self.downloadurl = 'attachment?aid=%s' % attach_pb.attachment_id

    self.url = None
    self.thumbnail_url = None
    self.video_url = None
    if IsViewableImage(attach_pb.mimetype, attach_pb.filesize):
      self.url = self.downloadurl + '&inline=1'
      self.thumbnail_url = self.url + '&thumb=1'
    elif IsViewableVideo(attach_pb.mimetype, attach_pb.filesize):
      self.url = self.downloadurl + '&inline=1'
      self.video_url = self.url
    elif IsViewableText(attach_pb.mimetype, attach_pb.filesize):
      self.url = tracker_helpers.FormatRelativeIssueURL(
          project_name, urls.ISSUE_ATTACHMENT_TEXT,
          aid=attach_pb.attachment_id)

    self.iconurl = '/images/paperclip.png'


def IsViewableImage(mimetype_charset, filesize):
  """Return true if we can safely display such an image in the browser.

  Args:
    mimetype_charset: string with the mimetype string that we got back
        from the 'file' command.  It may have just the mimetype, or it
        may have 'foo/bar; charset=baz'.
    filesize: int length of the file in bytes.

  Returns:
    True iff we should allow the user to view a thumbnail or safe version
    of the image in the browser.  False if this might not be safe to view,
    in which case we only offer a download link.
  """
  mimetype = mimetype_charset.split(';', 1)[0]
  return (mimetype in VIEWABLE_IMAGE_TYPES and
          filesize < MAX_PREVIEW_FILESIZE)


def IsViewableVideo(mimetype_charset, filesize):
  """Return true if we can safely display such a video in the browser.

  Args:
    mimetype_charset: string with the mimetype string that we got back
        from the 'file' command.  It may have just the mimetype, or it
        may have 'foo/bar; charset=baz'.
    filesize: int length of the file in bytes.

  Returns:
    True iff we should allow the user to watch the video in the page.
  """
  mimetype = mimetype_charset.split(';', 1)[0]
  return (mimetype in VIEWABLE_VIDEO_TYPES and
          filesize < MAX_PREVIEW_FILESIZE)


def IsViewableText(mimetype, filesize):
  """Return true if we can safely display such a file as escaped text."""
  return (mimetype.startswith('text/') and
          filesize < MAX_PREVIEW_FILESIZE)


class AmendmentView(object):
  """Wrapper class that makes it easier to display an Amendment via EZT."""

  def __init__(self, amendment, users_by_id, project_name):
    """Get the info from the PB and put it into easily accessible attrs.

    Args:
      amendment: Amendment part of an IssueComment protocol buffer.
      users_by_id: dict mapping user_ids to UserViews.
      project_name: Name of the project the issue/comment/amendment is in.
    """
    # TODO(jrobbins): take field-level restrictions into account.
    # Including the case where user is not allowed to see any amendments.
    self.field_name = tracker_bizobj.GetAmendmentFieldName(amendment)
    self.newvalue = tracker_bizobj.AmendmentString(amendment, users_by_id)
    self.values = tracker_bizobj.AmendmentLinks(
        amendment, users_by_id, project_name)


class ComponentDefView(template_helpers.PBProxy):
  """Wrapper class to make it easier to display component definitions."""

  def __init__(self, cnxn, services, component_def, users_by_id):
    super(ComponentDefView, self).__init__(component_def)

    c_path = component_def.path
    if '>' in c_path:
      self.parent_path = c_path[:c_path.rindex('>')]
      self.leaf_name = c_path[c_path.rindex('>') + 1:]
    else:
      self.parent_path = ''
      self.leaf_name = c_path

    self.docstring_short = template_helpers.FitUnsafeText(
        component_def.docstring, 200)

    self.admins = [users_by_id.get(admin_id)
                   for admin_id in component_def.admin_ids]
    self.cc = [users_by_id.get(cc_id) for cc_id in component_def.cc_ids]
    self.labels = [
        services.config.LookupLabel(cnxn, component_def.project_id, label_id)
        for label_id in component_def.label_ids]
    self.classes = 'all '
    if self.parent_path == '':
      self.classes += 'toplevel '
    self.classes += 'deprecated ' if component_def.deprecated else 'active '


class ComponentValueView(object):
  """Wrapper class that makes it easier to display a component value."""

  def __init__(self, component_id, config, derived):
    """Make the component name and docstring available as attrs.

    Args:
      component_id: int component_id to look up in the config
      config: ProjectIssueConfig PB for the issue's project.
      derived: True if this component was derived.
    """
    cd = tracker_bizobj.FindComponentDefByID(component_id, config)
    self.path = cd.path
    self.docstring = cd.docstring
    self.docstring_short = template_helpers.FitUnsafeText(cd.docstring, 60)
    self.derived = ezt.boolean(derived)


class FieldValueView(object):
  """Wrapper class that makes it easier to display a custom field value."""

  def __init__(
      self, fd, config, values, derived_values, issue_types, applicable=None):
    """Make several values related to this field available as attrs.

    Args:
      fd: field definition to be displayed (or not, if no value).
      config: ProjectIssueConfig PB for the issue's project.
      values: list of explicit field values.
      derived_values: list of derived field values.
      issue_types: set of lowered string values from issues' "Type-*" labels.
      applicable: optional boolean that overrides the rule that determines
          when a field is applicable.
    """
    self.field_def = FieldDefView(fd, config)
    self.field_id = fd.field_id
    self.field_name = fd.field_name
    self.field_docstring = fd.docstring
    self.field_docstring_short = template_helpers.FitUnsafeText(
        fd.docstring, 60)

    self.values = values
    self.derived_values = derived_values

    self.applicable_type = fd.applicable_type
    if applicable is not None:
      self.applicable = ezt.boolean(applicable)
    else:
      # A field is applicable to a given issue if it (a) applies to all issues,
      # or (b) already has a value on this issue, or (c) says that it applies to
      # issues with this type (or a prefix of it).
      self.applicable = ezt.boolean(
          not self.applicable_type or values or
          any(type_label.startswith(self.applicable_type.lower())
              for type_label in issue_types))
      # TODO(jrobbins): also evaluate applicable_predicate

    self.display = ezt.boolean(   # or fd.show_empty
        self.values or self.derived_values or
        (self.applicable and not fd.is_niche))


def MakeFieldValueView(
    fd, config, labels, derived_labels, field_values, users_by_id):
  """Return a view on the issue's field value."""
  field_name_lower = fd.field_name.lower()
  values = []
  derived_values = []

  if fd.field_type == tracker_pb2.FieldTypes.ENUM_TYPE:
    label_docs = {wkl.label: wkl.label_docstring
                  for wkl in config.well_known_labels}
    values = _ConvertLabelsToFieldValues(
        labels, field_name_lower, label_docs)
    derived_values = _ConvertLabelsToFieldValues(
        derived_labels, field_name_lower, label_docs)
  else:
    values = FindFieldValues(
        [fv for fv in field_values if not fv.derived],
        fd.field_id, users_by_id)
    derived_values = FindFieldValues(
        [fv for fv in field_values if fv.derived],
        fd.field_id, users_by_id)

  issue_types = set()
  for lab in list(derived_labels) + list(labels):
    if lab.lower().startswith('type-'):
      issue_types.add(lab.split('-', 1)[1].lower())

  return FieldValueView(fd, config, values, derived_values, issue_types)


def FindFieldValues(field_values, field_id, users_by_id):
  """Accumulate appropriate int, string, or user values in the given fields."""
  result = []
  for fv in field_values:
    if fv.field_id != field_id:
      continue

    val = tracker_bizobj.GetFieldValue(fv, users_by_id)
    result.append(template_helpers.EZTItem(
        val=val, docstring=val, idx=len(result)))

  return result


def MakeBounceFieldValueViews(field_vals, config):
  """Return a list of field values to display on a validation bounce page."""
  field_value_views = []
  for fd in config.field_defs:
    if fd.field_id in field_vals:
      # TODO(jrobbins): also bounce derived values.
      val_items = [
          template_helpers.EZTItem(val=v, docstring='', idx=idx)
          for idx, v in enumerate(field_vals[fd.field_id])]
      field_value_views.append(FieldValueView(
          fd, config, val_items, [], None, applicable=True))

  return field_value_views


def _ConvertLabelsToFieldValues(labels, field_name_lower, label_docs):
  """Iterate through the given labels and pull out values for the field.

  Args:
    labels: a list of label strings.
    field_name_lower: lowercase string name of the custom field.
    label_docs: {label: docstring} for well-known labels in the project.

  Returns:
    A list of EZT items with val and docstring fields.  One item is included
    for each label that matches the given field name.
  """
  values = []
  field_delim = field_name_lower + '-'
  for idx, lab in enumerate(labels):
    if lab.lower().startswith(field_delim):
      val = lab[len(field_delim):]
      # Use ellipsis in the display val if the val is too long.
      val_short = template_helpers.FitUnsafeText(str(val), 20)
      values.append(template_helpers.EZTItem(
          val=val, val_short=val_short, docstring=label_docs.get(lab, ''),
          idx=idx))

  return values


class FieldDefView(template_helpers.PBProxy):
  """Wrapper class to make it easier to display field definitions via EZT."""

  def __init__(self, field_def, config, user_views=None):
    super(FieldDefView, self).__init__(field_def)

    self.type_name = str(field_def.field_type)

    self.choices = []
    if field_def.field_type == tracker_pb2.FieldTypes.ENUM_TYPE:
      self.choices = tracker_helpers.LabelsMaskedByFields(
          config, [field_def.field_name], trim_prefix=True)

    self.docstring_short = template_helpers.FitUnsafeText(
        field_def.docstring, 200)
    self.validate_help = None

    if field_def.is_required:
      self.importance = 'required'
    elif field_def.is_niche:
      self.importance = 'niche'
    else:
      self.importance = 'normal'

    if field_def.min_value is not None:
      self.min_value = field_def.min_value
      self.validate_help = 'Value must be >= %d' % field_def.min_value
    else:
      self.min_value = None  # Otherwise it would default to 0

    if field_def.max_value is not None:
      self.max_value = field_def.max_value
      self.validate_help = 'Value must be <= %d' % field_def.max_value
    else:
      self.max_value = None  # Otherwise it would default to 0

    if field_def.min_value is not None and field_def.max_value is not None:
      self.validate_help = 'Value must be between %d and %d' % (
          field_def.min_value, field_def.max_value)

    if field_def.regex:
      self.validate_help = 'Value must match regex: %s' % field_def.regex

    if field_def.needs_member:
      self.validate_help = 'Value must be a project member'

    if field_def.needs_perm:
      self.validate_help = (
          'Value must be a project member with permission %s' %
          field_def.needs_perm)

    self.date_action_str = str(field_def.date_action or 'no_action').lower()

    self.admins = []
    if user_views:
      self.admins = [user_views.get(admin_id)
                     for admin_id in field_def.admin_ids]


class IssueTemplateView(template_helpers.PBProxy):
  """Wrapper class to make it easier to display an issue template via EZT."""

  def __init__(self, mr, template, user_service, config):
    super(IssueTemplateView, self).__init__(template)

    self.ownername = ''
    try:
      self.owner_view = framework_views.MakeUserView(
          mr.cnxn, user_service, template.owner_id)
    except user_svc.NoSuchUserException:
      self.owner_view = None
    if self.owner_view:
      self.ownername = self.owner_view.email

    self.admin_views = framework_views.MakeAllUserViews(
        mr.cnxn, user_service, template.admin_ids).values()
    self.admin_names = ', '.join(sorted([
        admin_view.email for admin_view in self.admin_views]))

    self.summary_must_be_edited = ezt.boolean(template.summary_must_be_edited)
    self.members_only = ezt.boolean(template.members_only)
    self.owner_defaults_to_member = ezt.boolean(
        template.owner_defaults_to_member)
    self.component_required = ezt.boolean(template.component_required)

    component_paths = []
    for component_id in template.component_ids:
      component_paths.append(
          tracker_bizobj.FindComponentDefByID(component_id, config).path)
    self.components = ', '.join(component_paths)

    self.can_view = ezt.boolean(permissions.CanViewTemplate(
        mr.auth.effective_ids, mr.perms, mr.project, template))
    self.can_edit = ezt.boolean(permissions.CanEditTemplate(
        mr.auth.effective_ids, mr.perms, mr.project, template))

    field_name_set = {fd.field_name.lower() for fd in config.field_defs
                      if not fd.is_deleted}  # TODO(jrobbins): restrictions
    non_masked_labels = [
        lab for lab in template.labels
        if not tracker_bizobj.LabelIsMaskedByField(lab, field_name_set)]

    for i, label in enumerate(non_masked_labels):
      setattr(self, 'label%d' % i, label)
    for i in range(len(non_masked_labels), framework_constants.MAX_LABELS):
      setattr(self, 'label%d' % i, '')

    field_user_views = MakeFieldUserViews(mr.cnxn, template, user_service)
    self.field_values = []
    for fv in template.field_values:
      self.field_values.append(template_helpers.EZTItem(
          field_id=fv.field_id,
          val=tracker_bizobj.GetFieldValue(fv, field_user_views),
          idx=len(self.field_values)))

    self.complete_field_values = [
        MakeFieldValueView(
            fd, config, template.labels, [], template.field_values,
            field_user_views)
        # TODO(jrobbins): field-level view restrictions, display options
        for fd in config.field_defs
        if not fd.is_deleted]

    # Templates only display and edit the first value of multi-valued fields, so
    # expose a single value, if any.
    # TODO(jrobbins): Fully support multi-valued fields in templates.
    for idx, field_value_view in enumerate(self.complete_field_values):
      field_value_view.idx = idx
      if field_value_view.values:
        field_value_view.val = field_value_view.values[0].val
      else:
        field_value_view.val = None


def MakeFieldUserViews(cnxn, template, user_service):
  """Return {user_id: user_view} for users in template field values."""
  field_user_ids = [
      fv.user_id for fv in template.field_values
      if fv.user_id]
  field_user_views = framework_views.MakeAllUserViews(
      cnxn, user_service, field_user_ids)
  return field_user_views


class ConfigView(template_helpers.PBProxy):
  """Make it easy to display most fieds of a ProjectIssueConfig in EZT."""

  def __init__(self, mr, services, config):
    """Gather data for the issue section of a project admin page.

    Args:
      mr: MonorailRequest, including a database connection, the current
          project, and authenticated user IDs.
      services: Persist services with ProjectService, ConfigService, and
          UserService included.
      config: ProjectIssueConfig for the current project..

    Returns:
      Project info in a dict suitable for EZT.
    """
    super(ConfigView, self).__init__(config)
    self.open_statuses = []
    self.closed_statuses = []
    for wks in config.well_known_statuses:
      item = template_helpers.EZTItem(
          name=wks.status,
          name_padded=wks.status.ljust(20),
          commented='#' if wks.deprecated else '',
          docstring=wks.status_docstring)
      if tracker_helpers.MeansOpenInProject(wks.status, config):
        self.open_statuses.append(item)
      else:
        self.closed_statuses.append(item)

    self.templates = [
        IssueTemplateView(mr, tmpl, services.user, config)
        for tmpl in config.templates]
    for index, template in enumerate(self.templates):
      template.index = index

    self.field_names = [  # TODO(jrobbins): field-level controls
        fd.field_name for fd in config.field_defs if not fd.is_deleted]
    self.issue_labels = tracker_helpers.LabelsNotMaskedByFields(
        config, self.field_names)
    self.excl_prefixes = [
        prefix.lower() for prefix in config.exclusive_label_prefixes]
    self.restrict_to_known = ezt.boolean(config.restrict_to_known)

    self.default_col_spec = (
        config.default_col_spec or tracker_constants.DEFAULT_COL_SPEC)
