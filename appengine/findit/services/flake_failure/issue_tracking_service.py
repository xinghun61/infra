# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import base64
import datetime
import json
import urllib
import logging

from google.appengine.api import app_identity

from libs import time_util
from monorail_api import IssueTrackerAPI
from monorail_api import Issue


def TraverseMergedIssues(bug_id, issue_tracker):
  """Finds an issue with the given id.

  Traverse if the bug was merged into another.

  Args:
    bug_id (int): Bug id of the issue.
    issue_tracker (IssueTrackerAPI): Api wrapper to talk to monorail.

  Returns:
    (Issue) Last issue in the chain of merges.
  """
  issue = issue_tracker.getIssue(bug_id)
  checked_issues = {}
  while issue and issue.merged_into:
    logging.info('%s was merged into %s', issue.id, issue.merged_into)
    checked_issues[issue.id] = issue
    issue = issue_tracker.getIssue(issue.merged_into)
    if issue.id in checked_issues:
      break  # There's a cycle, return the last issue looked at.
  return issue


def BugAlreadyExistsForId(bug_id):
  """Returns True if the bug exists and is open on monorail."""
  if bug_id is None:
    return False

  issue_tracker_api = IssueTrackerAPI('chromium', use_staging=True)
  issue = TraverseMergedIssues(bug_id, issue_tracker_api)

  if issue is None:
    return False

  return issue.open


def BugAlreadyExistsForLabel(test_name):
  """Returns True if the bug with the given label exists on monorail."""
  assert test_name

  issue_tracker_api = IssueTrackerAPI('chromium', use_staging=True)
  issues = issue_tracker_api.getIssues('label:%s' % test_name)
  if issues is None:
    return False

  open_issues = [issue for issue in issues if issue.open]
  if open_issues:
    return True

  return False


def CreateBugForTest(test_name, subject, description):
  """Creates a bug with the given information.

  Returns:
    (int) id of the bug that was filed.
  """
  assert test_name
  assert subject
  assert description

  issue = Issue({
      'status': 'Unconfirmed',
      'summary': subject,
      'description': description,
      'projectId': 'chromium',
      'labels': [test_name, 'Test-Findit-Analyzed', 'Sheriff-Chromium'],
      'state': 'open'
  })

  issue_tracker_api = IssueTrackerAPI('chromium', use_staging=True)
  issue_tracker_api.create(issue)
  return issue.id