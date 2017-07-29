# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Implementation of the filter rules feature."""

import logging

from features import filterrules_helpers
from framework import jsonfeed
from tracker import tracker_constants


class RecomputeDerivedFieldsTask(jsonfeed.InternalTask):
  """JSON servlet that recomputes derived fields on a batch of issues."""

  def HandleRequest(self, mr):
    """Recompute derived field values on one range of issues in a shard."""
    logging.info(
        'params are %r %r %r %r', mr.specified_project_id, mr.lower_bound,
        mr.upper_bound, mr.shard_id)
    project = self.services.project.GetProject(
        mr.cnxn, mr.specified_project_id)
    config = self.services.config.GetProjectConfig(
        mr.cnxn, mr.specified_project_id)
    filterrules_helpers.RecomputeAllDerivedFieldsNow(
        mr.cnxn, self.services, project, config, lower_bound=mr.lower_bound,
        upper_bound=mr.upper_bound)

    return {
        'success': True,
        }


class ReindexQueueCron(jsonfeed.InternalTask):
  """JSON servlet that reindexes some issues each minute, as needed."""

  def HandleRequest(self, mr):
    """Reindex issues that are listed in the reindex table."""
    num_reindexed = self.services.issue.ReindexIssues(
        mr.cnxn, tracker_constants.MAX_ISSUES_TO_REINDEX_PER_MINUTE,
        self.services.user)

    return {
        'num_reindexed': num_reindexed,
        }
