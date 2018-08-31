# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Functions for interfacing with Mororail bugs."""
import abc
import logging
import textwrap

from google.appengine.ext import ndb

from gae_libs import appengine_util
from model.flake.detection.flake import Flake
from model.flake.detection.flake_issue import FlakeIssue
from monorail_api import CustomizedField
from monorail_api import Issue
from monorail_api import IssueTrackerAPI

# Label for Chromium Sheriff bug queue.
_SHERIFF_CHROMIUM_LABEL = 'Sheriff-Chromium'

# Label for Type-Bug.
_TYPE_BUG_LABEL = 'Type-Bug'

# Label used to identify issues related to flaky tests.
_FLAKY_TEST_LABEL = 'Test-Flaky'

# Label used to identify issues filed against Findit due to wrong results.
_TEST_FINDIT_WRONG_LABEL = 'Test-Findit-Wrong'

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


class FlakyTestIssueGenerator(object):
  """Encapsulates details needed to create or update a Monorail issue."""
  __metaclass__ = abc.ABCMeta

  def __init__(self):
    """Initiates a FlakyTestIssueGenerator object."""

    # Id of the previous issue that was tracking this flaky test.
    self._previous_tracking_bug_id = None

  @abc.abstractmethod
  def GetStepName(self):
    """Gets the name of the step to create or update issue for.

    Returns:
      A String representing the step name.
    """
    return

  @abc.abstractmethod
  def GetTestName(self):
    """Gets the name of the test to create or update issue for.

    Returns:
      A string representing the test name.
    """
    return

  @abc.abstractmethod
  def GetDescription(self):
    """Gets description for the issue to be created.

    Returns:
      A string representing the description.
    """
    return

  @abc.abstractmethod
  def GetComment(self):
    """Gets a comment to post an update to the issue.

    Returns:
      A string representing the comment.
    """
    return

  @abc.abstractmethod
  def ShouldRestoreChromiumSheriffLabel(self):
    """Returns True if the Sheriff label should be restored when updating bugs.

    This value should be set based on whether the results of the service are
    actionable. For example, for Flake Detection, once it detects new
    occurrences of a flaky test, it is immediately actionable that Sheriffs
    should disable the test ASAP. However, for Flake Analyzer, when the
    confidence is low, the analysis results mostly only serve as FYI
    information, so it would be too noisy to notify Sheriffs on every bug.

    Returns:
      A boolean indicates whether the Sheriff label should be restored.
    """
    return

  @abc.abstractmethod
  def GetLabels(self):
    """Gets labels for the issue to be created.

    Returns:
      A list of string representing the labels.
    """
    return

  def _GetCommonFlakyTestLabel(self):
    """Returns a list of comment labels used for flaky tests related issues.

    Args:
      A list of string representing the labels.
    """
    return [_SHERIFF_CHROMIUM_LABEL, _TYPE_BUG_LABEL, _FLAKY_TEST_LABEL]

  def GetStatus(self):
    """Gets status for the issue to be created.

    Returns:
      A string representing the status, for example: Untriaged.
    """
    return 'Untriaged'

  def GetSummary(self):
    """Gets summary for the issue to be created.

    Returns:
      A string representing the summary.
    """
    return '%s is flaky' % self.GetTestName()

  def GetPriority(self):
    """Gets priority for the issue to be created.

    Defaults to P1 for all flaky tests related bugs.

    Returns:
      A string representing the priority of the issue. (e.g Pri-1, Pri-2)
    """
    return 'Pri-1'

  def GetFlakyTestCustomizedField(self):
    """Gets Flaky-Test customized fields for the issue to be created.

    Returns:
      A CustomizedField field whose value is the test name.
    """
    return CustomizedField(_FLAKY_TEST_CUSTOMIZED_FIELD, self.GetTestName())

  def GetMonorailProject(self):
    """Gets the name of the Monorail project the issue is for.

    Returns:
      A string representing the Monorail project.
    """
    return 'chromium'

  def GetPreviousTrackingBugId(self):
    """Gets the id of the previous issue that was tracking this flaky test.

    Returns:
      A string representing the Id of the issue.
    """
    return self._previous_tracking_bug_id

  def SetPreviousTrackingBugId(self, previous_tracking_bug_id):
    """Sets the id of the previous issue that was tracking this flaky test.

    Args:
      previous_tracking_bug_id: Id of the issue that was tracking this test.
    """
    self._previous_tracking_bug_id = previous_tracking_bug_id

  def OnIssueCreated(self):
    """Called when an issue was created successfully."""
    return

  def OnIssueUpdated(self):
    """Called when an issue was updated successfully."""
    return


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
  existing_bug = GetMergedDestinationIssueForId(bug_id, project_id)
  return existing_bug and existing_bug.open


def GetMergedDestinationIssueForId(issue_id, monorail_project='chromium'):
  """Given an id, traverse the merge chain to get the destination issue.

  Args:
    issue_id: The id to get merged destination issue for.
    monorail_project: The Monorail project the issue is on.

  Returns:
    The destination issue if the orignal issue was merged, otherwise itself, and
    returns None if there is an exception while communicating with Monorail.

    NOTE: If there is a cycle in the merge chain, the first visited issue in the
    circle will be returned.
  """
  if issue_id is None:
    return None

  issue_tracker_api = IssueTrackerAPI(
      monorail_project, use_staging=appengine_util.IsStaging())
  issue = issue_tracker_api.getIssue(issue_id)
  visited_issues = set()

  while issue and issue.merged_into:
    logging.info('Issue %s was merged into %s on project: %s.', issue.id,
                 issue.merged_into, monorail_project)
    visited_issues.add(issue)
    issue = issue_tracker_api.getIssue(issue.merged_into)
    if issue in visited_issues:
      # There is a cycle, bails out.
      break

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

  def _is_not_test_findit_wrong_issue(issue):
    return _TEST_FINDIT_WRONG_LABEL not in issue.labels

  query = _FLAKY_TEST_SUMMARY_QUERY_TEMPLATE.format(test_name)
  open_issues = _GetOpenIssues(query, monorail_project)
  flaky_test_open_issues = [
      issue for issue in open_issues if (_is_issue_related_to_flake(issue) and
                                         _is_not_test_findit_wrong_issue(issue))
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


def CreateIssueWithIssueGenerator(issue_generator):
  """Creates a new issue with a given issue generator.

  Args:
    issue_generator: A FlakyTestIssueGenerator object.

  Returns:
    The id of the newly created issue.
  """
  labels = issue_generator.GetLabels()
  labels.append(issue_generator.GetPriority())
  issue = Issue({
      'status': issue_generator.GetStatus(),
      'summary': issue_generator.GetSummary(),
      'description': issue_generator.GetDescription(),
      'projectId': issue_generator.GetMonorailProject(),
      'labels': labels,
      'fieldValues': [issue_generator.GetFlakyTestCustomizedField()]
  })

  issue_id = CreateBug(issue, issue_generator.GetMonorailProject())
  if issue_id:
    issue_generator.OnIssueCreated()

  return issue_id


def UpdateIssueWithIssueGenerator(issue_id, issue_generator):
  """Updates an existing issue with a given issue generator.

  Args:
    issue_id: Id of the issue to be updated.
    issue_generator: A FlakyTestIssueGenerator object.
  """
  issue = GetMergedDestinationIssueForId(issue_id,
                                         issue_generator.GetMonorailProject())
  for label in issue_generator.GetLabels():
    # It is most likely that existing issues already have their priorities set
    # by developers, so it would be annoy if FindIt tries to overwrite it.
    if label.startswith('Pri-'):
      continue

    if (label == _SHERIFF_CHROMIUM_LABEL and
        not issue_generator.ShouldRestoreChromiumSheriffLabel()):
      continue

    if label not in issue.labels:
      issue.labels.append(label)

  issue.field_values.append(issue_generator.GetFlakyTestCustomizedField())
  UpdateBug(issue, issue_generator.GetComment(),
            issue_generator.GetMonorailProject())
  issue_generator.OnIssueUpdated()


def UpdateIssueIfExistsOrCreate(issue_generator, luci_project='chromium'):
  """Updates an exsiting issue if it exists, otherwise creates a new one.

  This method uses the best-effort to search the existing FlakeIssue entities
  and open issues on Monorail that are related to the flaky tests and reuse them
  if found, otherwise, creates a new issue and attach it to a Flake Model entity
  so that the newly created issue can be reused in the future.

  Args:
    issue_generator: A FlakyTestIssueGenerator object.
    luci_project: Name of the LUCI project that the flaky test is in, it is
                  used for searching existing Flake and FlakeIssue entities.

  Returns:
    Id of the issue that was eventually created or updated.
  """
  step_name = issue_generator.GetStepName()
  test_name = issue_generator.GetTestName()

  flake_key = ndb.Key(Flake, Flake.GetId(luci_project, step_name, test_name))
  target_flake = flake_key.get()
  if not target_flake:
    target_flake = Flake.Create(luci_project, step_name, test_name)
    target_flake.put()

  monorail_project = issue_generator.GetMonorailProject()
  flake_issue = target_flake.flake_issue_key.get(
  ) if target_flake.flake_issue_key else None
  previous_tracking_bug_id = None

  if flake_issue:
    merged_issue = GetMergedDestinationIssueForId(flake_issue.issue_id,
                                                  monorail_project)
    if flake_issue.issue_id != merged_issue.id:
      logging.info(
          'Currently attached issue %s was merged to %s, attach the new issue '
          'id to this flake.',
          FlakeIssue.GetLinkForIssue(monorail_project, flake_issue.issue_id),
          FlakeIssue.GetLinkForIssue(monorail_project, merged_issue.id))
      previous_tracking_bug_id = flake_issue.issue_id
      flake_issue.issue_id = merged_issue.id
      flake_issue.put()

    if merged_issue.open:
      logging.info(
          'Currently attached issue %s is open, update flake: %s with new '
          'occurrences.',
          FlakeIssue.GetLinkForIssue(monorail_project, merged_issue.id),
          target_flake.key)
      issue_generator.SetPreviousTrackingBugId(previous_tracking_bug_id)
      UpdateIssueWithIssueGenerator(
          issue_id=flake_issue.issue_id, issue_generator=issue_generator)
      return flake_issue.issue_id

    logging.info(
        'flake %s has no issue attached or the attached issue was closed.' %
        target_flake.key)
    previous_tracking_bug_id = merged_issue.id

  # Re-use an existing open bug if possible.
  issue_id = SearchOpenIssueIdForFlakyTest(target_flake.normalized_test_name,
                                           monorail_project)
  if issue_id:
    logging.info(
        'An existing issue %s was found, attach it flake: %s and update it '
        'with new occurrences.',
        FlakeIssue.GetLinkForIssue(monorail_project, issue_id),
        target_flake.key)
    _AssignIssueIdToFlake(issue_id, target_flake)
    issue_generator.SetPreviousTrackingBugId(previous_tracking_bug_id)
    UpdateIssueWithIssueGenerator(
        issue_id=issue_id, issue_generator=issue_generator)
    return issue_id

  logging.info('No existing open issue was found, create a new one.')
  issue_generator.SetPreviousTrackingBugId(previous_tracking_bug_id)
  issue_id = CreateIssueWithIssueGenerator(issue_generator=issue_generator)
  logging.info('%s was created for flake: %s.',
               FlakeIssue.GetLinkForIssue(monorail_project, issue_id),
               target_flake.key)
  _AssignIssueIdToFlake(issue_id, target_flake)
  return issue_id


def _AssignIssueIdToFlake(issue_id, flake):
  """Assigns an issue id to a flake, and created a FlakeIssue if necessary.

  Args:
    issue_id: Id of a Monorail issue.
    flake: A Flake Model entity.
  """
  assert flake, 'The flake entity cannot be None.'

  flake_issue = flake.flake_issue_key.get() if flake.flake_issue_key else None
  if flake_issue and flake_issue.issue_id == issue_id:
    return

  if flake_issue:
    flake_issue.issue_id = issue_id
    flake_issue.put()
    return

  monorail_project = FlakeIssue.GetMonorailProjectFromLuciProject(
      flake.luci_project)
  flake_issue = FlakeIssue.Create(monorail_project, issue_id)
  flake_issue.put()
  flake.flake_issue_key = flake_issue.key
  flake.put()
