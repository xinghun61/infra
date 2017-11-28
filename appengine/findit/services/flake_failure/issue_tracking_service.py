# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import base64
import datetime
import json
import urllib
import logging

from google.appengine.api import app_identity
from gae_libs import appengine_util
from libs import time_util
from monorail_api import IssueTrackerAPI
from monorail_api import Issue

from model.flake import master_flake_analysis
from waterfall import waterfall_config
from waterfall.flake import flake_constants

_BUG_SUMMARY_SEARCH_QUERY_TEMPLATE = 'summary:{} is:open'


def IsBugFilingEnabledForAnalysis(analysis):
  """Returns true if bug filing is enabled, false otherwise"""
  return analysis.algorithm_parameters.get('create_monorail_bug', False)


def UnderDailyLimit(analysis):
  daily_bug_limit = analysis.algorithm_parameters.get(
      'new_flake_bugs_per_day', flake_constants.DEFAULT_NEW_FLAKE_BUGS_PER_DAY)
  query = master_flake_analysis.MasterFlakeAnalysis.query(
      master_flake_analysis.MasterFlakeAnalysis.request_time >=
      time_util.GetMostRecentUTCMidnight())
  bugs_filed_today = 0

  more = True
  cursor = None
  while more:
    results, cursor, more = query.fetch_page(100, start_cursor=cursor)
    for result in results:
      if result.has_attempted_filing and result.bug_id:
        bugs_filed_today += 1

  return bugs_filed_today < daily_bug_limit


def ShouldFileBugForAnalysis(analysis):
  """Returns true if a bug should be filed for this analysis.

  Ths requirements for a bug to be filed.
    - The bug creation feature if enabled.
    - The pipeline hasn't been attempted before (see above).
    - The analysis has sufficient confidence (1.0).
    - The analysis doesn't already have a bug associated with it.
    - A duplicate bug hasn't been filed by Findit or CTF.
    - A duplicate bug hasn't been filed by a human.
  """
  if not IsBugFilingEnabledForAnalysis(analysis):
    analysis.LogInfo('Bug creation feature disabled.')
    return False

  if _HasPreviousAttempt(analysis):
    analysis.LogWarning(
        'There has already been an attempt at filing a bug, aborting.')
    return False

  if not _HasSufficientConfidenceInCulprit(analysis):
    analysis.LogInfo(
        'Analysis has confidence=%d which isn\'t high enough to file a bug.' %
        analysis.confidence_in_culprit)
    return False

  if not UnderDailyLimit(analysis):
    analysis.LogInfo('Reached bug filing limit for the day.')
    return False

  # Check if there's already a bug attached to this issue.
  if BugAlreadyExistsForId(analysis.bug_id):
    analysis.LogInfo('Bug with id %d already exists.' % analysis.bug_id)
    return False

  if BugAlreadyExistsForLabel(analysis.test_name):
    analysis.LogInfo('Bug already exists for label %s' % analysis.test_name)
    return False

  if BugAlreadyExistsForTest(analysis.test_name):
    analysis.LogInfo('Bug about flakiness already exists')
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

  issue_tracker_api = IssueTrackerAPI(
      'chromium', use_staging=appengine_util.IsStaging())
  issue = TraverseMergedIssues(bug_id, issue_tracker_api)

  if issue is None:
    return False

  return issue.open


def BugAlreadyExistsForLabel(test_name):
  """Returns True if the bug with the given label exists on monorail."""
  assert test_name

  issue_tracker_api = IssueTrackerAPI(
      'chromium', use_staging=appengine_util.IsStaging())
  issues = issue_tracker_api.getIssues('label:%s' % test_name)
  if issues is None:
    return False

  open_issues = [issue for issue in issues if issue.open]
  if open_issues:
    return True

  return False


def BugAlreadyExistsForTest(test_name):
  """Search for test_name issues that are about flakiness.

  Args:
    test_name (str): The test name to search for.

  Returns:
    True is there is already a bug about this test being flaky, False otherwise.
  """
  assert test_name

  query = _BUG_SUMMARY_SEARCH_QUERY_TEMPLATE.format(test_name)

  issue_tracker_api = IssueTrackerAPI(
      'chromium', use_staging=appengine_util.IsStaging())
  issues = issue_tracker_api.getIssues(query)
  if not issues:
    return False

  for issue in issues:
    if issue.open and ('flake' in issue.summary or 'flaky' in issue.summary):
      logging.info('A bug for test %s already exists for flakiness. Bug id %s',
                   test_name, issue.id)
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
      'state': 'open',
      'components': ['Tests>Flaky']
  })

  issue_tracker_api = IssueTrackerAPI(
      'chromium', use_staging=appengine_util.IsStaging())
  issue_tracker_api.create(issue)
  return issue.id


def _HasPreviousAttempt(analysis):
  """Returns True if an analysis has already attempted to file a bug."""
  return analysis.has_attempted_filing


def _HasSufficientConfidenceInCulprit(analysis):
  """Returns true is there's high enough confidence in the culprit."""
  if not analysis.confidence_in_culprit:
    return False

  flake_settings = waterfall_config.GetCheckFlakeSettings()
  minimum_confidence = flake_settings.get(
      'minimum_confidence_to_create_bug',
      flake_constants.MINIMUM_CONFIDENCE_TO_CREATE_BUG)
  return (analysis.confidence_in_culprit + flake_constants.EPSILON >=
          minimum_confidence)
