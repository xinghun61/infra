# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from collections import defaultdict
import datetime
import logging
import textwrap

from google.appengine.ext import ndb

from gae_libs.appengine_util import IsStaging
from googleapiclient.errors import HttpError
from libs import time_util
from model.flake.detection.flake import Flake
from model.flake.detection.flake_occurrence import (
    CQFalseRejectionFlakeOccurrence)
from model.flake.detection.flake_issue import FlakeIssue
from services import issue_tracking_service
from services import monitoring

# Maximum number of Monorail issues allowed to be created or updated in any 24h
# window.
_CREATE_OR_UPDATE_ISSUES_LIMIT_24H = 30

# Minimum number of occurrences of a flaky test that are associated with
# different CLs within the past 24h are required in order to report the flake.
# Note that it has to be x different CLs, different patchsets of the same CL are
# only counted once, and the reason is to filter out flaky tests that are caused
# by a specific uncommitted CL.
_MIN_REQUIRED_FALSELY_REJECTED_CLS_24H = 3

# Length of window to tell if a flake is still active. The main use cause is to
# filter out flakes that were fixed and is no longer active anymore.
_ACTIVE_FLAKE_WINDOW_HOURS = 6

# Flake detection bug templates.
_FLAKE_DETECTION_BUG_DESCRIPTION = textwrap.dedent("""
{test_target}: {test_name} is flaky.

Findit has detected {num_occurrences} flake occurrences of this test within the
past 24 hours. List of all flake occurrences can be found at:
{flake_url}.

Unless the culprit CL is found and reverted, please disable this test first
within 30 minutes then find an appropriate owner.
{previous_tracking_bug_text}
{footer}""")

_FLAKE_DETECTION_BUG_COMMENT = textwrap.dedent("""
Findit has detected {num_occurrences} new flake occurrences of this test. List
of all flake occurrences can be found at:
{flake_url}.

Since this test is still flaky, this issue has been moved back onto the Sheriff
Bug Queue if it's not already there.
{previous_tracking_bug_text}
{footer}""")

_FLAKE_DETECTION_PREVIOUS_TRACKING_BUG = (
    '\nThis flaky test was previously tracked in bug {}.\n')

_FLAKE_DETECTION_FOOTER_TEMPLATE = textwrap.dedent(
    """If the result above is wrong, please file a bug using this link:
{wrong_results_bug_link}

Automatically posted by the findit-for-me app (https://goo.gl/Ot9f7N).""")

_FLAKE_DETECTION_WRONG_RESULTS_BUG_LINK = (
    'https://bugs.chromium.org/p/chromium/issues/entry?'
    'status=Unconfirmed&labels=Pri-1,Test-Findit-Wrong&'
    'components=Tools%3ETest%3EFindit%3EFlakiness&'
    'summary=%5BFindit%5D%20Flake%20Detection%20-%20Wrong%20result%20for%20{}&'
    'comment=Link%20to%20flake%20occurrences%3A%20{}')

_FLAKE_DETECTION_LABEL_TEXT = 'Test-Findit-Detected'


class FlakeDetectionIssueGenerator(
    issue_tracking_service.FlakyTestIssueGenerator):
  """Encapsulates the details of issues filed by Flake Detection."""

  def __init__(self, flake, num_occurrences):
    super(FlakeDetectionIssueGenerator, self).__init__()
    self._flake = flake
    self._num_occurrences = num_occurrences

  def GetStepName(self):
    return self._flake.normalized_step_name

  def GetTestName(self):
    return self._flake.normalized_test_name

  def GetMonorailProject(self):
    return FlakeIssue.GetMonorailProjectFromLuciProject(
        self._flake.luci_project)

  def GetDescription(self):
    previous_tracking_bug_id = self.GetPreviousTrackingBugId()
    previous_tracking_bug_text = _FLAKE_DETECTION_PREVIOUS_TRACKING_BUG.format(
        previous_tracking_bug_id) if previous_tracking_bug_id else ''
    description = _FLAKE_DETECTION_BUG_DESCRIPTION.format(
        test_target=self._flake.normalized_step_name,
        test_name=self._flake.normalized_test_name,
        num_occurrences=self._num_occurrences,
        flake_url=self._GetLinkForFlake(),
        previous_tracking_bug_text=previous_tracking_bug_text,
        footer=self._GetFooter())

    return description

  def GetComment(self):
    previous_tracking_bug_id = self.GetPreviousTrackingBugId()
    previous_tracking_bug_text = _FLAKE_DETECTION_PREVIOUS_TRACKING_BUG.format(
        previous_tracking_bug_id) if previous_tracking_bug_id else ''

    comment = _FLAKE_DETECTION_BUG_COMMENT.format(
        num_occurrences=self._num_occurrences,
        flake_url=self._GetLinkForFlake(),
        previous_tracking_bug_text=previous_tracking_bug_text,
        footer=self._GetFooter())

    return comment

  def ShouldRestoreChromiumSheriffLabel(self):
    # Flake Detection always requires Chromium Sheriff's attentions to disable
    # flaky tests when new occurrences are detected.
    return True

  def GetLabels(self):
    flaky_test_labels = self._GetCommonFlakyTestLabel()
    flaky_test_labels.append(_FLAKE_DETECTION_LABEL_TEXT)
    return flaky_test_labels

  def OnIssueCreated(self):
    monitoring.OnFlakeDetectionCreateOrUpdateIssues('create')

  def OnIssueUpdated(self):
    monitoring.OnFlakeDetectionCreateOrUpdateIssues('updated')

  def _GetLinkForFlake(self):
    """Given a flake, gets a link to the flake on flake detection UI.

    Returns:
      A link to the flake on flake detection UI.
    """
    url_template = ('https://findit-for-me%s.appspot.com/flake/detection/'
                    'show-flake?key=%s')
    suffix = '-staging' if IsStaging() else ''
    return url_template % (suffix, self._flake.key.urlsafe())

  def _GetFooter(self):
    """Gets the footer for the bug description of comment.

    Returns:
      A string representing footer.
    """
    wrong_results_bug_link = _FLAKE_DETECTION_WRONG_RESULTS_BUG_LINK.format(
        self._flake.normalized_test_name, self._GetLinkForFlake())
    return _FLAKE_DETECTION_FOOTER_TEMPLATE.format(
        wrong_results_bug_link=wrong_results_bug_link)


def _FlakeIssueWasCreatedOrUpdatedWithinPast24h(flake):
  """Returns True if the flake issue was created or updated within the past 24h.

  Args:
    flake: A Flake Model entity.

  Returns:
    A boolean value indicates whether the issue was create or updated within the
    past 24 hours.
  """
  flake_issue = _GetFlakeIssue(flake)
  if not flake_issue:
    return False

  utc_one_day_ago = time_util.GetUTCNow() - datetime.timedelta(days=1)
  return flake_issue.last_updated_time > utc_one_day_ago


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

  A flake has enough occurrences if:
    rule 1. The occurrences cover at least 3 different CLs.
    rule 2. At least 1 occurrence is still active.

  Args:
    unreported_occurrences: A list of occurrence that share the same parent
                            flake and haven't been reported yet.
                            The caller is responsible for making sure of it.
  """
  cl_ids = [occurrence.gerrit_cl_id for occurrence in unreported_occurrences]
  unique_cl_ids = set(cl_ids)
  if len(unique_cl_ids) < _MIN_REQUIRED_FALSELY_REJECTED_CLS_24H:
    return False

  active_window_boundary = time_util.GetUTCNow() - datetime.timedelta(
      hours=_ACTIVE_FLAKE_WINDOW_HOURS)
  for occurrence in unreported_occurrences:
    if occurrence.time_happened > active_window_boundary:
      return True

  return False


def _GetFlakesWithEnoughOccurrences():
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
    a list of corresponding recent and unreported occurrences.
  """
  utc_one_day_ago = time_util.GetUTCNow() - datetime.timedelta(days=1)
  occurrences = CQFalseRejectionFlakeOccurrence.query(
      CQFalseRejectionFlakeOccurrence.time_happened > utc_one_day_ago).fetch()

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
    last_updated_time = flake_issue.last_updated_time if flake_issue else None

    new_occurrences = [
        occurrence for occurrence in occurrences
        if not last_updated_time or occurrence.time_detected > last_updated_time
    ]
    if new_occurrences:
      flake_key_to_unreported_occurrences[flake_key] = new_occurrences

  # Set to None to avoid being mistakenly used in following code.
  flake_key_to_occurrences = None

  flakes_with_enough_occurrences = [
      flake for flake in flakes
      if flake.key in flake_key_to_unreported_occurrences and
      _FlakeHasEnoughOccurrences(flake_key_to_unreported_occurrences[flake.key])
  ]

  # Cannot use a dictionary because Model is not immutable.
  flake_and_occurrences_tuples = []
  for flake in flakes_with_enough_occurrences:
    flake_and_occurrences_tuples.append(
        (flake, flake_key_to_unreported_occurrences[flake.key]))

  return flake_and_occurrences_tuples


def GetFlakesNeedToReportToMonorail():
  """Creates or updates bugs for detected flakes.

  ONLY create or update a bug if:
    rule 1. Has NOT reached _CREATE_OR_UPDATE_ISSUES_LIMIT_24H.
    rule 2. The bug wasn't created or updated within the past 24h.

  Returns:
    A list of tuples whose first element is a flake entity and second element is
    a list of corresponding recent and unreported occurrences.
  """
  utc_one_day_ago = time_util.GetUTCNow() - datetime.timedelta(days=1)
  num_updated_issues_24h = FlakeIssue.query(
      FlakeIssue.last_updated_time > utc_one_day_ago).count()
  if num_updated_issues_24h >= _CREATE_OR_UPDATE_ISSUES_LIMIT_24H:
    logging.info('Issues created or updated during the past 24 hours has '
                 'reached the limit.')

  flake_tuples = _GetFlakesWithEnoughOccurrences()

  # An issue can be updated at most once in any 24h window avoid noises.
  flake_tuples_to_report = [
      flake_tuple for flake_tuple in flake_tuples
      if not _FlakeIssueWasCreatedOrUpdatedWithinPast24h(flake_tuple[0])
  ]

  flake_tuples_to_report = flake_tuples_to_report[:min(
      len(flake_tuples), _CREATE_OR_UPDATE_ISSUES_LIMIT_24H -
      num_updated_issues_24h)]
  logging.info('There are %d flakes whose issues will be created or updated.' %
               len(flake_tuples_to_report))

  return flake_tuples_to_report


def ReportFlakesToMonorail(flake_tuples_to_report):
  """Reports newly detected flakes and occurrences to Monorail.

  Args:
    flake_tuples_to_report: A list of tuples whose first element is a Flake
                            entity and second element is a list of corresponding
                            occurrences to report.
  """
  for flake, occurrences in flake_tuples_to_report:
    issue_generator = FlakeDetectionIssueGenerator(flake, len(occurrences))
    try:
      issue_tracking_service.UpdateIssueIfExistsOrCreate(
          issue_generator, flake.luci_project)

      # Update FlakeIssue's last_updated_time property. This property is only
      # applicable to Flake Detection because Flake Detection can update an
      # issue at most once every 24 hours.
      flake_issue = flake.flake_issue_key.get()
      flake_issue.last_updated_time = time_util.GetUTCNow()
      flake_issue.put()
    except HttpError as error:
      # benign exceptions (HttpError 403) may happen when FindIt tries to
      # update an issue that it doesn't have permission to. Do not raise
      # exception so that the for loop can move on to create or update next
      # issues.
      logging.error('Failed to create or update issue due to error: %s', error)
