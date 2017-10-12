# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A class to handle cron requests to expunge doomed and deletable projects."""

import logging
import time

from framework import jsonfeed

RUN_DURATION_LIMIT = 50 * 60  # 50 minutes


class Reap(jsonfeed.InternalTask):
  """Look for doomed and deletable projects and delete them."""

  def HandleRequest(self, mr):
    """Update/Delete doomed and deletable projects as needed.

    Args:
      mr: common information parsed from the HTTP request.

    Returns:
      Results dictionary in JSON format. The JSON will look like this:
      {
        'doomed_project_ids': <int>,
        'expunged_project_ids': <int>
      }
      doomed_project_ids are the projects which have been marked as deletable.
      expunged_project_ids are the projects that have either been completely
      expunged or are in the midst of being expunged.
    """
    doomed_project_ids = self._MarkDoomedProjects(mr.cnxn)
    expunged_project_ids = self._ExpungeDeletableProjects(mr.cnxn)
    return {
        'doomed_project_ids': doomed_project_ids,
        'expunged_project_ids': expunged_project_ids,
        }

  def _MarkDoomedProjects(self, cnxn):
    """No longer needed projects get doomed, and this marks them deletable."""
    now = int(time.time())
    doomed_project_rows = self.services.project.project_tbl.Select(
        cnxn, cols=['project_id'],
        # We only match projects with real timestamps and not delete_time = 0.
        where=[('delete_time < %s', [now]), ('delete_time != %s', [0])],
        state='archived', limit=1000)
    doomed_project_ids = [row[0] for row in doomed_project_rows]
    for project_id in doomed_project_ids:
      # Note: We go straight to services layer because this is an internal
      # request, not a request from a user.
      self.services.project.MarkProjectDeletable(
          cnxn, project_id, self.services.config)

    return doomed_project_ids

  def _ExpungeDeletableProjects(self, cnxn):
    """Chip away at deletable projects until they are gone."""
    request_deadline = time.time() + RUN_DURATION_LIMIT

    deletable_project_rows = self.services.project.project_tbl.Select(
        cnxn, cols=['project_id'], state='deletable', limit=100)
    deletable_project_ids = [row[0] for row in deletable_project_rows]
    # expunged_project_ids will contain projects that have either been
    # completely expunged or are in the midst of being expunged.
    expunged_project_ids = set()
    for project_id in deletable_project_ids:
      for _part in self._ExpungeParts(cnxn, project_id):
        expunged_project_ids.add(project_id)
        if time.time() > request_deadline:
          return list(expunged_project_ids)

    return list(expunged_project_ids)

  def _ExpungeParts(self, cnxn, project_id):
    """Delete all data from the specified project, one part at a time.

    This method purges all data associated with the specified project. The
    following is purged:
    * All issues of the project.
    * Project config.
    * Saved queries.
    * Filter rules.
    * Former locations.
    * Local ID counters.
    * Quick edit history.
    * Item stars.
    * Project from the DB.

    Returns a generator whose return values can be either issue
    ids or the specified project id. The returned values are intended to be
    iterated over and not read.
    """
    # Purge all issues of the project.
    while True:
      issue_id_rows = self.services.issue.issue_tbl.Select(
          cnxn, cols=['id'], project_id=project_id, limit=1000)
      issue_ids = [row[0] for row in issue_id_rows]
      for issue_id in issue_ids:
        self.services.issue_star.ExpungeStars(cnxn, issue_id)
      self.services.issue.ExpungeIssues(cnxn, issue_ids)
      yield issue_ids
      break

    # All project purge functions are called with cnxn and project_id.
    project_purge_functions = (
      self.services.config.ExpungeConfig,
      self.services.features.ExpungeSavedQueriesExecuteInProject,
      self.services.features.ExpungeFilterRules,
      self.services.issue.ExpungeFormerLocations,
      self.services.issue.ExpungeLocalIDCounters,
      self.services.features.ExpungeQuickEditHistory,
      self.services.project_star.ExpungeStars,
      self.services.project.ExpungeProject,
    )

    for f in project_purge_functions:
      f(cnxn, project_id)
      yield project_id
