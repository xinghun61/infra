# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from buildbucket_proto.build_pb2 import Build
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

  def testGetCompileFailures(self):
    build_id = 8765432109123
    build_number = 123
    build = Build(id=build_id, number=123)
    build.input.gitiles_commit.host = 'gitiles.host.com'
    build.input.gitiles_commit.project = 'project/name'
    build.input.gitiles_commit.ref = 'ref/heads/master'
    build.input.gitiles_commit.id = 'git_sha'
    build.output.properties['build_compile_failure_output'] = {
        'failures': [{
            'output_targets': ['chromeos/target1'],
            'rule': 'emerge'
        },]
    }
    step = Step()
    step.name = 'build_packages'

    expected_failures = {
        'build_packages': {
            'failures': {
                'chromeos/target1': {
                    'output_targets': ['chromeos/target1'],
                    'rule': 'emerge',
                    'first_failed_build': {
                        'id': build_id,
                        'number': build_number,
                        'commit_id': 'git_sha'
                    },
                    'last_passed_build': None,
                },
            },
            'first_failed_build': {
                'id': build_id,
                'number': build_number,
                'commit_id': 'git_sha'
            },
            'last_passed_build': None,
        },
    }

    self.assertEqual(expected_failures,
                     ChromeOSProjectAPI().GetCompileFailures(build, [step]))

  def testGetCompileFailuresNoFailure(self):
    build_id = 8765432109123
    build_number = 123
    build = Build(id=build_id, number=123)
    build.input.gitiles_commit.host = 'gitiles.host.com'
    build.input.gitiles_commit.project = 'project/name'
    build.input.gitiles_commit.ref = 'ref/heads/master'
    build.input.gitiles_commit.id = 'git_sha'
    step = Step()
    step.name = 'build_packages'

    expected_failures = {
        'build_packages': {
            'failures': {},
            'first_failed_build': {
                'id': build_id,
                'number': build_number,
                'commit_id': 'git_sha'
            },
            'last_passed_build': None,
        },
    }

    self.assertEqual(expected_failures,
                     ChromeOSProjectAPI().GetCompileFailures(build, [step]))
