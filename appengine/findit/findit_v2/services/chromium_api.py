# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Defines the chromium-specific APIs required by Findit."""

from findit_v2.services.failure_type import StepTypeEnum
from findit_v2.services.project_api import ProjectAPI


class ChromiumProjectAPI(ProjectAPI):

  def ClassifyStepType(self, _build, step):
    if step.name == 'compile':
      return StepTypeEnum.COMPILE

    for log in step.logs:
      if log.name == 'step_metadata':
        return StepTypeEnum.TEST

    return StepTypeEnum.INFRA

  def GetCompileFailures(self, build, compile_steps):  # pragma: no cover.
    raise NotImplementedError

  def GetTestFailures(self, build, test_steps):  # pragma: no cover.
    raise NotImplementedError

  def GetRerunBuilderId(self, build):  # pragma: no cover.
    raise NotImplementedError

  def GetTestRerunBuildInputProperties(self, tests):  # pragma: no cover.
    raise NotImplementedError
