# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Actions to be performed after a flake analysis has completed."""

from google.appengine.ext import ndb


def _GetFlakeIssueAndCulpritKeys(analysis_urlsafe_key):
  """Gets the FlakeIssue and FlakeCulprit keys to associate with one another."""
  analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
  assert analysis, 'Analysis {} missing unexpectedly!'.format(
      analysis_urlsafe_key)

  flake = analysis.flake_key.get() if analysis.flake_key else None
  flake_issue_key = flake.flake_issue_key if flake else None

  return flake_issue_key, ndb.Key(urlsafe=analysis.culprit_urlsafe_key)


# pylint: disable=E1120
@ndb.transactional(xg=True)
def MergeOrSplitFlakeIssueByCulprit(flake_issue_key, flake_culprit_key):
  """Associate FlakeCulprit with FlakeIssue and provided by MasterFlakeAnalysis.

  Args:
    analysis_urlafe_key (str): The key to the MasterFlakeAnalysis whose
      FlakeCulprit and Flake's FlakeIssue are to be associated.
  """
  if not flake_issue_key:  # pragma: no cover. Nothing to do if no FlakeIssue.
    # TODO(crbug.com/907603): All flake analyses should eventually be triggered
    # with a flake issue. This check should then be removed.
    return

  issue = flake_issue_key.get()
  assert issue, 'FlakeIssue {} missing unexpectedly!'.format(flake_issue_key)

  culprit = flake_culprit_key.get()
  assert culprit, 'FlakeCulprit {} missing unexpectedly!'.format(
      flake_culprit_key)

  if (culprit.flake_issue_key and
      culprit.flake_issue_key != issue.key):  # pragma: no cover.
    # TODO(crbug.com/905750): Merge flake_issue into the culprit's existing
    # FlakeIssue, as they have the same culprit and are thus duplicates. Remove
    # no cover when implemented.
    return

  if (issue.flake_culprit_key and
      issue.flake_culprit_key != culprit.key):  # pragma: no cover.
    # TODO(crbug.com/907313) flake_issue has a different culprit associated.
    # Create a new FlakeIssue for the new culprit. Remove no cover when
    # implemented.
    return

  # Link issue and culprit for when other analyses complete.
  culprit.flake_issue_key = issue.key
  issue.flake_culprit_key = culprit.key
  issue.put()
  culprit.put()


def OnCulpritIdentified(analysis_urlsafe_key):
  """All operations to perform when a culprit is identified.

  Args:
    analysis_urlafe_key (str): The urlsafe-key to the MasterFlakeAnalysis to
        update culprit information for.
    revision (str): The culprit's chromium revision.
    commit_position (int): The culprit's commit position.
    project (str): The name of the project/repo the culprit is in.
  """
  flake_issue_key, flake_culprit_key = _GetFlakeIssueAndCulpritKeys(
      analysis_urlsafe_key)

  # Deduplicate bugs or split them based on culprit.
  MergeOrSplitFlakeIssueByCulprit(flake_issue_key, flake_culprit_key)

  # TODO(crbug.com/893787): Other auto actions based on outcome.
