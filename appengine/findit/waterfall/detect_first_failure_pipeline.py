# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from model.wf_analysis import WfAnalysis
from pipeline_wrapper import pipeline
from pipeline_wrapper import BasePipeline
from waterfall import buildbot
from waterfall import build_util


_MAX_BUILDS_TO_CHECK = 20


class DetectFirstFailurePipeline(BasePipeline):
  """A pipeline to detect first failure of each step.

  TODO(stgao): do test-level detection for gtest.
  """

  def _ExtractBuildInfo(self, master_name, builder_name, build_number):
    """Returns a BuildInfo instance for the specified build."""
    build = build_util.DownloadBuildData(
        master_name, builder_name, build_number)

    if build is None:  # pragma: no cover
      raise pipeline.Retry('Too many download from %s' % master_name)
    if not build.data:  # pragma: no cover
      return None

    build_info = buildbot.ExtractBuildInfo(
        master_name, builder_name, build_number, build.data)

    if not build.completed:
      build.start_time = build_info.build_start_time
      build.completed = build_info.completed
      build.result = build_info.result
      build.put()

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    if analysis and not analysis.build_start_time:
      analysis.build_start_time = build_info.build_start_time
      analysis.put()

    return build_info

  def _SaveBlamelistAndChromiumRevisionIntoDict(self, build_info, builds):
    """
    Args:
      build_info (BuildInfo): a BuildInfo instance which contains blame list and
          chromium revision.
      builds (dict): to which the blame list and chromium revision is saved. It
          will be updated and looks like:
          {
            555 : {
              'chromium_revision': 'a_git_hash',
              'blame_list': ['git_hash1', 'git_hash2'],
            },
          }
    """
    builds[build_info.build_number] = {
        'chromium_revision': build_info.chromium_revision,
        'blame_list': build_info.blame_list
    }

  def _CreateADictOfFailedSteps(self, build_info):
    """ Returns a dict with build number for failed steps.

    Args:
      failed_steps (list): a list of failed steps.

    Returns:
      A dict like this:
      {
        'step_name': {
          'current_failure': 555,
          'first_failure': 553,
        },
      }
    """
    failed_steps = dict()
    for step_name in build_info.failed_steps:
      failed_steps[step_name] = {
          'current_failure': build_info.build_number,
          'first_failure': build_info.build_number,
      }

    return failed_steps

  def _CheckForFirstKnownFailure(self, master_name, builder_name, build_number,
                                 failed_steps, builds):
    """Checks for first known failures of the given failed steps.

    Args:
      master_name (str): master of the failed build.
      builder_name (str): builder of the failed build.
      build_number (int): builder number of the current failed build.
      failed_steps (dict): the failed steps of the current failed build. It will
          be updated with build numbers for 'first_failure' and 'last_pass' of
          each failed step.
      builds (dict): a dict to save blame list and chromium revision.
    """
    # Look back for first known failures.
    earliest_build_number = max(0, build_number - 1 - _MAX_BUILDS_TO_CHECK)
    for n in range(build_number - 1, earliest_build_number - 1, -1):
      # Extraction should stop when when we reach to the first build
      build_info = self._ExtractBuildInfo(master_name, builder_name, n)

      if not build_info:  # pragma: no cover
        # Failed to extract the build information, bail out.
        return

      self._SaveBlamelistAndChromiumRevisionIntoDict(build_info, builds)

      if build_info.result == buildbot.SUCCESS:
        for step_name in failed_steps:
          if 'last_pass' not in failed_steps[step_name]:
            failed_steps[step_name]['last_pass'] = build_info.build_number

        # All steps passed, so stop looking back.
        return
      else:
        # If a step is not run due to some bot exception, we are not sure
        # whether the step could pass or not. So we only check failed/passed
        # steps here.

        for step_name in build_info.failed_steps:
          if (step_name in failed_steps and
              not 'last_pass' in failed_steps[step_name]):
            failed_steps[step_name]['first_failure'] = build_info.build_number

        for step_name in failed_steps:
          if (step_name in build_info.passed_steps and
              'last_pass' not in failed_steps[step_name]):
            failed_steps[step_name]['last_pass'] = build_info.build_number

        if all('last_pass' in step_info for step_info in failed_steps.values()):
          # All failed steps passed in this build cycle.
          return

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number):
    """
    Args:
      master_name (str): the master name of a build.
      builder_name (str): the builder name of a build.
      build_number (int): the build number of a build.

    Returns:
      A dict in the following form:
      {
        "master_name": "chromium.gpu",
        "builder_name": "GPU Linux Builder"
        "build_number": 25410,
        "failed": true,
        "failed_steps": {
          "compile": {
            "last_pass": 25408,
            "current_failure": 25410,
            "first_failure": 25409
          }
        },
        "builds": {
          "25408": {
            "chromium_revision": "474ab324d17d2cd198d3fb067cabc10a775a8df7"
            "blame_list": [
              "474ab324d17d2cd198d3fb067cabc10a775a8df7"
            ],
          },
          "25409": {
            "chromium_revision": "33c6f11de20c5b229e102c51237d96b2d2f1be04"
            "blame_list": [
              "9d5ebc5eb14fc4b3823f6cfd341da023f71f49dd",
              ...
            ],
          },
          "25410": {
            "chromium_revision": "4bffcd598dd89e0016208ce9312a1f477ff105d1"
            "blame_list": [
              "b98e0b320d39a323c81cc0542e6250349183a4df",
              ...
            ],
          }
        }
      }
    """
    build_info = self._ExtractBuildInfo(master_name, builder_name, build_number)

    if not build_info:  # pragma: no cover
      raise pipeline.Retry('Failed to extract build info.')

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    analysis.not_passed_steps = build_info.not_passed_steps
    analysis.put()

    failure_info = {
        'failed': True,
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'chromium_revision': build_info.chromium_revision,
        'builds': {},
        'failed_steps': [],
    }

    if (build_info.result == buildbot.SUCCESS or
        not build_info.failed_steps):
      failure_info['failed'] = False
      return failure_info

    builds = dict()
    self._SaveBlamelistAndChromiumRevisionIntoDict(build_info, builds)

    failed_steps = self._CreateADictOfFailedSteps(build_info)

    self._CheckForFirstKnownFailure(
        master_name, builder_name, build_number, failed_steps, builds)

    failure_info['builds'] = builds
    failure_info['failed_steps'] = failed_steps
    return failure_info
