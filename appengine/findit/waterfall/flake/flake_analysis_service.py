# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from common import constants
from common import monitoring
from libs import email_util
from libs import time_util
from model.flake.flake_analysis_request import FlakeAnalysisRequest
from waterfall.flake import initialize_flake_pipeline
from waterfall.flake import step_mapper
from waterfall.test_info import TestInfo


def _CheckFlakeSwarmedAndSupported(request):
  """Checks if the flake is Swarmed and supported in any build step.

  Args:
    request (FlakeAnalysisRequest): The request to analyze a flake.

  Returns:
    (swarmed, supported, build_step)
    swarmed(bool): True if any step is Swarmed.
    supported(bool): True if any step is supported (Swarmed Gtest).
    build_step(BuildStep): The representative step that is Swarmed Gtest.
  """
  build_step = None
  swarmed = False
  supported = False
  for step in request.build_steps:
    swarmed = swarmed or step.swarmed
    supported = supported or step.supported
    if step.supported:
      build_step = step
      break
  return swarmed, supported, build_step


def _MergeNewRequestIntoExistingOne(new_request, existing_request, rerun=False):
  """Merges the new request into the existing request and creates a new record.

  Args:
    new_request (FlakeAnalysisRequest): The request to analyze a flake.
    existing_request (FlakeAnalysisRequest): The existing request in record.
    rerun (bool): The admin has forced a rerun.

  Returns:
    (version_number, build_step)
    version_number (int): The version of the FlakeAnalysisRequest if a new
        analysis is needed; otherwise 0.
    build_step (BuildStep): a BuildStep instance if a new analysis is needed;
        otherwise None.
  """
  # If no bug is attached to the existing analysis or the new request, or both
  # are attached to the same bug, start a new analysis with a different
  # configuration. For a configuration that was analyzed 7 days ago, reset it
  # to use the new reported step of the same configuration.
  # TODO: Move this setting to config.
  # TODO: Refactor this method, and put it in FlakeAnalysisRequest.
  seconds_n_days = 7 * 24 * 60 * 60  # 7 days.
  candidate_supported_steps = []
  need_updating = rerun
  for step in new_request.build_steps:
    existing_step = None
    for s in existing_request.build_steps:
      if (step.master_name == s.master_name and
          step.builder_name == s.builder_name):
        existing_step = s
        break

    if rerun and existing_step:
      candidate_supported_steps.append(existing_step)

    if existing_step and not rerun:
      # If last reported flake at the existing step was too long ago, drop it
      # so that the new one is recorded.
      time_diff = step.reported_time - existing_step.reported_time
      if time_diff.total_seconds() > seconds_n_days:
        existing_request.build_steps.remove(existing_step)
        existing_step = None

    if not existing_step and not rerun:
      need_updating = True
      existing_request.build_steps.append(step)
      if step.supported:
        candidate_supported_steps.append(step)

  if not candidate_supported_steps:
    # Find some existing configuration that is not analyzed yet.
    for s in existing_request.build_steps:
      if not s.scheduled and s.supported:
        candidate_supported_steps.append(s)

  supported_build_step = None
  if candidate_supported_steps:
    supported_build_step = candidate_supported_steps[0]
    existing_request.swarmed = (existing_request.swarmed or
                                supported_build_step.swarmed)
    existing_request.supported = True
    need_updating = True

  if supported_build_step and not existing_request.is_step:
    supported_build_step.scheduled = True  # This will be analyzed.

  if not existing_request.bug_id:  # No bug was attached before.
    existing_request.bug_id = new_request.bug_id
    need_updating = True

  if need_updating:
    existing_request.user_emails = (
        email_util.ObscureEmails(existing_request.user_emails, ['google.com']) +
        list(set(new_request.user_emails)))
    existing_request.user_emails_obscured = False
    existing_request.user_emails_last_edit = time_util.GetUTCNow()

    # This will create a new data entity.
    existing_request.put()

  if not supported_build_step or existing_request.is_step:
    # No new analysis if:
    # 1. All analyzed steps are fresh enough and cover all the steps in the
    #    request.
    # 2. No representative step is Swarmed Gtest.
    # 3. The flake is a step-level one.
    return 0, None

  return existing_request.version_number, supported_build_step


def _CheckForNewAnalysis(request, rerun=False):
  """Checks if a new analysis is needed for the requested flake.

  Args:
    request (FlakeAnalysisRequest): The request to analyze a flake.
    rerun (bool): Indicates a forced rerun by admin.

  Returns:
    (version_number, build_step)
    version_number (int): The version of the FlakeAnalysisRequest if a new
        analysis is needed; otherwise 0.
    build_step (BuildStep): a BuildStep instance if a new analysis is needed;
        otherwise None.
  """
  existing_request = FlakeAnalysisRequest.GetVersion(key=request.name)
  if not existing_request or (existing_request.bug_id and request.bug_id and
                              existing_request.bug_id != request.bug_id):
    # If no existing analysis or last analysis was for a different bug, randomly
    # pick one configuration for a new analysis.
    if existing_request:
      # Make a copy to preserve the version number of existing analysis and
      # prevent concurrent analyses of the same flake.
      user_emails = (
          email_util.ObscureEmails(existing_request.user_emails, ['google.com'])
          + list(set(request.user_emails)))
      existing_request.CopyFrom(request)
      request = existing_request
      request.user_emails = user_emails
    request.user_emails_obscured = False
    request.user_emails_last_edit = time_util.GetUTCNow()

    swarmed, supported, supported_build_step = _CheckFlakeSwarmedAndSupported(
        request)
    request.swarmed = swarmed
    request.supported = supported

    if supported_build_step and not request.is_step:
      supported_build_step.scheduled = True  # This step will be analyzed.

    # For unsupported or step-level flakes, still save them for monitoring.
    _, saved = request.Save(retry_on_conflict=False)  # Create a new version.

    if not saved or not supported_build_step or request.is_step:
      # No new analysis if:
      # 1. Another analysis was just triggered.
      # 2. No representative step is Swarmed Gtest.
      # 3. The flake is a step-level one.
      return 0, None

    return request.version_number, supported_build_step
  else:
    # If no bug is attached to the existing analysis or the new request, or both
    # are attached to the same bug, start a new analysis with a different
    # configuration. For a configuration that was analyzed 7 days ago, reset it
    # to use the new reported step of the same configuration.
    # TODO: move this setting to config.
    return _MergeNewRequestIntoExistingOne(request, existing_request, rerun)


def IsAuthorizedUser(user_email, is_admin):
  """Returns True if the given user email account is authorized for access."""
  return is_admin or (user_email and
                      (user_email in constants.WHITELISTED_APP_ACCOUNTS or
                       user_email.endswith('@google.com')))


def ScheduleAnalysisForFlake(request,
                             user_email,
                             is_admin,
                             triggering_source,
                             rerun=False):
  """Schedules an analysis on the flake in the given request if needed.

  Args:
    request (FlakeAnalysisRequest): The request to analyze a flake.
    user_email (str): The email of the requester.
    is_admin (bool): Whether the requester is an admin.
    triggering_source (int): Where the request is coming from, either Findit
      UI (check flake page), pipeline (from analysis) or Findit API.
    rerun (bool): This is a rerun, so force it to be run.

  Returns:
    True if an analysis was scheduled; False if a new analysis is not needed;
    None if the user has no permission to.
  """
  assert len(request.build_steps), 'At least 1 build step is needed!'

  if not IsAuthorizedUser(user_email, is_admin):
    logging.info(
        'Schedule failed because user is not authorized. user:%s, admin:%s',
        user_email, is_admin)
    return None
  request.user_emails = [user_email]

  manually_triggered = user_email.endswith('@google.com')

  trigger_action = 'manual' if manually_triggered else 'auto'
  flake_source = 'cq' if request.on_cq else 'waterfall'

  for build_step in request.build_steps:
    step_mapper.FindMatchingWaterfallStep(build_step, request.name)

  version_number, build_step = _CheckForNewAnalysis(request, rerun)
  if version_number and build_step:
    # A new analysis is needed.
    logging.info('A new analysis is needed for: %s', build_step)
    normalized_test = TestInfo(
        build_step.wf_master_name, build_step.wf_builder_name,
        build_step.wf_build_number, build_step.wf_step_name, request.name)
    original_test = TestInfo(build_step.master_name, build_step.builder_name,
                             build_step.build_number, build_step.step_name,
                             request.name)
    analysis = initialize_flake_pipeline.ScheduleAnalysisIfNeeded(
        normalized_test,
        original_test,
        bug_id=request.bug_id,
        allow_new_analysis=True,
        manually_triggered=manually_triggered,
        user_email=user_email,
        triggering_source=triggering_source,
        queue_name=constants.WATERFALL_ANALYSIS_QUEUE,
        force=rerun)
    if analysis:
      # TODO: put this in a transaction.
      request = FlakeAnalysisRequest.GetVersion(
          key=request.name, version=version_number)
      request.analyses.append(analysis.key)
      request.put()
      logging.info('A new analysis was triggered successfully with key: %s',
                   analysis.key)
      monitoring.flakes.increment({
          'operation': 'analyze',
          'trigger': trigger_action,
          'source': flake_source,
      })
      return True
    else:
      logging.error('But new analysis was not triggered!')
  else:
    logging.info('No new analysis is needed: %s', request)

  monitoring.flakes.increment({
      'operation': 'skip',
      'trigger': trigger_action,
      'source': flake_source,
  })
  return False
