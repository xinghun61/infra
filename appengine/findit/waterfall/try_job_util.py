# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from google.appengine.api import modules
from google.appengine.ext import ndb

from model import wf_analysis_status
from model.wf_try_job import WfTryJob
from waterfall import try_job_pipeline
from waterfall import waterfall_config

TRY_JOB_PIPELINE_QUEUE_NAME = 'try-job-queue'


def _CheckFailureForTryJobKey(
  master_name, builder_name, build_number,
  failure_result_map, step_name, failure):
  """Compares the current_failure and first_failure for each failed_step/test.

  If equal, a new try_job needs to start;
  If not, apply the key of the first_failure's try_job to this failure.
  """
  # TODO(chanli): Need to compare failures across builders
  # after the grouping of failures is implemented.
  new_try_job_key = '%s/%s/%s' % (master_name, builder_name, build_number)
  if failure['current_failure'] == failure['first_failure']:
    failure_result_map[step_name] = new_try_job_key
    return True  # A new try_job is needed.
  else:
    # TODO(chanli): Need to handle cases where first failure is actually
    # more than 20 builds back. The implementation should not be here,
    # but need to be taken care of.
    try_job_key = '%s/%s/%s' % (
        master_name, builder_name, failure['first_failure'])
    failure_result_map[step_name] = try_job_key
    return False


@ndb.transactional
def _NeedANewTryJob(
    master_name, builder_name, build_number, failed_steps):
  """Checks if a new try_job is needed."""
  failure_result_map = {}
  need_new_try_job = False

  for step_name, step in failed_steps.iteritems():
    # TODO(chanli): support test failures when the recipe is ready.
    if step_name =='compile':
      result = _CheckFailureForTryJobKey(
          master_name, builder_name, build_number,
          failure_result_map, step_name, step)
      need_new_try_job = result or need_new_try_job

      if need_new_try_job:
        try_job =  WfTryJob.Get(
            master_name, builder_name, build_number)

        if try_job:
          if try_job.failed:
            try_job.status = wf_analysis_status.PENDING
            try_job.put()
          else:
            need_new_try_job = False
            break
        else:
          try_job = WfTryJob.Create(
              master_name, builder_name, build_number)
          try_job.put()
      break

  return need_new_try_job, failure_result_map


def ScheduleTryJobIfNeeded(
    master_name, builder_name, build_number, failed_steps, revisions):
  tryserver_mastername, tryserver_buildername = (
      waterfall_config.GetTrybotForWaterfallBuilder(master_name, builder_name))
  if not tryserver_mastername or not tryserver_buildername:
    return {}

  need_new_try_job, failure_result_map =_NeedANewTryJob(
      master_name, builder_name, build_number, failed_steps)

  if need_new_try_job:
    new_try_job_pipeline = try_job_pipeline.TryJobPipeline(
        master_name, builder_name, build_number, revisions)
    new_try_job_pipeline.target = (
        '%s.build-failure-analysis' % modules.get_current_version_name())
    new_try_job_pipeline.start(TRY_JOB_PIPELINE_QUEUE_NAME)

  return failure_result_map
