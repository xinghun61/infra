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

from waterfall.flake import flake_constants


def ShouldFileBugForAnalysis(analysis):
  """Returns true if a bug should be filed for this analysis.

  Ths requirements for a bug to be filed.
    - The pipeline hasn't been attempted before (see above).
    - The analysis has sufficient confidence (1.0).
    - The analysis doesn't already have a bug associated with it.
    - A bug isn't open for the same test.
  """
  if _HasPreviousAttempt(analysis):
    analysis.LogWarning(
        'There has already been an attempt at filing a bug, aborting.')
    return False

  if not _HasSufficientConfidenceInCulprit(analysis):
    analysis.LogInfo(
        'Analysis has confidence=%d which isn\'t high enough to file a bug.' %
        analysis.confidence_in_culprit)
    return False

  # Check if there's already a bug attached to this issue.
  if BugAlreadyExistsForId(analysis.bug_id):
    analysis.LogInfo(
        'Bug with id %d already exists.' % analysis.bug_id)
    return False

  if BugAlreadyExistsForLabel(analysis.test_name):
    analysis.LogInfo('Bug already exists for label %s' % analysis.test_name)
    return False

  return True


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


def _HasPreviousAttempt(analysis):
  """Returns True if an analysis has already attempted to file a bug."""
  return analysis.has_attempted_filing


def _HasSufficientConfidenceInCulprit(analysis):
  """Returns true is there's high enough confidence in the culprit."""
  if not analysis.confidence_in_culprit:
    return False
  return (abs(analysis.confidence_in_culprit -
              flake_constants.MINIMUM_CONFIDENCE_TO_CREATE_BUG) <=
          flake_constants.EPSILON)
