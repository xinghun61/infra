# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Handler for running a swarmbucket tryjob on buildbot."""

import json

from gae_libs import appengine_util
from gae_libs import token
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission

from common import constants
from waterfall.schedule_compile_try_job_pipeline import (
    ScheduleCompileTryJobPipeline)
from waterfall.schedule_test_try_job_pipeline import (
    ScheduleTestTryJobPipeline)
from model.wf_try_job_data import WfTryJobData


def _GetProperties(sb_run):
  params = json.loads(sb_run.last_buildbucket_response.get('parameters_json'))
  properties = params['properties']
  additional_parameters = params.get('additional_build_parameters', {})
  return properties, additional_parameters


class RerunForCompare(BaseHandler):
  PERMISSION_LEVEL = Permission.ADMIN

  @token.VerifyXSRFToken(action_id='swarmbucket_performance')
  def HandlePost(self):
    # TODO: Ensure this runs at most once every x minutes for a given tryjob (we
    # don't want to trigger more jobs than necessary, and the ui could allow
    # this if it doesn't refresh after triggering)
    build_id = self.request.get('try_job')
    sb_run = WfTryJobData.Get(build_id)
    if not sb_run:
      # TODO(robertocn): Implement re-run for flake try jobs.
      return self.CreateError('Try job not found. (Flake not yet supported)',
                              404)
    sb_tryjob = sb_run.try_job_key.get()
    pipeline_job = None
    if sb_run.try_job_type == 'test':
      properties, additional_parameters = _GetProperties(sb_run)
      pipeline_job = ScheduleTestTryJobPipeline(
          sb_tryjob.master_name,
          sb_tryjob.builder_name,
          sb_tryjob.build_number,
          properties['good_revision'],
          properties['bad_revision'],
          sb_run.try_job_type,
          properties.get('suspected_revisions'),
          None,
          None,
          additional_parameters.get('tests'),
          force_buildbot=True)
      pipeline_job.target = appengine_util.GetTargetNameForModule(
          constants.WATERFALL_BACKEND)
      pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)

    else:
      # sb_run is of type 'compile'.
      properties, additional_parameters = _GetProperties(sb_run)
      pipeline_job = ScheduleCompileTryJobPipeline(
          sb_tryjob.master_name,
          sb_tryjob.builder_name,
          sb_tryjob.build_number,
          properties['good_revision'],
          properties['bad_revision'],
          sb_run.try_job_type,
          additional_parameters.get('compile_targets'),
          properties.get('suspected_revisions'),
          None,
          None,
          force_buildbot=True)
      pipeline_job.target = appengine_util.GetTargetNameForModule(
          constants.WATERFALL_BACKEND)
      pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    return {'data': {'pipeline_job_id': pipeline_job.pipeline_id}}
