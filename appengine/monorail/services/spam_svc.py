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
REASON_FAIL_OPEN = 'fail_open'
SPAM_CLASS_LABEL = '1'

SPAMREPORT_ISSUE_COLS = ['issue_id', 'reported_user_id', 'user_id']
MANUALVERDICT_ISSUE_COLS = ['user_id', 'issue_id', 'is_spam', 'reason',
    'project_id']
THRESHVERDICT_ISSUE_COLS = ['issue_id', 'is_spam', 'reason', 'project_id']

SPAMREPORT_COMMENT_COLS = ['comment_id', 'reported_user_id', 'user_id']
MANUALVERDICT_COMMENT_COLS = ['user_id', 'comment_id', 'is_spam', 'reason',
    'project_id']
THRESHVERDICT_COMMENT_COLS = ['comment_id', 'is_spam', 'reason', 'project_id']


class SpamService(object):
  """The persistence layer for spam reports."""
  issue_actions = ts_mon.CounterMetric(
      'monorail/spam_svc/issue',
      'Count of things that happen to issues.',
      [ts_mon.StringField('type')])
  comment_actions = ts_mon.CounterMetric(
      'monorail/spam_svc/comment',
      'Count of things that happen to comments.',
      [ts_mon.StringField('type')])
  ml_engine_failures = ts_mon.CounterMetric(
      'monorail/spam_svc/ml_engine_failure',
      'Failures calling the ML Engine API',
      None)

  def __init__(self):
    self.report_tbl = sql.SQLTableManager(SPAMREPORT_TABLE_NAME)
    self.verdict_tbl = sql.SQLTableManager(SPAMVERDICT_TABLE_NAME)
    self.issue_tbl = sql.SQLTableManager(ISSUE_TABLE)

    self.ml_engine = None
    try:
      credentials = GoogleCredentials.get_application_default()
      self.ml_engine = build('ml', 'v1',
                             http=httplib2.Http(),
                             credentials=credentials)
    except (Oauth2ClientError, ApiClientError):
      logging.error("Error setting up ML Engine API: %s" % sys.exc_info()[0])

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
      self.report_tbl.InsertRows(cnxn, SPAMREPORT_ISSUE_COLS, rows,
          ignore=True)
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
    self.verdict_tbl.InsertRows(cnxn, THRESHVERDICT_ISSUE_COLS, rows,
        ignore=True)
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

  def RecordClassifierIssueVerdict(self, cnxn, issue, is_spam, confidence,
        fail_open):
    reason = REASON_FAIL_OPEN if fail_open else REASON_CLASSIFIER
    self.verdict_tbl.InsertRow(cnxn, issue_id=issue.issue_id, is_spam=is_spam,
        reason=reason, classifier_confidence=confidence,
        project_id=issue.project_id)
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

    self.verdict_tbl.InsertRows(cnxn, MANUALVERDICT_ISSUE_COLS, rows,
        ignore=True)

    for issue in issues:
      issue.is_spam = is_spam

    if is_spam:
      self.issue_actions.increment_by(len(issues), {'type': 'manual'})
    else:
      issue_service.AllocateNewLocalIDs(cnxn, issues)

    # This will commit the transaction.
    issue_service.UpdateIssues(cnxn, issues, update_cols=['is_spam'])

  def RecordManualCommentVerdict(self, cnxn, issue_service, user_service,
        comment_id, user_id, is_spam):
    # TODO(seanmccullough): Bulk comment verdicts? There's no UI for that.
    self.verdict_tbl.InsertRow(cnxn, ignore=True,
      user_id=user_id, comment_id=comment_id, is_spam=is_spam,
      reason=REASON_MANUAL)
    comment = issue_service.GetComment(cnxn, comment_id)
    comment.is_spam = is_spam
    issue = issue_service.GetIssue(cnxn, comment.issue_id, use_cache=False)
    issue_service.SoftDeleteComment(
        cnxn, issue, comment, user_id, user_service, is_spam, True, is_spam)
    if is_spam:
      self.comment_actions.increment({'type': 'manual'})

  def RecordClassifierCommentVerdict(self, cnxn, comment, is_spam, confidence,
      fail_open):
    reason = REASON_FAIL_OPEN if fail_open else REASON_CLASSIFIER
    self.verdict_tbl.InsertRow(cnxn, comment_id=comment.id, is_spam=is_spam,
        reason=reason, classifier_confidence=confidence,
        project_id=comment.project_id)
    if is_spam:
      self.comment_actions.increment({'type': 'classifier'})

  def _predict(self, instance):
    """Requests a prediction from the ML Engine API.

    Sample API response:
      {'predictions': [{
        'classes': ['0', '1'],
        'probabilities': [0.4986788034439087, 0.5013211965560913]
      }]}

    This hits the default model.

    Returns:
      A floating point number representing the confidence
      the instance is spam.
    """
    model_name = 'projects/%s/models/spam' % settings.classifier_project_id
    body = {'instances': [instance]}
    request = self.ml_engine.projects().predict(name=model_name, body=body)
    response = request.execute()
    logging.info('ML Engine API response: %r' % response)
    prediction = response['predictions'][0]

    # Ensure the class confidence we return is for the spam, not the ham label.
    # The spam label, '1', is usually at index 1 but I'm not sure of any
    # guarantees around label order.
    if prediction['classes'][1] == SPAM_CLASS_LABEL:
      return prediction['probabilities'][1]
    elif prediction['classes'][0] == SPAM_CLASS_LABEL:
      return prediction['probabilities'][0]
    else:
      raise Exception('No predicted classes found.')

  def _IsExempt(self, author, is_project_member):
    """Return True if the user is exempt from spam checking."""
    if author.email is not None and author.email.endswith(
        settings.spam_whitelisted_suffixes):
      logging.info('%s whitelisted from spam filtering', author.email)
      return True

    if author.ignore_action_limits:
      logging.info('%s trusted not to spam', author.email)
      return True

    if is_project_member:
      logging.info('%s is a project member, assuming ham', author.email)
      return True

    return False

  def ClassifyIssue(self, issue, firstComment, reporter, is_project_member):
    """Classify an issue as either spam or ham.

    Args:
      issue: the Issue.
      firstComment: the first Comment on issue.
      reporter: User PB for the Issue reporter.
      is_project_member: True if reporter is a member of issue's project.

    Returns a JSON dict of classifier prediction results from
    the ML Engine API.
    """
    instance = spam_helpers.GenerateFeaturesRaw(issue.summary,
      firstComment.content, settings.spam_feature_hashes)
    return self._classify(instance, reporter, is_project_member)

  def ClassifyComment(self, comment_content, commenter, is_project_member=True):
    """Classify a comment as either spam or ham.

    Args:
      comment: the comment text.
      commenter: User PB for the user who authored the comment.

    Returns a JSON dict of classifier prediction results from
    the ML Engine API.
    """
    instance = spam_helpers.GenerateFeaturesRaw('', comment_content,
      settings.spam_feature_hashes)
    return self._classify(instance, commenter, is_project_member)


  def _classify(self, instance, author, is_project_member):
    # Fail-safe: not spam.
    result = {'confidence_is_spam': 0.0,
              'failed_open': False}

    if self._IsExempt(author, is_project_member):
      return result

    if not self.ml_engine:
      logging.error("ML Engine not initialized.")
      self.ml_engine_failures.increment()
      result['failed_open'] = True
      return result

    remaining_retries = 3
    while remaining_retries > 0:
      try:
        result['confidence_is_spam'] = self._predict(instance)
        result['failed_open'] = False
        return result
      except Exception as ex:
        remaining_retries = remaining_retries - 1
        self.ml_engine_failures.increment()
        logging.error('Error calling ML Engine API: %s' % ex)

      result['failed_open'] = True
    return result

  def GetIssueClassifierQueue(
      self, cnxn, _issue_service, project_id, offset=0, limit=10):
     """Returns list of recent issues with spam verdicts,
     ranked in ascending order of confidence (so uncertain items are first).
     """
     # TODO(seanmccullough): Optimize pagination. This query probably gets
     # slower as the number of SpamVerdicts grows, regardless of offset
     # and limit values used here.  Using offset,limit in general may not
     # be the best way to do this.
     issue_results = self.verdict_tbl.Select(cnxn,
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
     for row in issue_results:
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

  def GetIssueFlagQueue(
      self, cnxn, _issue_service, project_id, offset=0, limit=10):
     """Returns list of recent issues that have been flagged by users"""
     issue_flags = self.report_tbl.Select(cnxn,
         cols = ["Issue.project_id", "Report.issue_id", "count(*) as count",
                 "max(Report.created) as latest",
                 "count(distinct Report.user_id) as users"],
         left_joins=["Issue ON Issue.id = Report.issue_id"],
         where=[('Report.issue_id IS NOT NULL', []),
                ("Issue.project_id == %v", [project_id])],
         order_by=[('count DESC', [])],
         group_by=['Report.issue_id'],
         offset=offset, limit=limit)
     ret = []
     for row in issue_flags:
       ret.append(ModerationItem(
         project_id=row[0],
         issue_id=row[1],
         count=row[2],
         latest_report=row[3],
         num_users=row[4],
       ))

     count = self.verdict_tbl.SelectValue(cnxn,
         col='COUNT(DISTINCT Report.issue_id)',
         where=[('Issue.project_id = %s', [project_id])],
         left_joins=["Issue ON Issue.id = SpamReport.issue_id"])
     return ret, count


  def GetCommentClassifierQueue(
      self, cnxn, _issue_service, project_id, offset=0, limit=10):
     """Returns list of recent comments with spam verdicts,
     ranked in ascending order of confidence (so uncertain items are first).
     """
     # TODO(seanmccullough): Optimize pagination. This query probably gets
     # slower as the number of SpamVerdicts grows, regardless of offset
     # and limit values used here.  Using offset,limit in general may not
     # be the best way to do this.
     comment_results = self.verdict_tbl.Select(cnxn,
         cols=['issue_id', 'is_spam', 'reason', 'classifier_confidence',
               'created'],
         where=[
             ('project_id = %s', [project_id]),
             ('classifier_confidence <= %s',
                 [settings.classifier_moderation_thresh]),
             ('overruled = %s', [False]),
             ('comment_id IS NOT NULL', []),
         ],
         order_by=[
             ('classifier_confidence ASC', []),
             ('created ASC', []),
             ],
         group_by=['comment_id'],
         offset=offset,
         limit=limit,
         )

     ret = []
     for row in comment_results:
       ret.append(ModerationItem(
         comment_id=long(row[0]),
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
             ('comment_id IS NOT NULL', []),
         ])

     return ret, count


  def GetTrainingIssues(self, cnxn, issue_service, since, offset=0, limit=100):
    """Returns list of recent issues with human-labeled spam/ham verdicts.
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
    """Returns list of recent comments with human-labeled spam/ham verdicts.
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
