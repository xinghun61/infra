# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import json

from buildbucket_proto.build_pb2 import Build
from buildbucket_proto.build_pb2 import BuilderID
from buildbucket_proto.step_pb2 import Step

from findit_v2.model.compile_failure import CompileFailure
from findit_v2.model.compile_failure import CompileFailureGroup
from findit_v2.model.luci_build import LuciFailedBuild
from findit_v2.services.chromeos_api import ChromeOSProjectAPI
from findit_v2.services.context import Context
from findit_v2.services.failure_type import StepTypeEnum
from waterfall.test import wf_testcase


class ChromeOSProjectAPITest(wf_testcase.TestCase):

  def setUp(self):
    super(ChromeOSProjectAPITest, self).setUp()
    self.first_failed_commit_id = 'git_sha'
    self.first_failed_commit_position = 65450
    self.context = Context(
        luci_project_name='chromeos',
        gitiles_host='gitiles.host.com',
        gitiles_project='project/name',
        gitiles_ref='ref/heads/master',
        gitiles_id='git_sha')

    self.builder = BuilderID(
        project='chromeos', bucket='postsubmit', builder='builder-postsubmit')

    self.group_build_id = 8000000000189
    self.group_build = LuciFailedBuild.Create(
        luci_project=self.context.luci_project_name,
        luci_bucket=self.builder.bucket,
        luci_builder='builder2-postsubmit',
        build_id=self.group_build_id,
        legacy_build_number=12345,
        gitiles_host=self.context.gitiles_host,
        gitiles_project=self.context.gitiles_project,
        gitiles_ref=self.context.gitiles_ref,
        gitiles_id=self.context.gitiles_id,
        commit_position=self.first_failed_commit_position,
        status=20,
        create_time=datetime(2019, 3, 28),
        start_time=datetime(2019, 3, 28, 0, 1),
        end_time=datetime(2019, 3, 28, 1),
        build_failure_type=StepTypeEnum.COMPILE)
    self.group_build.put()

  def testCompileStep(self):
    step = Step()
    step.name = 'install packages'
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
    output_target1 = json.dumps({
        'category': 'chromeos-base',
        'packageName': 'target1'
    })
    output_target2 = json.dumps({
        'category': 'chromeos-base',
        'packageName': 'target2'
    })
    build.output.properties['build_compile_failure_output'] = {
        'failures': [{
            'output_targets': [output_target1, output_target2],
            'rule': 'emerge'
        },]
    }
    step = Step()
    step.name = 'install packages'

    expected_failures = {
        'install packages': {
            'failures': {
                frozenset([output_target1, output_target2]): {
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
    step.name = 'install packages'

    expected_failures = {
        'install packages': {
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

  def testGetRerunBuilderId(self):
    build = Build(builder=self.builder)
    build.output.properties['BISECT_BUILDER'] = 'builder-bisect'

    self.assertEqual('chromeos/postsubmit/builder-bisect',
                     ChromeOSProjectAPI().GetRerunBuilderId(build))

  def testGetCompileRerunBuildInputProperties(self):
    build_target = 'abc'
    output_target1 = json.dumps({
        'category': 'chromeos-base',
        'packageName': 'target1'
    })
    targets = {'install packages': [output_target1]}

    build = Build()
    build.input.properties['build_target'] = {'name': build_target}

    expected_prop = {
        'recipe': 'build_target',
        'build_target': {
            'name': build_target
        },
        '$chromeos/cros_bisect': {
            'targets': [output_target1]
        },
    }

    self.assertEqual(
        expected_prop,
        ChromeOSProjectAPI().GetCompileRerunBuildInputProperties(
            build, targets))

  def testGetCompileRerunBuildInputPropertiesOtherStep(self):
    build_target = 'abc'
    output_target1 = json.dumps({
        'category': 'chromeos-base',
        'packageName': 'target1'
    })
    targets = {'compile': [output_target1]}

    build = Build()
    build.input.properties['build_target'] = {'name': build_target}

    self.assertIsNone(ChromeOSProjectAPI().GetCompileRerunBuildInputProperties(
        build, targets))

  def testGetFailuresWithMatchingCompileFailureGroupsNoExistingGroup(self):
    build_id = 8000000000122
    build = Build(builder=self.builder, number=122, id=build_id)
    build.input.gitiles_commit.host = 'gitiles.host.com'
    build.input.gitiles_commit.project = 'project/name'
    build.input.gitiles_commit.ref = 'ref/heads/master'
    build.input.gitiles_commit.id = 'git_sha'

    last_passed_build_info = {
        'id': 8000000000121,
        'number': 121,
        'commit_id': 'git_sha_121'
    }

    output_target1 = json.dumps({
        'category': 'chromeos-base',
        'packageName': 'target1'
    })

    first_failures_in_current_build = {
        'failures': {
            'install packages': {
                'output_targets': [frozenset([output_target1])],
                'last_passed_build': last_passed_build_info,
            },
        },
        'last_passed_build': last_passed_build_info
    }

    self.assertEqual(
        {},
        ChromeOSProjectAPI().GetFailuresWithMatchingCompileFailureGroups(
            self.context, build, first_failures_in_current_build))

  def testGetFailuresWithMatchingCompileFailureGroupsFailureNotExactlySame(
      self):
    build_id = 8000000000122
    build = Build(builder=self.builder, number=122, id=build_id)
    build.input.gitiles_commit.host = 'gitiles.host.com'
    build.input.gitiles_commit.project = 'project/name'
    build.input.gitiles_commit.ref = 'ref/heads/master'
    build.input.gitiles_commit.id = 'git_sha'

    output_target1 = json.dumps({
        'category': 'chromeos-base',
        'packageName': 'target1'
    })
    output_target2 = json.dumps({
        'category': 'chromeos-base',
        'packageName': 'target2'
    })

    last_passed_build_info = {
        'id': 8000000000121,
        'number': 121,
        'commit_id': 'git_sha_121'
    }

    first_failures_in_current_build = {
        'failures': {
            'install packages': {
                'output_targets': [
                    frozenset([output_target1]),
                    frozenset([output_target2])
                ],
                'last_passed_build':
                    last_passed_build_info,
            },
        },
        'last_passed_build': last_passed_build_info
    }

    compile_failure = CompileFailure.Create(
        self.group_build.key,
        'install packages', [output_target1],
        'CXX',
        first_failed_build_id=self.group_build_id,
        last_passed_build_id=8000000000160)
    compile_failure.put()

    CompileFailureGroup.Create(
        luci_project=self.context.luci_project_name,
        luci_bucket=build.builder.bucket,
        build_id=self.group_build_id,
        gitiles_host=self.context.gitiles_host,
        gitiles_project=self.context.gitiles_project,
        gitiles_ref=self.context.gitiles_ref,
        last_passed_gitiles_id=last_passed_build_info['commit_id'],
        last_passed_commit_position=654321,
        first_failed_gitiles_id=self.first_failed_commit_id,
        first_failed_commit_position=654340,
        compile_failure_keys=[compile_failure.key]).put()

    self.assertEqual(
        {},
        ChromeOSProjectAPI().GetFailuresWithMatchingCompileFailureGroups(
            self.context, build, first_failures_in_current_build))

  def testGetFailuresWithMatchingCompileFailureGroupsWithExistingGroup(self):
    build_id = 8000000000122
    build = Build(builder=self.builder, number=122, id=build_id)
    build.input.gitiles_commit.host = 'gitiles.host.com'
    build.input.gitiles_commit.project = 'project/name'
    build.input.gitiles_commit.ref = 'ref/heads/master'
    build.input.gitiles_commit.id = 'git_sha'

    last_passed_build_info = {
        'id': 8000000000121,
        'number': 121,
        'commit_id': 'git_sha_121'
    }

    first_failures_in_current_build = {
        'failures': {
            'install packages': {
                'output_targets': [frozenset(['target1']),],
                'last_passed_build': last_passed_build_info,
            },
        },
        'last_passed_build': last_passed_build_info
    }

    compile_failure = CompileFailure.Create(
        self.group_build.key,
        'install packages', ['target1'],
        'CXX',
        first_failed_build_id=self.group_build_id,
        last_passed_build_id=8000000000160)
    compile_failure.put()

    CompileFailureGroup.Create(
        luci_project=self.context.luci_project_name,
        luci_bucket=build.builder.bucket,
        build_id=self.group_build_id,
        gitiles_host=self.context.gitiles_host,
        gitiles_project=self.context.gitiles_project,
        gitiles_ref=self.context.gitiles_ref,
        last_passed_gitiles_id=last_passed_build_info['commit_id'],
        last_passed_commit_position=654321,
        first_failed_gitiles_id=self.first_failed_commit_id,
        first_failed_commit_position=654340,
        compile_failure_keys=[compile_failure.key]).put()

    expected_failures_with_existing_group = {
        'install packages': {
            frozenset(['target1']): self.group_build_id
        }
    }

    self.assertEqual(
        expected_failures_with_existing_group,
        ChromeOSProjectAPI().GetFailuresWithMatchingCompileFailureGroups(
            self.context, build, first_failures_in_current_build))
