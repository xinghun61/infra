# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from buildbucket_proto.step_pb2 import Step

from findit_v2.services.chromium_api import ChromiumProjectAPI
from findit_v2.services.failure_type import StepTypeEnum


class ChromiumProjectAPITest(unittest.TestCase):

  def testCompileStep(self):
    step = Step()
    step.name = 'compile'
    log = step.logs.add()
    log.name = 'stdout'
    self.assertEqual(StepTypeEnum.COMPILE,
                     ChromiumProjectAPI().ClassifyStepType(None, step))

  def testTestStep(self):
    step = Step()
    step.name = 'browser_tests'
    log = step.logs.add()
    log.name = 'step_metadata'
    self.assertEqual(StepTypeEnum.TEST,
                     ChromiumProjectAPI().ClassifyStepType(None, step))

  def testInfraStep(self):
    step = Step()
    step.name = 'infra'
    log = step.logs.add()
    log.name = 'report'
    self.assertEqual(StepTypeEnum.INFRA,
                     ChromiumProjectAPI().ClassifyStepType(None, step))
