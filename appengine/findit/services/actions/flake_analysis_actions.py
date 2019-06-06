# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Actions to be performed after a flake analysis has completed."""

import logging

from google.appengine.ext import ndb

from common import monitoring
from googleapiclient.errors import HttpError
from libs import time_util
from model import entity_util
from model.flake.flake_issue import FlakeIssue
from services import flake_issue_util
from services import issue_generator
from services import monorail_util
from services.flake_failure import flake_bug_util


def _GetMostUpdatedCulpritFlakeIssue(flake_culprit):
  if not flake_culprit.flake_issue_key:
    return None

  culprit_flake_issue = flake_culprit.flake_issue_key.get()
  assert culprit_flake_issue, (
      'Culprit FlakeIssue {} missing unexpectedly!'.format(
          flake_culprit.flake_issue_key))
  return culprit_flake_issue.GetMostUpdatedIssue()


# pylint: disable=E1120
@ndb.transactional(xg=True)
def _AttachCulpritFlakeIssueToFlake(flake, flake_culprit_key):
  """Attaches culprit flake issue to flake and returns the flake_issue's key."""
  if not flake or not flake_culprit_key:
    return None

  flake_culprit = flake_culprit_key.get()
  assert flake_culprit, 'FlakeCulprit {} missing unexpectedly!'.format(
      flake_culprit_key)

  culprit_flake_issue = _GetMostUpdatedCulpritFlakeIssue(flake_culprit)
  if not culprit_flake_issue:
    return None

  flake.flake_issue_key = culprit_flake_issue.key
  flake.put()
  return culprit_flake_issue.key


def _MergeFlakeIssuesAndUpdateMonorail(culprit, culprit_flake_issue,
                                       flake_issue):
  """Merges flake issues and updates the corresponding issue ids on Monorail.

    This function should never be used outside the context of a cross-group
    transaction between flake issues and flake culprits.

  Args:
    culprit (FlakeCulprit): The culprit whose commit position will be used for
      generating the update comment in Monorail.
    culprit_flake_issue (FlakeIssue): The flake issue to be merged or merged
      into already associated with culprit.
    flake_issue (FlakeIssue): The flake issue to be merged or merged into
      not yet associated with a culprit.

  Returns:
    (flake_issue_key, flake_issue_key): The key of the flake issue that was
      merged and the key of the flake issue it was merged into.
  """
  assert ndb.in_transaction(), (
      '_MergeFlakeIssues should only be called from within a transaction')
  culprit_monorail_issue = monorail_util.GetMonorailIssueForIssueId(
      culprit_flake_issue.issue_id)
  flake_monorail_issue = monorail_util.GetMonorailIssueForIssueId(
      flake_issue.issue_id)
  if not culprit_monorail_issue or not flake_monorail_issue:
    logging.info('Not merge flake issues due to no sufficient info on %d or %d',
                 culprit_flake_issue.issue_id, flake_issue.issue_id)
    return None, None

  if (monorail_util.WasCreatedByFindit(culprit_monorail_issue) and
      not monorail_util.WasCreatedByFindit(flake_monorail_issue)):
    # If the flake's Monorail bug was created by a human while the bug already
    # associated with the culprit is that of Findit, merge into the human-
    # created bug.
    duplicate_monorail_issue = culprit_monorail_issue
    destination_monorail_issue = flake_monorail_issue
    duplicate_flake_issue = culprit_flake_issue
    destination_flake_issue = flake_issue
  else:
    # In all other cases (both created by humans or both created by Findit,
    # etc.), merge into the culprit's bug (first-come-first-serve).
    duplicate_monorail_issue = flake_monorail_issue
    destination_monorail_issue = culprit_monorail_issue
    duplicate_flake_issue = flake_issue
    destination_flake_issue = culprit_flake_issue

  assert duplicate_flake_issue.key != destination_flake_issue.key, (
      'Merging FlakeIssue into itself! {}'.format(duplicate_flake_issue.key))

  # Include a comment for why the merge is taking place.
  comment = issue_generator.GenerateDuplicateComment(culprit.commit_position)

  # Merge in Monorail.
  try:
    monorail_util.MergeDuplicateIssues(duplicate_monorail_issue,
                                       destination_monorail_issue, comment)
  except HttpError as error:  # pragma: no cover. This is unexpected.
    # Raise an exception to abort any merging of data on Findit side, as this
    # can lead to some inconsistent states between FlakeIssue and Monorail.
    logging.error('Could not merge %s into %s Monorail',
                  duplicate_monorail_issue.id, destination_monorail_issue.id)
    raise error

  # Update the merged flake issue to point to the culprit if not already.
  if (destination_flake_issue.flake_culprit_key !=
      culprit.key):  # pragma: no branch
    destination_flake_issue.flake_culprit_key = culprit.key
    destination_flake_issue.put()

  # Update the duplicate's merge_destination_key to the merged flake issue.
  duplicate_flake_issue.merge_destination_key = destination_flake_issue.key
  duplicate_flake_issue.put()

  return duplicate_flake_issue.key, destination_flake_issue.key


# pylint: disable=E1120
@ndb.transactional(xg=True)
def MergeOrSplitFlakeIssueByCulprit(flake_issue_key, flake_culprit_key):
  """Associate FlakeCulprit with FlakeIssue and provided by MasterFlakeAnalysis.

    If flake_issue and/or culprit_flake_issue has been closed over a week, no
    merge needed.

    The end result of this method should include:
    1. FlakeCulprit's |flake_issue_key| before and after should not change.
    2. Flakeculprit's FlakeIssue.GetMostUpdatedIssue() should be the latest
       FlakeIssue.
    2. The FlakeIssue that gets merged will have the most up-to-date
       |merge_destination_key|.
    3. Obsolete FlakeIssues not involved in this method may have obsolete
       |merge_destination_key|s will still be obsolete, and the return value of
       this function should indicate a refresh is needed.

  Args:
    flake_issue_key (ndb.Key): The key to the FlakeIssue to be associated with
      the corresponding FlakeCulprit.
    flake_culprit_key (ndb.Key): The key to the flake culprit identified after
      analysis.

  Returns:
    (flake_issue_key, flake_issue_key): The key of the flake issue that was
      merged and the key of the flake issue it was merged into. Returns
      (None, None) if no merge took place.
  """
  flake_issue = flake_issue_key.get()
  assert flake_issue, 'FlakeIssue {} missing unexpectedly!'.format(
      flake_issue_key)

  # At this stage, flake_issue may already have been merged as the result of
  # another analysis, or manually in Monorail. These are expected to be rare
  # as the window of opportunity for this to occur is small.
  flake_issue = flake_issue.GetMostUpdatedIssue()

  if not flake_issue_util.IsFlakeIssueActionable(flake_issue):
    return None, None

  flake_culprit = flake_culprit_key.get()
  assert flake_culprit, 'FlakeCulprit {} missing unexpectedly!'.format(
      flake_culprit_key)

  most_updated_culprit_flake_issue = _GetMostUpdatedCulpritFlakeIssue(
      flake_culprit)
  if (most_updated_culprit_flake_issue and
      flake_issue_util.IsFlakeIssueActionable(most_updated_culprit_flake_issue)
      and most_updated_culprit_flake_issue.key != flake_issue.key):
    # The culprit already has an open/newly closed FlakeIssue so one should
    # merge into the other. The calling code should then perform any syncing
    # with impacted FlakeIssue |merge_destination_key|s.
    return _MergeFlakeIssuesAndUpdateMonorail(
        flake_culprit, most_updated_culprit_flake_issue, flake_issue)

  if (flake_issue.flake_culprit_key and
      flake_issue.flake_culprit_key != flake_culprit.key):  # pragma: no cover.
    # TODO(crbug.com/907313) flake_issue has a different culprit associated.
    # Create a new FlakeIssue for the new culprit. Remove no cover when
    # implemented.
    return None, None

  # FlakeCulprit either doesn't have a flake_issue_key or has one that's closed.
  # Update it and the incoming FlakeIssue to point to each other for subsequent
  # analyses to deduplicate.
  flake_culprit.flake_issue_key = flake_issue.key
  flake_issue.flake_culprit_key = flake_culprit.key
  flake_issue.put()
  flake_culprit.put()
  return None, None


def UpdateMonorailBugWithCulprit(analysis_urlsafe_key):
  """Updates a bug in monorail with the culprit of a MasterFlakeAnalsyis"""
  analysis = entity_util.GetEntityFromUrlsafeKey(analysis_urlsafe_key)
  assert analysis, 'Analysis {} missing unexpectedly!'.format(
      analysis_urlsafe_key)

  if not analysis.flake_key:  # pragma: no cover.
    logging.warning(
        'Analysis %s has no flake key. Bug updates should only be '
        'routed through Flake and FlakeIssue', analysis_urlsafe_key)
    return

  flake = analysis.flake_key.get()
  assert flake, 'Analysis\' associated Flake {} missing unexpectedly!'.format(
      analysis.flake_key)

  flake_urlsafe_key = flake.key.urlsafe()
  if flake.archived:
    logging.info('Flake %s has been archived when flake analysis %s completes.',
                 flake_urlsafe_key, analysis_urlsafe_key)
    return

  if not flake.flake_issue_key:  # pragma: no cover.
    logging.warning(
        'Flake %s has no flake_issue_key. Bug updates should only'
        ' be routed through Flake and FlakeIssue', flake_urlsafe_key)
    return

  flake_issue = flake.flake_issue_key.get()
  assert flake_issue, 'Flake issue {} missing unexpectedly!'.format(
      flake.flake_issue_key)

  # Only comment on the latest flake issue.
  flake_issue_to_update = flake_issue.GetMostUpdatedIssue()
  issue_link = FlakeIssue.GetLinkForIssue(
      flake_issue_to_update.monorail_project, flake_issue_to_update.issue_id)

  # Don't comment if the issue is closed.
  latest_merged_monorail_issue = monorail_util.GetMonorailIssueForIssueId(
      flake_issue_to_update.issue_id)
  if not latest_merged_monorail_issue or not latest_merged_monorail_issue.open:
    logging.info('Skipping updating issue %s which is not accessible or closed',
                 issue_link)
    return

  # Don't comment if there are existing updates by Findit to prevent spamming.
  if flake_issue_to_update.last_updated_time_with_analysis_results:
    logging.info('Skipping updating issue %s as it has already been updated',
                 issue_link)
    return

  # Don't comment if Findit has filled the daily quota of monorail updates.
  if flake_issue_util.GetRemainingPostAnalysisDailyBugUpdatesCount() <= 0:
    logging.info(
        'Skipping updating issue %s due to maximum daily bug limit being '
        'reached', issue_link)
    return

  # Comment with link to FlakeCulprit.
  monorail_util.UpdateIssueWithIssueGenerator(
      flake_issue_to_update.issue_id,
      issue_generator.FlakeAnalysisIssueGenerator(analysis))
  flake_issue_to_update.last_updated_time_with_analysis_results = (
      time_util.GetUTCNow())
  flake_issue_to_update.last_updated_time_in_monorail = time_util.GetUTCNow()
  flake_issue_to_update.put()

  monitoring.flake_analyses.increment({
      'result': 'culprit-identified',
      'action_taken': 'bug-updated',
      'reason': ''
  })


def OnCulpritIdentified(analysis_urlsafe_key):
  """All operations to perform when a culprit is identified.

    Should only be called for results with high confidence.

  Args:
    analysis_urlafe_key (str): The urlsafe-key to the MasterFlakeAnalysis to
        update culprit information for.
    revision (str): The culprit's chromium revision.
    commit_position (int): The culprit's commit position.
    project (str): The name of the project/repo the culprit is in.
  """
  analysis = entity_util.GetEntityFromUrlsafeKey(analysis_urlsafe_key)
  assert analysis, 'Analysis missing unexpectedly!'

  if not flake_bug_util.HasSufficientConfidenceInCulprit(
      analysis, flake_bug_util.GetMinimumConfidenceToUpdateEndpoints()):
    analysis.LogInfo(
        'Skipping auto actions due to insufficient confidence {}'.format(
            analysis.confidence_in_culprit))
    return

  analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
  assert analysis, 'Analysis {} missing unexpectedly!'.format(
      analysis_urlsafe_key)

  # TODO(crbug.com/944670): make sure every analysis links to a flake - even
  # for manually triggered ones.
  flake = analysis.flake_key.get() if analysis.flake_key else None
  flake_issue_key = flake.flake_issue_key if flake else None
  flake_issue = flake_issue_key.get() if flake_issue_key else None
  flake_culprit_key = ndb.Key(urlsafe=analysis.culprit_urlsafe_key)

  if not flake_issue:
    # Attaches culprit's flake issue to the flake.
    _AttachCulpritFlakeIssueToFlake(flake, flake_culprit_key)
  else:
    # Deduplicate bugs or split them based on culprit.
    (duplicate_flake_issue_key,
     destination_flake_issue_key) = MergeOrSplitFlakeIssueByCulprit(
         flake_issue_key, flake_culprit_key)

    if (duplicate_flake_issue_key and
        destination_flake_issue_key):  # pragma: no branch
      # A merge occurred. Update potentially impacted FlakeIssue merge
      # destination keys.
      flake_issue_util.UpdateIssueLeaves(duplicate_flake_issue_key,
                                         destination_flake_issue_key)

  # TODO(crbug.com/942224): Log bugs if no FlakeIssue and still flaky.

  # TODO(crbug.com/893787): Other auto actions based on outcome.
  UpdateMonorailBugWithCulprit(analysis_urlsafe_key)
