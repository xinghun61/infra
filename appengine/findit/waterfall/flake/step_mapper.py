# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from common.findit_http_client import FinditHttpClient
from libs.test_results import test_results_util
from services import step_util
from services import swarmed_test_util
from services import swarming
from waterfall import buildbot


def _GetMatchingWaterfallBuildStep(cq_build_step, http_client):
  """Returns the matching Waterfall build step of the given CQ one.

  Args:
    cq_build_step (BuildStep): A build step on Commit Queue.
    http_client (RetryHttpClient): A http client to send http requests.

  Returns:
      (master_name, builder_name, build_number, step_name, step_metadata)
    or
      None
  """
  no_matching_result = (None, None, None, None, None)

  # 0. Get step_metadata.
  step_metadata = cq_build_step.step_metadata or step_util.GetStepMetadata(
      cq_build_step.master_name, cq_build_step.builder_name,
      cq_build_step.build_number, cq_build_step.step_name)
  if not step_metadata:
    logging.error('Couldn\'t get step_metadata')
    return no_matching_result

  # 1. Map a cq trybot to the matching waterfall buildbot:
  # get master_name and builder_name.
  wf_master_name = step_metadata.get('waterfall_mastername')
  wf_builder_name = step_metadata.get('waterfall_buildername')
  if not wf_master_name or not wf_builder_name:
    # Either waterfall_mastername or waterfall_buildername doesn't exist.
    logging.info('%s/%s has no matching Waterfall buildbot',
                 cq_build_step.master_name, cq_build_step.builder_name)
    return no_matching_result  # No matching Waterfall buildbot.

  # 2. Get "name" of the CQ trybot step.

  # Name of the step in the tags of a Swarming task.
  # Can't use step name, as cq one is with "(with patch)" while waterfall one
  # without.
  name = step_metadata.get('canonical_step_name')
  # The OS in which the test runs on. The same test binary might run on two
  # different OS platforms.
  os_name = step_metadata.get('dimensions', {}).get('os')
  if not name or not os_name:
    logging.error('Couldn\'t find name/os')
    return no_matching_result  # No name of the step.

  # TODO: cache and throttle QPS to the same master.
  # 3. Retrieve latest completed build cycle on the buildbot.
  builds = buildbot.GetRecentCompletedBuilds(
      wf_master_name, wf_builder_name, page_size=1)
  if not builds:
    logging.error('Couldn\'t find latest builds.')
    return no_matching_result  # No name of the step.

  # 4. Check whether there is matching step.
  tasks = swarming.ListSwarmingTasksDataByTags(
      http_client,
      wf_master_name,
      wf_builder_name,
      builds[0],
      additional_tag_filters={
          'name': name,
          'os': os_name
      })
  if tasks:  # One matching buildbot is found.
    wf_step_name = tasks[0].tags['stepname'][0] if 'stepname' in tasks[
        0].tags else ''
    logging.info('%s/%s/%s is mapped to %s/%s/%s', cq_build_step.master_name,
                 cq_build_step.builder_name, cq_build_step.step_name,
                 wf_master_name, wf_builder_name, wf_step_name)
    return (wf_master_name, wf_builder_name, builds[0], wf_step_name,
            step_metadata)

  return no_matching_result


def FindMatchingWaterfallStep(build_step, test_name):
  """Finds the matching Waterfall step and checks whether it is supported.

  Only Swarmed and gtest-based steps are supported at the moment.

  Args:
    build_step (BuildStep): A build step on Waterfall or Commit Queue. It
        will be updated with the matching Waterfall step and whether it is
        Swarmed and supported.
    test_name (str): The name of the test.
  """

  build_step.swarmed = False
  build_step.supported = False

  http_client = FinditHttpClient()

  if build_step.on_cq:
    wf_master_name, wf_builder_name, wf_build_number, wf_step_name, metadata = (
        _GetMatchingWaterfallBuildStep(build_step, http_client))

    build_step.wf_master_name = wf_master_name
    build_step.wf_builder_name = wf_builder_name
    build_step.wf_build_number = wf_build_number
    build_step.wf_step_name = wf_step_name

    if not build_step.has_matching_waterfall_step:
      return
  else:
    build_step.wf_master_name = build_step.master_name
    build_step.wf_builder_name = build_step.builder_name
    build_step.wf_build_number = build_step.build_number
    build_step.wf_step_name = build_step.step_name
    metadata = build_step.step_metadata or step_util.GetStepMetadata(
        build_step.master_name, build_step.builder_name,
        build_step.build_number, build_step.step_name)
    if not metadata:
      logging.error('Couldn\'t get step_metadata')
      return

  build_step.step_metadata = metadata
  # Query Swarming for isolated data.
  build_step.swarmed = True if metadata.get('swarm_task_ids') else False

  if build_step.swarmed:
    need_to_continue = False
    for task_id in metadata['swarm_task_ids']:
      output = swarmed_test_util.GetTestResultForSwarmingTask(
          task_id, http_client)
      if output:
        # Guess from the format.
        test_result_object = test_results_util.GetTestResultObject(
            output, partial_result=True)
        if not test_result_object:
          build_step.supported = False
        elif not step_util.IsStepSupportedByFindit(
            test_result_object,
            metadata.get('canonical_step_name') or build_step.step_name,
            build_step.wf_master_name):
          build_step.supported = False
        else:
          test_exists = test_result_object.DoesTestExist(test_name)
          if test_exists:
            build_step.supported = True
          elif test_result_object.contains_all_tests:
            # There is no such test for sure.
            build_step.supported = False
          else:
            # Test is not in this task, but cannot determine if it's in other
            # tasks.
            need_to_continue = True
      if not need_to_continue:
        break
