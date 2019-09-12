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
from services.issue_generator import FlakeDetectionGroupIssueGenerator
from waterfall import waterfall_config

# The default number of entities to query for at a time should paging be needed.
_PAGE_SIZE = 1000


class FlakeGroup(object):

  def __init__(self, occurrences, luci_project):
    self.flakes = []
    self.num_occurrences = len(occurrences)
    self.luci_project = luci_project

  def AddFlakeIfBelong(self, flake, occurrences):
    """Tries to add a flake to group if it can belong.

    Returns:
      (bool), True if the flake is added to the group otherwise False.
    """
    raise NotImplementedError(
        'AddFlakeIfBelong should be implemented in the child class')


# Group of flakes that need the same new bug.
class FlakeGroupByOccurrences(FlakeGroup):

  def __init__(self, flake, occurrences):
    super(FlakeGroupByOccurrences, self).__init__(occurrences,
                                                  flake.luci_project)
    self.canonical_step_name = flake.GetTagValue(
        'test_type') or flake.normalized_step_name
    self.flakes.append(flake)
    self.builds = self._GenerateBuildsList(occurrences)

  def _GenerateBuildsList(self, occurrences):
    occurrence_builds = []
    for occurrence in occurrences:
      build_key = '{}@{}@{}'.format(occurrence.build_configuration.luci_project,
                                    occurrence.build_configuration.luci_bucket,
                                    occurrence.build_id)
      occurrence_builds.append(build_key)
    return occurrence_builds

  def AddFlakeIfBelong(self, flake, occurrences):
    """Adds the flake if it happens at the same builds as other flakes in group.

    Args:
      flake (Flake): Flake entity to be added in the group.
      occurrences (list): A list of occurrences of the flake.

    Returns:
      (bool), True if the flake is added to the group otherwise False.
    """
    if len(occurrences) != len(self.builds):
      return False

    occurrence_builds = self._GenerateBuildsList(occurrences)

    if sorted(occurrence_builds) == sorted(self.builds):
      self.flakes.append(flake)
      return True

    return False

  def ToDict(self):
    # For unittest purpose.
    return {
        'canonical_step_name': self.canonical_step_name,
        'flakes': self.flakes,
        'builds': self.builds,
        'num_occurrences': self.num_occurrences
    }


# Group of flakes that are already linked to the same issue directly or
# linked to issues that merge into the issue. The flakes will only be grouped by
# the issue in this case, and they may not meet the heuristic rules as
# FlakeGroupByOccurrences.
class FlakeGroupByFlakeIssue(FlakeGroup):

  def __init__(self, flake_issue, flake, occurrences, previous_flake_issue):
    super(FlakeGroupByFlakeIssue, self).__init__(occurrences,
                                                 flake.luci_project)
    self.flake_issue = flake_issue
    self.flakes_with_same_occurrences = True
    self.flakes.append(flake)

    if flake_issue.issue_id != previous_flake_issue.issue_id:
      self.previous_issue_id = previous_flake_issue.issue_id
    else:
      self.previous_issue_id = None

  def AddFlakeIfBelong(self, flake, occurrences):
    """Adds the flake, also updates flakes_with_same_occurrences and
      num_occurrences if needed.

    Args:
      flake (Flake): Flake entity to be added in the group.
      occurrences (list): A list of occurrences of the flake.

    Returns:
      (bool), True if the flake is added to the group otherwise False.
    """

    flake_issue = GetFlakeIssue(flake)
    assert flake_issue == self.flake_issue, (
        'Tried to add flake {flake} to group with issue {issue}, while flake '
        'links to another issue {a_issue}'.format(
            flake=flake.key.urlsafe(),
            issue=FlakeIssue.GetLinkForIssue(self.flake_issue.monorail_project,
                                             self.flake_issue.issue_id),
            a_issue=FlakeIssue.GetLinkForIssue(flake_issue.monorail_project,
                                               flake_issue.issue_id)
            if flake_issue else None))

    self.flakes.append(flake)
    if len(occurrences) < self.num_occurrences:
      # Only maintains a minimum num_occurrences to show in bug comments.
      self.num_occurrences = len(occurrences)
      self.flakes_with_same_occurrences = False
    return True

  def ToDict(self):
    # For unittest purpose.
    return {
        'flake_issue': self.flake_issue,
        'flakes': self.flakes,
        'flakes_with_same_occurrences': self.flakes_with_same_occurrences,
        'num_occurrences': self.num_occurrences
    }


def _GetIssueIdForFlakyTestByCustomizedField(test_name,
                                             monorail_project='chromium',
                                             is_open=True):
  """Returns flaky tests related issue by searching customized field.

  Args:
    test_name: The name of the test to search for.
    monorail_project: The Monorail project to search for.
    is_open: True if the issue must be open, False if the issue is just closed.

  Returns:
    Id of the issue if it exists, otherwise None.
  """
  query = issue_constants.FLAKY_TEST_CUSTOMIZED_FIELD_QUERY_TEMPLATE.format(
      test_name)
  if is_open:
    issues = monorail_util.GetOpenIssues(query, monorail_project)
  else:
    issues = monorail_util.GetIssuesClosedWithinAWeek(query, monorail_project)
  return issues[0].id if issues else None


def _GetIssueIdForFlakyTestBySummary(test_name,
                                     monorail_project='chromium',
                                     is_open=True):
  """Returns flaky tests related issue by searching summary.

  Note that searching for |test_name| in the summary alone is not enough, for
  example: 'suite.test needs to be rewritten', so at least one of the following
  additional identifiers is also required:
  1. The issue has label: Test-Flaky.
  2. The issue has one of the issue_constants.FLAKY_TEST_SUMMARY_KEYWORDS in
     the summary.

  Args:
    test_name: The name of the test to search for.
    monorail_project: The Monorail project to search for.
    is_open: True if the issue must be open, False if the issue is just closed.

  Returns:
    Minimum id among the matched issues if exists, otherwise None.
  """

  def _is_issue_related_to_flake(issue):
    if issue_constants.FLAKY_TEST_LABEL in issue.labels:
      return True

    return any(keyword in issue.summary.lower()
               for keyword in issue_constants.FLAKY_TEST_SUMMARY_KEYWORDS)

  def _is_not_test_findit_wrong_issue(issue):
    return issue_constants.TEST_FINDIT_WRONG_LABEL not in issue.labels

  query = issue_constants.FLAKY_TEST_SUMMARY_QUERY_TEMPLATE.format(test_name)

  if is_open:
    issues = monorail_util.GetOpenIssues(query, monorail_project)
  else:
    issues = monorail_util.GetIssuesClosedWithinAWeek(query, monorail_project)
  flaky_test_issues = [
      issue for issue in issues if (_is_issue_related_to_flake(issue) and
                                    _is_not_test_findit_wrong_issue(issue))
  ]
  if not flaky_test_issues:
    return None

  return min([issue.id for issue in flaky_test_issues])


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
  # Prefers issues without customized field because it means that the bugs were
  # created manually by develoepers, so it is more likely to gain attentions.
  # Also prefers open issues.
  return (_GetIssueIdForFlakyTestBySummary(test_name, monorail_project) or
          _GetIssueIdForFlakyTestByCustomizedField(test_name, monorail_project))


def SearchRecentlyClosedIssueIdForFlakyTest(test_name,
                                            monorail_project='chromium'):
  """Searches for issue which is closed within a week for a flake on Monorail.

  Args:
    test_name: The test name to search for.
    monorail_project: The Monorail project to search for.

  Returns:
    Id of the issue if it exists, otherwise None.
  """
  # Prefer issues without customized field because it means that the bugs were
  # created manually by develoepers, so it is more likely to gain attentions.
  return (_GetIssueIdForFlakyTestBySummary(
      test_name, monorail_project, is_open=False) or
          _GetIssueIdForFlakyTestByCustomizedField(
              test_name, monorail_project, is_open=False))


def GetFlakeIssue(flake):
  """Returns the associated flake issue to a flake.

  Tries to use the flake's issue's merge_destination, and falls back to the
    issue itself if it doesn't merge into any other ones.

  Args:
    flake: A Flake Model entity.

  Returns:
    A FlakeIssue entity if it exists, otherwise None. This entity should be the
      final merging destination issue.
  """
  if not flake:
    return None

  return flake.GetIssue(up_to_date=True)


def _FlakeHasEnoughOccurrences(unreported_occurrences):
  """Returns True if there are enough occurrences to worth reporting the flake.

  A flake has enough occurrences if the occurrences cover at least 3 different
  CLs for CQ flakes.

  Args:
    unreported_occurrences: A list of non hidden occurrence that share the same
      parent flake and haven't been reported yet.
      The caller is responsible for making sure of it.
  """
  flake_detection_settings = waterfall_config.GetFlakeDetectionSettings()
  required_non_hidden_impacted_cls = flake_detection_settings.get(
      'min_required_impacted_cls_per_day',
      flake_constants.DEFAULT_MINIMUM_REQUIRED_IMPACTED_CLS_PER_DAY)
  cl_ids = [occurrence.gerrit_cl_id for occurrence in unreported_occurrences]
  unique_cl_ids = set(cl_ids)
  return len(unique_cl_ids) >= required_non_hidden_impacted_cls


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
    A list of tuples whose first element is a flake entity, second element is
    number of corresponding recent and unreported occurrences, third element is
    the flake issue the flake links to if exist. And this list is sorted by each
    flake's flake_score_last_week in descending order.
  """
  utc_one_day_ago = time_util.GetUTCNow() - datetime.timedelta(days=1)
  occurrences = FlakeOccurrence.query(
      ndb.AND(
          FlakeOccurrence.flake_type.IN(
              [FlakeType.CQ_FALSE_REJECTION, FlakeType.RETRY_WITH_PATCH]),
          FlakeOccurrence.time_happened > utc_one_day_ago)).fetch()

  logging.info('There are %d non cq hidden occurrences within the past 24h.' %
               len(occurrences))

  flake_key_to_occurrences = defaultdict(list)
  for occurrence in occurrences:
    flake_key_to_occurrences[occurrence.key.parent()].append(occurrence)

  unique_flake_keys = flake_key_to_occurrences.keys()
  flakes = ndb.get_multi(unique_flake_keys)

  key_to_flake = dict(zip(unique_flake_keys, flakes))

  luci_test_keys = [
      ndb.Key('LuciTest', flake_key.id()) for flake_key in unique_flake_keys
  ]
  luci_tests = ndb.get_multi(luci_test_keys)
  key_to_luci_test = dict(zip(unique_flake_keys, luci_tests))

  # Filter out occurrences that have already been reported according to the
  # last update time of the associated flake issue.
  flake_key_to_enough_unreported_occurrences = {}
  for flake_key, occurrences in flake_key_to_occurrences.iteritems():
    if not key_to_flake[flake_key]:
      logging.error('Flake not found for key %s', flake_key.urlsafe())
      continue

    if not _FlakeHasEnoughOccurrences(occurrences):
      continue

    flake_issue = GetFlakeIssue(flake_key.get())
    # Do not update issues for flakes which have been disabled and the
    # FlakeIssue is being tracked by LuciTest.
    luci_test = key_to_luci_test.get(flake_key)
    if (flake_issue and luci_test and luci_test.disabled and
        flake_issue.key in luci_test.issue_keys):
      continue
    last_updated_time_by_flake_detection = (
        flake_issue.last_updated_time_by_flake_detection
        if flake_issue else None)
    if (last_updated_time_by_flake_detection and
        last_updated_time_by_flake_detection > utc_one_day_ago):
      # An issue can be updated at most once in any 24h window avoid noises.
      continue

    flake_key_to_enough_unreported_occurrences[flake_key] = {
        'occurrences': occurrences,
        'flake_issue': flake_issue
    }

  flake_tuples_to_report = [
      (key_to_flake[flake_key], info['occurrences'], info['flake_issue']) for
      flake_key, info in flake_key_to_enough_unreported_occurrences.iteritems()
  ]

  return sorted(
      flake_tuples_to_report,
      key=lambda tup: tup[0].flake_score_last_week,
      reverse=True)


def GetAndUpdateMergedIssue(flake_issue):
  """Gets the most up-to-date merged issue and update data in data store.

  Args:
    flake_issue (FlakeIssue): FlakeIssue to check its merge destination and
       update.

  Returns:
    merged_issue (monorail_api.Issue): Merge destination of the flake_issue.
  """
  monorail_project = flake_issue.monorail_project
  merged_issue = monorail_util.GetMergedDestinationIssueForId(
      flake_issue.issue_id, monorail_project)
  if merged_issue and flake_issue.issue_id != merged_issue.id:
    logging.info(
        'Flake issue %s was merged to %s, updates this issue and'
        ' all issues were merged into it.',
        FlakeIssue.GetLinkForIssue(monorail_project, flake_issue.issue_id),
        FlakeIssue.GetLinkForIssue(monorail_project, merged_issue.id))
    _UpdateMergeDestinationAndIssueLeaves(flake_issue, merged_issue)

  return merged_issue


def _AddFlakeToGroupWithIssue(flake_groups_to_update_issue, flake_issue, flake,
                              occurrences):
  flake_group = flake_groups_to_update_issue.get(flake_issue.issue_id)

  if flake_group:
    flake_group.AddFlakeIfBelong(flake, occurrences)
    return True

  merged_monorail_issue = GetAndUpdateMergedIssue(flake_issue)
  if not merged_monorail_issue or not (
      merged_monorail_issue.open or
      monorail_util.IsIssueClosedWithinAWeek(merged_monorail_issue)):
    # Only creates new group of flakes by FlakeIssue if the issue is still
    # open or closed within a week.
    return False

  updated_flake_issue = flake_issue.GetMostUpdatedIssue()

  flake_group = FlakeGroupByFlakeIssue(updated_flake_issue, flake, occurrences,
                                       flake_issue)
  flake_groups_to_update_issue[updated_flake_issue.issue_id] = flake_group
  return True


def _AddFlakeToGroupWithoutIssue(flake_groups_to_add_issue, flake, occurrences):
  basic_group_key = '{}@{}'.format(
      flake.luci_project,
      flake.GetTagValue('test_type') or flake.normalized_step_name)

  grouped = False
  for flake_group in flake_groups_to_add_issue[basic_group_key]:
    grouped = flake_group.AddFlakeIfBelong(flake, occurrences)
    if grouped:
      break

  if not grouped:
    flake_group = FlakeGroupByOccurrences(flake, occurrences)
    flake_groups_to_add_issue[basic_group_key].append(flake_group)


def GetFlakeGroupsForActionsOnBugs(flake_tuples_to_report):
  """Groups the flakes either by heuristic rules (if they linked to no issue)
    or by issue (if they have linked to an open issue).

  Args:
  flake_tuples_to_report: A list of tuples whose first element is a Flake
                          entity and second element is a list of corresponding
                          occurrences to report and the third element is
                          the linked FlakeIssue entity.

  Cases:
    1. Flake1 and Flake2 don't link to any FlakeIssue. They have the same
      luci_project and canonical_step_name, and they failed
      in the same builds, group them together in a FlakeGroupByOccurrence.
    2. Flake3 doesn't link to any FlakeIssue. It has the same
      luci_project, and canonical_step_name, but it failed
      in different builds from Flake1 and Flake2, make Flake3 in a different
      FlakeGroupByOccurrence.
    3. Flake4 doesn't link to any FlakeIssue. It failed in the same builds as
       Flake1 and Flake2 but it has different canonical_step_name, make Flake4
       in a different FlakeGroupByOccurrence.
    4. Flake5 and Flake6 link to the same FlakeIssue, and the issue is still
      open. Even though the flakes have different canonical_step_name, they are
      still in the same group of FlakeGroupByFlakeIssue.
    5. Flake7 and Flake8 link to the same FlakeIssue which is closed (
      not merged) within a week. Even though the flakes have different
      canonical_step_name, they are still in the same group of
      FlakeGroupByFlakeIssue.
    6. Flake9 and Flake10 link to the same FlakeIssue but it is closed over a
      week. So look for groups for each of them by their luci_project,
      canonical_step_name and failed builds separately.

  Returns:
     ([FlakeGroupByOccurrence], [FlakeGroupByFlakeIssue]): groups of flakes.
  """
  # Groups of flakes that need the same new bug.
  # Keyed by luci_project, canonical_step_name and test_suite_name.
  # Since we will group flakes only when they happen in the same builds,
  # it's possible to have different FlakeGroupByOccurrences with the same key,
  # so use a list to save them.
  flake_groups_to_add_issue = defaultdict(list)
  # Groups of flakes that are already linked to open issues.
  flake_groups_to_update_issue = {}

  for flake, occurrences, flake_issue in flake_tuples_to_report:
    if flake_issue:
      added_to_group = _AddFlakeToGroupWithIssue(
          flake_groups_to_update_issue, flake_issue, flake, occurrences)
      if added_to_group:
        continue

    # Group by heuristic for flakes not linked to any issue or the issue has
    # been closed.
    _AddFlakeToGroupWithoutIssue(flake_groups_to_add_issue, flake, occurrences)

  flake_groups_to_add_issue_list = []
  for heuristic_groups in flake_groups_to_add_issue.values():
    flake_groups_to_add_issue_list.extend(heuristic_groups)

  return flake_groups_to_add_issue_list, flake_groups_to_update_issue.values()


def GetRemainingPreAnalysisDailyBugUpdatesCount():
  """Returns how many FlakeIssue updates can be made by Flake Detection."""
  action_settings = waterfall_config.GetActionSettings()
  limit = action_settings.get('max_flake_detection_bug_updates_per_day',
                              flake_constants.DEFAULT_MAX_BUG_UPDATES_PER_DAY)

  utc_one_day_ago = time_util.GetUTCNow() - datetime.timedelta(days=1)
  num_updated_issues_24h = FlakeIssue.query(
      FlakeIssue.last_updated_time_by_flake_detection > utc_one_day_ago).count(
      )

  return limit - num_updated_issues_24h


def GetRemainingPostAnalysisDailyBugUpdatesCount():
  """Returns how many FlakeIssue updates can be made by Flake Analyzer."""
  action_settings = waterfall_config.GetActionSettings()
  limit = action_settings.get('max_flake_analysis_bug_updates_per_day',
                              flake_constants.DEFAULT_MAX_BUG_UPDATES_PER_DAY)

  utc_one_day_ago = time_util.GetUTCNow() - datetime.timedelta(days=1)
  num_updated_issues_24h = FlakeIssue.query(
      FlakeIssue.last_updated_time_with_analysis_results > utc_one_day_ago
  ).count()

  return limit - num_updated_issues_24h


# TODO(crbug.com/903459): Move ReportFlakesToMonorail and
#  ReportFlakesToFlakeAnalyzer to auto action layer.
def ReportFlakesToMonorail(flake_groups_to_add_issue,
                           flake_groups_to_update_issue):
  """Reports newly detected flakes and occurrences to Monorail.

  ONLY create or update a bug if:
    rule 1. Has NOT reached the maximum configured bug update limit within 24h.
    rule 2. The bug wasn't created or updated within the past 24h (has been
      fulfilled when getting flake groups).

  Args:
    flake_groups_to_add_issue([FlakeGroupByOccurrences]]): A list of flake
      groups that are not yet linked with a FlakeIssue.
    flake_groups_to_update_issue([FlakeGroupByFlakeIssue(list]): A list of
      flake groups that have been linked with a FlakeIssue.
  """
  total_remaining_issue_num = GetRemainingPreAnalysisDailyBugUpdatesCount()
  if total_remaining_issue_num <= 0:
    logging.info('Issues created or updated during the past 24 hours has '
                 'reached the limit, no issues could be created.')
    return

  # Fulfills the needs of creating bugs first, then updating bugs.
  num_of_issues_to_create = min(
      len(flake_groups_to_add_issue), total_remaining_issue_num)
  _CreateIssuesForFlakes(flake_groups_to_add_issue, num_of_issues_to_create)

  remaining_issue_num_update = (
      total_remaining_issue_num - num_of_issues_to_create)
  if remaining_issue_num_update <= 0:
    logging.info('Issues created or updated during the past 24 hours has '
                 'reached the limit, no issues could be updated.')
    return

  num_of_issues_to_update = min(
      len(flake_groups_to_update_issue), remaining_issue_num_update)
  _UpdateIssuesForFlakes(flake_groups_to_update_issue[:num_of_issues_to_update])


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
                            occurrences to report and the third element is
                            the linked FlakeIssue entity.
  """
  if not _IsReportFlakesToFlakeAnalyzerEnabled():
    logging.info('Skip reporting flakes to Flake Analyzer because the feature '
                 'is disabled.')
    return

  for flake, occurrences, flake_issue in flake_tuples_to_report:
    issue_id = flake_issue.issue_id if flake_issue else None
    for occurrence in occurrences:
      AnalyzeDetectedFlakeOccurrence(flake, occurrence, issue_id)


def _ArchiveFlakesForClosedIssue(flake_issue):
  """Archives flakes with closed issue.

  Flakes with closed issue should be archived since they are fixed or not
  actionable.
  """
  flakes = Flake.query(Flake.flake_issue_key == flake_issue.key).fetch()
  for flake in flakes:
    flake.archived = True
  ndb.put_multi(flakes)


# TODO(crbug.com/916278): Transactional
def _UpdateFlakeIssueWithMonorailIssue(flake_issue, monorail_issue):
  """Updates a FlakeIssue with its corresponding Monorail issue."""
  issue_id = flake_issue.issue_id
  monorail_project = flake_issue.monorail_project
  issue_link = FlakeIssue.GetLinkForIssue(monorail_project, issue_id)

  if not monorail_issue:
    # Possible reason: Findit doesn't have access to the monorail issue.
    return

  assert monorail_issue.status is not None, (
      'Failed to get issue.status from {}'.format(issue_link))
  assert monorail_issue.updated or monorail_issue.closed, (
      'Failed to get updated time from {}'.format(issue_link))

  if monorail_issue.status == 'Duplicate':
    # Impacted |merge_destination_key|s need to be updated.
    merged_monorail_issue = monorail_util.GetMergedDestinationIssueForId(
        issue_id, monorail_project)
    if not merged_monorail_issue.id:
      logging.warning('Failed to get merged monorail issue %s', issue_link)

    _UpdateMergeDestinationAndIssueLeaves(flake_issue, merged_monorail_issue)

  flake_issue.Update(
      status=monorail_issue.status,
      labels=monorail_issue.labels,
      last_updated_time_in_monorail=(monorail_issue.closed or
                                     monorail_issue.updated),
      create_time_in_monorail=monorail_issue.created)


def _GetOrCreateFlakeIssue(issue_id, monorail_project):
  """Gets or creates a FlakeIssue entity for the monorail issue.

  Args:
    issue_id (int): Id of the issue.
    monorail_project (str): Monorail project of the issue.
  Returns:
    (FlakeIssue): a FlakeIssue entity of the issue.
  """
  flake_issue = FlakeIssue.Get(monorail_project, issue_id)
  if flake_issue:
    return flake_issue

  flake_issue = FlakeIssue.Create(monorail_project, issue_id)
  flake_issue.put()
  monorail_issue = monorail_util.GetMonorailIssueForIssueId(
      issue_id, monorail_project)

  _UpdateFlakeIssueWithMonorailIssue(flake_issue, monorail_issue)
  return flake_issue


def _UpdateMergeDestinationAndIssueLeaves(flake_issue, merged_monorail_issue):
  """Updates flake_issue and all other issues that are merged into it to
    store the new merging_destination.

  Args:
    flake_issue (FlakeIssue): A FlakeIssue to update.
    merged_monorail_issue (Issue): The merged Monorail issue.
  """
  merged_flake_issue = _GetOrCreateFlakeIssue(
      int(merged_monorail_issue.id), flake_issue.monorail_project)
  assert merged_flake_issue, (
      'Failed to get or create FlakeIssue for merged_issue %s' %
      FlakeIssue.GetLinkForIssue(flake_issue.monorail_project,
                                 merged_flake_issue.id))

  merged_flake_issue_key = merged_flake_issue.key
  flake_issue.merge_destination_key = merged_flake_issue_key
  flake_issue.put()

  UpdateIssueLeaves(flake_issue.key, merged_flake_issue_key)


# TODO(crbug.com/916278): Update issue leaves in a transaction as multiple
# services may attempt to update at the same time.
def UpdateIssueLeaves(flake_issue_key, merged_flake_issue_key):
  """Updates all issues that were merged into flake_issue_key.

  Args:
    flake_issue_key (ndb.Key): The key to the FlakeIssue that is now obsolete.
    merged_flake_issue_key (ndb.Key): The key to the up-to-date FlakeIssue
      that should replace flake_issue_key.
  """
  if flake_issue_key == merged_flake_issue_key:  # pragma: no cover.
    # Same key, nothing to do.
    return

  issue_leaves = FlakeIssue.query(
      FlakeIssue.merge_destination_key == flake_issue_key).fetch()
  if not issue_leaves:
    return

  for issue_leaf in issue_leaves:
    issue_leaf.merge_destination_key = merged_flake_issue_key

  ndb.put_multi(issue_leaves)


def _CreateIssueForFlake(issue_generator, target_flake, create_or_update_bug):
  """Creates a monorail bug for a single flake.

  This function is used to create bugs for detected flakes and flake analysis
  results.

  Args:
    create_or_update_bug (bool): True to create or update monorail bug,
      otherwise False. Should always look for existing bugs for flakes, even if
      cannot update the bug.
  """
  monorail_project = issue_generator.GetMonorailProject()

  # Re-uses an existing open bug if possible.
  issue_id = SearchOpenIssueIdForFlakyTest(target_flake.normalized_test_name,
                                           monorail_project)

  if not issue_id:
    # Reopens a recently closed bug if possible.
    issue_id = SearchRecentlyClosedIssueIdForFlakyTest(
        target_flake.normalized_test_name, monorail_project)

  if issue_id:
    logging.info('An existing issue %s was found, attach it to flake: %s.',
                 FlakeIssue.GetLinkForIssue(monorail_project, issue_id),
                 target_flake.key)
    _AssignIssueToFlake(issue_id, target_flake)

    if create_or_update_bug:
      monorail_util.UpdateIssueWithIssueGenerator(
          issue_id=issue_id, issue_generator=issue_generator, reopen=True)
    return issue_id

  if not create_or_update_bug:
    # No existing bug found, and cannot create bug, bail out.
    return None

  logging.info('No existing open issue was found, create a new one.')
  issue_id = monorail_util.CreateIssueWithIssueGenerator(
      issue_generator=issue_generator)

  if not issue_id:
    logging.warning('Failed to create monorail bug for flake: %s.',
                    target_flake.key)
    return None
  logging.info('%s was created for flake: %s.',
               FlakeIssue.GetLinkForIssue(monorail_project, issue_id),
               target_flake.key)
  _AssignIssueToFlake(issue_id, target_flake)
  return issue_id


def _CreateIssueForFlakeGroup(flake_group):
  """Creates an issue for a flake group.

  Args:
    flake_group (FlakeGroupByOccurrences): A flake group without an issue.

  Returns:
    Id of the issue that was eventually created or linked.
  """

  assert isinstance(flake_group, FlakeGroupByOccurrences), (
      'flake_group is not a FlakeGroupByOccurrences instance.')

  issue_generator = FlakeDetectionGroupIssueGenerator(
      flake_group.flakes,
      flake_group.num_occurrences,
      canonical_step_name=flake_group.canonical_step_name)
  issue_id = monorail_util.CreateIssueWithIssueGenerator(
      issue_generator=issue_generator)
  if not issue_id:
    logging.warning('Failed to create monorail bug for flake group: %s.',
                    flake_group.canonical_step_name)
    return None
  logging.info(
      '%s was created for flake_group: %s.',
      FlakeIssue.GetLinkForIssue(issue_generator.GetMonorailProject(),
                                 issue_id), flake_group.canonical_step_name)

  flake_issue = _AssignIssueToFlake(issue_id, flake_group.flakes[0])
  for i in xrange(1, len(flake_group.flakes)):
    flake = flake_group.flakes[i]
    flake.flake_issue_key = flake_issue.key
    flake.put()

  issue_generator.SetFlakeIssue(flake_issue)

  monorail_util.PostCommentOnMonorailBug(
      issue_id, issue_generator,
      issue_generator.GetFirstCommentWhenBugJustCreated())

  return issue_id


def _CreateIssuesForFlakes(flake_groups_to_create_issue,
                           num_of_issues_to_create):
  """Creates monorail bugs.

  Args:
    flake_groups_to_create_issue([FlakeGroupByOccurrences]]): A list of flake
      groups that are not yet linked with a FlakeIssue.
    num_of_issues_to_create(int): Total number for
      - New bugs created
      - Existing bugs found, linked to flakes and then updated.
      Note that it's possible that more bugs are found and linked to flakes, but
      will not be updated because of the limit.
  """
  for flake_group in flake_groups_to_create_issue:
    try:
      if len(flake_group.flakes) == 1:
        # A single flake in group, uses this flake's info to look for or create
        # a bug. If num_of_issues_to_create has reached 0, only looks for
        # existing monorail bug for it.
        issue_generator = FlakeDetectionIssueGenerator(
            flake_group.flakes[0], flake_group.num_occurrences)
        issue_id = _CreateIssueForFlake(
            issue_generator,
            flake_group.flakes[0],
            create_or_update_bug=num_of_issues_to_create > 0)
      elif num_of_issues_to_create > 0:
        # Multiple flakes in group, only creates a bug when the bug count has
        # not reached the limit.
        issue_id = _CreateIssueForFlakeGroup(flake_group)
      else:
        # Multiple flakes in group, and no more bug is allowed.
        issue_id = None

      if issue_id and num_of_issues_to_create > 0:
        # A monorail bug has been created or updated.
        num_of_issues_to_create -= 1

        # Updates FlakeIssue's last updated_time_by_flake_detection property.
        # This property is only applicable to Flake Detection because Flake
        # Detection can update an issue at most once every 24 hours.
        # Also change last_updated_time_in_monorail to keep in sync.
        flake_issue = GetFlakeIssue(flake_group.flakes[0])
        flake_issue.last_updated_time_by_flake_detection = time_util.GetUTCNow()
        flake_issue.last_updated_time_in_monorail = time_util.GetUTCNow()
        flake_issue.put()

    except HttpError as error:
      # Benign exceptions (HttpError 403) may happen when FindIt tries to
      # update an issue that it doesn't have permission to. Do not raise
      # exception so that the for loop can move on to create or update next
      # issues.
      logging.warning('Failed to create or update issue due to error: %s',
                      error)


def _UpdateFlakeIssueForFlakeGroup(flake_group):
  """Updates an issue for a flake group.

  Args:
    flake_group (FlakeGroupByFlakeIssue): A flake group with an issue.

  Returns:
    Id of the issue that was eventually created or linked.
  """
  assert isinstance(flake_group, FlakeGroupByFlakeIssue), (
      'flake_group is not a FlakeGroupByFlakeIssue instance.')
  issue_generator = FlakeDetectionGroupIssueGenerator(
      flake_group.flakes,
      flake_group.num_occurrences,
      flake_issue=flake_group.flake_issue,
      flakes_with_same_occurrences=flake_group.flakes_with_same_occurrences)

  flake_issue = flake_group.flake_issue
  monorail_util.UpdateIssueWithIssueGenerator(
      issue_id=flake_issue.issue_id,
      issue_generator=issue_generator,
      reopen=True)
  return flake_issue.issue_id


def _UpdateIssuesForFlakes(flake_groups_to_update_issue):
  """Updates monorail bugs.

  The issues have been updated when generating flake groups, so in this function
  directly updates the issues.

  Args:
    flake_groups_to_update_issue ([FlakeGroupByFlakeIssue]): A list of flake
      groups with bugs.
  """
  for flake_group in flake_groups_to_update_issue:
    try:
      if len(flake_group.flakes) == 1:
        # A single flake in group, updates the bug using this flake's info.
        issue_generator = FlakeDetectionIssueGenerator(
            flake_group.flakes[0], flake_group.num_occurrences)
        issue_generator.SetPreviousTrackingBugId(flake_group.previous_issue_id)
        monorail_util.UpdateIssueWithIssueGenerator(
            issue_id=flake_group.flake_issue.issue_id,
            issue_generator=issue_generator,
            reopen=True)
      else:
        _UpdateFlakeIssueForFlakeGroup(flake_group)
      # Update FlakeIssue's last_updated_time_by_flake_detection property. This
      # property is only applicable to Flake Detection because Flake Detection
      # can update an issue at most once every 24 hours.
      flake_issue = flake_group.flake_issue
      flake_issue.last_updated_time_by_flake_detection = time_util.GetUTCNow()
      flake_issue.last_updated_time_in_monorail = time_util.GetUTCNow()
      flake_issue.put()
    except HttpError as error:
      # Benign exceptions (HttpError 403) may happen when FindIt tries to
      # update an issue that it doesn't have permission to. Do not raise
      # exception so that the for loop can move on to create or update next
      # issues.
      logging.warning('Failed to create or update issue due to error: %s',
                      error)


def _AssignIssueToFlake(issue_id, flake):
  """Assigns an issue id to a flake, and created a FlakeIssue if necessary.

  Args:
    issue_id: Id of a Monorail issue.
    flake: A Flake Model entity.
  """
  assert flake, 'The flake entity cannot be None.'

  monorail_project = FlakeIssue.GetMonorailProjectFromLuciProject(
      flake.luci_project)
  flake_issue = _GetOrCreateFlakeIssue(issue_id, monorail_project)
  flake.flake_issue_key = flake_issue.key
  flake.put()
  return flake_issue


def _GetIssueStatusesNeedingUpdating():
  """Returns a list of statuses to check for that might need updating.

    Issues that have been closed are assumed not to need further updates to
    prevent the number of FlakeIssues needing updates to increase monotonically.
  """
  statuses = [None]
  statuses.extend(issue_constants.OPEN_STATUSES)
  return statuses


def _GetFlakeIssuesNeedingUpdating():
  """Returns a list of all FlakeIssue entities needing updating."""
  issue_statuses_needing_updates = _GetIssueStatusesNeedingUpdating()
  # Query and update issues by oldest first that's still open in case there are
  # exceptions when trying to update issues.
  flake_issues_query = FlakeIssue.query().filter(
      FlakeIssue.status.IN(issue_statuses_needing_updates)).order(
          FlakeIssue.last_updated_time_in_monorail, FlakeIssue.key)

  flake_issues_needing_updating = []
  cursor = None
  more = True

  while more:
    flake_issues, cursor, more = flake_issues_query.fetch_page(
        _PAGE_SIZE, start_cursor=cursor)
    flake_issues_needing_updating.extend(flake_issues)

  return flake_issues_needing_updating


def SyncOpenFlakeIssuesWithMonorail():
  """Updates open FlakeIssues to reflect the latest state in Monorail."""
  flake_issues_needing_updating = _GetFlakeIssuesNeedingUpdating()

  for flake_issue in flake_issues_needing_updating:
    issue_id = flake_issue.issue_id
    monorail_project = flake_issue.monorail_project

    # TODO(crbug.com/914160): Monorail has a maximum of 300 requests per minute
    # within any 5 minute window. Should the limit be exceeded, requests will
    # result in 4xx errors and exponential backoff should be used.
    monorail_issue = monorail_util.GetMonorailIssueForIssueId(
        issue_id, monorail_project)
    if (not monorail_issue or monorail_issue.id is None or
        int(monorail_issue.id) != issue_id):  # pragma: no cover
      # No cover due to being unexpected, but log a warning regardless and skip.
      link = FlakeIssue.GetLinkForIssue(monorail_project, issue_id)
      logging.warning('Failed to get issue %s', link)
      continue

    _UpdateFlakeIssueWithMonorailIssue(flake_issue, monorail_issue)

    if monorail_issue.status in issue_constants.CLOSED_STATUSES_NO_DUPLICATE:
      # Issue is closed, detaches it from flakes.
      _ArchiveFlakesForClosedIssue(flake_issue)


def IsFlakeIssueActionable(flake_issue):
  """Checks if the flake_issue is actionable.

  If the issue has been closed on monorail over 7 days, the flake_issue is not
  actionable.
  """
  is_bug_stale = (
      flake_issue.status in issue_constants.CLOSED_STATUSES_NO_DUPLICATE and
      flake_issue.last_updated_time_in_monorail and
      flake_issue.last_updated_time_in_monorail <
      time_util.GetDateDaysBeforeNow(days=7))

  if is_bug_stale:
    logging.info(
        'Flake issue %d has been closed over 7 days, don\'t take action on it.',
        flake_issue.issue_id)
    return False
  return True
