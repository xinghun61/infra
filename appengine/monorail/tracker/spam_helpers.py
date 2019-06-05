# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Set of helpers for constructing spam-related pages.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from framework import template_helpers
from third_party import ezt

from datetime import datetime

def DecorateIssueClassifierQueue(
    cnxn, issue_service, spam_service, user_service, moderation_items):
  issue_ids = [item.issue_id for item in moderation_items]
  issues = issue_service.GetIssues(cnxn, issue_ids)
  issue_map = {}
  for issue in issues:
    issue_map[issue.issue_id] = issue

  flag_counts = spam_service.LookupIssueFlagCounts(cnxn, issue_ids)

  reporter_ids = [issue.reporter_id for issue in issues]
  reporters = user_service.GetUsersByIDs(cnxn, reporter_ids)
  comments = issue_service.GetCommentsForIssues(cnxn, issue_ids)

  items = []
  for item in moderation_items:
    issue=issue_map[item.issue_id]
    first_comment = comments.get(item.issue_id, ["[Empty]"])[0]

    items.append(template_helpers.EZTItem(
        issue=issue,
        summary=template_helpers.FitUnsafeText(issue.summary, 80),
        comment_text=template_helpers.FitUnsafeText(first_comment.content, 80),
        reporter=reporters[issue.reporter_id],
        flag_count=flag_counts.get(issue.issue_id, 0),
        is_spam=ezt.boolean(item.is_spam),
        verdict_time=item.verdict_time,
        classifier_confidence=item.classifier_confidence,
        reason=item.reason,
    ))

  return items
