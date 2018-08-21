# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Functions for interfacing with Mororail bugs."""
import logging
import textwrap

from gae_libs import appengine_util
from monorail_api import CustomizedField
from monorail_api import Issue
from monorail_api import IssueTrackerAPI
from services import monitoring

# Label for Chromium Sheriff bug queue.
_SHERIFF_CHROMIUM_LABEL = 'Sheriff-Chromium'

# Label for Type-Bug.
_TYPE_BUG_LABEL = 'Type-Bug'

# Label used to identify issues related to flaky tests.
_FLAKY_TEST_LABEL = 'Test-Flaky'

# Component used to identify issues related to flaky tests.
_FLAKY_TEST_COMPONENT = 'Tests>Flaky'

# Customized field for flaky test.
_FLAKY_TEST_CUSTOMIZED_FIELD = 'Flaky-Test'

# Query used to search for flaky test in customized field.
_FLAKY_TEST_CUSTOMIZED_FIELD_QUERY_TEMPLATE = (
    '%s={} is:open' % _FLAKY_TEST_CUSTOMIZED_FIELD)

# Query used to search for flaky test in summary.
_FLAKY_TEST_SUMMARY_QUERY_TEMPLATE = 'summary:{} is:open'

# A list of keywords in issue summary to identify issues that are related to
# flaky tests.
_FLAKY_TEST_SUMMARY_KEYWORDS = ['flake', 'flaky', 'flakiness']

_FINDIT_ANALYZED_LABEL_TEXT = 'Test-Findit-Analyzed'

_LOW_FLAKINESS_COMMENT_TEMPLATE = textwrap.dedent("""
This flake is either a longstanding, has low flakiness, or not reproducible
based on the flakiness trend in the config "%s / %s":

https://findit-for-me.appspot.com/waterfall/flake?key=%s

Automatically posted by the findit-for-me app (https://goo.gl/Ot9f7N).""")

# Flake detection bug templates.
_FLAKE_DETECTION_BUG_SUMMARY = '{test_name} is flaky'

_FLAKE_DETECTION_BUG_DESCRIPTION = textwrap.dedent("""
{test_target}: {test_name} is flaky.

Findit detected {num_occurrences} flake occurrences of this test within the past
24 hours. List of all flake occurrences can be found at:
{flake_url}.

Flaky tests should be disabled within 30 minutes unless culprit CL is found and
reverted, please disable it first and then find an appropriate owner.
{previous_tracking_bug_text}
Automatically posted by the findit-for-me app (https://goo.gl/Ot9f7N). If this
result was incorrect, please apply the label Test-Findit-Wrong and mark the bug
as untriaged.""")

_FLAKE_DETECTION_PREVIOUS_TRACKING_BUG = (
    '\nThis flaky test was previously tracked in bug {}.\n')

_FLAKE_DETECTION_BUG_COMMENT = textwrap.dedent("""
Findit detected {num_occurrences} new flake occurrences of this test. To see the
list of flake occurrences, please visit:
{flake_url}.

Since flakiness is ongoing, the issue was moved back into the Sheriff Bug Queue
(unless already there).
{previous_tracking_bug_text}
Automatically posted by the findit-for-me app (https://goo.gl/Ot9f7N).
Feedback is welcome! Please use component Tools>Test>FindIt>Flakiness.""")

_FLAKE_DETECTION_LABEL_TEXT = 'Test-Findit-Detected'


def AddFinditLabelToIssue(issue):
  """Ensures an issue's label has been marked as analyzed by Findit."""
  assert issue
  if _FINDIT_ANALYZED_LABEL_TEXT not in issue.labels:
    issue.labels.append(_FINDIT_ANALYZED_LABEL_TEXT)


def _GetOpenIssues(query, monorail_project):
  """Searches for open bugs that match the query.

  This method wraps a call IssueTrackerAPI.getIssues(), it is needed because
  it's unclear from the API name and the documentation whether the returned
  issues are all open issues or not, so check the property to make sure that
  only open bugs are considered.

  Args:
    query: A query to search for bugs on Monorail.
    monorail_project: The monorail project to search for.

  Returns:
    A list of open bugs that match the query.
  """
  issue_tracker_api = IssueTrackerAPI(
      monorail_project, use_staging=appengine_util.IsStaging())
  issues = issue_tracker_api.getIssues(query)
  if not issues:
    return []

  return [issue for issue in issues if issue.open]


def OpenBugAlreadyExistsForId(bug_id, project_id='chromium'):
  """Returns True if the bug exists and is open on monorail."""
  existing_bug = GetBugForId(bug_id, project_id)
  return existing_bug and existing_bug.open


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
  """Gets a bug by bug id.

  If the bug was marked as Duplicate, then this method traverses the chain to
  find the last merged one.

  Args:
    bug_id: Id of the bug.
    project_id: The project that bug was filed for.
   """
  if bug_id is None:
    return None

  issue_tracker_api = IssueTrackerAPI(
      project_id, use_staging=appengine_util.IsStaging())
  issue = TraverseMergedIssues(bug_id, issue_tracker_api)

  return issue


def _GetOpenIssueIdForFlakyTestByCustomizedField(test_name,
                                                 monorail_project='chromium'):
  """Returns flaky tests related issue by searching customized field.

  Args:
    test_name: The name of the test to search for.
    monorail_project: The Monorail project to search for.

  Returns:
    Id of the issue if it exists, otherwise None.
  """
  query = _FLAKY_TEST_CUSTOMIZED_FIELD_QUERY_TEMPLATE.format(test_name)
  open_issues = _GetOpenIssues(query, monorail_project)
  return open_issues[0].id if open_issues else None


def _GetOpenIssueIdForFlakyTestBySummary(test_name,
                                         monorail_project='chromium'):
  """Returns flaky tests related issue by searching summary.

  Note that searching for |test_name| in the summary alone is not enough, for
  example: 'suite.test needs to be rewritten', so at least one of the following
  additional identifiers is also required:
  1. The issue has label: Test-Flaky.
  2. The issue has component: Tests>Flaky.
  3. The issue has one of the _FLAKY_TEST_SUMMARY_KEYWORDS in the summary.

  Args:
    test_name: The name of the test to search for.
    monorail_project: The Monorail project to search for.

  Returns:
    Minimum id among the matched issues if exists, otherwise None.
  """

  def _is_issue_related_to_flake(issue):
    if _FLAKY_TEST_LABEL in issue.labels:
      return True

    if _FLAKY_TEST_COMPONENT in issue.components:
      return True

    return any(keyword in issue.summary.lower()
               for keyword in _FLAKY_TEST_SUMMARY_KEYWORDS)

  query = _FLAKY_TEST_SUMMARY_QUERY_TEMPLATE.format(test_name)
  open_issues = _GetOpenIssues(query, monorail_project)
  flaky_test_open_issues = [
      issue for issue in open_issues if _is_issue_related_to_flake(issue)
  ]
  if not flaky_test_open_issues:
    return None

  return min([issue.id for issue in flaky_test_open_issues])


def SearchOpenIssueIdForFlakyTest(test_name, monorail_project='chromium'):
  """Searches for existing open issue for a flaky test on Monorail.

  Args:
    test_name: The test name to search for.
    monorail_project: The Monorail project to search for.

  Returns:
    Id of the issue if it exists, otherwise None.
  """
  # Prefer issues without customized field because it means that the bugs were
  # created manually by develoepers, so it is more likely to gain attentions.
  return (_GetOpenIssueIdForFlakyTestBySummary(test_name, monorail_project) or
          _GetOpenIssueIdForFlakyTestByCustomizedField(test_name,
                                                       monorail_project))


def OpenIssueAlreadyExistsForFlakyTest(test_name, monorail_project='chromium'):
  """Returns True if a related flaky test bug already exists on Monorail.

  Args:
    test_name: The test name to search for.
    monorail_project: The Monorail project to search for.

  Returns:
    True is there is already a bug about this test being flaky, False otherwise.
  """
  return SearchOpenIssueIdForFlakyTest(test_name, monorail_project) is not None


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
          _FINDIT_ANALYZED_LABEL_TEXT, _SHERIFF_CHROMIUM_LABEL, priority,
          _TYPE_BUG_LABEL, _FLAKY_TEST_LABEL
      ],
      'fieldValues': [CustomizedField(_FLAKY_TEST_CUSTOMIZED_FIELD, test_name)]
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


def CreateBugForFlakeDetection(normalized_step_name,
                               normalized_test_name,
                               num_occurrences,
                               monorail_project,
                               flake_url,
                               previous_tracking_bug_id=None,
                               priority='Pri-1'):
  """Creates a bug for a detected flaky test.

  Args:
    normalized_step_name: Normalized name of the flaky step, please see Flake
                          Model for the definitions.
    normalized_test_name: Normalized name of the flaky test, please see Flake
                          Model for the definitions.
    num_occurrences: Number of new occurrences to report.
    monorail_project: The project the bug is created for.
    flake_url: The URL that points to this flake on the flake detection UI.
    previous_tracking_bug_id: id of the previous bug that was used to track this
                              flaky test.
    priority: Priority of the bug.

  Returns:
    id of the newly created bug.
  """
  summary = _FLAKE_DETECTION_BUG_SUMMARY.format(test_name=normalized_test_name)

  previous_tracking_bug_text = _FLAKE_DETECTION_PREVIOUS_TRACKING_BUG.format(
      previous_tracking_bug_id) if previous_tracking_bug_id else ''

  description = _FLAKE_DETECTION_BUG_DESCRIPTION.format(
      test_target=normalized_step_name,
      test_name=normalized_test_name,
      num_occurrences=num_occurrences,
      flake_url=flake_url,
      previous_tracking_bug_text=previous_tracking_bug_text)

  issue = Issue({
      'status':
          'Untriaged',
      'summary':
          summary,
      'description':
          description,
      'projectId':
          monorail_project,
      'labels': [
          _FLAKE_DETECTION_LABEL_TEXT, _SHERIFF_CHROMIUM_LABEL, priority,
          _TYPE_BUG_LABEL, _FLAKY_TEST_LABEL
      ],
      'fieldValues': [
          CustomizedField(_FLAKY_TEST_CUSTOMIZED_FIELD, normalized_test_name)
      ]
  })

  return CreateBug(issue, monorail_project)


def UpdateBugForFlakeDetection(bug_id,
                               normalized_test_name,
                               num_occurrences,
                               monorail_project,
                               flake_url,
                               previous_tracking_bug_id=None):
  """Updates the bug with newly detected flake occurrences.

  Args:
    bug_id: id of the bug to update.
    normalized_test_name: Normalized name of the flaky test, please see Flake
                          Model for the definitions.
    num_occurrences: Number of new occurrences to report.
    monorail_project: The project the bug is created for.
    flake_url: The URL that points to this flake on the flake detection UI.
    previous_tracking_bug_id: id of the previous bug that was used to track this
                              flaky test.
  """
  previous_tracking_bug_text = _FLAKE_DETECTION_PREVIOUS_TRACKING_BUG.format(
      previous_tracking_bug_id) if previous_tracking_bug_id else ''
  comment = _FLAKE_DETECTION_BUG_COMMENT.format(
      num_occurrences=num_occurrences,
      flake_url=flake_url,
      previous_tracking_bug_text=previous_tracking_bug_text)

  issue = GetBugForId(bug_id)
  if _FLAKE_DETECTION_LABEL_TEXT not in issue.labels:
    issue.labels.append(_FLAKE_DETECTION_LABEL_TEXT)

  if _SHERIFF_CHROMIUM_LABEL not in issue.labels:
    issue.labels.append(_SHERIFF_CHROMIUM_LABEL)

  if _FLAKY_TEST_LABEL not in issue.labels:
    issue.labels.append(_FLAKY_TEST_LABEL)

  # Set Flaky-Test field. If it's already there, it's a no-op.
  flaky_field = CustomizedField(_FLAKY_TEST_CUSTOMIZED_FIELD,
                                normalized_test_name)
  issue.field_values.append(flaky_field)

  UpdateBug(issue, comment, monorail_project)
