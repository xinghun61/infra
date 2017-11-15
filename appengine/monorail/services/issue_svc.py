# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A set of functions that provide persistence for Monorail issue tracking.

This module provides functions to get, update, create, and (in some
cases) delete each type of business object.  It provides a logical
persistence layer on top of an SQL database.

Business objects are described in tracker_pb2.py and tracker_bizobj.py.
"""

import collections
import json
import logging
import os
import time
import uuid

from google.appengine.api import app_identity
from google.appengine.api import images
from third_party import cloudstorage

import settings
from features import filterrules_helpers
from framework import framework_bizobj
from framework import framework_constants
from framework import framework_helpers
from framework import gcs_helpers
from framework import permissions
from framework import sql
from infra_libs import ts_mon
from proto import project_pb2
from proto import tracker_pb2
from services import caches
from services import tracker_fulltext
from tracker import tracker_bizobj
from tracker import tracker_helpers


ISSUE_TABLE_NAME = 'Issue'
ISSUESUMMARY_TABLE_NAME = 'IssueSummary'
ISSUE2LABEL_TABLE_NAME = 'Issue2Label'
ISSUE2COMPONENT_TABLE_NAME = 'Issue2Component'
ISSUE2CC_TABLE_NAME = 'Issue2Cc'
ISSUE2NOTIFY_TABLE_NAME = 'Issue2Notify'
ISSUE2FIELDVALUE_TABLE_NAME = 'Issue2FieldValue'
COMMENT_TABLE_NAME = 'Comment'
COMMENTCONTENT_TABLE_NAME = 'CommentContent'
ATTACHMENT_TABLE_NAME = 'Attachment'
ISSUERELATION_TABLE_NAME = 'IssueRelation'
DANGLINGRELATION_TABLE_NAME = 'DanglingIssueRelation'
ISSUEUPDATE_TABLE_NAME = 'IssueUpdate'
ISSUEFORMERLOCATIONS_TABLE_NAME = 'IssueFormerLocations'
REINDEXQUEUE_TABLE_NAME = 'ReindexQueue'
LOCALIDCOUNTER_TABLE_NAME = 'LocalIDCounter'

ISSUE_COLS = [
    'id', 'project_id', 'local_id', 'status_id', 'owner_id', 'reporter_id',
    'opened', 'closed', 'modified',
    'owner_modified', 'status_modified', 'component_modified',
    'derived_owner_id', 'derived_status_id',
    'deleted', 'star_count', 'attachment_count', 'is_spam']
ISSUESUMMARY_COLS = ['issue_id', 'summary']
ISSUE2LABEL_COLS = ['issue_id', 'label_id', 'derived']
ISSUE2COMPONENT_COLS = ['issue_id', 'component_id', 'derived']
ISSUE2CC_COLS = ['issue_id', 'cc_id', 'derived']
ISSUE2NOTIFY_COLS = ['issue_id', 'email']
ISSUE2FIELDVALUE_COLS = [
    'issue_id', 'field_id', 'int_value', 'str_value', 'user_id', 'date_value',
    'url_value', 'derived']
COMMENT_COLS = [
    'Comment.id', 'issue_id', 'created', 'Comment.project_id', 'commenter_id',
    'deleted_by', 'Comment.is_spam', 'is_description',
    'commentcontent_id']  # Note: commentcontent_id must be last.
COMMENTCONTENT_COLS = [
    'CommentContent.id', 'content', 'inbound_message']
ABBR_COMMENT_COLS = ['Comment.id', 'commenter_id', 'deleted_by',
    'is_description']
ATTACHMENT_COLS = [
    'id', 'issue_id', 'comment_id', 'filename', 'filesize', 'mimetype',
    'deleted', 'gcs_object_id']
ISSUERELATION_COLS = ['issue_id', 'dst_issue_id', 'kind', 'rank']
ABBR_ISSUERELATION_COLS = ['dst_issue_id', 'rank']
DANGLINGRELATION_COLS = [
    'issue_id', 'dst_issue_project', 'dst_issue_local_id', 'kind']
ISSUEUPDATE_COLS = [
    'id', 'issue_id', 'comment_id', 'field', 'old_value', 'new_value',
    'added_user_id', 'removed_user_id', 'custom_field_name']
ISSUEFORMERLOCATIONS_COLS = ['issue_id', 'project_id', 'local_id']
REINDEXQUEUE_COLS = ['issue_id', 'created']

CHUNK_SIZE = 1000


class IssueIDTwoLevelCache(caches.AbstractTwoLevelCache):
  """Class to manage RAM and memcache for Issue IDs."""

  def __init__(self, cache_manager, issue_service):
    super(IssueIDTwoLevelCache, self).__init__(
        cache_manager, 'issue_id', 'issue_id:', int,
        max_size=settings.issue_cache_max_size)
    self.issue_service = issue_service

  def _MakeCache(self, cache_manager, kind, max_size=None):
    """Override normal RamCache creation with ValueCentricRamCache."""
    return caches.ValueCentricRamCache(cache_manager, kind, max_size=max_size)

  def _DeserializeIssueIDs(self, project_local_issue_ids):
    """Convert database rows into a dict {(project_id, local_id): issue_id}."""
    return {(project_id, local_id): issue_id
            for (project_id, local_id, issue_id) in project_local_issue_ids}

  def FetchItems(self, cnxn, keys):
    """On RAM and memcache miss, hit the database."""
    local_ids_by_pid = collections.defaultdict(list)
    for project_id, local_id in keys:
      local_ids_by_pid[project_id].append(local_id)

    where = []  # We OR per-project pairs of conditions together.
    for project_id, local_ids_in_project in local_ids_by_pid.iteritems():
      term_str = ('(Issue.project_id = %%s AND Issue.local_id IN (%s))' %
                  sql.PlaceHolders(local_ids_in_project))
      where.append((term_str, [project_id] + local_ids_in_project))

    rows = self.issue_service.issue_tbl.Select(
        cnxn, cols=['project_id', 'local_id', 'id'],
        where=where, or_where_conds=True)
    return self._DeserializeIssueIDs(rows)

  def _KeyToStr(self, key):
    """This cache uses pairs of ints as keys. Convert them to strings."""
    return '%d,%d' % key

  def _StrToKey(self, key_str):
    """This cache uses pairs of ints as keys. Convert them from strings."""
    project_id_str, local_id_str = key_str.split(',')
    return int(project_id_str), int(local_id_str)


class IssueTwoLevelCache(caches.AbstractTwoLevelCache):
  """Class to manage RAM and memcache for Issue PBs."""

  def __init__(
      self, cache_manager, issue_service, project_service, config_service):
    super(IssueTwoLevelCache, self).__init__(
        cache_manager, 'issue', 'issue:', tracker_pb2.Issue,
        max_size=settings.issue_cache_max_size)
    self.issue_service = issue_service
    self.project_service = project_service
    self.config_service = config_service

  def _UnpackIssue(self, cnxn, issue_row):
    """Partially construct an issue object using info from a DB row."""
    (issue_id, project_id, local_id, status_id, owner_id, reporter_id,
     opened, closed, modified, owner_modified, status_modified,
     component_modified, derived_owner_id, derived_status_id,
     deleted, star_count, attachment_count, is_spam) = issue_row

    issue = tracker_pb2.Issue()
    project = self.project_service.GetProject(cnxn, project_id)
    issue.project_name = project.project_name
    issue.issue_id = issue_id
    issue.project_id = project_id
    issue.local_id = local_id
    if status_id is not None:
      status = self.config_service.LookupStatus(cnxn, project_id, status_id)
      issue.status = status
    issue.owner_id = owner_id or 0
    issue.reporter_id = reporter_id or 0
    issue.derived_owner_id = derived_owner_id or 0
    if derived_status_id is not None:
      derived_status = self.config_service.LookupStatus(
          cnxn, project_id, derived_status_id)
      issue.derived_status = derived_status
    issue.deleted = bool(deleted)
    if opened:
      issue.opened_timestamp = opened
    if closed:
      issue.closed_timestamp = closed
    if modified:
      issue.modified_timestamp = modified
    if owner_modified:
      issue.owner_modified_timestamp = owner_modified
    if status_modified:
      issue.status_modified_timestamp = status_modified
    if component_modified:
      issue.component_modified_timestamp = component_modified
    issue.star_count = star_count
    issue.attachment_count = attachment_count
    issue.is_spam = bool(is_spam)
    return issue

  def _UnpackFieldValue(self, fv_row):
    """Construct a field value object from a DB row."""
    (issue_id, field_id, int_value, str_value, user_id, date_value, url_value,
     derived) = fv_row
    fv = tracker_bizobj.MakeFieldValue(
        field_id, int_value, str_value, user_id, date_value, url_value,
        bool(derived))
    return fv, issue_id

  def _DeserializeIssues(
      self, cnxn, issue_rows, summary_rows, label_rows, component_rows,
      cc_rows, notify_rows, fieldvalue_rows, relation_rows,
      dangling_relation_rows):
    """Convert the given DB rows into a dict of Issue PBs."""
    results_dict = {}
    for issue_row in issue_rows:
      issue = self._UnpackIssue(cnxn, issue_row)
      results_dict[issue.issue_id] = issue

    for issue_id, summary in summary_rows:
      results_dict[issue_id].summary = summary

    # TODO(jrobbins): it would be nice to order labels by rank and name.
    for issue_id, label_id, derived in label_rows:
      issue = results_dict.get(issue_id)
      if not issue:
        logging.info('Got label for an unknown issue: %r %r',
                     label_rows, issue_rows)
        continue
      label = self.config_service.LookupLabel(cnxn, issue.project_id, label_id)
      assert label, ('Label ID %r on IID %r not found in project %r' %
                     (label_id, issue_id, issue.project_id))
      if derived:
        results_dict[issue_id].derived_labels.append(label)
      else:
        results_dict[issue_id].labels.append(label)

    for issue_id, component_id, derived in component_rows:
      if derived:
        results_dict[issue_id].derived_component_ids.append(component_id)
      else:
        results_dict[issue_id].component_ids.append(component_id)

    for issue_id, user_id, derived in cc_rows:
      if derived:
        results_dict[issue_id].derived_cc_ids.append(user_id)
      else:
        results_dict[issue_id].cc_ids.append(user_id)

    for issue_id, email in notify_rows:
      results_dict[issue_id].derived_notify_addrs.append(email)

    for fv_row in fieldvalue_rows:
      fv, issue_id = self._UnpackFieldValue(fv_row)
      results_dict[issue_id].field_values.append(fv)

    for issue_id, dst_issue_id, kind, rank in relation_rows:
      src_issue = results_dict.get(issue_id)
      dst_issue = results_dict.get(dst_issue_id)
      assert src_issue or dst_issue, (
          'Neither source issue %r nor dest issue %r was found' %
          (issue_id, dst_issue_id))
      if src_issue:
        if kind == 'blockedon':
          src_issue.blocked_on_iids.append(dst_issue_id)
          src_issue.blocked_on_ranks.append(rank)
        elif kind == 'mergedinto':
          src_issue.merged_into = dst_issue_id
        else:
          logging.info('unknown relation kind %r', kind)
          continue

      if dst_issue:
        if kind == 'blockedon':
          dst_issue.blocking_iids.append(issue_id)

    for issue_id, dst_issue_proj, dst_issue_id, kind in dangling_relation_rows:
      src_issue = results_dict.get(issue_id)
      if kind == 'blockedon':
        src_issue.dangling_blocked_on_refs.append(
            tracker_bizobj.MakeDanglingIssueRef(dst_issue_proj, dst_issue_id))
      elif kind == 'blocking':
        src_issue.dangling_blocking_refs.append(
            tracker_bizobj.MakeDanglingIssueRef(dst_issue_proj, dst_issue_id))
      else:
        logging.warn('unhandled danging relation kind %r', kind)
        continue

    return results_dict

  # Note: sharding is used to here to allow us to load issues from the replicas
  # without placing load on the master.  Writes are not sharded.
  # pylint: disable=arguments-differ
  def FetchItems(self, cnxn, issue_ids, shard_id=None):
    """Retrieve and deserialize issues."""
    issue_rows = self.issue_service.issue_tbl.Select(
        cnxn, cols=ISSUE_COLS, id=issue_ids, shard_id=shard_id)

    summary_rows = self.issue_service.issuesummary_tbl.Select(
        cnxn, cols=ISSUESUMMARY_COLS, shard_id=shard_id, issue_id=issue_ids)
    label_rows = self.issue_service.issue2label_tbl.Select(
        cnxn, cols=ISSUE2LABEL_COLS, shard_id=shard_id, issue_id=issue_ids)
    component_rows = self.issue_service.issue2component_tbl.Select(
        cnxn, cols=ISSUE2COMPONENT_COLS, shard_id=shard_id, issue_id=issue_ids)
    cc_rows = self.issue_service.issue2cc_tbl.Select(
        cnxn, cols=ISSUE2CC_COLS, shard_id=shard_id, issue_id=issue_ids)
    notify_rows = self.issue_service.issue2notify_tbl.Select(
        cnxn, cols=ISSUE2NOTIFY_COLS, shard_id=shard_id, issue_id=issue_ids)
    fieldvalue_rows = self.issue_service.issue2fieldvalue_tbl.Select(
        cnxn, cols=ISSUE2FIELDVALUE_COLS, shard_id=shard_id,
        issue_id=issue_ids)
    if issue_ids:
      ph = sql.PlaceHolders(issue_ids)
      blocked_on_rows = self.issue_service.issuerelation_tbl.Select(
          cnxn, cols=ISSUERELATION_COLS, issue_id=issue_ids, kind='blockedon',
          order_by=[('issue_id', []), ('rank DESC', []), ('dst_issue_id', [])])
      blocking_rows = self.issue_service.issuerelation_tbl.Select(
          cnxn, cols=ISSUERELATION_COLS, dst_issue_id=issue_ids,
          kind='blockedon', order_by=[('issue_id', []), ('dst_issue_id', [])])
      unique_blocking = tuple(
          row for row in blocking_rows if row not in blocked_on_rows)
      merge_rows = self.issue_service.issuerelation_tbl.Select(
          cnxn, cols=ISSUERELATION_COLS,
          where=[('(issue_id IN (%s) OR dst_issue_id IN (%s))' % (ph, ph),
                  issue_ids + issue_ids),
                 ('kind != %s', ['blockedon'])])
      relation_rows = blocked_on_rows + unique_blocking + merge_rows
      dangling_relation_rows = self.issue_service.danglingrelation_tbl.Select(
          cnxn, cols=DANGLINGRELATION_COLS, issue_id=issue_ids)
    else:
      relation_rows = []
      dangling_relation_rows = []

    issue_dict = self._DeserializeIssues(
        cnxn, issue_rows, summary_rows, label_rows, component_rows, cc_rows,
        notify_rows, fieldvalue_rows, relation_rows, dangling_relation_rows)
    logging.info('IssueTwoLevelCache.FetchItems returning: %r', issue_dict)
    return issue_dict


class IssueService(object):
  """The persistence layer for Monorail's issues, comments, and attachments."""
  spam_labels = ts_mon.CounterMetric(
      'monorail/issue_svc/spam_label',
      'Issues created, broken down by spam label.',
      [ts_mon.StringField('type')])

  def __init__(self, project_service, config_service, cache_manager):
    """Initialize this object so that it is ready to use.

    Args:
      project_service: services object for project info.
      config_service: services object for tracker configuration info.
      cache_manager: local cache with distributed invalidation.
    """
    # Tables that represent issue data.
    self.issue_tbl = sql.SQLTableManager(ISSUE_TABLE_NAME)
    self.issuesummary_tbl = sql.SQLTableManager(ISSUESUMMARY_TABLE_NAME)
    self.issue2label_tbl = sql.SQLTableManager(ISSUE2LABEL_TABLE_NAME)
    self.issue2component_tbl = sql.SQLTableManager(ISSUE2COMPONENT_TABLE_NAME)
    self.issue2cc_tbl = sql.SQLTableManager(ISSUE2CC_TABLE_NAME)
    self.issue2notify_tbl = sql.SQLTableManager(ISSUE2NOTIFY_TABLE_NAME)
    self.issue2fieldvalue_tbl = sql.SQLTableManager(ISSUE2FIELDVALUE_TABLE_NAME)
    self.issuerelation_tbl = sql.SQLTableManager(ISSUERELATION_TABLE_NAME)
    self.danglingrelation_tbl = sql.SQLTableManager(DANGLINGRELATION_TABLE_NAME)
    self.issueformerlocations_tbl = sql.SQLTableManager(
        ISSUEFORMERLOCATIONS_TABLE_NAME)

    # Tables that represent comments.
    self.comment_tbl = sql.SQLTableManager(COMMENT_TABLE_NAME)
    self.commentcontent_tbl = sql.SQLTableManager(COMMENTCONTENT_TABLE_NAME)
    self.issueupdate_tbl = sql.SQLTableManager(ISSUEUPDATE_TABLE_NAME)
    self.attachment_tbl = sql.SQLTableManager(ATTACHMENT_TABLE_NAME)

    # Tables for cron tasks.
    self.reindexqueue_tbl = sql.SQLTableManager(REINDEXQUEUE_TABLE_NAME)

    # Tables for generating sequences of local IDs.
    self.localidcounter_tbl = sql.SQLTableManager(LOCALIDCOUNTER_TABLE_NAME)

    # Like a dictionary {(project_id, local_id): issue_id}
    # Use value centric cache here because we cannot store a tuple in the
    # Invalidate table.
    self.issue_id_2lc = IssueIDTwoLevelCache(cache_manager, self)
    # Like a dictionary {issue_id: issue}
    self.issue_2lc = IssueTwoLevelCache(
        cache_manager, self, project_service, config_service)

    self._config_service = config_service

  ### Issue ID lookups

  def LookupIssueIDs(self, cnxn, project_local_id_pairs):
    """Find the global issue IDs given the project ID and local ID of each."""
    issue_id_dict, misses = self.issue_id_2lc.GetAll(
        cnxn, project_local_id_pairs)

    # Put the Issue IDs in the order specified by project_local_id_pairs
    issue_ids = [issue_id_dict[pair] for pair in project_local_id_pairs
                 if pair in issue_id_dict]

    return issue_ids, misses

  def LookupIssueID(self, cnxn, project_id, local_id):
    """Find the global issue ID given the project ID and local ID."""
    issue_ids, _misses = self.LookupIssueIDs(cnxn, [(project_id, local_id)])
    try:
      return issue_ids[0]
    except IndexError:
      raise NoSuchIssueException()

  def ResolveIssueRefs(
      self, cnxn, ref_projects, default_project_name, refs):
    """Look up all the referenced issues and return their issue_ids.

    Args:
      cnxn: connection to SQL database.
      ref_projects: pre-fetched dict {project_name: project} of all projects
          mentioned in the refs as well as the default project.
      default_project_name: string name of the current project, this is used
          when the project_name in a ref is None.
      refs: list of (project_name, local_id) pairs.  These are parsed from
          textual references in issue descriptions, comments, and the input
          in the blocked-on field.

    Returns:
      A list of issue_ids for all the referenced issues.  References to issues
      in deleted projects and any issues not found are simply ignored.
    """
    if not refs:
      return [], []

    project_local_id_pairs = []
    for project_name, local_id in refs:
      project = ref_projects.get(project_name or default_project_name)
      if not project or project.state == project_pb2.ProjectState.DELETABLE:
        continue  # ignore any refs to issues in deleted projects
      project_local_id_pairs.append((project.project_id, local_id))

    return self.LookupIssueIDs(cnxn, project_local_id_pairs)  # tuple

  ### Issue objects

  def CreateIssue(
      self, cnxn, services, project_id, summary, status,
      owner_id, cc_ids, labels, field_values, component_ids, reporter_id,
      marked_description, blocked_on=None, blocking=None, attachments=None,
      timestamp=None, index_now=True):
    """Create and store a new issue with all the given information.

    Args:
      cnxn: connection to SQL database.
      services: persistence layer for users, issues, and projects.
      project_id: int ID for the current project.
      summary: one-line summary string summarizing this issue.
      status: string issue status value.  E.g., 'New'.
      owner_id: user ID of the issue owner.
      cc_ids: list of user IDs for users to be CC'd on changes.
      labels: list of label strings.  E.g., 'Priority-High'.
      field_values: list of FieldValue PBs.
      component_ids: list of int component IDs.
      reporter_id: user ID of the user who reported the issue.
      marked_description: issue description with initial HTML markup.
      blocked_on: list of issue_ids that this issue is blocked on.
      blocking: list of issue_ids that this issue blocks.
      attachments: [(filename, contents, mimetype),...] attachments uploaded at
          the time the comment was made.
      timestamp: time that the issue was entered, defaults to now.
      index_now: True if the issue should be updated in the full text index.

    Returns:
      The integer local ID of the new issue.
    """
    config = self._config_service.GetProjectConfig(cnxn, project_id)
    iids_to_invalidate = set()

    status = framework_bizobj.CanonicalizeLabel(status)
    labels = [framework_bizobj.CanonicalizeLabel(l) for l in labels]
    labels = [l for l in labels if l]

    issue = tracker_pb2.Issue()
    issue.project_id = project_id
    issue.project_name = services.project.LookupProjectNames(
        cnxn, [project_id]).get(project_id)
    issue.summary = summary
    issue.status = status
    issue.owner_id = owner_id
    issue.cc_ids.extend(cc_ids)
    issue.labels.extend(labels)
    issue.field_values.extend(field_values)
    issue.component_ids.extend(component_ids)
    issue.reporter_id = reporter_id
    if blocked_on is not None:
      iids_to_invalidate.update(blocked_on)
      issue.blocked_on_iids = blocked_on
      issue.blocked_on_ranks = [0] * len(blocked_on)
    if blocking is not None:
      iids_to_invalidate.update(blocking)
      issue.blocking_iids = blocking
    if attachments:
      issue.attachment_count = len(attachments)
    timestamp = timestamp or int(time.time())
    issue.opened_timestamp = timestamp
    issue.modified_timestamp = timestamp
    issue.owner_modified_timestamp = timestamp
    issue.status_modified_timestamp = timestamp
    issue.component_modified_timestamp = timestamp

    comment = self._MakeIssueComment(
        project_id, reporter_id, marked_description,
        attachments=attachments, timestamp=timestamp,
        is_description=True)

    # Set the closed_timestamp both before and after filter rules.
    if not tracker_helpers.MeansOpenInProject(
        tracker_bizobj.GetStatus(issue), config):
      issue.closed_timestamp = timestamp
    filterrules_helpers.ApplyFilterRules(cnxn, services, issue, config)
    if not tracker_helpers.MeansOpenInProject(
        tracker_bizobj.GetStatus(issue), config):
      issue.closed_timestamp = timestamp

    reporter = services.user.GetUser(cnxn, reporter_id)
    project = services.project.GetProject(cnxn, project_id)
    effective_ids = services.usergroup.LookupMemberships(cnxn, reporter_id)
    is_project_member = framework_bizobj.UserIsInProject(project, effective_ids)
    classification = services.spam.ClassifyIssue(
        issue, comment, reporter, is_project_member)

    if classification['confidence_is_spam'] > settings.classifier_spam_thresh:
      issue.is_spam = True
      predicted_label = 'spam'
    else:
      predicted_label = 'ham'

    logging.info('classified new issue as %s' % predicted_label)
    self.spam_labels.increment({'type': predicted_label})

    issue.local_id = self.AllocateNextLocalID(cnxn, project_id)
    issue_id = self.InsertIssue(cnxn, issue)
    comment.issue_id = issue_id
    self.InsertComment(cnxn, comment)

    issue.issue_id = issue_id

    # ClassifyIssue only returns confidence_is_spam, but
    # RecordClassifierIssueVerdict records confidence of
    # ham or spam. Therefore if ham, invert score.
    confidence = classification['confidence_is_spam']
    if not issue.is_spam:
      confidence = 1.0 - confidence

    services.spam.RecordClassifierIssueVerdict(
      cnxn, issue, predicted_label=='spam',
      confidence, classification['failed_open'])

    if permissions.HasRestrictions(issue, 'view'):
      self._config_service.InvalidateMemcache(
          [issue], key_prefix='nonviewable:')

    # Add a comment to existing issues saying they are now blocking or
    # blocked on this issue.
    blocked_add_issues = self.GetIssues(cnxn, blocked_on or [])
    for add_issue in blocked_add_issues:
      self.CreateIssueComment(
          cnxn, add_issue, reporter_id, content='',
          amendments=[tracker_bizobj.MakeBlockingAmendment(
              [(issue.project_name, issue.local_id)], [],
              default_project_name=add_issue.project_name)])
    blocking_add_issues = self.GetIssues(cnxn, blocking or [])
    for add_issue in blocking_add_issues:
      self.CreateIssueComment(
          cnxn, add_issue, reporter_id, content='',
          amendments=[tracker_bizobj.MakeBlockedOnAmendment(
              [(issue.project_name, issue.local_id)], [],
              default_project_name=add_issue.project_name)])

    self._UpdateIssuesModified(
        cnxn, iids_to_invalidate, modified_timestamp=timestamp)

    if index_now:
      tracker_fulltext.IndexIssues(
          cnxn, [issue], services.user, self, self._config_service)

    return issue.local_id

  def AllocateNewLocalIDs(self, cnxn, issues):
    # Filter to just the issues that need new local IDs.
    issues = [issue for issue in issues if issue.local_id < 0]

    for issue in issues:
      if issue.local_id < 0:
        issue.local_id = self.AllocateNextLocalID(cnxn, issue.project_id)

    self.UpdateIssues(cnxn, issues)

    logging.info("AllocateNewLocalIDs")

  def GetAllIssuesInProject(
      self, cnxn, project_id, min_local_id=None, use_cache=True):
    """Special query to efficiently get ALL issues in a project.

    This is not done while the user is waiting, only by backround tasks.

    Args:
      cnxn: connection to SQL database.
      project_id: the ID of the project.
      min_local_id: optional int to start at.
      use_cache: optional boolean to turn off using the cache.

    Returns:
      A list of Issue protocol buffers for all issues.
    """
    all_local_ids = self.GetAllLocalIDsInProject(
        cnxn, project_id, min_local_id=min_local_id)
    return self.GetIssuesByLocalIDs(
        cnxn, project_id, all_local_ids, use_cache=use_cache)

  def GetAnyOnHandIssue(self, issue_ids, start=None, end=None):
    """Get any one issue from RAM or memcache, otherwise return None."""
    return self.issue_2lc.GetAnyOnHandItem(issue_ids, start=start, end=end)

  def GetIssuesDict(self, cnxn, issue_ids, use_cache=True, shard_id=None):
    """Get a dict {iid: issue} from the DB or cache."""
    issue_dict, _missed_iids = self.issue_2lc.GetAll(
        cnxn, issue_ids, use_cache=use_cache, shard_id=shard_id)
    if not use_cache:
      for issue in issue_dict.values():
        issue.assume_stale = False
    return issue_dict

  def GetIssues(self, cnxn, issue_ids, use_cache=True, shard_id=None):
    """Get a list of Issue PBs from the DB or cache.

    Args:
      cnxn: connection to SQL database.
      issue_ids: integer global issue IDs of the issues.
      use_cache: optional boolean to turn off using the cache.
      shard_id: optional int shard_id to limit retrieval.

    Returns:
      A list of Issue PBs in the same order as the given issue_ids.
    """
    issue_dict = self.GetIssuesDict(
        cnxn, issue_ids, use_cache=use_cache, shard_id=shard_id)

    # Return a list that is ordered the same as the given issue_ids.
    issue_list = [issue_dict[issue_id] for issue_id in issue_ids
                  if issue_id in issue_dict]

    return issue_list

  def GetIssue(self, cnxn, issue_id, use_cache=True):
    """Get one Issue PB from the DB.

    Args:
      cnxn: connection to SQL database.
      issue_id: integer global issue ID of the issue.
      use_cache: optional boolean to turn off using the cache.

    Returns:
      The requested Issue protocol buffer.

    Raises:
      NoSuchIssueException: the issue was not found.
    """
    issues = self.GetIssues(cnxn, [issue_id], use_cache=use_cache)
    try:
      return issues[0]
    except IndexError:
      raise NoSuchIssueException()

  def GetIssuesByLocalIDs(
      self, cnxn, project_id, local_id_list, use_cache=True, shard_id=None):
    """Get all the requested issues.

    Args:
      cnxn: connection to SQL database.
      project_id: int ID of the project to which the issues belong.
      local_id_list: list of integer local IDs for the requested issues.
      use_cache: optional boolean to turn off using the cache.
      shard_id: optional int shard_id to choose a replica.

    Returns:
      List of Issue PBs for the requested issues.  The result Issues
      will be ordered in the same order as local_id_list.
    """
    issue_ids_to_fetch, _misses = self.LookupIssueIDs(
        cnxn, [(project_id, local_id) for local_id in local_id_list])
    issues = self.GetIssues(
        cnxn, issue_ids_to_fetch, use_cache=use_cache, shard_id=shard_id)
    return issues

  def GetIssueByLocalID(self, cnxn, project_id, local_id, use_cache=True):
    """Get one Issue PB from the DB.

    Args:
      cnxn: connection to SQL database.
      project_id: the ID of the project to which the issue belongs.
      local_id: integer local ID of the issue.
      use_cache: optional boolean to turn off using the cache.

    Returns:
      The requested Issue protocol buffer.
    """
    issues = self.GetIssuesByLocalIDs(
        cnxn, project_id, [local_id], use_cache=use_cache)
    try:
      return issues[0]
    except IndexError:
      raise NoSuchIssueException('The issue %s:%d does not exist.' % (
          project_id, local_id))

  def GetOpenAndClosedIssues(self, cnxn, issue_ids):
    """Return the requested issues in separate open and closed lists.

    Args:
      cnxn: connection to SQL database.
      issue_ids: list of int issue issue_ids.

    Returns:
      A pair of lists, the first with open issues, second with closed issues.
    """
    if not issue_ids:
      return [], []  # make one common case efficient

    issues = self.GetIssues(cnxn, issue_ids)
    project_ids = {issue.project_id for issue in issues}
    configs = self._config_service.GetProjectConfigs(cnxn, project_ids)
    open_issues = []
    closed_issues = []
    for issue in issues:
      config = configs[issue.project_id]
      if tracker_helpers.MeansOpenInProject(
          tracker_bizobj.GetStatus(issue), config):
        open_issues.append(issue)
      else:
        closed_issues.append(issue)

    return open_issues, closed_issues

  def GetCurrentLocationOfMovedIssue(self, cnxn, project_id, local_id):
    """Return the current location of a moved issue based on old location."""
    issue_id = int(self.issueformerlocations_tbl.SelectValue(
        cnxn, 'issue_id', default=0, project_id=project_id, local_id=local_id))
    if not issue_id:
      return None, None
    project_id, local_id = self.issue_tbl.SelectRow(
        cnxn, cols=['project_id', 'local_id'], id=issue_id)
    return project_id, local_id

  def GetPreviousLocations(self, cnxn, issue):
    """Get all the previous locations of an issue."""
    location_rows = self.issueformerlocations_tbl.Select(
        cnxn, cols=['project_id', 'local_id'], issue_id=issue.issue_id)
    locations = [(pid, local_id) for (pid, local_id) in location_rows
                 if pid != issue.project_id or local_id != issue.local_id]
    return locations

  def GetCommentsByUser(self, cnxn, user_id):
    """Get all comments created by a user"""
    comments = self.GetComments(cnxn, commenter_id=user_id,
        is_description=False, limit=10000)
    return comments

  def GetIssueIDsReportedByUser(self, cnxn, user_id):
    """Get all issue IDs created by a user"""
    rows = self.issue_tbl.Select(cnxn, cols=['id'], reporter_id=user_id,
        limit=10000)
    return [row[0] for row in rows]

  def InsertIssue(self, cnxn, issue):
    """Store the given issue in SQL.

    Args:
      cnxn: connection to SQL database.
      issue: Issue PB to insert into the database.

    Returns:
      The int issue_id of the newly created issue.
    """
    status_id = self._config_service.LookupStatusID(
        cnxn, issue.project_id, issue.status)
    row = (issue.project_id, issue.local_id, status_id,
           issue.owner_id or None,
           issue.reporter_id,
           issue.opened_timestamp,
           issue.closed_timestamp,
           issue.modified_timestamp,
           issue.owner_modified_timestamp,
           issue.status_modified_timestamp,
           issue.component_modified_timestamp,
           issue.derived_owner_id or None,
           self._config_service.LookupStatusID(
               cnxn, issue.project_id, issue.derived_status),
           bool(issue.deleted),
           issue.star_count, issue.attachment_count,
           issue.is_spam)
    # ISSUE_COLs[1:] to skip setting the ID
    # Insert into the Master DB.
    generated_ids = self.issue_tbl.InsertRows(
        cnxn, ISSUE_COLS[1:], [row], commit=False, return_generated_ids=True)
    issue_id = generated_ids[0]
    issue.issue_id = issue_id
    self.issue_tbl.Update(
      cnxn, {'shard': issue_id % settings.num_logical_shards},
      id=issue.issue_id, commit=False)

    self._UpdateIssuesSummary(cnxn, [issue], commit=False)
    self._UpdateIssuesLabels(cnxn, [issue], commit=False)
    self._UpdateIssuesFields(cnxn, [issue], commit=False)
    self._UpdateIssuesComponents(cnxn, [issue], commit=False)
    self._UpdateIssuesCc(cnxn, [issue], commit=False)
    self._UpdateIssuesNotify(cnxn, [issue], commit=False)
    self._UpdateIssuesRelation(cnxn, [issue], commit=False)
    cnxn.Commit()
    self._config_service.InvalidateMemcache([issue])

    return issue_id

  def UpdateIssues(
      self, cnxn, issues, update_cols=None, just_derived=False, commit=True,
      invalidate=True):
    """Update the given issues in SQL.

    Args:
      cnxn: connection to SQL database.
      issues: list of issues to update, these must have been loaded with
          use_cache=False so that issue.assume_stale is False.
      update_cols: optional list of just the field names to update.
      just_derived: set to True when only updating derived fields.
      commit: set to False to skip the DB commit and do it in the caller.
      invalidate: set to False to leave cache invalidatation to the caller.
    """
    if not issues:
      return

    for issue in issues:  # slow, but mysql will not allow REPLACE rows.
      assert not issue.assume_stale, (
          'issue2514: Storing issue that might be stale: %r' % issue)
      delta = {
          'project_id': issue.project_id,
          'local_id': issue.local_id,
          'owner_id': issue.owner_id or None,
          'status_id': self._config_service.LookupStatusID(
              cnxn, issue.project_id, issue.status) or None,
          'opened': issue.opened_timestamp,
          'closed': issue.closed_timestamp,
          'modified': issue.modified_timestamp,
          'owner_modified': issue.owner_modified_timestamp,
          'status_modified': issue.status_modified_timestamp,
          'component_modified': issue.component_modified_timestamp,
          'derived_owner_id': issue.derived_owner_id or None,
          'derived_status_id': self._config_service.LookupStatusID(
              cnxn, issue.project_id, issue.derived_status) or None,
          'deleted': bool(issue.deleted),
          'star_count': issue.star_count,
          'attachment_count': issue.attachment_count,
          'is_spam': issue.is_spam,
          }
      if update_cols is not None:
        delta = {key: val for key, val in delta.iteritems()
                 if key in update_cols}
      self.issue_tbl.Update(cnxn, delta, id=issue.issue_id, commit=False)

    if not update_cols:
      self._UpdateIssuesLabels(cnxn, issues, commit=False)
      self._UpdateIssuesCc(cnxn, issues, commit=False)
      self._UpdateIssuesFields(cnxn, issues, commit=False)
      self._UpdateIssuesComponents(cnxn, issues, commit=False)
      self._UpdateIssuesNotify(cnxn, issues, commit=False)
      if not just_derived:
        self._UpdateIssuesSummary(cnxn, issues, commit=False)
        self._UpdateIssuesRelation(cnxn, issues, commit=False)

    iids_to_invalidate = [issue.issue_id for issue in issues]
    if just_derived and invalidate:
      self.issue_2lc.InvalidateAllKeys(cnxn, iids_to_invalidate)
    elif invalidate:
      self.issue_2lc.InvalidateKeys(cnxn, iids_to_invalidate)
    if commit:
      cnxn.Commit()
    if invalidate:
      self._config_service.InvalidateMemcache(issues)

  def UpdateIssue(
      self, cnxn, issue, update_cols=None, just_derived=False, commit=True,
      invalidate=True):
    """Update the given issue in SQL.

    Args:
      cnxn: connection to SQL database.
      issue: the issue to update.
      update_cols: optional list of just the field names to update.
      just_derived: set to True when only updating derived fields.
      commit: set to False to skip the DB commit and do it in the caller.
      invalidate: set to False to leave cache invalidatation to the caller.
    """
    self.UpdateIssues(
        cnxn, [issue], update_cols=update_cols, just_derived=just_derived,
        commit=commit, invalidate=invalidate)

  def _UpdateIssuesSummary(self, cnxn, issues, commit=True):
    """Update the IssueSummary table rows for the given issues."""
    self.issuesummary_tbl.InsertRows(
        cnxn, ISSUESUMMARY_COLS,
        [(issue.issue_id, issue.summary) for issue in issues],
        replace=True, commit=commit)

  def _UpdateIssuesLabels(self, cnxn, issues, commit=True):
    """Update the Issue2Label table rows for the given issues."""
    label_rows = []
    for issue in issues:
      issue_shard = issue.issue_id % settings.num_logical_shards
      # TODO(jrobbins): If the user adds many novel labels in one issue update,
      # that could be slow. Solution is to add all new labels in a batch first.
      label_rows.extend(
          (issue.issue_id,
           self._config_service.LookupLabelID(cnxn, issue.project_id, label),
           False,
           issue_shard)
          for label in issue.labels)
      label_rows.extend(
          (issue.issue_id,
           self._config_service.LookupLabelID(cnxn, issue.project_id, label),
           True,
           issue_shard)
          for label in issue.derived_labels)

    self.issue2label_tbl.Delete(
        cnxn, issue_id=[issue.issue_id for issue in issues],
        commit=False)
    self.issue2label_tbl.InsertRows(
        cnxn, ISSUE2LABEL_COLS + ['issue_shard'],
        label_rows, ignore=True, commit=commit)

  def _UpdateIssuesFields(self, cnxn, issues, commit=True):
    """Update the Issue2FieldValue table rows for the given issues."""
    fieldvalue_rows = []
    for issue in issues:
      issue_shard = issue.issue_id % settings.num_logical_shards
      for fv in issue.field_values:
        fieldvalue_rows.append(
            (issue.issue_id, fv.field_id, fv.int_value, fv.str_value,
             fv.user_id or None, fv.date_value, fv.url_value, fv.derived,
             issue_shard))

    self.issue2fieldvalue_tbl.Delete(
        cnxn, issue_id=[issue.issue_id for issue in issues], commit=False)
    self.issue2fieldvalue_tbl.InsertRows(
        cnxn, ISSUE2FIELDVALUE_COLS + ['issue_shard'],
        fieldvalue_rows, commit=commit)

  def _UpdateIssuesComponents(self, cnxn, issues, commit=True):
    """Update the Issue2Component table rows for the given issues."""
    issue2component_rows = []
    for issue in issues:
      issue_shard = issue.issue_id % settings.num_logical_shards
      issue2component_rows.extend(
          (issue.issue_id, component_id, False, issue_shard)
          for component_id in issue.component_ids)
      issue2component_rows.extend(
          (issue.issue_id, component_id, True, issue_shard)
          for component_id in issue.derived_component_ids)

    self.issue2component_tbl.Delete(
        cnxn, issue_id=[issue.issue_id for issue in issues], commit=False)
    self.issue2component_tbl.InsertRows(
        cnxn, ISSUE2COMPONENT_COLS + ['issue_shard'],
        issue2component_rows, ignore=True, commit=commit)

  def _UpdateIssuesCc(self, cnxn, issues, commit=True):
    """Update the Issue2Cc table rows for the given issues."""
    cc_rows = []
    for issue in issues:
      issue_shard = issue.issue_id % settings.num_logical_shards
      cc_rows.extend(
          (issue.issue_id, cc_id, False, issue_shard)
          for cc_id in issue.cc_ids)
      cc_rows.extend(
          (issue.issue_id, cc_id, True, issue_shard)
          for cc_id in issue.derived_cc_ids)

    self.issue2cc_tbl.Delete(
        cnxn, issue_id=[issue.issue_id for issue in issues], commit=False)
    self.issue2cc_tbl.InsertRows(
        cnxn, ISSUE2CC_COLS + ['issue_shard'],
        cc_rows, ignore=True, commit=commit)

  def _UpdateIssuesNotify(self, cnxn, issues, commit=True):
    """Update the Issue2Notify table rows for the given issues."""
    notify_rows = []
    for issue in issues:
      derived_rows = [[issue.issue_id, email]
                      for email in issue.derived_notify_addrs]
      notify_rows.extend(derived_rows)

    self.issue2notify_tbl.Delete(
        cnxn, issue_id=[issue.issue_id for issue in issues], commit=False)
    self.issue2notify_tbl.InsertRows(
        cnxn, ISSUE2NOTIFY_COLS, notify_rows, ignore=True, commit=commit)

  def _UpdateIssuesRelation(self, cnxn, issues, commit=True):
    """Update the IssueRelation table rows for the given issues."""
    relation_rows = []
    blocking_rows = []
    dangling_relation_rows = []
    for issue in issues:
      for i, dst_issue_id in enumerate(issue.blocked_on_iids):
        rank = issue.blocked_on_ranks[i]
        relation_rows.append((issue.issue_id, dst_issue_id, 'blockedon', rank))
      for dst_issue_id in issue.blocking_iids:
        blocking_rows.append((dst_issue_id, issue.issue_id, 'blockedon'))
      for dst_ref in issue.dangling_blocked_on_refs:
        dangling_relation_rows.append((
            issue.issue_id, dst_ref.project, dst_ref.issue_id, 'blockedon'))
      for dst_ref in issue.dangling_blocking_refs:
        dangling_relation_rows.append((
            issue.issue_id, dst_ref.project, dst_ref.issue_id, 'blocking'))
      if issue.merged_into:
        relation_rows.append((
            issue.issue_id, issue.merged_into, 'mergedinto', None))

    old_blocking = self.issuerelation_tbl.Select(
        cnxn, cols=ISSUERELATION_COLS[:-1],
        dst_issue_id=[issue.issue_id for issue in issues], kind='blockedon')
    relation_rows.extend([
      (row + (0,)) for row in blocking_rows if row not in old_blocking])
    delete_rows = [row for row in old_blocking if row not in blocking_rows]

    for issue_id, dst_issue_id, kind in delete_rows:
      self.issuerelation_tbl.Delete(cnxn, issue_id=issue_id,
          dst_issue_id=dst_issue_id, kind=kind, commit=False)
    self.issuerelation_tbl.Delete(
        cnxn, issue_id=[issue.issue_id for issue in issues], commit=False)
    self.issuerelation_tbl.InsertRows(
        cnxn, ISSUERELATION_COLS, relation_rows, ignore=True, commit=commit)
    self.danglingrelation_tbl.Delete(
        cnxn, issue_id=[issue.issue_id for issue in issues], commit=False)
    self.danglingrelation_tbl.InsertRows(
        cnxn, DANGLINGRELATION_COLS, dangling_relation_rows, ignore=True,
        commit=commit)

  def _UpdateIssuesModified(
      self, cnxn, iids, modified_timestamp=None, invalidate=True):
    """Store a modified timestamp for each of the specified issues."""
    delta = {'modified': modified_timestamp or int(time.time())}
    self.issue_tbl.Update(cnxn, delta, id=iids, commit=False)
    if invalidate:
      self.InvalidateIIDs(cnxn, iids)

  def DeltaUpdateIssue(
      self, cnxn, services, reporter_id, project_id,
      config, issue, status, owner_id, cc_add, cc_remove, comp_ids_add,
      comp_ids_remove, labels_add, labels_remove, field_vals_add,
      field_vals_remove, fields_clear, blocked_on_add=None,
      blocked_on_remove=None, blocking_add=None, blocking_remove=None,
      merged_into=None, index_now=False, comment=None, summary=None,
      iids_to_invalidate=None, rules=None, predicate_asts=None,
      is_description=False, timestamp=None):
    """Update the issue in the database and return a set of update tuples.

    Args:
      cnxn: connection to SQL database.
      services: connections to persistence layer.
      reporter_id: user ID of the user making this change.
      project_id: int ID for the current project.
      config: ProjectIssueConfig PB for this project.
      issue: Issue PB of issue to update.
      status: new issue status string, if a change is desired.
      owner_id: user ID of the new issue owner, if a change is desired.
      cc_add: list of user IDs of users to add to CC list.
      cc_remove: list of user IDs of users to remove from CC list.
      comp_ids_add: list of component IDs to add to the issue.
      comp_ids_remove: list of component IDs to remove from the issue.
      labels_add: list of issue label strings to add.
      labels_remove: list of issue label strings to remove.
      field_vals_add: dict of FieldValue PBs to add.
      field_vals_remove: list of FieldValue PBs to remove.
      fields_clear: list of custom field IDs to clear.
      blocked_on_add: list of IIDs that this issue is now blocked on.
      blocked_on_remove: list of IIDs that this issue is no longer blocked on.
      blocking_add: list of IIDs that this issue is blocking.
      blocking_remove: list of IIDs that this issue is no longer blocking.
      merged_into: IID of issue that this issue was merged into, 0 to clear,
          or None for no change.
      index_now: True if the issue should be updated in the full text index.
      comment: This should be the content of the comment
          corresponding to this change.
      summary: new issue summary, currently only used by GData API.
      rules: optional list of preloaded FilterRule PBs for this project.
      predicate_asts: optional list of QueryASTs for the rules.  If rules are
          provided, then predicate_asts should also be provided.
      is_description: True if the comment is a new description for the issue.
      timestamp: int timestamp set during testing, otherwise defaults to
          int(time.time()).

    Returns:
      A list of Amendment PBs that describe the set of metadata updates that
      the user made.  This tuple is later used in making the IssueComment.
    """
    timestamp = timestamp or int(time.time())
    old_effective_owner = tracker_bizobj.GetOwnerId(issue)
    old_effective_status = tracker_bizobj.GetStatus(issue)
    old_components = set(issue.component_ids)

    # Make all user input safe to echo out again later.
    status = framework_bizobj.CanonicalizeLabel(status)
    labels_add = [framework_bizobj.CanonicalizeLabel(l) for l in labels_add]
    labels_add = [l for l in labels_add if l]
    labels_remove = [framework_bizobj.CanonicalizeLabel(l)
                     for l in labels_remove]
    labels_remove = [l for l in labels_remove if l]

    logging.info(
        'Bulk edit to project_id %s issue.local_id %s, comment %r',
        project_id, issue.local_id, comment)
    if iids_to_invalidate is None:
      iids_to_invalidate = set([issue.issue_id])
      invalidate = True
    else:
      iids_to_invalidate.add(issue.issue_id)
      invalidate = False  # Caller will do it.

    # Store each updated value in the issue PB, and compute Update PBs
    amendments = []
    if status is not None and status != issue.status:
      amendments.append(tracker_bizobj.MakeStatusAmendment(
          status, issue.status))
      issue.status = status
    if owner_id is not None and owner_id != issue.owner_id:
      amendments.append(tracker_bizobj.MakeOwnerAmendment(
          owner_id, issue.owner_id))
      issue.owner_id = owner_id

    # compute the set of cc'd users added and removed
    cc_add = [cc for cc in cc_add if cc not in issue.cc_ids]
    cc_remove = [cc for cc in cc_remove if cc in issue.cc_ids]
    if cc_add or cc_remove:
      cc_ids = [cc for cc in list(issue.cc_ids) + cc_add
                if cc not in cc_remove]
      issue.cc_ids = cc_ids
      amendments.append(tracker_bizobj.MakeCcAmendment(cc_add, cc_remove))

    # compute the set of components added and removed
    comp_ids_add = [c for c in comp_ids_add if c not in issue.component_ids]
    comp_ids_remove = [c for c in comp_ids_remove if c in issue.component_ids]
    if comp_ids_add or comp_ids_remove:
      comp_ids = [cid for cid in list(issue.component_ids) + comp_ids_add
                  if cid not in comp_ids_remove]
      issue.component_ids = comp_ids
      amendments.append(tracker_bizobj.MakeComponentsAmendment(
          comp_ids_add, comp_ids_remove, config))

    # compute the set of labels added and removed
    (labels, update_labels_add,
     update_labels_remove) = framework_bizobj.MergeLabels(
         issue.labels, labels_add, labels_remove,
         config.exclusive_label_prefixes)

    if update_labels_add or update_labels_remove:
      issue.labels = labels
      amendments.append(tracker_bizobj.MakeLabelsAmendment(
          update_labels_add, update_labels_remove))

    # compute the set of custom fields added and removed
    (field_vals, update_fields_add,
     update_fields_remove) = tracker_bizobj.MergeFields(
         issue.field_values, field_vals_add, field_vals_remove,
         config.field_defs)

    if update_fields_add or update_fields_remove:
      issue.field_values = field_vals
      for fd in config.field_defs:
        added_values_this_field = [
            fv for fv in update_fields_add if fv.field_id == fd.field_id]
        if added_values_this_field:
          amendments.append(tracker_bizobj.MakeFieldAmendment(
              fd.field_id, config,
              [tracker_bizobj.GetFieldValue(fv, {})
               for fv in added_values_this_field],
              old_values=[]))
        removed_values_this_field = [
            fv for fv in update_fields_remove if fv.field_id == fd.field_id]
        if removed_values_this_field:
          amendments.append(tracker_bizobj.MakeFieldAmendment(
              fd.field_id, config, [],
              old_values=[tracker_bizobj.GetFieldValue(fv, {})
                          for fv in removed_values_this_field]))

    if fields_clear:
      field_clear_set = set(fields_clear)
      revised_fields = []
      for fd in config.field_defs:
        if fd.field_id not in field_clear_set:
          revised_fields.extend(
              fv for fv in issue.field_values if fv.field_id == fd.field_id)
        else:
          amendments.append(
              tracker_bizobj.MakeFieldClearedAmendment(fd.field_id, config))
          if fd.field_type == tracker_pb2.FieldTypes.ENUM_TYPE:
            prefix = fd.field_name.lower() + '-'
            filtered_labels = [
                lab for lab in issue.labels
                if not lab.lower().startswith(prefix)]
            issue.labels = filtered_labels

      issue.field_values = revised_fields

    if blocked_on_add or blocked_on_remove:
      old_blocked_on = issue.blocked_on_iids
      blocked_on_add = [iid for iid in blocked_on_add
                        if iid not in old_blocked_on]
      add_refs = [(ref_issue.project_name, ref_issue.local_id)
                  for ref_issue in self.GetIssues(cnxn, blocked_on_add)]
      blocked_on_rm = [iid for iid in blocked_on_remove
                       if iid in old_blocked_on]
      remove_refs = [
          (ref_issue.project_name, ref_issue.local_id)
          for ref_issue in self.GetIssues(cnxn, blocked_on_rm)]
      amendments.append(tracker_bizobj.MakeBlockedOnAmendment(
          add_refs, remove_refs, default_project_name=issue.project_name))
      blocked_on = [iid for iid in old_blocked_on + blocked_on_add
                    if iid not in blocked_on_remove]
      issue.blocked_on_iids, issue.blocked_on_ranks = self.SortBlockedOn(
          cnxn, issue, blocked_on)
      iids_to_invalidate.update(blocked_on_add + blocked_on_remove)

    if blocking_add or blocking_remove:
      old_blocking = issue.blocking_iids
      blocking_add = [iid for iid in blocking_add
                      if iid not in old_blocking]
      add_refs = [(ref_issue.project_name, ref_issue.local_id)
                  for ref_issue in self.GetIssues(cnxn, blocking_add)]
      blocking_remove = [iid for iid in blocking_remove
                         if iid in old_blocking]
      remove_refs = [
          (ref_issue.project_name, ref_issue.local_id)
          for ref_issue in self.GetIssues(cnxn, blocking_remove)]
      amendments.append(tracker_bizobj.MakeBlockingAmendment(
          add_refs, remove_refs, default_project_name=issue.project_name))
      blocking_refs = [iid for iid in old_blocking + blocking_add
                       if iid not in blocking_remove]
      issue.blocking_iids = blocking_refs
      iids_to_invalidate.update(blocking_add + blocking_remove)

    if merged_into is not None and merged_into != issue.merged_into:
      merged_remove = issue.merged_into
      merged_add = merged_into
      issue.merged_into = merged_into
      try:
        remove_issue = self.GetIssue(cnxn, merged_remove)
        remove_ref = remove_issue.project_name, remove_issue.local_id
        iids_to_invalidate.add(merged_remove)
      except NoSuchIssueException:
        remove_ref = None

      try:
        add_issue = self.GetIssue(cnxn, merged_add)
        add_ref = add_issue.project_name, add_issue.local_id
        iids_to_invalidate.add(merged_add)
      except NoSuchIssueException:
        add_ref = None

      amendments.append(tracker_bizobj.MakeMergedIntoAmendment(
          add_ref, remove_ref, default_project_name=issue.project_name))

    if summary and summary != issue.summary:
      amendments.append(tracker_bizobj.MakeSummaryAmendment(
          summary, issue.summary))
      issue.summary = summary

    # If this was a no-op with no comment, bail out and don't save,
    # invalidate, or re-index anything.
    if not amendments and (not comment or not comment.strip()):
      logging.info('No amendments and no comment, so this is a no-op.')
      return [], None

    # Note: no need to check for collisions when the user is doing a delta.

    # update the modified_timestamp for any comment added, even if it was
    # just a text comment with no issue fields changed.
    issue.modified_timestamp = timestamp

    # Update the closed timestamp before filter rules so that rules
    # can test for closed_timestamp, and also after filter rules
    # so that closed_timestamp will be set if the issue is closed by the rule.
    _UpdateClosedTimestamp(config, issue, old_effective_status)
    if rules is None:
      logging.info('Rules were not given')
      rules = services.features.GetFilterRules(cnxn, config.project_id)
      predicate_asts = filterrules_helpers.ParsePredicateASTs(
          rules, config, None)

    filterrules_helpers.ApplyGivenRules(
        cnxn, services, issue, config, rules, predicate_asts)
    _UpdateClosedTimestamp(config, issue, old_effective_status)
    if old_effective_owner != tracker_bizobj.GetOwnerId(issue):
      issue.owner_modified_timestamp = timestamp
    if old_effective_status != tracker_bizobj.GetStatus(issue):
      issue.status_modified_timestamp = timestamp
    if old_components != set(issue.component_ids):
      issue.component_modified_timestamp = timestamp

    # Store the issue in SQL.
    self.UpdateIssue(cnxn, issue, commit=False, invalidate=False)

    comment_pb = self.CreateIssueComment(
        cnxn, issue, reporter_id, comment, amendments=amendments,
        is_description=is_description, commit=False)
    self._UpdateIssuesModified(
        cnxn, iids_to_invalidate, modified_timestamp=issue.modified_timestamp,
        invalidate=invalidate)

    if not invalidate:
      cnxn.Commit()

    if index_now:
      tracker_fulltext.IndexIssues(
          cnxn, [issue], services.user_service, self, self._config_service)

    return amendments, comment_pb

  def InvalidateIIDs(self, cnxn, iids_to_invalidate):
    """Invalidate the specified issues in the Invalidate table and memcache."""
    issues_to_invalidate = self.GetIssues(cnxn, iids_to_invalidate)
    self.issue_2lc.InvalidateKeys(cnxn, iids_to_invalidate)
    self._config_service.InvalidateMemcache(issues_to_invalidate)

  def ApplyIssueComment(
      self, cnxn, services, reporter_id, project_id,
      local_id, summary, status, owner_id, cc_ids, labels, field_values,
      component_ids, blocked_on, blocking, dangling_blocked_on_refs,
      dangling_blocking_refs, merged_into, index_now=True,
      page_gen_ts=None, comment=None, inbound_message=None, attachments=None,
      kept_attachments=None, is_description=False, timestamp=None):
    """Update the issue in the database and return info for notifications.

    Args:
      cnxn: connection to SQL database.
      services: connection to persistence layer.
      reporter_id: user ID of the user making this change.
      project_id: int Project ID for the current project.
      local_id: integer local ID of the issue to update.
      summary: new issue summary string.
      status: new issue status string.
      owner_id: user ID of the new issue owner.
      cc_ids: list of user IDs of users to CC when the issue changes.
      labels: list of new issue label strings.
      field_values: list of FieldValue PBs.
      component_ids: list of int component IDs.
      blocked_on: list of IIDs that this issue is blocked on.
      blocking: list of IIDs that this issue is blocking.
      dangling_blocked_on_refs: list of Codesite issues this is blocked on.
      dangling_blocking_refs: list of Codesite issues this is blocking.
      merged_into: IID of issue that this issue was merged into, 0 to clear.
      index_now: True if the issue should be updated in the full text index.
      page_gen_ts: time at which the issue HTML page was generated,
          used in detecting mid-air collisions.
      comment: This should be the content of the comment
          corresponding to this change.
      inbound_message: optional string full text of an email that caused
          this comment to be added.
      attachments: This should be a list of
          [(filename, contents, mimetype),...] attachments uploaded at
          the time the comment was made.
      kept_attachments: This should be a list of int attachment ids for
          attachments kept from previous descriptions, if the comment is
          a change to the issue description
      is_description: True if the comment is a new description for the issue.
      timestamp: int timestamp set during testing, otherwise defaults to
          int(time.time()).

    Returns:
      (amendments, comment_pb).  Amendments is a list of Amendment PBs
      that describe the set of metadata updates that the user made.
      Comment_pb is the IssueComment for the change.

    Raises:
      MidAirCollisionException: indicates that the issue has been
          changed since the user loaded the page.
    """
    timestamp = timestamp or int(time.time())
    status = framework_bizobj.CanonicalizeLabel(status)
    labels = [framework_bizobj.CanonicalizeLabel(l) for l in labels]
    labels = [l for l in labels if l]

    # Use canonical label names
    label_ids = self._config_service.LookupLabelIDs(
        cnxn, project_id, labels, autocreate=True)
    labels = [self._config_service.LookupLabel(cnxn, project_id, l_id)
              for l_id in label_ids]

    # Get the issue and project configurations.
    config = self._config_service.GetProjectConfig(cnxn, project_id)
    # Because we will modify the issue, load from DB rather than cache.
    issue = self.GetIssueByLocalID(cnxn, project_id, local_id, use_cache=False)

    old_effective_owner = tracker_bizobj.GetOwnerId(issue)
    old_effective_status = tracker_bizobj.GetStatus(issue)
    old_components = set(issue.component_ids)

    # Store each updated value in the issue PB, and compute amendments
    amendments = []
    iids_to_invalidate = set()

    if summary and summary != issue.summary:
      amendments.append(tracker_bizobj.MakeSummaryAmendment(
          summary, issue.summary))
      issue.summary = summary

    if status != issue.status:
      amendments.append(tracker_bizobj.MakeStatusAmendment(
          status, issue.status))
      issue.status = status

    if owner_id != issue.owner_id:
      amendments.append(tracker_bizobj.MakeOwnerAmendment(
          owner_id, issue.owner_id))
      if owner_id == framework_constants.NO_USER_SPECIFIED:
        issue.reset('owner_id')
      else:
        issue.owner_id = owner_id

    # TODO(jrobbins): factor the CC code into a method and add a test
    # compute the set of cc'd users added and removed
    cc_added = [cc for cc in cc_ids if cc not in issue.cc_ids]
    cc_removed = [cc for cc in issue.cc_ids if cc not in cc_ids]
    if cc_added or cc_removed:
      amendments.append(tracker_bizobj.MakeCcAmendment(cc_added, cc_removed))
      issue.cc_ids = cc_ids

    # TODO(jrobbins): factor the labels code into a method and add a test
    # compute the set of labels added and removed
    labels_added = [lab for lab in labels
                    if lab not in issue.labels]
    labels_removed = [lab for lab in issue.labels
                      if lab not in labels]
    if labels_added or labels_removed:
      amendments.append(tracker_bizobj.MakeLabelsAmendment(
          labels_added, labels_removed))
      issue.labels = labels

    old_field_values = collections.defaultdict(list)
    for ofv in issue.field_values:
      # Passing {} because I just want the user_id, not the email address.
      old_field_values[ofv.field_id].append(
          tracker_bizobj.GetFieldValue(ofv, {}))
    for field_id, values in old_field_values.iteritems():
      old_field_values[field_id] = sorted(values)

    new_field_values = collections.defaultdict(list)
    for nfv in field_values:
      new_field_values[nfv.field_id].append(
          tracker_bizobj.GetFieldValue(nfv, {}))
    for field_id, values in new_field_values.iteritems():
      new_field_values[field_id] = sorted(values)

    field_ids_added = {fv.field_id for fv in field_values
                       if fv.field_id not in old_field_values}
    field_ids_removed = {ofv.field_id for ofv in issue.field_values
                         if ofv.field_id not in new_field_values}
    field_ids_changed = {
        fv.field_id for fv in field_values
        if (fv.field_id in old_field_values and
            old_field_values[fv.field_id] != new_field_values[fv.field_id])}

    if field_ids_added or field_ids_removed or field_ids_changed:
      amendments.extend(
          tracker_bizobj.MakeFieldAmendment(fid, config, new_field_values[fid])
          for fid in field_ids_added)
      amendments.extend(
          tracker_bizobj.MakeFieldAmendment(
              fid, config, new_field_values[fid],
              old_values=old_field_values[fid])
          for fid in field_ids_changed)
      amendments.extend(
          tracker_bizobj.MakeFieldAmendment(fid, config, [])
          for fid in field_ids_removed)

      issue.field_values = field_values

    comps_added = [comp for comp in component_ids
                   if comp not in issue.component_ids]
    comps_removed = [comp for comp in issue.component_ids
                     if comp not in component_ids]
    if comps_added or comps_removed:
      amendments.append(tracker_bizobj.MakeComponentsAmendment(
          comps_added, comps_removed, config))
      issue.component_ids = component_ids

    if merged_into != issue.merged_into:
      # TODO(jrobbins): refactor this into LookupIssueRefByIssueID().
      try:
        merged_remove = self.GetIssue(cnxn, issue.merged_into)
        remove_ref = merged_remove.project_name, merged_remove.local_id
        iids_to_invalidate.add(issue.merged_into)
      except NoSuchIssueException:
        remove_ref = None

      try:
        merged_add = self.GetIssue(cnxn, merged_into)
        add_ref = merged_add.project_name, merged_add.local_id
        iids_to_invalidate.add(merged_into)
      except NoSuchIssueException:
        add_ref = None

      issue.merged_into = merged_into
      amendments.append(tracker_bizobj.MakeMergedIntoAmendment(
          add_ref, remove_ref, default_project_name=issue.project_name))

    blockers_added, blockers_removed = framework_helpers.ComputeListDeltas(
        issue.blocked_on_iids, blocked_on)
    danglers_added, danglers_removed = framework_helpers.ComputeListDeltas(
        issue.dangling_blocked_on_refs, dangling_blocked_on_refs)
    blocked_add_issues = []
    blocked_remove_issues = []
    if blockers_added or blockers_removed or danglers_added or danglers_removed:
      blocked_add_issues = self.GetIssues(cnxn, blockers_added)
      add_refs = [(ref_issue.project_name, ref_issue.local_id)
                  for ref_issue in blocked_add_issues]
      add_refs.extend([(ref.project, ref.issue_id) for ref in danglers_added])
      blocked_remove_issues = self.GetIssues(cnxn, blockers_removed)
      remove_refs = [
          (ref_issue.project_name, ref_issue.local_id)
          for ref_issue in blocked_remove_issues]
      remove_refs.extend([(ref.project, ref.issue_id)
                          for ref in danglers_removed])
      amendments.append(tracker_bizobj.MakeBlockedOnAmendment(
          add_refs, remove_refs, default_project_name=issue.project_name))
      issue.blocked_on_iids, issue.blocked_on_ranks = self.SortBlockedOn(
          cnxn, issue, blocked_on)
      issue.dangling_blocked_on_refs = dangling_blocked_on_refs
      iids_to_invalidate.update(blockers_added + blockers_removed)

    blockers_added, blockers_removed = framework_helpers.ComputeListDeltas(
        issue.blocking_iids, blocking)
    danglers_added, danglers_removed = framework_helpers.ComputeListDeltas(
        issue.dangling_blocking_refs, dangling_blocking_refs)
    blocking_add_issues = []
    blocking_remove_issues = []
    if blockers_added or blockers_removed or danglers_added or danglers_removed:
      blocking_add_issues = self.GetIssues(cnxn, blockers_added)
      add_refs = [(ref_issue.project_name, ref_issue.local_id)
                  for ref_issue in blocking_add_issues]
      add_refs.extend([(ref.project, ref.issue_id) for ref in danglers_added])
      blocking_remove_issues = self.GetIssues(cnxn, blockers_removed)
      remove_refs = [
          (ref_issue.project_name, ref_issue.local_id)
          for ref_issue in blocking_remove_issues]
      remove_refs.extend([(ref.project, ref.issue_id)
                          for ref in danglers_removed])
      amendments.append(tracker_bizobj.MakeBlockingAmendment(
          add_refs, remove_refs, default_project_name=issue.project_name))
      issue.blocking_iids = blocking
      issue.dangling_blocking_refs = dangling_blocking_refs
      iids_to_invalidate.update(blockers_added + blockers_removed)

    logging.info('later amendments so far is %r', amendments)

    # Raise an exception if the issue was changed by another user
    # while this user was viewing/editing the issue.
    if page_gen_ts and amendments:
      # The issue timestamp is stored in seconds, convert to microseconds to
      # match the page_gen_ts.
      issue_ts = issue.modified_timestamp * 1000000
      if issue_ts > page_gen_ts:
        logging.info('%d > %d', issue_ts, page_gen_ts)
        logging.info('amendments: %s', amendments)
        # Forget all the modificiations made to this issue in RAM.
        self.issue_2lc.InvalidateKeys(cnxn, [issue.issue_id])
        raise MidAirCollisionException('issue %d' % local_id, local_id)

    # update the modified_timestamp for any comment added, even if it was
    # just a text comment with no issue fields changed.
    issue.modified_timestamp = timestamp

    # Update closed_timestamp both before and after filter rules.
    _UpdateClosedTimestamp(config, issue, old_effective_status)
    filterrules_helpers.ApplyFilterRules(cnxn, services, issue, config)
    _UpdateClosedTimestamp(config, issue, old_effective_status)
    if old_effective_owner != tracker_bizobj.GetOwnerId(issue):
      issue.owner_modified_timestamp = timestamp
    if old_effective_status != tracker_bizobj.GetStatus(issue):
      issue.status_modified_timestamp = timestamp
    if old_components != set(issue.component_ids):
      issue.component_modified_timestamp = timestamp

    self.UpdateIssue(cnxn, issue)
    # TODO(jrobbins): only invalidate nonviewable if the following changed:
    # restriction label, owner, cc, or user-type custom field.
    self._config_service.InvalidateMemcache([issue], key_prefix='nonviewable:')

    author = services.user.GetUser(cnxn, reporter_id)
    project = services.project.GetProject(cnxn, project_id)
    effective_ids = services.usergroup.LookupMemberships(cnxn, reporter_id)
    is_project_member = framework_bizobj.UserIsInProject(project, effective_ids)
    classification = services.spam.ClassifyComment(
        comment, author, is_project_member)

    if classification['confidence_is_spam'] > settings.classifier_spam_thresh:
      logging.info('classified comment as spam: %s' % comment)
      is_spam = True
    else:
      logging.info('classified comment as ham')
      is_spam = False

    if amendments or (comment and comment.strip()) or attachments:
      logging.info('amendments = %r', amendments)
      comment_pb = self.CreateIssueComment(
          cnxn, issue, reporter_id, comment,
          amendments=amendments, attachments=attachments,
          inbound_message=inbound_message, is_spam=is_spam,
          is_description=is_description, kept_attachments=kept_attachments)

      # ClassifyComment only returns confidence_is_spam, but
      # RecordClassifierCommentVerdict records confidence of
      # ham or spam. Therefore if ham, invert score.
      confidence = classification['confidence_is_spam']
      if not is_spam:
        confidence = 1.0 - confidence

      services.spam.RecordClassifierCommentVerdict(
          cnxn, comment_pb, is_spam, confidence,
          classification['failed_open'])
    else:
      comment_pb = None

    # Add a comment to the newly added issues saying they are now blocking
    # this issue.
    for add_issue in blocked_add_issues:
      self.CreateIssueComment(
          cnxn, add_issue, reporter_id, content='',
          amendments=[tracker_bizobj.MakeBlockingAmendment(
              [(issue.project_name, issue.local_id)], [],
              default_project_name=add_issue.project_name)])
    # Add a comment to the newly removed issues saying they are no longer
    # blocking this issue.
    for remove_issue in blocked_remove_issues:
      self.CreateIssueComment(
          cnxn, remove_issue, reporter_id, content='',
          amendments=[tracker_bizobj.MakeBlockingAmendment(
              [], [(issue.project_name, issue.local_id)],
              default_project_name=remove_issue.project_name)])

    # Add a comment to the newly added issues saying they are now blocked on
    # this issue.
    for add_issue in blocking_add_issues:
      self.CreateIssueComment(
          cnxn, add_issue, reporter_id, content='',
          amendments=[tracker_bizobj.MakeBlockedOnAmendment(
              [(issue.project_name, issue.local_id)], [],
              default_project_name=add_issue.project_name)])
    # Add a comment to the newly removed issues saying they are no longer
    # blocked on this issue.
    for remove_issue in blocking_remove_issues:
      self.CreateIssueComment(
          cnxn, remove_issue, reporter_id, content='',
          amendments=[tracker_bizobj.MakeBlockedOnAmendment(
              [], [(issue.project_name, issue.local_id)],
              default_project_name=remove_issue.project_name)])

    self._UpdateIssuesModified(
        cnxn, iids_to_invalidate, modified_timestamp=issue.modified_timestamp)

    if index_now:
      tracker_fulltext.IndexIssues(
          cnxn, [issue], services.user, self, self._config_service)

    if is_spam:
      # Soft-deletes have to have a user ID, so spam comments are
      # just "deleted" by the commenter.
      self.SoftDeleteComment(cnxn, issue, comment_pb,
          reporter_id, services.user, is_spam=True)
    return amendments, comment_pb

  def RelateIssues(self, cnxn, issue_relation_dict, commit=True):
    """Update the IssueRelation table rows for the given relationships.

    issue_relation_dict is a mapping of 'source' issues to 'destination' issues,
    paired with the kind of relationship connecting the two.
    """
    relation_rows = []
    for src_iid, dests in issue_relation_dict.iteritems():
      for dst_iid, kind in dests:
        if kind == 'blocking':
          relation_rows.append((dst_iid, src_iid, 'blockedon', 0))
        elif kind == 'blockedon':
          relation_rows.append((src_iid, dst_iid, 'blockedon', 0))
        elif kind == 'mergedinto':
          relation_rows.append((src_iid, dst_iid, 'mergedinto', None))

    self.issuerelation_tbl.InsertRows(
        cnxn, ISSUERELATION_COLS, relation_rows, ignore=True, commit=commit)

  def CopyIssues(self, cnxn, dest_project, issues, user_service, copier_id):
    """Copy the given issues into the destination project."""
    created_issues = []
    iids_to_invalidate = set()

    for target_issue in issues:
      assert not target_issue.assume_stale, (
          'issue2514: Copying issue that might be stale: %r' % target_issue)
      new_issue = tracker_pb2.Issue()
      new_issue.project_id = dest_project.project_id
      new_issue.project_name = dest_project.project_name
      new_issue.summary = target_issue.summary
      new_issue.labels.extend(target_issue.labels)
      new_issue.field_values.extend(target_issue.field_values)
      new_issue.reporter_id = copier_id

      timestamp = int(time.time())
      new_issue.opened_timestamp = timestamp
      new_issue.modified_timestamp = timestamp

      target_comments = self.GetCommentsForIssue(cnxn, target_issue.issue_id)
      initial_summary_comment = target_comments[0]

      # Note that blocking and merge_into are not copied.
      if target_issue.blocked_on_iids:
        blocked_on = target_issue.blocked_on_iids
        iids_to_invalidate.update(blocked_on)
        new_issue.blocked_on_iids = blocked_on

      # Gather list of attachments from the target issue's summary comment.
      # MakeIssueComments expects a list of [(filename, contents, mimetype),...]
      attachments = []
      for attachment in initial_summary_comment.attachments:
        object_path = ('/' + app_identity.get_default_gcs_bucket_name() +
                       attachment.gcs_object_id)
        with cloudstorage.open(object_path, 'r') as f:
          content = f.read()
          attachments.append(
              [attachment.filename, content, attachment.mimetype])

      if attachments:
        new_issue.attachment_count = len(attachments)

      # Create the same summary comment as the target issue.
      comment = self._MakeIssueComment(
          dest_project.project_id, copier_id, initial_summary_comment.content,
          attachments=attachments, timestamp=timestamp, is_description=True)

      new_issue.local_id = self.AllocateNextLocalID(
          cnxn, dest_project.project_id)
      issue_id = self.InsertIssue(cnxn, new_issue)
      comment.issue_id = issue_id
      self.InsertComment(cnxn, comment)

      if permissions.HasRestrictions(new_issue, 'view'):
        self._config_service.InvalidateMemcache(
            [new_issue], key_prefix='nonviewable:')

      tracker_fulltext.IndexIssues(
          cnxn, [new_issue], user_service, self, self._config_service)
      created_issues.append(new_issue)

    # The referenced issues are all modified when the relationship is added.
    self._UpdateIssuesModified(
      cnxn, iids_to_invalidate, modified_timestamp=timestamp)

    return created_issues

  def MoveIssues(self, cnxn, dest_project, issues, user_service):
    """Move the given issues into the destination project."""
    old_location_rows = [
        (issue.issue_id, issue.project_id, issue.local_id)
        for issue in issues]
    moved_back_iids = set()

    former_locations_in_project = self.issueformerlocations_tbl.Select(
        cnxn, cols=ISSUEFORMERLOCATIONS_COLS,
        project_id=dest_project.project_id,
        issue_id=[issue.issue_id for issue in issues])
    former_locations = {
        issue_id: local_id
        for issue_id, project_id, local_id in former_locations_in_project}

    # Remove the issue id from issue_id_2lc so that it does not stay
    # around in cache and memcache.
    # The Key of IssueIDTwoLevelCache is (project_id, local_id).
    issue_id_2lc_key = (issues[0].project_id, issues[0].local_id)
    self.issue_id_2lc.InvalidateKeys(cnxn, [issue_id_2lc_key])

    for issue in issues:
      if issue.issue_id in former_locations:
        dest_id = former_locations[issue.issue_id]
        moved_back_iids.add(issue.issue_id)
      else:
        dest_id = self.AllocateNextLocalID(cnxn, dest_project.project_id)

      issue.local_id = dest_id
      issue.project_id = dest_project.project_id
      issue.project_name = dest_project.project_name

    # Rewrite each whole issue so that status and label IDs are looked up
    # in the context of the destination project.
    self.UpdateIssues(cnxn, issues)

    # Comments also have the project_id because it is needed for an index.
    self.comment_tbl.Update(
        cnxn, {'project_id': dest_project.project_id},
        issue_id=[issue.issue_id for issue in issues], commit=False)

    # Record old locations so that we can offer links if the user looks there.
    self.issueformerlocations_tbl.InsertRows(
        cnxn, ISSUEFORMERLOCATIONS_COLS, old_location_rows, ignore=True,
        commit=False)
    cnxn.Commit()

    tracker_fulltext.IndexIssues(
        cnxn, issues, user_service, self, self._config_service)

    return moved_back_iids

  def ExpungeFormerLocations(self, cnxn, project_id):
    """Delete history of issues that were in this project but moved out."""
    self.issueformerlocations_tbl.Delete(cnxn, project_id=project_id)

  def ExpungeIssues(self, cnxn, issue_ids):
    """Completely delete the specified issues from the database."""
    logging.info('expunging the issues %r', issue_ids)
    tracker_fulltext.UnindexIssues(issue_ids)

    remaining_iids = issue_ids[:]

    # Note: these are purposely not done in a transaction to allow
    # incremental progress in what might be a very large change.
    # We are not concerned about non-atomic deletes because all
    # this data will be gone eventually anyway.
    while remaining_iids:
      iids_in_chunk = remaining_iids[:CHUNK_SIZE]
      remaining_iids = remaining_iids[CHUNK_SIZE:]
      self.issuesummary_tbl.Delete(cnxn, issue_id=iids_in_chunk)
      self.issue2label_tbl.Delete(cnxn, issue_id=iids_in_chunk)
      self.issue2component_tbl.Delete(cnxn, issue_id=iids_in_chunk)
      self.issue2cc_tbl.Delete(cnxn, issue_id=iids_in_chunk)
      self.issue2notify_tbl.Delete(cnxn, issue_id=iids_in_chunk)
      self.issueupdate_tbl.Delete(cnxn, issue_id=iids_in_chunk)
      self.attachment_tbl.Delete(cnxn, issue_id=iids_in_chunk)
      self.comment_tbl.Delete(cnxn, issue_id=iids_in_chunk)
      self.issuerelation_tbl.Delete(cnxn, issue_id=iids_in_chunk)
      self.issuerelation_tbl.Delete(cnxn, dst_issue_id=iids_in_chunk)
      self.danglingrelation_tbl.Delete(cnxn, issue_id=iids_in_chunk)
      self.issueformerlocations_tbl.Delete(cnxn, issue_id=iids_in_chunk)
      self.reindexqueue_tbl.Delete(cnxn, issue_id=iids_in_chunk)
      self.issue_tbl.Delete(cnxn, id=iids_in_chunk)

  def SoftDeleteIssue(self, cnxn, project_id, local_id, deleted, user_service):
    """Set the deleted boolean on the indicated issue and store it.

    Args:
      cnxn: connection to SQL database.
      project_id: int project ID for the current project.
      local_id: int local ID of the issue to freeze/unfreeze.
      deleted: boolean, True to soft-delete, False to undelete.
      user_service: persistence layer for users, used to lookup user IDs.
    """
    issue = self.GetIssueByLocalID(cnxn, project_id, local_id, use_cache=False)
    issue.deleted = deleted
    self.UpdateIssue(cnxn, issue, update_cols=['deleted'])
    tracker_fulltext.IndexIssues(
        cnxn, [issue], user_service, self, self._config_service)

  def DeleteComponentReferences(self, cnxn, component_id):
    """Delete any references to the specified component."""
    # TODO(jrobbins): add tasks to re-index any affected issues.
    # Note: if this call fails, some data could be left
    # behind, but it would not be displayed, and it could always be
    # GC'd from the DB later.
    self.issue2component_tbl.Delete(cnxn, component_id=component_id)

  ### Local ID generation

  def InitializeLocalID(self, cnxn, project_id):
    """Initialize the local ID counter for the specified project to zero.

    Args:
      cnxn: connection to SQL database.
      project_id: int ID of the project.
    """
    self.localidcounter_tbl.InsertRow(
        cnxn, project_id=project_id, used_local_id=0, used_spam_id=0)

  def SetUsedLocalID(self, cnxn, project_id):
    """Set the local ID counter based on existing issues.

    Args:
      cnxn: connection to SQL database.
      project_id: int ID of the project.
    """
    highest_id = self.GetHighestLocalID(cnxn, project_id)
    self.localidcounter_tbl.InsertRow(
        cnxn, replace=True, used_local_id=highest_id, project_id=project_id)
    return highest_id

  def AllocateNextLocalID(self, cnxn, project_id):
    """Return the next available issue ID in the specified project.

    Args:
      cnxn: connection to SQL database.
      project_id: int ID of the project.

    Returns:
      The next local ID.
    """
    try:
      next_local_id = self.localidcounter_tbl.IncrementCounterValue(
          cnxn, 'used_local_id', project_id=project_id)
    except AssertionError as e:
      logging.info('exception incrementing local_id counter: %s', e)
      next_local_id = self.SetUsedLocalID(cnxn, project_id) + 1
    return next_local_id

  def GetHighestLocalID(self, cnxn, project_id):
    """Return the highest used issue ID in the specified project.

    Args:
      cnxn: connection to SQL database.
      project_id: int ID of the project.

    Returns:
      The highest local ID for an active or moved issues.
    """
    highest = self.issue_tbl.SelectValue(
        cnxn, 'MAX(local_id)', project_id=project_id)
    highest = highest or 0  # It will be None if the project has no issues.
    highest_former = self.issueformerlocations_tbl.SelectValue(
        cnxn, 'MAX(local_id)', project_id=project_id)
    highest_former = highest_former or 0
    return max(highest, highest_former)

  def GetAllLocalIDsInProject(self, cnxn, project_id, min_local_id=None):
    """Return the list of local IDs only, not the actual issues.

    Args:
      cnxn: connection to SQL database.
      project_id: the ID of the project to which the issue belongs.
      min_local_id: point to start at.

    Returns:
      A range object of local IDs from 1 to N, or from min_local_id to N.  It
      may be the case that some of those local IDs are no longer used, e.g.,
      if some issues were moved out of this project.
    """
    if not min_local_id:
      min_local_id = 1
    highest_local_id = self.GetHighestLocalID(cnxn, project_id)
    return range(min_local_id, highest_local_id + 1)

  def ExpungeLocalIDCounters(self, cnxn, project_id):
    """Delete history of local ids that were in this project."""
    self.localidcounter_tbl.Delete(cnxn, project_id=project_id)

  ### Comments

  def _UnpackComment(self, comment_row, content_dict, inbound_message_dict):
    """Partially construct a Comment PB from a DB row."""
    (comment_id, issue_id, created, project_id, commenter_id,
     deleted_by, is_spam, is_description, commentcontent_id) = comment_row
    comment = tracker_pb2.IssueComment()
    comment.id = comment_id
    comment.issue_id = issue_id
    comment.timestamp = created
    comment.project_id = project_id
    comment.user_id = commenter_id
    comment.content = content_dict.get(commentcontent_id, '')
    comment.inbound_message = inbound_message_dict.get(commentcontent_id, '')
    comment.deleted_by = deleted_by or 0
    comment.is_spam = bool(is_spam)
    comment.is_description = bool(is_description)
    return comment

  def _UnpackAmendment(self, amendment_row):
    """Construct an Amendment PB from a DB row."""
    (_id, _issue_id, comment_id, field_name,
     old_value, new_value, added_user_id, removed_user_id,
     custom_field_name) = amendment_row
    amendment = tracker_pb2.Amendment()
    field_enum = tracker_pb2.FieldID(field_name.upper())
    amendment.field = field_enum

    # TODO(jrobbins): display old values in more cases.
    if new_value is not None:
      amendment.newvalue = new_value
    if old_value is not None:
      amendment.oldvalue = old_value
    if added_user_id:
      amendment.added_user_ids.append(added_user_id)
    if removed_user_id:
      amendment.removed_user_ids.append(removed_user_id)
    if custom_field_name:
      amendment.custom_field_name = custom_field_name
    return amendment, comment_id

  def _ConsolidateAmendments(self, amendments):
    """Consoliodate amendments of the same field in one comment into one
    amendment PB."""

    fields_dict = {}
    result = []

    for amendment in amendments:
      key = amendment.field, amendment.custom_field_name
      fields_dict.setdefault(key, []).append(amendment)
    for (field, _custom_name), amendments in fields_dict.iteritems():
      new_amendment = tracker_pb2.Amendment()
      new_amendment.field = field
      for amendment in amendments:
        if amendment.newvalue is not None:
          new_amendment.newvalue = amendment.newvalue
        if amendment.oldvalue is not None:
          new_amendment.oldvalue = amendment.oldvalue
        if amendment.added_user_ids:
          new_amendment.added_user_ids.extend(amendment.added_user_ids)
        if amendment.removed_user_ids:
          new_amendment.removed_user_ids.extend(amendment.removed_user_ids)
        if amendment.custom_field_name:
          new_amendment.custom_field_name = amendment.custom_field_name
      result.append(new_amendment)
    return result

  def _UnpackAttachment(self, attachment_row):
    """Construct an Attachment PB from a DB row."""
    (attachment_id, _issue_id, comment_id, filename, filesize, mimetype,
     deleted, gcs_object_id) = attachment_row
    attach = tracker_pb2.Attachment()
    attach.attachment_id = attachment_id
    attach.filename = filename
    attach.filesize = filesize
    attach.mimetype = mimetype
    attach.deleted = bool(deleted)
    attach.gcs_object_id = gcs_object_id
    return attach, comment_id

  def _DeserializeComments(
      self, comment_rows, commentcontent_rows, amendment_rows, attachment_rows):
    """Turn rows into IssueComment PBs."""
    results = []  # keep objects in the same order as the rows
    results_dict = {}  # for fast access when joining.

    content_dict = dict(
        (commentcontent_id, content) for
        commentcontent_id, content, _ in commentcontent_rows)
    inbound_message_dict = dict(
        (commentcontent_id, inbound_message) for
        commentcontent_id, _, inbound_message in commentcontent_rows)

    for comment_row in comment_rows:
      comment = self._UnpackComment(
          comment_row, content_dict, inbound_message_dict)
      results.append(comment)
      results_dict[comment.id] = comment

    for amendment_row in amendment_rows:
      amendment, comment_id = self._UnpackAmendment(amendment_row)
      try:
        results_dict[comment_id].amendments.extend([amendment])
      except KeyError:
        logging.error('Found amendment for missing comment: %r', comment_id)

    for attachment_row in attachment_rows:
      attach, comment_id = self._UnpackAttachment(attachment_row)
      try:
        results_dict[comment_id].attachments.append(attach)
      except KeyError:
        logging.error('Found attachment for missing comment: %r', comment_id)

    for c in results:
      c.amendments = self._ConsolidateAmendments(c.amendments)

    return results

  # TODO(jrobbins): make this a private method and expose just the interface
  # needed by activities.py.
  def GetComments(self, cnxn, where=None, order_by=None, **kwargs):
    """Retrieve comments from SQL."""
    # Explicitly specify column Comment.id to allow joins on other tables that
    # have an id column.
    order_by = order_by or [('created', [])]
    comment_rows = self.comment_tbl.Select(
        cnxn, cols=COMMENT_COLS, where=where,
        order_by=order_by, **kwargs)
    cids = [row[0] for row in comment_rows]
    commentcontent_ids = [row[-1] for row in comment_rows]
    content_rows = self.commentcontent_tbl.Select(
        cnxn, cols=COMMENTCONTENT_COLS, id=commentcontent_ids)
    amendment_rows = self.issueupdate_tbl.Select(
        cnxn, cols=ISSUEUPDATE_COLS, comment_id=cids)
    attachment_rows = self.attachment_tbl.Select(
        cnxn, cols=ATTACHMENT_COLS, comment_id=cids)

    comments = self._DeserializeComments(
        comment_rows, content_rows, amendment_rows, attachment_rows)
    return comments

  def GetComment(self, cnxn, comment_id):
    """Get the requested comment, or raise an exception."""
    comments = self.GetComments(cnxn, id=comment_id)
    try:
      return comments[0]
    except IndexError:
      raise NoSuchCommentException()

  def GetCommentsForIssue(self, cnxn, issue_id):
    """Return all IssueComment PBs for the specified issue.

    Args:
      cnxn: connection to SQL database.
      issue_id: int global ID of the issue.

    Returns:
      A list of the IssueComment protocol buffers for the description
      and comments on this issue.
    """
    comments = self.GetComments(cnxn, issue_id=[issue_id])
    for i, comment in enumerate(comments):
      comment.sequence = i

    return comments

  def GetCommentsByID(self, cnxn, comment_ids, sequences):
    """Return all IssueComment PBs by comment ids.

    Args:
      cnxn: connection to SQL database.
      comment_ids: a list of comment ids.
      sequences: sequence of the comments.

    Returns:
      A list of the IssueComment protocol buffers for the description
      and comments on this issue.
    """
    order_by = [('created ASC', [])]
    comment_rows = self.comment_tbl.Select(
        cnxn, cols=COMMENT_COLS, order_by=order_by, id=comment_ids)
    comment_ids = [row[0] for row in comment_rows]
    commentcontent_ids = [row[-1] for row in comment_rows]
    content_rows = self.commentcontent_tbl.Select(
        cnxn, cols=COMMENTCONTENT_COLS, id=commentcontent_ids)
    amendment_rows = self.issueupdate_tbl.Select(
        cnxn, cols=ISSUEUPDATE_COLS, comment_id=comment_ids)
    attachment_rows = self.attachment_tbl.Select(
        cnxn, cols=ATTACHMENT_COLS, comment_id=comment_ids)

    comments = self._DeserializeComments(
        comment_rows, content_rows, amendment_rows, attachment_rows)

    for i in xrange(len(comment_ids)):
      comments[i].sequence = sequences[i]

    return comments

  def GetAbbrCommentsForIssue(self, cnxn, issue_id):
    """Get all abbreviated comments for the specified issue."""
    order_by = [('created ASC', [])]
    comment_rows = self.comment_tbl.Select(
        cnxn, cols=ABBR_COMMENT_COLS, issue_id=[issue_id], order_by=order_by)

    return comment_rows

  # TODO(jrobbins): remove this method because it is too slow when an issue
  # has a huge number of comments.
  def GetCommentsForIssues(self, cnxn, issue_ids):
    """Return all IssueComment PBs for each issue ID in the given list.

    Args:
      cnxn: connection to SQL database.
      issue_ids: list of integer global issue IDs.

    Returns:
      Dict {issue_id: [IssueComment, ...]} with IssueComment protocol
      buffers for the description and comments on each issue.
    """
    comments = self.GetComments(cnxn, issue_id=issue_ids)

    comments_dict = collections.defaultdict(list)
    for comment in comments:
      comment.sequence = len(comments_dict[comment.issue_id])
      comments_dict[comment.issue_id].append(comment)

    return comments_dict

  def InsertComment(self, cnxn, comment, commit=True):
    """Store the given issue comment in SQL.

    Args:
      cnxn: connection to SQL database.
      comment: IssueComment PB to insert into the database.
      commit: set to False to avoid doing the commit for now.
    """
    commentcontent_id = self.commentcontent_tbl.InsertRow(
        cnxn, content=comment.content,
        inbound_message=comment.inbound_message, commit=commit)
    comment_id = self.comment_tbl.InsertRow(
        cnxn, issue_id=comment.issue_id, created=comment.timestamp,
        project_id=comment.project_id,
        commenter_id=comment.user_id,
        deleted_by=comment.deleted_by or None,
        is_spam=comment.is_spam, is_description=comment.is_description,
        commentcontent_id=commentcontent_id,
        commit=commit)
    comment.id = comment_id

    amendment_rows = []
    for amendment in comment.amendments:
      field_enum = str(amendment.field).lower()
      if (amendment.get_assigned_value('newvalue') is not None and
          not amendment.added_user_ids and not amendment.removed_user_ids):
        amendment_rows.append((
            comment.issue_id, comment_id, field_enum,
            amendment.oldvalue, amendment.newvalue,
            None, None, amendment.custom_field_name))
      for added_user_id in amendment.added_user_ids:
        amendment_rows.append((
            comment.issue_id, comment_id, field_enum, None, None,
            added_user_id, None, amendment.custom_field_name))
      for removed_user_id in amendment.removed_user_ids:
        amendment_rows.append((
            comment.issue_id, comment_id, field_enum, None, None,
            None, removed_user_id, amendment.custom_field_name))
    # ISSUEUPDATE_COLS[1:] to skip id column.
    self.issueupdate_tbl.InsertRows(
        cnxn, ISSUEUPDATE_COLS[1:], amendment_rows, commit=commit)

    attachment_rows = []
    for attach in comment.attachments:
      attachment_rows.append([
          comment.issue_id, comment.id, attach.filename, attach.filesize,
          attach.mimetype, attach.deleted, attach.gcs_object_id])
    self.attachment_tbl.InsertRows(
        cnxn, ATTACHMENT_COLS[1:], attachment_rows, commit=commit)

  def _UpdateComment(self, cnxn, comment, update_cols=None):
    """Update the given issue comment in SQL.

    Args:
      cnxn: connection to SQL database.
      comment: IssueComment PB to update in the database.
      update_cols: optional list of just the field names to update.
    """
    delta = {
        'commenter_id': comment.user_id,
        'deleted_by': comment.deleted_by or None,
        'is_spam': comment.is_spam,
        }
    if update_cols is not None:
      delta = {key: val for key, val in delta.iteritems()
               if key in update_cols}

    self.comment_tbl.Update(cnxn, delta, id=comment.id)

  def _MakeIssueComment(
      self, project_id, user_id, content, inbound_message=None,
      amendments=None, attachments=None, kept_attachments=None, timestamp=None,
      is_spam=False, is_description=False):
    """Create in IssueComment protocol buffer in RAM.

    Args:
      project_id: Project with the issue.
      user_id: the user ID of the user who entered the comment.
      content: string body of the comment.
      inbound_message: optional string full text of an email that
          caused this comment to be added.
      amendments: list of Amendment PBs describing the
          metadata changes that the user made along w/ comment.
      attachments: [(filename, contents, mimetype),...] attachments uploaded at
          the time the comment was made.
      kept_attachments: list of Attachment PBs for attachments kept from
          previous descriptions, if the comment is a description
      timestamp: time at which the comment was made, defaults to now.
      is_spam: True if the comment was classified as spam.
      is_description: True if the comment is a description for the issue.
    Returns:
      The new IssueComment protocol buffer.

    The content may have some markup done during input processing.

    Any attachments are immediately stored.
    """
    comment = tracker_pb2.IssueComment()
    comment.project_id = project_id
    comment.user_id = user_id
    comment.content = content or ''
    comment.is_spam = is_spam
    comment.is_description = is_description
    if not timestamp:
      timestamp = int(time.time())
    comment.timestamp = int(timestamp)
    if inbound_message:
      comment.inbound_message = inbound_message
    if amendments:
      logging.info('amendments is %r', amendments)
      comment.amendments.extend(amendments)

    if attachments:
      for filename, body, mimetype in attachments:
        gcs_object_id = gcs_helpers.StoreObjectInGCS(body, mimetype, project_id)
        attach = tracker_pb2.Attachment()
        # attachment id is determined later by the SQL DB.
        attach.filename = filename
        attach.filesize = len(body)
        attach.mimetype = mimetype
        attach.gcs_object_id = gcs_object_id
        comment.attachments.extend([attach])
        logging.info("Save attachment with object_id: %s" % gcs_object_id)

    if kept_attachments:
      for kept_attach in kept_attachments:
        (filename, filesize, mimetype, deleted,
         gcs_object_id) = kept_attach[3:]
        new_attach = tracker_pb2.Attachment(
            filename=filename, filesize=filesize, mimetype=mimetype,
            deleted=bool(deleted), gcs_object_id=gcs_object_id)
        comment.attachments.append(new_attach)
        logging.info("Copy attachment with object_id: %s" % gcs_object_id)

    return comment

  def CreateIssueComment(
      self, cnxn, issue, user_id, content, inbound_message=None,
      amendments=None, attachments=None, kept_attachments=None, timestamp=None,
      is_spam=False, is_description=False, commit=True):
    """Create and store a new comment on the specified issue.

    Args:
      cnxn: connection to SQL database.
      issue: the issue on which to add the comment, must be loaded from
          database with use_cache=False so that assume_stale == False.
      user_id: the user ID of the user who entered the comment.
      content: string body of the comment.
      inbound_message: optional string full text of an email that caused
          this comment to be added.
      amendments: list of Amendment PBs describing the
          metadata changes that the user made along w/ comment.
      attachments: [(filename, contents, mimetype),...] attachments uploaded at
          the time the comment was made.
      kept_attachments: list of attachment ids for attachments kept from
          previous descriptions, if the comment is an update to the description
      timestamp: time at which the comment was made, defaults to now.
      is_spam: True if the comment is classified as spam.
      is_description: True if the comment is a description for the issue.
      commit: set to False to not commit to DB yet.

    Returns:
      The new IssueComment protocol buffer.

    Note that we assume that the content is safe to echo out
    again. The content may have some markup done during input
    processing.
    """
    if is_description:
      kept_attachments = self.GetAttachmentsByID(cnxn, kept_attachments)
    else:
      kept_attachments = []

    comment = self._MakeIssueComment(
        issue.project_id, user_id, content, amendments=amendments,
        inbound_message=inbound_message, attachments=attachments,
        timestamp=timestamp, is_spam=is_spam, is_description=is_description,
        kept_attachments=kept_attachments)
    comment.issue_id = issue.issue_id

    if attachments or kept_attachments:
      issue.attachment_count = (
          issue.attachment_count + len(attachments) + len(kept_attachments))
      self.UpdateIssue(cnxn, issue, update_cols=['attachment_count'])

    self.InsertComment(cnxn, comment, commit=commit)

    return comment

  def SoftDeleteComment(
      self, cnxn, issue, issue_comment, deleted_by_user_id,
      user_service, delete=True, reindex=True, is_spam=False):
    """Mark comment as un/deleted, which shows/hides it from average users."""
    # Update number of attachments
    attachments = 0
    if issue_comment.attachments:
      for attachment in issue_comment.attachments:
        if not attachment.deleted:
          attachments += 1

    # Delete only if it's not in deleted state
    if delete:
      if not issue_comment.deleted_by:
        issue_comment.deleted_by = deleted_by_user_id
        issue.attachment_count = issue.attachment_count - attachments

    # Undelete only if it's in deleted state
    elif issue_comment.deleted_by:
      issue_comment.deleted_by = 0
      issue.attachment_count = issue.attachment_count + attachments

    issue_comment.is_spam = is_spam
    self._UpdateComment(
        cnxn, issue_comment, update_cols=['deleted_by', 'is_spam'])
    self.UpdateIssue(cnxn, issue, update_cols=['attachment_count'])

    # Reindex the issue to take the comment deletion/undeletion into account.
    if reindex:
      tracker_fulltext.IndexIssues(
          cnxn, [issue], user_service, self, self._config_service)

  ### Attachments

  def GetAttachmentAndContext(self, cnxn, attachment_id):
    """Load a IssueAttachment from database, and its comment ID and IID.

    Args:
      cnxn: connection to SQL database.
      attachment_id: long integer unique ID of desired issue attachment.

    Returns:
      An Attachment protocol buffer that contains metadata about the attached
      file, or None if it doesn't exist.  Also, the comment ID and issue IID
      of the comment and issue that contain this attachment.

    Raises:
      NoSuchAttachmentException: the attachment was not found.
    """
    if attachment_id is None:
      raise NoSuchAttachmentException()

    attachment_row = self.attachment_tbl.SelectRow(
        cnxn, cols=ATTACHMENT_COLS, id=attachment_id)
    if attachment_row:
      (attach_id, issue_id, comment_id, filename, filesize, mimetype,
       deleted, gcs_object_id) = attachment_row
      if not deleted:
        attachment = tracker_pb2.Attachment(
            attachment_id=attach_id, filename=filename, filesize=filesize,
            mimetype=mimetype, deleted=bool(deleted),
            gcs_object_id=gcs_object_id)
        return attachment, comment_id, issue_id

    raise NoSuchAttachmentException()

  def GetAttachmentsByID(self, cnxn, attachment_ids):
    """Return all Attachment PBs by attachment ids.

    Args:
      cnxn: connection to SQL database.
      attachment_ids: a list of comment ids.

    Returns:
      A list of the Attachment protocol buffers for the attachments with
      these ids.
    """
    attachment_rows = self.attachment_tbl.Select(
        cnxn, cols=ATTACHMENT_COLS, id=attachment_ids)

    return attachment_rows

  def _UpdateAttachment(self, cnxn, attach, update_cols=None):
    """Update attachment metadata in the DB.

    Args:
      cnxn: connection to SQL database.
      attach: IssueAttachment PB to update in the DB.
      update_cols: optional list of just the field names to update.
    """
    delta = {
        'filename': attach.filename,
        'filesize': attach.filesize,
        'mimetype': attach.mimetype,
        'deleted': bool(attach.deleted),
        }
    if update_cols is not None:
      delta = {key: val for key, val in delta.iteritems()
               if key in update_cols}

    self.attachment_tbl.Update(cnxn, delta, id=attach.attachment_id)

  def SoftDeleteAttachment(
      self, cnxn, project_id, local_id, seq_num, attach_id, user_service,
      delete=True, index_now=True):
    """Mark attachment as un/deleted, which shows/hides it from avg users."""
    issue = self.GetIssueByLocalID(cnxn, project_id, local_id, use_cache=False)
    all_comments = self.GetCommentsForIssue(cnxn, issue.issue_id)
    try:
      issue_comment = all_comments[seq_num]
    except IndexError:
      logging.warning(
          'Tried to (un)delete attachment on non-existent comment #%s in  '
          'issue %s:%s', seq_num, project_id, local_id)
      return

    attachment = None
    for attach in issue_comment.attachments:
      if attach.attachment_id == attach_id:
        attachment = attach

    if not attachment:
      logging.warning(
          'Tried to (un)delete non-existent attachment #%s in project '
          '%s issue %s', attach_id, project_id, local_id)
      return

    if not issue_comment.deleted_by:
      # Decrement attachment count only if it's not in deleted state
      if delete:
        if not attachment.deleted:
          issue.attachment_count = issue.attachment_count - 1

      # Increment attachment count only if it's in deleted state
      elif attachment.deleted:
        issue.attachment_count = issue.attachment_count + 1

    attachment.deleted = delete

    self._UpdateAttachment(cnxn, attachment, update_cols=['deleted'])
    self.UpdateIssue(cnxn, issue, update_cols=['attachment_count'])

    if index_now:
      tracker_fulltext.IndexIssues(
          cnxn, [issue], user_service, self, self._config_service)

  ### Reindex queue

  def EnqueueIssuesForIndexing(self, cnxn, issue_ids):
    """Add the given issue IDs to the ReindexQueue table."""
    reindex_rows = [(issue_id,) for issue_id in issue_ids]
    self.reindexqueue_tbl.InsertRows(
        cnxn, ['issue_id'], reindex_rows, ignore=True)

  def ReindexIssues(self, cnxn, num_to_reindex, user_service):
    """Reindex some issues specified in the IndexQueue table."""
    rows = self.reindexqueue_tbl.Select(
        cnxn, order_by=[('created', [])], limit=num_to_reindex)
    issue_ids = [row[0] for row in rows]

    if issue_ids:
      issues = self.GetIssues(cnxn, issue_ids)
      tracker_fulltext.IndexIssues(
          cnxn, issues, user_service, self, self._config_service)
      self.reindexqueue_tbl.Delete(cnxn, issue_id=issue_ids)

    return len(issue_ids)

  ### Search functions

  def RunIssueQuery(
      self, cnxn, left_joins, where, order_by, shard_id=None, limit=None):
    """Run a SQL query to find matching issue IDs.

    Args:
      cnxn: connection to SQL database.
      left_joins: list of SQL LEFT JOIN clauses.
      where: list of SQL WHERE clauses.
      order_by: list of SQL ORDER BY clauses.
      shard_id: int shard ID to focus the search.
      limit: int maximum number of results, defaults to
          settings.search_limit_per_shard.

    Returns:
      (issue_ids, capped) where issue_ids is a list of the result issue IDs,
      and capped is True if the number of results reached the limit.
    """
    limit = limit or settings.search_limit_per_shard
    where = where + [('Issue.deleted = %s', [False])]
    rows = self.issue_tbl.Select(
        cnxn, shard_id=shard_id, distinct=True, cols=['Issue.id'],
        left_joins=left_joins, where=where, order_by=order_by,
        limit=limit)
    issue_ids = [row[0] for row in rows]
    capped = len(issue_ids) >= limit
    return issue_ids, capped

  def GetIIDsByLabelIDs(self, cnxn, label_ids, project_id, shard_id):
    """Return a list of IIDs for issues with any of the given label IDs."""
    where = []
    if shard_id is not None:
      slice_term = ('shard = %s', [shard_id])
      where.append(slice_term)

    rows = self.issue_tbl.Select(
        cnxn, shard_id=shard_id, cols=['id'],
        left_joins=[('Issue2Label ON Issue.id = Issue2Label.issue_id', [])],
        label_id=label_ids, project_id=project_id, where=where)

    return [row[0] for row in rows]

  def GetIIDsByParticipant(self, cnxn, user_ids, project_ids, shard_id):
    """Return IIDs for issues where any of the given users participate."""
    iids = []
    where = []
    if shard_id is not None:
      where.append(('shard = %s', [shard_id]))
    if project_ids:
      cond_str = 'Issue.project_id IN (%s)' % sql.PlaceHolders(project_ids)
      where.append((cond_str, project_ids))

    # TODO(jrobbins): Combine these 3 queries into one with ORs.   It currently
    # is not the bottleneck.
    rows = self.issue_tbl.Select(
        cnxn, cols=['id'], reporter_id=user_ids,
        where=where, shard_id=shard_id)
    for row in rows:
      iids.append(row[0])

    rows = self.issue_tbl.Select(
        cnxn, cols=['id'], owner_id=user_ids,
        where=where, shard_id=shard_id)
    for row in rows:
      iids.append(row[0])

    rows = self.issue_tbl.Select(
        cnxn, cols=['id'], derived_owner_id=user_ids,
        where=where, shard_id=shard_id)
    for row in rows:
      iids.append(row[0])

    rows = self.issue_tbl.Select(
        cnxn, cols=['id'],
        left_joins=[('Issue2Cc ON Issue2Cc.issue_id = Issue.id', [])],
        cc_id=user_ids,
        where=where + [('cc_id IS NOT NULL', [])],
        shard_id=shard_id)
    for row in rows:
      iids.append(row[0])

    rows = self.issue_tbl.Select(
        cnxn, cols=['Issue.id'],
        left_joins=[
            ('Issue2FieldValue ON Issue.id = Issue2FieldValue.issue_id', []),
            ('FieldDef ON Issue2FieldValue.field_id = FieldDef.id', [])],
        user_id=user_ids, grants_perm='View',
        where=where + [('user_id IS NOT NULL', [])],
        shard_id=shard_id)
    for row in rows:
      iids.append(row[0])

    return iids

  ### Issue Dependency Rankings

  def SortBlockedOn(self, cnxn, issue, blocked_on_iids):
    """Sort blocked_on dependencies by rank and dst_issue_id.

    Args:
      cnxn: connection to SQL database.
      issue: the issue being blocked.
      blocked_on_iids: the iids of all the issue's blockers

    Returns:
      a tuple (ids, ranks), where ids is the sorted list of
      blocked_on_iids and ranks is the list of corresponding ranks
    """
    rows = self.issuerelation_tbl.Select(
        cnxn, cols=ISSUERELATION_COLS, issue_id=issue.issue_id,
        dst_issue_id=blocked_on_iids, kind='blockedon',
        order_by=[('rank DESC', []), ('dst_issue_id', [])])
    ids = [row[1] for row in rows]
    ids.extend([iid for iid in blocked_on_iids if iid not in ids])
    ranks = [row[3] for row in rows]
    ranks.extend([0] * (len(blocked_on_iids) - len(ranks)))
    return ids, ranks

  def ApplyIssueRerank(
      self, cnxn, parent_id, relations_to_change, commit=True, invalidate=True):
    """Updates rankings of blocked on issue relations to new values

    Args:
      cnxn: connection to SQL database.
      parent_id: the global ID of the blocked issue to update
      relations_to_change: This should be a list of
        [(blocker_id, new_rank),...] of relations that need to be changed
      commit: set to False to skip the DB commit and do it in the caller.
      invalidate: set to False to leave cache invalidatation to the caller.
    """
    blocker_ids = [blocker for (blocker, rank) in relations_to_change]
    self.issuerelation_tbl.Delete(
        cnxn, issue_id=parent_id, dst_issue_id=blocker_ids, commit=False)
    insert_rows = [(parent_id, blocker, 'blockedon', rank)
                   for (blocker, rank) in relations_to_change]
    self.issuerelation_tbl.InsertRows(
        cnxn, cols=ISSUERELATION_COLS, row_values=insert_rows, commit=commit)
    if invalidate:
      self.InvalidateIIDs(cnxn, [parent_id])


def _UpdateClosedTimestamp(config, issue, old_effective_status):
  """Sets or unsets the closed_timestamp based based on status changes.

  If the status is changing from open to closed, the closed_timestamp is set to
  the current time.

  If the status is changing form closed to open, the close_timestamp is unset.

  If the status is changing from one closed to another closed, or from one
  open to another open, no operations are performed.

  Args:
    config: the project configuration
    issue: the issue being updated (a protocol buffer)
    old_effective_status: the old issue status string. E.g., 'New'
  """
  # open -> closed
  if (tracker_helpers.MeansOpenInProject(old_effective_status, config)
      and not tracker_helpers.MeansOpenInProject(
          tracker_bizobj.GetStatus(issue), config)):

    logging.info('setting closed_timestamp on issue: %d', issue.local_id)

    issue.closed_timestamp = int(time.time())
    return

  # closed -> open
  if (not tracker_helpers.MeansOpenInProject(old_effective_status, config)
      and tracker_helpers.MeansOpenInProject(
          tracker_bizobj.GetStatus(issue), config)):

    logging.info('clearing closed_timestamp on issue: %s', issue.local_id)

    issue.reset('closed_timestamp')
    return


class Error(Exception):
  """Base exception class for this package."""
  pass


class NoSuchIssueException(Error):
  """The requested issue was not found."""
  pass


class NoSuchAttachmentException(Error):
  """The requested attachment was not found."""
  pass


class NoSuchCommentException(Error):
  """The requested comment was not found."""
  pass


class MidAirCollisionException(Error):
  """The item was updated by another user at the same time."""

  def __init__(self, name, continue_issue_id):
    super(MidAirCollisionException, self).__init__()
    self.name = name  # human-readable name for the artifact being edited.
    self.continue_issue_id = continue_issue_id  # ID of issue to start over.
