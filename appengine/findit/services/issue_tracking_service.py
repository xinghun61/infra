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

# Label for flaky tests.
_TEST_FLAKY_Label = 'Test-Flaky'

# Customized field for flaky test.
_FLAKY_TEST_CUSTOMIZED_FIELD = 'Flaky-Test'

_BUG_CUSTOM_FIELD_SEARCH_QUERY_TEMPLATE = 'Flaky-Test={} is:open'

_BUG_SUMMARY_SEARCH_QUERY_TEMPLATE = (
    'summary:{} is:open label:%s' % _TEST_FLAKY_Label)

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


def GetExistingBugIdForCustomizedField(field_value,
                                       monorail_project='chromium'):
  """Returns the bug id of an existing bug for this test.

  Args:
    field_value: The value of the customized field to search for.
    monorail_project: The Monorail project to search for.

  Returns:
    Id of the bug if it exists, otherwise None.
  """
  assert field_value, 'Value for customized field cannot be None or empty.'
  query = _BUG_CUSTOM_FIELD_SEARCH_QUERY_TEMPLATE.format(field_value)
  open_issues = _GetOpenIssues(query, monorail_project)
  return open_issues[0].id if open_issues else None


def BugAlreadyExistsForCustomField(test_name):
  """Returns True if the bug with the given custom field exists on monorail."""
  return GetExistingBugIdForCustomizedField(test_name) is not None


def GetExistingOpenBugIdForTest(test_name, monorail_project='chromium'):
  """Search for test_name issues that are about flakiness, and return id.

  Args:
    test_name: The test name to search for.
    monorail_project: The Monorail project to search for.

  Returns:
    Bug minimum id if exists, otherwise None.
  """
  assert test_name, 'Test name to search summary for cannot be None or empty.'
  query = _BUG_SUMMARY_SEARCH_QUERY_TEMPLATE.format(test_name)
  open_issues = _GetOpenIssues(query, monorail_project)

  if not open_issues:
    return None

  # Returns the one that was filed ealierst if there are multiple issues filed
  # by developers.
  return min([issue.id for issue in open_issues])


def OpenBugAlreadyExistsForTest(test_name):
  """Returns True if a bug about test_name being flaky exists on Monorail.

  Args:
    test_name: The test name to search for.

  Returns:
    True is there is already a bug about this test being flaky, False otherwise.
  """
  return GetExistingOpenBugIdForTest(test_name) is not None


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
          _TYPE_BUG_LABEL, _TEST_FLAKY_Label
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
          _TYPE_BUG_LABEL, _TEST_FLAKY_Label
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

  if _TEST_FLAKY_Label not in issue.labels:
    issue.labels.append(_TEST_FLAKY_Label)

  # Set Flaky-Test field. If it's already there, it's a no-op.
  flaky_field = CustomizedField(_FLAKY_TEST_CUSTOMIZED_FIELD,
                                normalized_test_name)
  issue.field_values.append(flaky_field)

  UpdateBug(issue, comment, monorail_project)
