# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from common import buildbucket_client
from pipeline_wrapper import BasePipeline
from pipeline_wrapper import pipeline
from waterfall import waterfall_config


class ScheduleTryJobPipeline(BasePipeline):
  """A piepline for sechduling a new tryjob for current build."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(
      self, master_name, builder_name, revisions):
    tryserver_mastername, tryserver_buildername = (
        waterfall_config.GetTrybotForWaterfallBuilder(master_name, builder_name)
    )
    recipe = 'findit/chromium/compile'
    properties = {
        'recipe': recipe,
        'root_solution_revisions': revisions,
        'target_mastername': master_name,
        'target_buildername': builder_name
    }

    try_job = buildbucket_client.TryJob(
        tryserver_mastername, tryserver_buildername, None, properties, [])
    error, build = buildbucket_client.TriggerTryJobs([try_job])[0]
    if error:  # pragma: no cover
      raise pipeline.Retry(
          'Error "%s" orrurs. Reason: "%s"' % (error.message, error.reason))
    return [build.id]
