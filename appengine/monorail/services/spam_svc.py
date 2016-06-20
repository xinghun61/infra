# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

""" Set of functions for detaling with spam reports.
"""

import collections
import httplib2
import logging
import settings
import sys
import settings

from collections import defaultdict
from features import filterrules_helpers
from framework import sql
from infra_libs import ts_mon
from services import spam_helpers

from apiclient.discovery import build
from oauth2client.client import GoogleCredentials
from apiclient.errors import Error as ApiClientError
from oauth2client.client import Error as Oauth2ClientError

SPAMREPORT_TABLE_NAME = 'SpamReport'
SPAMVERDICT_TABLE_NAME = 'SpamVerdict'
ISSUE_TABLE = 'Issue'

REASON_MANUAL = 'manual'
REASON_THRESHOLD = 'threshold'
REASON_CLASSIFIER = 'classifier'

SPAMREPORT_COLS = ['issue_id', 'reported_user_id', 'user_id']
MANUALVERDICT_COLS = ['user_id', 'issue_id', 'is_spam', 'reason', 'project_id']
THRESHVERDICT_COLS = ['issue_id', 'is_spam', 'reason', 'project_id']


class SpamService(object):
  """The persistence layer for spam reports."""
  issue_actions = ts_mon.CounterMetric('monorail/spam_svc/issue')
  comment_actions = ts_mon.CounterMetric('monorail/spam_svc/comment')

  def __init__(self):
    self.report_tbl = sql.SQLTableManager(SPAMREPORT_TABLE_NAME)
    self.verdict_tbl = sql.SQLTableManager(SPAMVERDICT_TABLE_NAME)
    self.issue_tbl = sql.SQLTableManager(ISSUE_TABLE)

    self.prediction_service = None
    try:
      credentials = GoogleCredentials.get_application_default()
      self.prediction_service = build('prediction', 'v1.6',
                                      http=httplib2.Http(),
                                      credentials=credentials)
    except (Oauth2ClientError, ApiClientError):
      logging.error("Error getting GoogleCredentials: %s" % sys.exc_info()[0])

  def LookupIssueFlaggers(self, cnxn, issue_id):
    """Returns users who've reported the issue or its comments as spam.

    Returns a tuple. First element is a list of users who flagged the issue;
    second element is a dictionary of comment id to a list of users who flagged
    that comment.
    """
    rows = self.report_tbl.Select(
        cnxn, cols=['user_id', 'comment_id'],
        issue_id=issue_id)

    issue_reporters = []
    comment_reporters = collections.defaultdict(list)
    for row in rows:
      if row[1]:
        comment_reporters[row[1]].append(row[0])
      else:
        issue_reporters.append(row[0])

    return issue_reporters, comment_reporters

  def LookupIssueFlagCounts(self, cnxn, issue_ids):
    """Returns a map of issue_id to flag counts"""
    rows = self.report_tbl.Select(cnxn, cols=['issue_id', 'COUNT(*)'],
                                  issue_id=issue_ids, group_by=['issue_id'])
    counts = {}
    for row in rows:
      counts[long(row[0])] = row[1]
    return counts

  def LookupIssueVerdicts(self, cnxn, issue_ids):
    """Returns a map of issue_id to most recent spam verdicts"""
    rows = self.verdict_tbl.Select(cnxn,
                                   cols=['issue_id', 'reason', 'MAX(created)'],
                                   issue_id=issue_ids, group_by=['issue_id'])
    counts = {}
    for row in rows:
      counts[long(row[0])] = row[1]
    return counts

  def LookupIssueVerdictHistory(self, cnxn, issue_ids):
    """Returns a map of issue_id to most recent spam verdicts"""
    rows = self.verdict_tbl.Select(cnxn, cols=[
        'issue_id', 'reason', 'created', 'is_spam', 'classifier_confidence',
            'user_id', 'overruled'],
        issue_id=issue_ids, order_by=[('issue_id', []), ('created', [])])

    # TODO: group by issue_id, make class instead of dict for verdict.
    verdicts = []
    for row in rows:
      verdicts.append({
        'issue_id': row[0],
        'reason': row[1],
        'created': row[2],
        'is_spam': row[3],
        'classifier_confidence': row[4],
        'user_id': row[5],
        'overruled': row[6],
      })

    return verdicts

  def LookupCommentVerdictHistory(self, cnxn, comment_ids):
    """Returns a map of issue_id to most recent spam verdicts"""
    rows = self.verdict_tbl.Select(cnxn, cols=[
        'comment_id', 'reason', 'created', 'is_spam', 'classifier_confidence',
            'user_id', 'overruled'],
        comment_id=comment_ids, order_by=[('comment_id', []), ('created', [])])

    # TODO: group by comment_id, make class instead of dict for verdict.
    verdicts = []
    for row in rows:
      verdicts.append({
        'comment_id': row[0],
        'reason': row[1],
        'created': row[2],
        'is_spam': row[3],
        'classifier_confidence': row[4],
        'user_id': row[5],
        'overruled': row[6],
      })

    return verdicts

  def FlagIssues(self, cnxn, issue_service, issues, reporting_user_id,
                 flagged_spam):
    """Creates or deletes a spam report on an issue."""
    verdict_updates = []
    if flagged_spam:
      rows = [(issue.issue_id, issue.reporter_id, reporting_user_id)
          for issue in issues]
      self.report_tbl.InsertRows(cnxn, SPAMREPORT_COLS, rows, ignore=True)
    else:
      issue_ids = [issue.issue_id for issue in issues]
      self.report_tbl.Delete(
          cnxn, issue_id=issue_ids, user_id=reporting_user_id,
          comment_id=None)

    project_id = issues[0].project_id

    # Now record new verdicts and update issue.is_spam, if they've changed.
    ids = [issue.issue_id for issue in issues]
    counts = self.LookupIssueFlagCounts(cnxn, ids)
    previous_verdicts = self.LookupIssueVerdicts(cnxn, ids)

    for issue_id in counts:
      # If the flag counts changed enough to toggle the is_spam bit, need to
      # record a new verdict and update the Issue.
      if ((flagged_spam and counts[issue_id] >= settings.spam_flag_thresh or
          not flagged_spam and counts[issue_id] < settings.spam_flag_thresh) and
          (previous_verdicts[issue_id] != REASON_MANUAL if issue_id in
           previous_verdicts else True)):
        verdict_updates.append(issue_id)

    if len(verdict_updates) == 0:
      return

    # Some of the issues may have exceed the flag threshold, so issue verdicts
    # and mark as spam in those cases.
    rows = [(issue_id, flagged_spam, REASON_THRESHOLD, project_id)
        for issue_id in verdict_updates]
    self.verdict_tbl.InsertRows(cnxn, THRESHVERDICT_COLS, rows, ignore=True)
    update_issues = []
    for issue in issues:
      if issue.issue_id in verdict_updates:
        issue.is_spam = flagged_spam
        update_issues.append(issue)

    if flagged_spam:
      self.issue_actions.increment_by(len(update_issues), {'type': 'flag'})

    issue_service.UpdateIssues(cnxn, update_issues, update_cols=['is_spam'])

  def FlagComment(self, cnxn, issue_id, comment_id, reported_user_id,
                  reporting_user_id, flagged_spam):
    """Creates or deletes a spam report on a comment."""
    # TODO(seanmccullough): Bulk comment flagging? There's no UI for that.
    if flagged_spam:
      self.report_tbl.InsertRow(
          cnxn, ignore=True, issue_id=issue_id,
          comment_id=comment_id, reported_user_id=reported_user_id,
          user_id=reporting_user_id)
      self.comment_actions.increment({'type': 'flag'})
    else:
      self.report_tbl.Delete(
          cnxn, issue_id=issue_id, comment_id=comment_id,
          user_id=reporting_user_id)

  def RecordClassifierIssueVerdict(self, cnxn, issue, is_spam, confidence):
    self.verdict_tbl.InsertRow(cnxn, issue_id=issue.issue_id, is_spam=is_spam,
        reason=REASON_CLASSIFIER, classifier_confidence=confidence)
    if is_spam:
      self.issue_actions.increment({'type': 'classifier'})
    # This is called at issue creation time, so there's nothing else to do here.

  def RecordManualIssueVerdicts(self, cnxn, issue_service, issues, user_id,
                                is_spam):
    rows = [(user_id, issue.issue_id, is_spam, REASON_MANUAL, issue.project_id)
        for issue in issues]
    issue_ids = [issue.issue_id for issue in issues]

    # Overrule all previous verdicts.
    self.verdict_tbl.Update(cnxn, {'overruled': True}, [
        ('issue_id IN (%s)' % sql.PlaceHolders(issue_ids), issue_ids)
        ], commit=False)

    self.verdict_tbl.InsertRows(cnxn, MANUALVERDICT_COLS, rows, ignore=True)

    for issue in issues:
      issue.is_spam = is_spam

    if is_spam:
      self.issue_actions.increment_by(len(issues), {'type': 'manual'})
    else:
      issue_service.AllocateNewLocalIDs(cnxn, issues)

    # This will commit the transaction.
    issue_service.UpdateIssues(cnxn, issues, update_cols=['is_spam'])

  def RecordManualCommentVerdict(self, cnxn, issue_service, user_service,
        comment_id, sequence_num, user_id, is_spam):
    # TODO(seanmccullough): Bulk comment verdicts? There's no UI for that.
    self.verdict_tbl.InsertRow(cnxn, ignore=True,
      user_id=user_id, comment_id=comment_id, is_spam=is_spam,
      reason=REASON_MANUAL)
    comment = issue_service.GetComment(cnxn, comment_id)
    comment.is_spam = is_spam
    issue = issue_service.GetIssue(cnxn, comment.issue_id)
    issue_service.SoftDeleteComment(cnxn, comment.project_id, issue.local_id,
                                    sequence_num, user_id, user_service,
                                    is_spam, True, is_spam)
    if is_spam:
      self.comment_actions.increment({'type': 'manual'})

  def RecordClassifierCommentVerdict(self, cnxn, comment, is_spam, confidence):
    self.verdict_tbl.InsertRow(cnxn, comment_id=comment.id, is_spam=is_spam,
        reason=REASON_CLASSIFIER, classifier_confidence=confidence,
        project_id=comment.project_id)
    if is_spam:
      self.comment_actions.increment({'type': 'classifier'})

  def _predict(self, body):
    return self.prediction_service.trainedmodels().predict(
        settings.classifier_prorect_id,
        settings.classifier_model_id,
        body).execute()

  def ClassifyIssue(self, issue, firstComment, author_email):
    """Classify an issue as either spam or ham.

    Args:
      issue: the Issue.
      firstComment: the first Comment on issue.
      author_email: the email address of the Issue reporter.

    Returns a JSON dict of classifier prediction results from
    the Cloud Prediction API.
    """
    # Fail-safe: not spam.
    result = {'outputLabel': 'ham',
              'outputMulti': [{'label':'ham', 'score': '1.0'}]}

    if author_email is not None and author_email.endswith(
        settings.spam_whitelisted_suffixes):
      logging.info('%s excempted from spam filtering', author_email)
      return result

    if not self.prediction_service:
      logging.error("prediction_service not initialized.")
      return result

    features = spam_helpers.GenerateFeatures(issue.summary,
        firstComment.content, author_email, settings.spam_feature_hashes,
        settings.spam_whitelisted_suffixes)
 
    remaining_retries = 3
    while remaining_retries > 0:
      try:
        result = self._predict(
             {
               'input': {
                 'csvInstance': features,
               }
             }
           )
        return result
      except Exception:
        remaining_retries = remaining_retries - 1
        logging.error('Error calling prediction API: %s' % sys.exc_info()[2])

    return result

  def ClassifyComment(self, comment_content, author_email):
    """Classify a comment as either spam or ham.

    Args:
      comment: the comment text.

    Returns a JSON dict of classifier prediction results from
    the Cloud Prediction API.
    """
    # Fail-safe: not spam.
    result = {'outputLabel': 'ham',
              'outputMulti': [{'label':'ham', 'score': '1.0'}]}

    if author_email is not None and author_email.endswith(
        settings.spam_whitelisted_suffixes):
      logging.info('%s excempted from spam filtering', author_email)
      return result

    if not self.prediction_service:
      logging.error("prediction_service not initialized.")
      return result

    features = spam_helpers.GenerateFeatures('', comment_content,
        author_email, settings.spam_feature_hashes,
        settings.spam_whitelisted_suffixes)
 
    remaining_retries = 3
    while remaining_retries > 0:
      try:
        result = self._predict(
             {
               'input': {
                 'csvInstance': features,
               }
             }
           )
        return result
      except Exception:
        remaining_retries = remaining_retries - 1
        logging.error('Error calling prediction API: %s' % sys.exc_info()[0])

    return result

  def GetModerationQueue(
      self, cnxn, _issue_service, project_id, offset=0, limit=10):
     """Returns list of recent issues with spam verdicts,
     ranked in ascending order of confidence (so uncertain items are first).
     """
     # TODO(seanmccullough): Optimize pagination. This query probably gets
     # slower as the number of SpamVerdicts grows, regardless of offset
     # and limit values used here.  Using offset,limit in general may not
     # be the best way to do this.
     # Also: add comments to the moderation queue.
     results = self.verdict_tbl.Select(cnxn,
         cols=['issue_id', 'is_spam', 'reason', 'classifier_confidence',
               'created'],
         where=[
             ('project_id = %s', [project_id]),
             ('classifier_confidence <= %s',
                 [settings.classifier_moderation_thresh]),
             ('overruled = %s', [False]),
             ('issue_id IS NOT NULL', []),
         ],
         order_by=[
             ('classifier_confidence ASC', []),
             ('created ASC', []),
             ],
         group_by=['issue_id'],
         offset=offset,
         limit=limit,
         )

     ret = []
     for row in results:
       ret.append(ModerationItem(
         issue_id=long(row[0]),
         is_spam=row[1] == 1,
         reason=row[2],
         classifier_confidence=row[3],
         verdict_time='%s' % row[4],
       ))

     count = self.verdict_tbl.SelectValue(cnxn,
         col='COUNT(*)',
         where=[
             ('project_id = %s', [project_id]),
             ('classifier_confidence <= %s',
                 [settings.classifier_moderation_thresh]),
             ('overruled = %s', [False]),
             ('issue_id IS NOT NULL', []),
         ])

     return ret, count

  def GetTrainingIssues(self, cnxn, issue_service, since, offset=0, limit=100):
    """Returns list of recent issues with spam verdicts,
    ranked in ascending order of confidence (so uncertain items are first).
    """

    # get all of the manual verdicts in the past day.
    results = self.verdict_tbl.Select(cnxn,
        cols=['issue_id'],
        where=[
            ('overruled = %s', [False]),
            ('reason = %s', ['manual']),
            ('issue_id IS NOT NULL', []),
            ('created > %s', [since.isoformat()]),
        ],
        offset=offset,
        limit=limit,
        )

    issue_ids = [long(row[0]) for row in results if row[0]]
    issues = issue_service.GetIssues(cnxn, issue_ids)
    comments = issue_service.GetCommentsForIssues(cnxn, issue_ids)
    first_comments = {}
    for issue in issues:
      first_comments[issue.issue_id] = (comments[issue.issue_id][0].content
          if issue.issue_id in comments else "[Empty]")

    count = self.verdict_tbl.SelectValue(cnxn,
        col='COUNT(*)',
        where=[
            ('overruled = %s', [False]),
            ('reason = %s', ['manual']),
            ('issue_id IS NOT NULL', []),
            ('created > %s', [since.isoformat()]),
        ])

    return issues, first_comments, count

  def GetTrainingComments(self, cnxn, issue_service, since, offset=0,
      limit=100):
    """Returns list of recent comments with spam verdicts,
    ranked in ascending order of confidence (so uncertain items are first).
    """

    # get all of the manual verdicts in the past day.
    results = self.verdict_tbl.Select(cnxn,
        cols=['comment_id'],
        where=[
            ('overruled = %s', [False]),
            ('reason = %s', ['manual']),
            ('comment_id IS NOT NULL', []),
            ('created > %s', [since.isoformat()]),
        ],
        offset=offset,
        limit=limit,
        )

    comment_ids = [long(row[0]) for row in results if row[0]]
    # Don't care about sequence numbers in this context yet.
    comments = issue_service.GetCommentsByID(cnxn, comment_ids,
        defaultdict(int))

    count = self.verdict_tbl.SelectValue(cnxn,
        col='COUNT(*)',
        where=[
            ('overruled = %s', [False]),
            ('reason = %s', ['manual']),
            ('comment_id IS NOT NULL', []),
            ('created > %s', [since.isoformat()]),
        ])

    return comments, count


class ModerationItem:
  def __init__(self, **kwargs):
    self.__dict__ = kwargs
