# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Utilities for assisting in bug management for flaky tests."""

from collections import defaultdict
import datetime
import logging

from google.appengine.ext import ndb

from googleapiclient.errors import HttpError
from libs import time_util
from model.flake.detection.flake_occurrence import FlakeOccurrence
from model.flake.flake import Flake
from model.flake.flake_issue import FlakeIssue
from model.flake.flake_type import FlakeType
from services import issue_constants
from services import monorail_util
from services.apis import AnalyzeDetectedFlakeOccurrence
from services.flake_failure import flake_constants
from services.issue_generator import FlakeDetectionIssueGenerator
from waterfall import waterfall_config


def _GetOpenIssueIdForFlakyTestByCustomizedField(test_name,
                                                 monorail_project='chromium'):
  """Returns flaky tests related issue by searching customized field.

  Args:
    test_name: The name of the test to search for.
    monorail_project: The Monorail project to search for.

  Returns:
    Id of the issue if it exists, otherwise None.
  """
  query = issue_constants.FLAKY_TEST_CUSTOMIZED_FIELD_QUERY_TEMPLATE.format(
      test_name)
  open_issues = monorail_util.GetOpenIssues(query, monorail_project)
  return open_issues[0].id if open_issues else None


def _GetOpenIssueIdForFlakyTestBySummary(test_name,
                                         monorail_project='chromium'):
  """Returns flaky tests related issue by searching summary.

  Note that searching for |test_name| in the summary alone is not enough, for
  example: 'suite.test needs to be rewritten', so at least one of the following
  additional identifiers is also required:
  1. The issue has label: Test-Flaky.
  2. The issue has component: Tests>Flaky.
  3. The issue has one of the issue_constants.FLAKY_TEST_SUMMARY_KEYWORDS in
     the summary.

  Args:
    test_name: The name of the test to search for.
    monorail_project: The Monorail project to search for.

  Returns:
    Minimum id among the matched issues if exists, otherwise None.
  """

  def _is_issue_related_to_flake(issue):
    if issue_constants.FLAKY_TEST_LABEL in issue.labels:
      return True

    if issue_constants.FLAKY_TEST_COMPONENT in issue.components:
      return True

    return any(keyword in issue.summary.lower()
               for keyword in issue_constants.FLAKY_TEST_SUMMARY_KEYWORDS)

  def _is_not_test_findit_wrong_issue(issue):
    return issue_constants.TEST_FINDIT_WRONG_LABEL not in issue.labels

  query = issue_constants.FLAKY_TEST_SUMMARY_QUERY_TEMPLATE.format(test_name)
  open_issues = monorail_util.GetOpenIssues(query, monorail_project)
  flaky_test_open_issues = [
      issue for issue in open_issues if (_is_issue_related_to_flake(issue) and
                                         _is_not_test_findit_wrong_issue(issue))
  ]
  if not flaky_test_open_issues:
    return None

  return min([issue.id for issue in flaky_test_open_issues])


def OpenIssueAlreadyExistsForFlakyTest(test_name, monorail_project='chromium'):
  """Returns True if a related flaky test bug already exists on Monorail.

  Args:
    test_name: The test name to search for.
    monorail_project: The Monorail project to search for.

  Returns:
    True is there is already a bug about this test being flaky, False otherwise.
  """
  return SearchOpenIssueIdForFlakyTest(test_name, monorail_project) is not None


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


def _GetFlakeIssue(flake):
  """Returns the associated flake issue if it exists.

  Args:
    flake: A Flake Model entity.

  Returns:
    A FlakeIssue entity if it exists, otherwise None.
  """
  if not flake or not flake.flake_issue_key:
    return None

  flake_issue = flake.flake_issue_key.get()
  if not flake_issue:
    # Data is inconsistent, reset the key to allow a new FlakeIssue to be
    # attached later.
    flake.flake_issue_key = None
    flake.put()
    return None

  return flake_issue


def _FlakeHasEnoughOccurrences(unreported_occurrences):
  """Returns True if there are enough occurrences to worth reporting the flake.

  A flake has enough occurrences if the occurrences cover at least 3 different
  CLs.

  Args:
    unreported_occurrences: A list of occurrence that share the same parent
                            flake and haven't been reported yet.
                            The caller is responsible for making sure of it.
  """
  flake_detection_settings = waterfall_config.GetFlakeDetectionSettings()
  required_falsely_rejected_cls = flake_detection_settings.get(
      'min_required_impacted_cls_per_day',
      flake_constants.DEFAULT_MINIMUM_REQUIRED_IMPACTED_CLS_PER_DAY)
  cl_ids = [occurrence.gerrit_cl_id for occurrence in unreported_occurrences]
  unique_cl_ids = set(cl_ids)
  return len(unique_cl_ids) >= required_falsely_rejected_cls


def GetFlakesWithEnoughOccurrences():
  """Queries Datastore and returns flakes that has enough occurrences.

  The most intuitive algorithm is to fetch all flakes first, and then for each
  flake, fetch its recent and unreported flake occurrences, but it has
  performance implications when there are a lot of flakes (too many RPC calls)
  because a large number of calls are wasted on flakes that don't even have any
  recent and unreported flake occurrence.

  So, instead, this algorithm first fetches all recent and unreported flake
  occurrences, and then by looking up their parents to figure out the subset of
  flakes that need to be fetched.

  Returns:
    A list of tuples whose first element is a flake entity and second element is
    number of corresponding recent and unreported occurrences.
  """
  utc_one_day_ago = time_util.GetUTCNow() - datetime.timedelta(days=1)
  occurrences = FlakeOccurrence.query(
      ndb.AND(FlakeOccurrence.flake_type == FlakeType.CQ_FALSE_REJECTION,
              FlakeOccurrence.time_happened > utc_one_day_ago)).fetch()

  logging.info(
      'There are %d cq false rejection occurrences within the past 24h.' %
      len(occurrences))

  flake_key_to_occurrences = defaultdict(list)
  for occurrence in occurrences:
    flake_key_to_occurrences[occurrence.key.parent()].append(occurrence)

  unique_flake_keys = flake_key_to_occurrences.keys()
  flakes = ndb.get_multi(unique_flake_keys)
  flakes = [flake for flake in flakes if flake is not None]

  # Filter out occurrences that have already been reported according to the
  # last update time of the associated flake issue.
  flake_key_to_unreported_occurrences = {}
  for flake_key, occurrences in flake_key_to_occurrences.iteritems():
    flake_issue = _GetFlakeIssue(flake_key.get())
    last_updated_time_by_flake_detection = (
        flake_issue.last_updated_time_by_flake_detection
        if flake_issue else None)

    if (last_updated_time_by_flake_detection and
        last_updated_time_by_flake_detection > utc_one_day_ago):
      # An issue can be updated at most once in any 24h window avoid noises.
      continue

    flake_key_to_unreported_occurrences[flake_key] = occurrences

  # Set to None to avoid being mistakenly used in following code.
  flake_key_to_occurrences = None

  flakes_with_enough_occurrences = [
      flake for flake in flakes
      if flake.key in flake_key_to_unreported_occurrences and
      _FlakeHasEnoughOccurrences(flake_key_to_unreported_occurrences[flake.key])
  ]

  # Cannot use a dictionary because Model is not immutable.
  flake_and_occurrences_count_tuples = []
  for flake in flakes_with_enough_occurrences:
    flake_and_occurrences_count_tuples.append(
        (flake, len(flake_key_to_unreported_occurrences[flake.key])))

  return flake_and_occurrences_count_tuples


# TODO(crbug.com/903459): Move ReportFlakesToMonorail and
#  ReportFlakesToFlakeAnalyzer to auto action layer.
def ReportFlakesToMonorail(flake_tuples_to_report):
  """Reports newly detected flakes and occurrences to Monorail.

  ONLY create or update a bug if:
    rule 1. Has NOT reached the maximum configured bug update limit within 24h.
    rule 2. The bug wasn't created or updated within the past 24h.

  Args:
    flake_tuples_to_report: A list of tuples whose first element is a Flake
                            entity and second element is a list of corresponding
                            occurrences to report.
  """
  action_settings = waterfall_config.GetActionSettings()
  limit = action_settings.get('max_flake_bug_updates_per_day',
                              flake_constants.DEFAULT_MAX_BUG_UPDATES_PER_DAY)

  utc_one_day_ago = time_util.GetUTCNow() - datetime.timedelta(days=1)
  num_updated_issues_24h = (
      FlakeIssue.query(
          FlakeIssue.last_updated_time_by_flake_detection > utc_one_day_ago)
      .count())

  if num_updated_issues_24h >= limit:
    logging.info('Issues created or updated during the past 24 hours has '
                 'reached the limit.')
    return

  num_of_flakes_to_report = min(
      len(flake_tuples_to_report), limit - num_updated_issues_24h)
  flake_tuples_to_report = flake_tuples_to_report[:num_of_flakes_to_report]
  logging.info('There are %d flakes whose issues will be created or updated.' %
               num_of_flakes_to_report)

  for flake, occurrences_count in flake_tuples_to_report:
    issue_generator = FlakeDetectionIssueGenerator(flake, occurrences_count)
    try:
      CreateOrUpdateIssue(issue_generator, flake.luci_project)

      # Update FlakeIssue's last_updated_time_by_flake_detection property. This
      # property is only applicable to Flake Detection because Flake Detection
      # can update an issue at most once every 24 hours.
      flake_issue = flake.flake_issue_key.get()
      flake_issue.last_updated_time_by_flake_detection = time_util.GetUTCNow()
      flake_issue.put()
    except HttpError as error:
      # benign exceptions (HttpError 403) may happen when FindIt tries to
      # update an issue that it doesn't have permission to. Do not raise
      # exception so that the for loop can move on to create or update next
      # issues.
      logging.warning('Failed to create or update issue due to error: %s',
                      error)


def _IsReportFlakesToFlakeAnalyzerEnabled():
  """Returns True if the feature to report flakes to Flake Analyzer is enabled.

  Returns:
    Returns True if it is enabled, otherwise False.
  """
  # Unless the flag is explicitly set, assumes disabled by default.
  return waterfall_config.GetFlakeDetectionSettings().get(
      'report_flakes_to_flake_analyzer', False)


def ReportFlakesToFlakeAnalyzer(flake_tuples_to_report):
  """Reports newly detected flakes and occurrences to Flake Analyzer.

  Args:
    flake_tuples_to_report: A list of tuples whose first element is a Flake
                            entity and second element is a list of corresponding
                            occurrences to report.
  """
  if not _IsReportFlakesToFlakeAnalyzerEnabled():
    logging.info('Skip reporting flakes to Flake Analyzer because the feature '
                 'is disabled.')
    return

  for flake, occurrences in flake_tuples_to_report:
    flake_issue = _GetFlakeIssue(flake)
    issue_id = flake_issue.issue_id if flake_issue else None
    for occurrence in occurrences:
      AnalyzeDetectedFlakeOccurrence(flake, occurrence, issue_id)


def CreateOrUpdateIssue(issue_generator, luci_project='chromium'):
  """Updates an issue if it exists, otherwise creates a new one.

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
  test_label_name = issue_generator.GetTestLabelName()

  target_flake = Flake.Get(luci_project, step_name, test_name)
  if not target_flake:
    target_flake = Flake.Create(luci_project, step_name, test_name,
                                test_label_name)
    target_flake.put()

  monorail_project = issue_generator.GetMonorailProject()
  flake_issue = target_flake.flake_issue_key.get(
  ) if target_flake.flake_issue_key else None
  previous_tracking_bug_id = None

  if flake_issue:
    merged_issue = monorail_util.GetMergedDestinationIssueForId(
        flake_issue.issue_id, monorail_project)
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
      monorail_util.UpdateIssueWithIssueGenerator(
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
    monorail_util.UpdateIssueWithIssueGenerator(
        issue_id=issue_id, issue_generator=issue_generator)
    return issue_id

  logging.info('No existing open issue was found, create a new one.')
  issue_generator.SetPreviousTrackingBugId(previous_tracking_bug_id)
  issue_id = monorail_util.CreateIssueWithIssueGenerator(
      issue_generator=issue_generator)
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
