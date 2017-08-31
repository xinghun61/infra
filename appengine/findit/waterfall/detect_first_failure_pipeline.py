# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.waterfall import failure_type
from gae_libs.pipeline_wrapper import BasePipeline
from model.wf_analysis import WfAnalysis
from services import ci_failure
from services.test_failure import ci_test_failure


class DetectFirstFailurePipeline(BasePipeline):
  """A pipeline to detect first failure of each step."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, failure_info):
    """
    Args:
      failure_info (dict): A dict of failure info for the current failed build
        in the following form:
      {
        "master_name": "chromium.gpu",
        "builder_name": "GPU Linux Builder"
        "build_number": 25410,
        "failed": true,
        "failed_steps": {
          "compile": {
            "current_failure": 25410,
            "first_failure": 25409
          }
        },
        "builds": {
          "25410": {
            "chromium_revision": "4bffcd598dd89e0016208ce9312a1f477ff105d1"
            "blame_list": [
              "b98e0b320d39a323c81cc0542e6250349183a4df",
              ...
            ],
          }
        }
      }

    Returns:
      A dict  of failure info with first failure info in the following form:
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
    master_name = failure_info['master_name']
    builder_name = failure_info['builder_name']
    build_number = failure_info['build_number']

    builds = failure_info['builds']
    # Checks first failed builds for each failed step.
    ci_failure.CheckForFirstKnownFailure(master_name, builder_name,
                                         build_number,
                                         failure_info['failed_steps'], builds)

    if failure_info['failure_type'] == failure_type.TEST:
      # Checks first failed builds for each failed test.
      ci_test_failure.CheckFirstKnownFailureForSwarmingTests(
          master_name, builder_name, build_number, failure_info['failed_steps'],
          builds)

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    analysis.failure_info = failure_info
    analysis.put()

    return failure_info
