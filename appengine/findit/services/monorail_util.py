# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Functions for interfacing with Mororail bugs."""
import logging

from googleapiclient.errors import HttpError

from common import constants
from gae_libs import appengine_util
from libs import time_util
from monorail_api import Issue
from monorail_api import IssueTrackerAPI
from services.constants import DAYS_IN_A_WEEK
from services import issue_constants


def GetOpenIssues(query, monorail_project):
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


def IsIssueClosedWithinAWeek(issue):
  """Checks if a monorail issue is closed (excepted Merged) within a week."""
  return (issue.status in issue_constants.CLOSED_STATUSES_NO_DUPLICATE and
          issue.closed > time_util.GetDateDaysBeforeNow(DAYS_IN_A_WEEK))


def GetIssuesClosedWithinAWeek(query, monorail_project):
  """Searches for bugs that match the query and closed within a week.

  Args:
    query: A query to search for bugs on Monorail.
    monorail_project: The monorail project to search for.

  Returns:
    A list of recently closed bugs that match the query.
  """
  issue_tracker_api = IssueTrackerAPI(
      monorail_project, use_staging=appengine_util.IsStaging())
  issues = issue_tracker_api.getIssues(query)
  if not issues:
    return []

  return [issue for issue in issues if IsIssueClosedWithinAWeek(issue)]


def OpenBugAlreadyExistsForId(bug_id, project_id='chromium'):
  """Returns True if the bug exists and is open on monorail."""
  existing_bug = GetMergedDestinationIssueForId(bug_id, project_id)
  return existing_bug and existing_bug.open


def GetMonorailIssueForIssueId(issue_id,
                               monorail_project='chromium',
                               issue_tracker_api=None):
  """Returns a Monorail Issue object representation given an issue_id.

  Args:
    issue_id (int): The id to query Monorail with.
    monorail_project (str): The project name to query Monorail with.
    issue_tracker_api (IssueTrackerAPI): When provided, no need to create a new
      one.

  Returns:
    (Issue): An Issue object representing what is currently stored on Monorail.
  """
  issue_tracker_api = issue_tracker_api or IssueTrackerAPI(
      monorail_project, use_staging=appengine_util.IsStaging())
  try:
    return issue_tracker_api.getIssue(issue_id)
  except HttpError as e:
    logging.warning('Failed to download monorail issue %d: %s.', issue_id, e)
    return None


def WasCreatedByFindit(issue):
  return issue.reporter == constants.DEFAULT_SERVICE_ACCOUNT


def GetMergedDestinationIssueForId(issue_id,
                                   monorail_project='chromium',
                                   force_follow_merge_chain=False):
  """Given an id, traverse the merge chain to get the destination issue.

  Args:
    issue_id: The id to get merged destination issue for.
    monorail_project: The Monorail project the issue is on.
    force_follow_merge_chain: True for traversing the merge chain regardless of
      the status of requested change; False if only traverse when the issue is
      in Duplicate status.

  issue.merged_into is the most recent issue it was merged into, so if an
  issue was merged then unmerged, this field will still have value.

  Returns:
    The destination issue if the original issue was merged, otherwise itself,
    and returns None if there is an exception while communicating with
    Monorail.

    NOTE: If there is a circle in the merge chain, the first visited issue in
    the circle will be returned.
  """
  if issue_id is None:
    return None

  issue_tracker_api = IssueTrackerAPI(
      monorail_project, use_staging=appengine_util.IsStaging())
  issue = GetMonorailIssueForIssueId(
      issue_id, issue_tracker_api=issue_tracker_api)
  visited_issues = set()

  while issue and issue.merged_into and (force_follow_merge_chain or
                                         issue.status == 'Duplicate'):
    logging.info('Issue %s was merged into %s on project: %s.', issue.id,
                 issue.merged_into, monorail_project)
    visited_issues.add(issue)
    merged_issue = GetMonorailIssueForIssueId(
        issue.merged_into, issue_tracker_api=issue_tracker_api)

    if not merged_issue:
      # Cannot access merged_issue, could be an restricted issue.
      return issue

    issue = merged_issue
    if issue in visited_issues:
      # There is a circle, bails out.
      break

  return issue


def MergeDuplicateIssues(duplicate_issue, destination_issue, comment):
  """Merges duplicate_issue into destination_issue on Monorail.

  Args:
    duplicate_issue (Issue): Duplicate issue to be merged.
    destination_issue (Issue): Issue to be merged into.
    comment (str): The comment to include when merging duplicate_issue.
  """
  duplicate_issue.status = 'Duplicate'
  duplicate_issue.merged_into = str(destination_issue.id)
  UpdateBug(duplicate_issue, comment)


def GetComments(issue_id, monorail_project='chromium'):
  """Returns a list of Monorail Comment objects given an issue id."""
  issue_tracker_api = IssueTrackerAPI(
      monorail_project, use_staging=appengine_util.IsStaging())
  try:
    return issue_tracker_api.getComments(issue_id)
  except HttpError as e:
    logging.warning('Failed to get comments of issue %d: %s', issue_id, e)
    return []


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

  try:
    issue_tracker_api.update(issue, comment, send_email=True)
  except HttpError as e:
    logging.warning('Failed to update monorail issue %d: %s.', issue.id, e)
    return issue.id

  return issue.id


def CreateIssueWithIssueGenerator(issue_generator):
  """Creates a new issue with a given issue generator.

  Args:
    issue_generator: A FlakyTestIssueGenerator object.

  Returns:
    The id of the newly created issue.
  """
  issue_info = {
      'status': issue_generator.GetStatus(),
      'summary': issue_generator.GetSummary(),
      'description': issue_generator.GetDescription(),
      'projectId': issue_generator.GetMonorailProject(),
      'labels': issue_generator.GetLabels(),
      'components': issue_generator.GetComponents()
  }
  field_value = issue_generator.GetFlakyTestCustomizedField()
  if field_value:
    issue_info['fieldValues'] = [field_value]

  issue = Issue(issue_info)
  issue.owner = issue_generator.GetAutoAssignOwner()
  issue_id = CreateBug(issue, issue_generator.GetMonorailProject())

  if issue_id:
    issue_generator.OnIssueCreated()

  return issue_id


def UpdateIssueWithIssueGenerator(issue_id, issue_generator, reopen=False):
  """Updates an existing issue with a given issue generator.

  Args:
    issue_id: Id of the issue to be updated.
    issue_generator: A FlakyTestIssueGenerator object.
    reopen: True to reopen a closed bug, otherwise False.
  """
  issue = GetMergedDestinationIssueForId(issue_id,
                                         issue_generator.GetMonorailProject())
  if not issue:
    return

  for label in issue_generator.GetLabels():
    # It is most likely that existing issues already have their priorities set
    # by developers, so it would be annoy if FindIt tries to overwrite it.
    if label.startswith('Pri-'):
      continue

    if (label == issue_constants.SHERIFF_CHROMIUM_LABEL and
        not issue_generator.ShouldRestoreChromiumSheriffLabel()):
      continue

    if label not in issue.labels:
      issue.labels.append(label)

  field_value = issue_generator.GetFlakyTestCustomizedField()
  if field_value:
    issue.field_values.append(field_value)

  if not issue.owner:
    # Assign a potential owner if one is not already set.
    issue.owner = issue_generator.GetAutoAssignOwner()

  if reopen and issue.status in issue_constants.CLOSED_STATUSES_NO_DUPLICATE:
    # Reopens a closed issue.
    issue.status = 'Assigned' if issue.owner else 'Available'

  UpdateBug(issue, issue_generator.GetComment(),
            issue_generator.GetMonorailProject())
  issue_generator.OnIssueUpdated()


def PostCommentOnMonorailBug(issue_id, issue_generator, comment):
  """Posts a comment on monorail bug.

  Args:
    issue_id: Id of the issue to be updated.
    issue_generator: A FlakyTestIssueGenerator object.
    comment: Comment content.
  """
  issue = GetMergedDestinationIssueForId(issue_id,
                                         issue_generator.GetMonorailProject())
  UpdateBug(issue, comment, issue_generator.GetMonorailProject())
  issue_generator.OnIssueUpdated()
