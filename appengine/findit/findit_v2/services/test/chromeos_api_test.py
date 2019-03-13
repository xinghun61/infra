# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from buildbucket_proto.step_pb2 import Step

from findit_v2.services.chromeos_api import ChromeOSProjectAPI
from findit_v2.services.failure_type import StepTypeEnum


class ChromeOSProjectAPITest(unittest.TestCase):

  def testCompileStep(self):
    step = Step()
    step.name = 'build_packages'
    log = step.logs.add()
    log.name = 'stdout'
    self.assertEqual(StepTypeEnum.COMPILE,
                     ChromeOSProjectAPI().ClassifyStepType(step))

  def testInfraStep(self):
    step = Step()
    step.name = 'Failure Reason'
    log = step.logs.add()
    log.name = 'reason'
    self.assertEqual(StepTypeEnum.INFRA,
                     ChromeOSProjectAPI().ClassifyStepType(step))
