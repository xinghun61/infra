# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from common.findit_http_client import FinditHttpClient
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs import analysis_status
from model.flake.analysis.flake_culprit import FlakeCulprit
from services import constants
from services import git
from services import swarmed_test_util
from waterfall import extractor_util

_FINDIT_HTTP_CLIENT = FinditHttpClient()

# TODO(crbug.com/839620): blame_list, build_number, etc. are deprecated. Data
# should instead be passed in memory rather than stored to the data points.


def GenerateSuspectedRanges(suspected_revisions, revision_range):
  """Generates a list of revision tuples.

  Args:
    revision_range (list): The list of revisions of a suspected flake build.
        The revisions are expected to be in chronological order as a
        DataPoint's blame_list.
    suspected_revisions (list): A list of suspected revisions according to
        git blame.

  Returns:
    A list of (previous, suspected_revision) tuples. For example, if r1-r10 are
        in the revision range and r1 and r5 are suspected, then returns
        [(None, r1), (r4, r5)]. These values will be passed to the try job
        pipeline to run the previous and suspected revision(s) to confirm the
        suspected revision(s) of being the culprit.
  """
  ranges = []
  previous = None

  for revision in revision_range:
    if revision in suspected_revisions:
      ranges.append((previous, revision))
    previous = revision

  return ranges


def GetSuspectedRevisions(git_blame, revision_range):
  """Returns a list of revisions that intersect git_blame and revision_range.

  Args:
    git_blame (list): A list of Region objects representing the git blame of a
        file at a particular revision.
    revision_range (list): The list of revisions of a suspected flake build.
        The revisions are expected to be in chronological order from newest
        to oldest.

  Returns:
    A list of revisions found in both git_blame and revision_range.
  """
  # TODO(lijeffrey): Currently the approach here is just to see if any revisions
  # in the revision range were the last to modify the file. Later, we may want
  # to perform a more sophisticated heuristic analysis that examines each
  # revision in greater depth, such as adding or modifying related files and
  # score them appropriately.
  if not git_blame or not revision_range:
    return []

  return list(
      set(region.revision for region in git_blame) & set(revision_range))


def IdentifySuspectedRevisions(analysis):
  """Identifies revisions to have introduced flakiness.

  Args:
    analysis (MasterFlakeAnalysis): The MasterFlakeAnalysis entity to perform
        heuristic analysis on.

  Returns:
    (list): A list of revisions in chronological order suspected to have
        introduced test flakiness.
  """
  regression_range = analysis.GetLatestRegressionRange()

  if regression_range.lower is None or regression_range.upper is None:
    analysis.LogWarning(
        'Unable to identify suspects without a complete regression range')
    return []

  upper_data_point = analysis.FindMatchingDataPointWithCommitPosition(
      regression_range.upper.commit_position)
  assert upper_data_point, 'Cannot get test location without data point'
  assert upper_data_point.git_hash, 'Upper bound revision is None'

  test_location = swarmed_test_util.GetTestLocation(
      upper_data_point.GetSwarmingTaskId(), analysis.test_name)
  if not test_location:
    analysis.LogWarning('Failed to get test location. Heuristic results will '
                        'not be available.')
    return []

  normalized_file_path = extractor_util.NormalizeFilePath(test_location.file)
  git_blame = git.GetGitBlame(constants.CHROMIUM_GIT_REPOSITORY_URL,
                              upper_data_point.git_hash, normalized_file_path)

  if git_blame is None:
    analysis.LogWarning('Failed to get git blame for {}, {}'.format(
        normalized_file_path, upper_data_point.git_hash))
    return []

  lower_revision = regression_range.lower.revision
  assert lower_revision, 'Lower bound revision is None'

  revisions = git.GetCommitsBetweenRevisionsInOrder(
      lower_revision,
      upper_data_point.git_hash,
      repo_url=constants.CHROMIUM_GIT_REPOSITORY_URL,
      ascending=True)

  if not revisions:
    analysis.LogWarning('Failed to get revisions in range [{}, {}]'.format(
        lower_revision, upper_data_point.git_hash))
    return []

  return GetSuspectedRevisions(git_blame, revisions)


def ListCommitPositionsFromSuspectedRanges(revisions_to_commits,
                                           suspected_ranges):
  """Generates an ordered list of commit positions (ints) from suspected_ranges.

      This list is to be consumed when attempting to identify flake culprits
      using heuristic guidance and its corresponding revisions analyzed first in
      the order given.

  Args:
    revisions_to_commits (dict): A dict mapping revisions to commit
        positions.
    suspected_ranges (list): A list of pairs of revisions, where the first of
        each pair is previous revision of the second in the pair, e.g.
        [('r1', 'r2'), ('r4', 'r5')].

  Returns:
    A flattened list of commit positions. For example, if
        [(None, 'r1'), ('r4', 'r5')] is passed in where 'r1' has commit position
        1, returns [1, 4, 5]. The returned list should be in ascending order.
  """

  def Flatten(revision_ranges):
    # Flattens revision_ranges into a list of revisions.
    return [r for revision_range in revision_ranges for r in revision_range]

  commit_positions = set()

  for revision in Flatten(suspected_ranges):
    if revision in revisions_to_commits:
      commit_positions.add(revisions_to_commits[revision])

  # TODO(crbug.com/759806): Incorporate scores with heurstic results to
  # associate scores with suspects and sort by highest score.
  return sorted(list(commit_positions))


def RunHeuristicAnalysis(analysis):
  """Performs heuristic analysis on a MasterFlakeAnalysis.

  Args:
    analysis (MasterFlakeAnalysis): The analysis to run heuristic results on.
        Results are saved to the analysis itself as a list of FlakeCulprit
        urlsafe keys.
  """
  suspected_revisions = IdentifySuspectedRevisions(analysis)
  SaveFlakeCulpritsForSuspectedRevisions(analysis.key.urlsafe(),
                                         suspected_revisions)


# pylint: disable=E1120
@ndb.transactional(xg=True)
def SaveFlakeCulpritsForSuspectedRevisions(analysis_urlsafe_key,
                                           suspected_revisions,
                                           repo_name='chromium'):
  """Saves each suspect to the datastore as a FlakeCulprit.

    Also updates a MasterFlakeAnalysis' heuristic analysis results to include
        each suspect.

  Args:
    analysis_urlsafe_key (str): The urlsafe key of the MasterFlakeAnalysis to
        update.
    suspected_revisions (list): A list of revisions suspected to have caused the
        flakiness to create FlakeCulprits for.
  """
  analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
  assert analysis

  for revision in suspected_revisions:
    commit_position = git.GetCommitPositionFromRevision(revision)
    assert commit_position, 'Canot create FlakeCulprit without commit position'
    suspect = (
        FlakeCulprit.Get(repo_name, revision) or
        FlakeCulprit.Create(repo_name, revision, commit_position))

    if suspect.url is None:
      commits_info = git.GetCommitsInfo([revision])

      if commits_info:
        suspect.url = commits_info[revision]['url']
        suspect.put()
      else:
        logging.error('Unable to retrieve change logs for %s', revision)
        continue

    # Save each culprit to the analysis' list of heuristic culprits.
    suspect_urlsafe_key = suspect.key.urlsafe()
    if suspect_urlsafe_key not in analysis.suspect_urlsafe_keys:
      analysis.suspect_urlsafe_keys.append(suspect_urlsafe_key)

  analysis.heuristic_analysis_status = analysis_status.COMPLETED
  analysis.put()
