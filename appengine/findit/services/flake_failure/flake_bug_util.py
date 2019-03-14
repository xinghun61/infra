# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Utilities to determining whether to log/update bugs."""
from libs import time_util
from model.flake.analysis import master_flake_analysis
from services import flake_issue_util
from services import monitoring
from services import monorail_util
from services.flake_failure import flake_constants
from waterfall import waterfall_config

# TODO(crbug.com/903451): Deprecate this entire module when switch to auto
# action layer is ready.


def ShouldFileBugForAnalysis(analysis):
  """Returns true if a bug should be filed for this analysis.

  The requirements for a bug to be filed.
    - The bug creation feature if enabled.
    - The pipeline hasn't been attempted before (see above).
    - The analysis has sufficient confidence (1.0).
    - The analysis doesn't already have a bug associated with it.
    - A duplicate bug hasn't been filed by Findit or CTF.
    - A duplicate bug hasn't been filed by a human.
  """
  if not UnderDailyLimit():
    analysis.LogInfo('Reached bug filing limit for the day.')
    return False

  if HasPreviousAttempt(analysis):
    analysis.LogWarning(
        'There has already been an attempt at filing a bug, aborting.')
    return False

  if not HasSufficientConfidenceInCulprit(
      analysis, GetMinimumConfidenceToUpdateEndpoints()):
    analysis.LogInfo('''Analysis has confidence {:.2%}
        which isn\'t high enough to file a bug.'''.format(
        analysis.confidence_in_culprit))
    return False

  # Check if there's already a bug attached to this issue.
  if analysis.bug_id and monorail_util.OpenBugAlreadyExistsForId(
      analysis.bug_id):
    analysis.LogInfo('Bug with id {} already exists.'.format(analysis.bug_id))
    return False

  if flake_issue_util.OpenIssueAlreadyExistsForFlakyTest(analysis.test_name):
    analysis.LogInfo('Bug already exists for flaky test: {}'.format(
        analysis.test_name))
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

  if (analysis.culprit_urlsafe_key and not HasSufficientConfidenceInCulprit(
      analysis, GetMinimumConfidenceToUpdateEndpoints())):
    # There is a culprit, but insufficient confidence.
    monitoring.OnFlakeCulprit('culprit-identified', 'none',
                              'insufficient-confidence')
    return False

  # TODO(crbug.com/847960): Do not update bugs if Findit already logged one as
  # the information would be redundant.
  return True


def UnderDailyLimit():
  # TODO(crbug.com/942222): Distinguish between Flake Analyzer and Flake
  # Detection bug operations.
  action_settings = waterfall_config.GetActionSettings()
  daily_bug_limit = action_settings.get(
      'max_flake_detection_bug_updates_per_day',
      flake_constants.DEFAULT_MAX_BUG_UPDATES_PER_DAY)
  query = master_flake_analysis.MasterFlakeAnalysis.query(
      master_flake_analysis.MasterFlakeAnalysis.request_time >= time_util
      .GetMostRecentUTCMidnight())
  bugs_filed_today = 0

  more = True
  cursor = None
  while more:
    results, cursor, more = query.fetch_page(100, start_cursor=cursor)
    for result in results:
      if result.has_attempted_filing and result.bug_id:
        bugs_filed_today += 1

  return bugs_filed_today < daily_bug_limit


def HasSufficientConfidenceInCulprit(analysis, required_confidence):
  """Returns true is there's high enough confidence in the culprit."""
  if not analysis.confidence_in_culprit:
    return False

  return (analysis.confidence_in_culprit + flake_constants.EPSILON >=
          required_confidence)


def GetMinimumConfidenceToUpdateEndpoints():
  return waterfall_config.GetActionSettings().get(
      'minimum_confidence_to_update_endpoints',
      flake_constants.DEFAULT_MINIMUM_CONFIDENCE_SCORE_TO_UPDATE_ENDPOINTS)


def HasPreviousAttempt(analysis):
  """Returns True if an analysis has already attempted to file a bug."""
  return analysis.has_attempted_filing
