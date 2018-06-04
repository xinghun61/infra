# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Functions for interfacing with Mororail bugs."""

import base64
import datetime
import json
import urllib
import logging
import textwrap

from google.appengine.api import app_identity
from google.appengine.ext import ndb
from gae_libs import appengine_util
from libs import analysis_status
from libs import time_util
from model.flake import master_flake_analysis
from monorail_api import CustomizedField
from monorail_api import IssueTrackerAPI
from monorail_api import Issue
from services import monitoring
from services.flake_failure import flake_constants
from waterfall import waterfall_config

_BUG_CUSTOM_FIELD_SEARCH_QUERY_TEMPLATE = 'Flaky-Test={} is:open'

_BUG_SUMMARY_SEARCH_QUERY_TEMPLATE = 'summary:{} is:open'

_COMMENT_FOOTER = textwrap.dedent("""
Automatically posted by the findit-for-me app (https://goo.gl/Ot9f7N).
Feedback is welcome! Please use component Tools>Test>FindIt>Flakiness""")

# Comment for culprit template.
_LINK = 'https://findit-for-me.appspot.com/waterfall/flake?key=%s'
_CULPRIT_COMMENT_TEMPLATE = textwrap.dedent(
    """
Findit identified the culprit r%s with confidence %.1f%% in the config "%s / %s"
based on the flakiness trend:"""
    .lstrip() + '\n\n' + _LINK + '\n\n' + _COMMENT_FOOTER)

_FINDIT_ANALYZED_LABEL_TEXT = 'Test-Findit-Analyzed'

# Flake detection templates.
_FINDIT_DETECTED_LABEL_TEXT = 'Test-Findit-Detected'

_FLAKE_DETECTION_CREATE_BUG_BODY = (
    'We have found {flake_count} recent flakes. List of all flakes '
    'can be found at {flake_url}.')

_FLAKE_DETECTION_CREATE_BUG_BODY_FOOTER = (
    'This issue was created automatically by Findit. Please find the right '
    'owner to fix the respective test/step and assign this issue accordingly.')

_FLAKE_DETECTION_CREATE_BUG_BODY_HEADER = '{test_name} is flaky.'

_FLAKE_DETECTION_COMMENT_BODY = (
    'Findit detected {flake_count} new flakes for test/step {test_name}. To see'
    'the actual flakes, please visit {flake_url}. Since flakiness is ongoing, '
    'the issue was moved back into the Sheriff Bug Queue '
    '(unless already there).')

_FLAKE_DETECTION_CREATE_BUG_BODY_PREVIOUS_ISSUE = (
    'This flaky test/step was previously tracked in issue {old_issue_id}.')

_FLAKE_DETECTION_BUG_TITLE = '{test_name} is flaky'

_LOW_FLAKINESS_COMMENT_TEMPLATE = textwrap.dedent(
    """
This flake is either a longstanding, has low flakiness, or not reproducible
based on the flakiness trend in the config "%s / %s":"""
    .lstrip() + '\n\n' + _LINK + '\n\n' + _COMMENT_FOOTER)


def AddFinditLabelToIssue(issue):
  """Ensures an issue's label has been marked as analyzed by Findit."""
  assert issue
  if _FINDIT_ANALYZED_LABEL_TEXT not in issue.labels:
    issue.labels.append(_FINDIT_ANALYZED_LABEL_TEXT)


def OpenBugAlreadyExistsForLabel(test_name):
  """Returns True if the bug with the given label exists on monorail."""
  assert test_name

  issue_tracker_api = IssueTrackerAPI(
      flake_constants.CHROMIUM_PROJECT_NAME,
      use_staging=appengine_util.IsStaging())
  issues = issue_tracker_api.getIssues('label:%s' % test_name)
  if issues is None:
    return False

  open_issues = [issue for issue in issues if issue.open]
  if open_issues:
    return True

  return False


def OpenBugAlreadyExistsForId(bug_id, project_id='chromium'):
  """Returns True if the bug exists and is open on monorail."""
  existing_bug = GetBugForId(bug_id, project_id)

  return existing_bug and existing_bug.open


def GenerateBugComment(analysis):
  """Generates a comment to update a bug with based on the analysis' result."""
  assert not analysis.failed

  if analysis.culprit_urlsafe_key is not None:
    culprit = ndb.Key(urlsafe=analysis.culprit_urlsafe_key).get()
    assert culprit
    assert analysis.confidence_in_culprit is not None
    return _CULPRIT_COMMENT_TEMPLATE % (culprit.commit_position,
                                        analysis.confidence_in_culprit * 100,
                                        analysis.original_master_name,
                                        analysis.original_builder_name,
                                        analysis.key.urlsafe())

  return _LOW_FLAKINESS_COMMENT_TEMPLATE % (analysis.original_master_name,
                                            analysis.original_builder_name,
                                            analysis.key.urlsafe())


def GetMinimumConfidenceToUpdateBugs():
  return waterfall_config.GetCheckFlakeSettings().get(
      'minimum_confidence_to_update_cr',
      flake_constants.DEFAULT_MINIMUM_CONFIDENCE_SCORE_TO_UPDATE_CR)


def GetMinimumConfidenceToFileBugs():
  return waterfall_config.GetCheckFlakeSettings().get(
      'minimum_confidence_to_create_bug',
      flake_constants.DEFAULT_MINIMUM_CONFIDENCE_TO_CREATE_BUG)


def IsBugFilingEnabled():
  """Returns True if bug filing is enabled, False otherwise."""
  return waterfall_config.GetCheckFlakeSettings().get('create_monorail_bug',
                                                      False)


def IsBugUpdatingEnabled():
  return waterfall_config.GetCheckFlakeSettings().get('update_monorail_bug',
                                                      False)


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
  if not IsBugFilingEnabled():
    analysis.LogInfo('Bug creation feature disabled.')
    return False

  if _HasPreviousAttempt(analysis):
    analysis.LogWarning(
        'There has already been an attempt at filing a bug, aborting.')
    return False

  if not HasSufficientConfidenceInCulprit(analysis,
                                          GetMinimumConfidenceToFileBugs()):
    analysis.LogInfo('''Analysis has confidence {:.2%}
        which isn\'t high enough to file a bug.'''.format(
        analysis.confidence_in_culprit))
    return False

  if not UnderDailyLimit(analysis):
    analysis.LogInfo('Reached bug filing limit for the day.')
    return False

  # Check if there's already a bug attached to this issue.
  if OpenBugAlreadyExistsForId(analysis.bug_id):
    analysis.LogInfo('Bug with id {} already exists.'.format(analysis.bug_id))
    return False

  # TODO (crbug.com/808199): Turn off label checking when CTF is offline.
  if OpenBugAlreadyExistsForLabel(analysis.test_name):
    analysis.LogInfo('Bug already exists for label {}'.format(
        analysis.test_name))
    return False

  if BugAlreadyExistsForCustomField(analysis.test_name):
    analysis.LogInfo('Bug already exists for custom field {}'.format(
        analysis.test_name))
    return False

  if OpenBugAlreadyExistsForTest(analysis.test_name):
    analysis.LogInfo('Bug about flakiness already exists')
    return False

  return True


def ShouldUpdateBugForAnalysis(analysis):
  assert not analysis.error

  if not analysis.bug_id:
    analysis.LogInfo('bug=%s' % analysis.bug_id)
    if analysis.culprit_urlsafe_key:
      monitoring.OnFlakeCulprit('culprit-identified', 'none',
                                'no-bug-to-update')
    else:
      monitoring.OnFlakeCulprit('culprit-not-identified', 'none',
                                'no-bug-to-update')
    return False

  if len(analysis.data_points) < 2:
    analysis.LogInfo('%d data points' % len(analysis.data_points))
    monitoring.OnFlakeCulprit('culprit-identified', 'none',
                              'insufficient-datapoints')
    return False

  if not IsBugUpdatingEnabled():
    analysis.LogInfo('update_monorail_bug not set or is False')
    if analysis.culprit_urlsafe_key:
      # There is a culprit, but updating bugs is disabled.
      monitoring.OnFlakeCulprit('culprit-identified', 'none',
                                'update-bug-disabled')
    else:
      analysis.LogInfo('No culprit to update bugs with')
      # There is no culprit, but updating bugs is disabled.
      monitoring.OnFlakeCulprit('culprit-not-identified', 'none',
                                'update-bug-disabled')
    return False

  if (analysis.culprit_urlsafe_key and not HasSufficientConfidenceInCulprit(
      analysis, GetMinimumConfidenceToUpdateBugs())):
    # There is a culprit, but insufficient confidence.
    monitoring.OnFlakeCulprit('culprit-identified', 'none',
                              'insufficient-confidence')
    return False

  # TODO(crbug.com/847960): Do not update bugs if Findit already logged one as
  # the information would be redundant.
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


def GetBugForId(bug_id, project_id='chromium'):
  """Gets a bug by id."""
  if bug_id is None:
    return False

  issue_tracker_api = IssueTrackerAPI(
      project_id, use_staging=appengine_util.IsStaging())
  issue = TraverseMergedIssues(bug_id, issue_tracker_api)

  return issue


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


def GetExistingBugForCustomizedField(field, project_id='chromium'):
  """Returns the existing bug for this test if any, None otherwise."""
  assert field
  query = _BUG_CUSTOM_FIELD_SEARCH_QUERY_TEMPLATE.format(field)

  issue_tracker_api = IssueTrackerAPI(
      project_id, use_staging=appengine_util.IsStaging())
  issues = issue_tracker_api.getIssues(query)

  # If there are issues, find the root one, and return the id of it.
  if issues and issues[0]:
    return issues[0]
  else:
    return None


def GetExistingBugIdForCustomizedField(test_name, project_id='chromium'):
  """Returns the bug id of an existing bug for this test."""
  bug = GetExistingBugForCustomizedField(test_name, project_id)
  return bug.id if bug else None


def BugAlreadyExistsForCustomField(test_name):
  """Returns True if the bug with the given custom field exists on monorail."""
  return GetExistingBugIdForCustomizedField(test_name) is not None


def OpenBugAlreadyExistsForTest(test_name):
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

  return True


def GetPriorityLabelForConfidence(confidence):
  """Returns a priority for a given confidence score."""
  assert confidence
  assert confidence <= 1.0
  assert confidence >= 0.0

  # Default to P1 for all findings of flakiness.
  return 'Pri-1'


def CreateBugForFlakeAnalyzer(test_name, subject, description,
                              priority='Pri-2'):
  """Creates a bug for Flake Analyzer with the given information.

  Args:
    test_name (str): Name of the test.
    subject (str): Subject for the issue.
    description (str): Description for the issue.
    priority (str, optional): Priority for the issue (Pri-0/1/2/3/4).
  Returns:
    (int) id of the bug that was filed.
  """
  assert test_name
  assert subject
  assert description

  issue = Issue({
      'status':
          'Available',
      'summary':
          subject,
      'description':
          description,
      'projectId':
          'chromium',
      'labels': [
          _FINDIT_ANALYZED_LABEL_TEXT, 'Sheriff-Chromium', priority, 'Type-Bug'
      ],
      'state':
          'open',
      'components': ['Tests>Flaky'],
      'fieldValues': [CustomizedField('Flaky-Test', test_name)]
  })
  issue_id = CreateBug(issue)

  if issue_id > 0:
    monitoring.OnIssueChange('created', 'flake')

  return issue_id


def CreateBug(issue, project_id='chromium'):
  """Creates a bug with the given information.

  Returns:
    (int) id of the bug that was filed.
  """
  assert issue

  issue_tracker_api = IssueTrackerAPI(
      project_id, use_staging=appengine_util.IsStaging())
  issue_tracker_api.create(issue)

  return issue.id


def UpdateBug(issue, comment, project_id='chromium'):
  """Creates a bug with the given information."""
  assert issue

  issue_tracker_api = IssueTrackerAPI(
      project_id, use_staging=appengine_util.IsStaging())
  issue_tracker_api.update(issue, comment, send_email=True)

  return issue.id


def _HasPreviousAttempt(analysis):
  """Returns True if an analysis has already attempted to file a bug."""
  return analysis.has_attempted_filing


def HasSufficientConfidenceInCulprit(analysis, required_confidence):
  """Returns true is there's high enough confidence in the culprit."""
  if not analysis.confidence_in_culprit:
    return False

  return (analysis.confidence_in_culprit + flake_constants.EPSILON >=
          required_confidence)
