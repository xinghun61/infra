# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from model.flake.flake_culprit import FlakeCulprit


def GenerateSuspectedRanges(suspected_revisions, revision_range):
  """Generates a list of revision tuples.

  Args:
    suspected_revisions (list): A list of suspected revisions according to
        git blame.
    revision_range (list): The list of revisions of a suspected flake build.
        The revisions are expected to be in chronological order as a
        DataPoint's blame_list.

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


# pylint: disable=E1120
@ndb.transactional(xg=True)
def SaveFlakeCulpritsForSuspectedRevisions(git_repo,
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
