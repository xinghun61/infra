# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from dto.test_location import TestLocation

from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository

from model.flake.flake_culprit import FlakeCulprit

from waterfall import swarming_util
from waterfall.flake import flake_constants


def GetTestLocation(task_id, test_name, http_client):
  """Gets the filepath and line number of a test from swarming.

  Args:
    task_id (str): The swarming task id to query.
    test_name (str): The name of the test whose location to return.

  Returns:
    (TestLocation): The file path and line number of the test, or None
        if the test location was not be retrieved.

  """
  task_output = swarming_util.GetIsolatedOutputForTask(task_id, http_client)

  if not task_output:
    logging.error('No isolated output returned for %s', task_id)
    return None

  test_locations = task_output.get('test_locations')

  if not test_locations:
    logging.error('test_locations not found for task %s', task_id)
    return None

  test_location = test_locations.get(test_name)

  if not test_location:
    logging.error('test_location not found for %s', test_name)
    return None

  return TestLocation.FromSerializable(test_location)


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
        The revisions are expected to be in chronological order as a
        DataPoint's blame_list.

  Returns:
    A list of revisions found in both git_blame and revision_range.
  """
  # TODO(lijeffrey): Currently the approach here is just to see if any revisions
  # in the revision range were the last to modify the file. Later, we may want
  # to perform a more sophisticated heuristic analysis that examines each
  # revision in greater depth, such as adding or modifying related files and
  # score them appropriately.
  return list(
      set(region.revision for region in git_blame) & set(revision_range))


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


# pylint: disable=E1120
@ndb.transactional(xg=True)
def SaveFlakeCulpritsForSuspectedRevisions(http_client,
                                           analysis_urlsafe_key,
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

  suspected_build_point = analysis.GetDataPointOfSuspectedBuild()
  assert suspected_build_point

  new_suspects_identified = False

  for revision in suspected_revisions:
    commit_position = suspected_build_point.GetCommitPosition(revision)
    suspect = (FlakeCulprit.Get(repo_name, revision) or
               FlakeCulprit.Create(repo_name, revision, commit_position))

    if suspect.url is None:
      git_repo = CachedGitilesRepository(
          http_client, flake_constants.CHROMIUM_GIT_REPOSITORY_URL)
      change_log = git_repo.GetChangeLog(revision)

      if change_log:
        suspect.url = change_log.code_review_url or change_log.commit_url
        suspect.put()
      else:
        logging.error('Unable to retrieve change logs for %s', revision)
        continue

    # Save each culprit to the analysis' list of heuristic culprits.
    suspect_urlsafe_key = suspect.key.urlsafe()
    if suspect_urlsafe_key not in analysis.suspect_urlsafe_keys:
      new_suspects_identified = True
      analysis.suspect_urlsafe_keys.append(suspect_urlsafe_key)

  if new_suspects_identified:
    analysis.put()
