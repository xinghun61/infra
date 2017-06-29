# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A set of functions that provide fulltext search for issues."""

import collections
import logging
import time

from google.appengine.api import search

import settings
from framework import framework_constants
from framework import framework_helpers
from framework import framework_views
from services import fulltext_helpers
from tracker import tracker_bizobj


# When updating and re-indexing all issues in a project, work in batches
# of this size to manage memory usage and avoid rpc timeouts.
_INDEX_BATCH_SIZE = 40


# The user can search for text that occurs specifically in these
# parts of an issue.
ISSUE_FULLTEXT_FIELDS = ['summary', 'description', 'comment']
# Note: issue documents also contain a "metadata" field, but we do not
# expose that to users.  Issue metadata can be searched in a structured way
# by giving a specific field name such as "owner:" or "status:". The metadata
# search field exists only for fulltext queries that do not specify any field.


def IndexIssues(cnxn, issues, user_service, issue_service, config_service):
  """(Re)index all the given issues.

  Args:
    cnxn: connection to SQL database.
    issues: list of Issue PBs to index.
    user_service: interface to user data storage.
    issue_service: interface to issue data storage.
    config_service: interface to configuration data storage.
  """
  issues = list(issues)
  config_dict = config_service.GetProjectConfigs(
      cnxn, {issue.project_id for issue in issues})
  for start in xrange(0, len(issues), _INDEX_BATCH_SIZE):
    logging.info('indexing issues: %d remaining', len(issues) - start)
    _IndexIssueBatch(
        cnxn, issues[start:start + _INDEX_BATCH_SIZE], user_service,
        issue_service, config_dict)


def _IndexIssueBatch(cnxn, issues, user_service, issue_service, config_dict):
  """Internal method to (re)index the given batch of issues.

  Args:
    cnxn: connection to SQL database.
    issues: list of Issue PBs to index.
    user_service: interface to user data storage.
    issue_service: interface to issue data storage.
    config_dict: dict {project_id: config} for all the projects that
        the given issues are in.
  """
  user_ids = tracker_bizobj.UsersInvolvedInIssues(issues)
  comments_dict = issue_service.GetCommentsForIssues(
      cnxn, [issue.issue_id for issue in issues])
  for comments in comments_dict.itervalues():
    user_ids.update([ic.user_id for ic in comments])

  users_by_id = framework_views.MakeAllUserViews(
      cnxn, user_service, user_ids)
  _CreateIssueSearchDocuments(issues, comments_dict, users_by_id, config_dict)


def _CreateIssueSearchDocuments(
    issues, comments_dict, users_by_id, config_dict):
  """Make the GAE search index documents for the given issue batch.

  Args:
    issues: list of issues to index.
    comments_dict: prefetched dictionary of comments on those issues.
    users_by_id: dictionary {user_id: UserView} so that the email
        addresses of users who left comments can be found via search.
    config_dict: dict {project_id: config} for all the projects that
        the given issues are in.
  """
  documents_by_shard = collections.defaultdict(list)
  for issue in issues:
    comments = comments_dict.get(issue.issue_id, [])
    comments = _IndexableComments(comments, users_by_id)
    summary = issue.summary
    # TODO(jrobbins): allow search specifically on explicit vs derived
    # fields.
    owner_id = tracker_bizobj.GetOwnerId(issue)
    owner_email = users_by_id[owner_id].email
    config = config_dict[issue.project_id]
    component_paths = []
    for component_id in issue.component_ids:
      cd = tracker_bizobj.FindComponentDefByID(component_id, config)
      if cd:
        component_paths.append(cd.path)

    field_values = [str(tracker_bizobj.GetFieldValue(fv, users_by_id))
                    for fv in issue.field_values]

    metadata = '%s %s %s %s %s %s' % (
        tracker_bizobj.GetStatus(issue),
        owner_email,
        [users_by_id[cc_id].email for cc_id in
         tracker_bizobj.GetCcIds(issue)],
        ' '.join(component_paths),
        ' '.join(field_values),
        ' '.join(tracker_bizobj.GetLabels(issue)))
    if comments:
      description = _ExtractCommentText(comments[0], users_by_id)
      description = description[:framework_constants.MAX_FTS_FIELD_SIZE]
      all_comments = ' '. join(
          _ExtractCommentText(c, users_by_id) for c in comments[1:])
      all_comments = all_comments[:framework_constants.MAX_FTS_FIELD_SIZE]
    else:
      description = ''
      all_comments = ''
      logging.info(
          'Issue %s:%r has zero indexable comments',
          issue.project_name, issue.local_id)

    custom_fields = _BuildCustomFTSFields(issue)
    doc = search.Document(
        doc_id=str(issue.issue_id),
        fields=[
            search.NumberField(name='project_id', value=issue.project_id),
            search.TextField(name='summary', value=summary),
            search.TextField(name='metadata', value=metadata),
            search.TextField(name='description', value=description),
            search.TextField(name='comment', value=all_comments),
            ] + custom_fields)

    shard_id = issue.issue_id % settings.num_logical_shards
    documents_by_shard[shard_id].append(doc)

  start_time = time.time()
  promises = []
  for shard_id, documents in documents_by_shard.iteritems():
    if documents:
      promises.append(framework_helpers.Promise(
          _IndexDocsInShard, shard_id, documents))

  for promise in promises:
    promise.WaitAndGetValue()

  logging.info('Finished %d indexing in shards in %d ms',
               len(documents_by_shard), int((time.time() - start_time) * 1000))


def _IndexableComments(comments, users_by_id):
  """We only index the comments that are not deleted or banned.

  Args:
    comments: list of Comment PBs for one issue.
    users_by_id: Dict of (user_id -> UserView) for all users.

  Returns:
    A list of comments filtered to not have any deleted comments or
    comments from banned users.  If the issue has a huge number of
    comments, only a certain number of the first and last comments
    are actually indexed.
  """
  allowed_comments = []
  for comment in comments:
    user_view = users_by_id.get(comment.user_id)
    if not (comment.deleted_by or (user_view and user_view.banned)):
      if comment.is_description and allowed_comments:
        # index the latest description, but not older descriptions
        allowed_comments[0] = comment
      else:
        allowed_comments.append(comment)

  reasonable_size = (framework_constants.INITIAL_COMMENTS_TO_INDEX +
                     framework_constants.FINAL_COMMENTS_TO_INDEX)
  if len(allowed_comments) <= reasonable_size:
    return allowed_comments

  candidates = (  # Prioritize the description and recent comments.
    allowed_comments[0:1] +
    allowed_comments[-framework_constants.FINAL_COMMENTS_TO_INDEX:] +
    allowed_comments[1:framework_constants.INITIAL_COMMENTS_TO_INDEX])
  total_length = 0
  result = []
  for comment in candidates:
    total_length += len(comment.content)
    if total_length < framework_constants.MAX_FTS_FIELD_SIZE:
      result.append(comment)

  return result


def _IndexDocsInShard(shard_id, documents):
  search_index = search.Index(
      name=settings.search_index_name_format % shard_id)
  search_index.put(documents)
  logging.info('FTS indexed %d docs in shard %d', len(documents), shard_id)
  # TODO(jrobbins): catch OverQuotaError and add the issues to the
  # ReindexQueue table instead.


def _ExtractCommentText(comment, users_by_id):
  """Return a string with all the searchable text of the given Comment PB."""
  commenter_email = users_by_id[comment.user_id].email
  return '%s %s %s' % (
      commenter_email,
      comment.content,
      ' '.join(attach.filename
               for attach in comment.attachments
               if not attach.deleted))


def _BuildCustomFTSFields(issue):
  """Return a list of FTS Fields to index string-valued custom fields."""
  fts_fields = []
  for fv in issue.field_values:
    if fv.str_value:
      # TODO(jrobbins): also indicate which were derived vs. explicit.
      # TODO(jrobbins): also toss in the email addresses of any users in
      # user-valued custom fields, ints for int-valued fields, etc.
      fts_field = search.TextField(
          name='custom_%d' % fv.field_id, value=fv.str_value)
      fts_fields.append(fts_field)

  return fts_fields


def UnindexIssues(issue_ids):
  """Remove many issues from the sharded search indexes."""
  iids_by_shard = {}
  for issue_id in issue_ids:
    shard_id = issue_id % settings.num_logical_shards
    iids_by_shard.setdefault(shard_id, [])
    iids_by_shard[shard_id].append(issue_id)

  for shard_id, iids_in_shard in iids_by_shard.iteritems():
    try:
      logging.info(
          'unindexing %r issue_ids in %r', len(iids_in_shard), shard_id)
      search_index = search.Index(
          name=settings.search_index_name_format % shard_id)
      search_index.delete([str(iid) for iid in iids_in_shard])
    except search.Error:
      logging.exception('FTS deletion failed')


def SearchIssueFullText(project_ids, query_ast_conj, shard_id):
  """Do full-text search in GAE FTS.

  Args:
    project_ids: list of project ID numbers to consider.
    query_ast_conj: One conjuctive clause from the AST parsed
        from the user's query.
    shard_id: int shard ID for the shard to consider.

  Returns:
    (issue_ids, capped) where issue_ids is a list of issue issue_ids that match
    the full-text query.  And, capped is True if the results were capped due to
    an implementation limitation.  Or, return (None, False) if the given AST
    conjunction contains no full-text conditions.
  """
  fulltext_query = fulltext_helpers.BuildFTSQuery(
      query_ast_conj, ISSUE_FULLTEXT_FIELDS)
  if fulltext_query is None:
    return None, False

  if project_ids:
    project_clause = ' OR '.join(
        'project_id:%d' % pid for pid in project_ids)
    fulltext_query = '(%s) %s' % (project_clause, fulltext_query)

  # TODO(jrobbins): it would be good to also include some other
  # structured search terms to narrow down the set of index
  # documents considered.  E.g., most queries are only over the
  # open issues.
  logging.info('FTS query is %r', fulltext_query)
  issue_ids = fulltext_helpers.ComprehensiveSearch(
      fulltext_query, settings.search_index_name_format % shard_id)
  capped = len(issue_ids) >= settings.fulltext_limit_per_shard
  return issue_ids, capped
