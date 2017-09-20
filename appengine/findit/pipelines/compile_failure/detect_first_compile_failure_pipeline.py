# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.pipeline_wrapper import BasePipeline
from model.wf_analysis import WfAnalysis
from services import ci_failure


#TODO(crbug/766851): Make this pipeline to inherit from new base pipeline.
class DetectFirstCompileFailurePipeline(BasePipeline):
  """A pipeline to detect first failure of compile step."""

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
            "first_failure": 25410
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
      A dict of failure info with first failure info in the following form:
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
    # Checks first failed builds for failed compile step.
    ci_failure.CheckForFirstKnownFailure(master_name, builder_name,
                                         build_number,
                                         failure_info['failed_steps'], builds)

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    analysis.failure_info = failure_info
    analysis.put()
    return failure_info
