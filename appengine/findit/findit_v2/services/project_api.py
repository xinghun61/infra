# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Defines the APIs that each supported project must implement."""


class ProjectAPI(object):  # pragma: no cover.

  def ClassifyStepType(self, step):
    """ Returns the failure type of the given build step.

    Args:
      step (buildbucket step.proto): ALL info about the build step.

    Returns:
      findit_v2.services.failure_type.StepTypeEnum
    """
    raise NotImplementedError
