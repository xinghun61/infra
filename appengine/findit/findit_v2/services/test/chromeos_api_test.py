# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import json

from buildbucket_proto.build_pb2 import Build
from buildbucket_proto.build_pb2 import BuilderID
from buildbucket_proto.step_pb2 import Step
from google.appengine.ext import ndb

from findit_v2.model.compile_failure import CompileFailure
from findit_v2.model.compile_failure import CompileFailureGroup
from findit_v2.model.luci_build import LuciFailedBuild
from findit_v2.model.test_failure import TestFailure
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

    self.output_target1 = json.dumps({
        'category': 'chromeos-base',
        'packageName': 'target1'
    })
    self.output_target2 = json.dumps({
        'category': 'chromeos-base',
        'packageName': 'target2'
    })
    self.output_targets = [self.output_target1, self.output_target2]

  def _CreateBuildbucketBuild(self, build_id, build_number):
    build = Build(id=build_id, number=build_number)
    build.input.gitiles_commit.host = 'gitiles.host.com'
    build.input.gitiles_commit.project = 'project/name'
    build.input.gitiles_commit.ref = 'ref/heads/master'
    build.input.gitiles_commit.id = 'git_sha'
    return build

  def _CreateBuildbucketBuildForCompile(
      self,
      build_id,
      build_number,
      output_targets=None,
      step_name=None,
  ):
    build = self._CreateBuildbucketBuild(build_id, build_number)

    if output_targets:
      build.output.properties['compile_failures'] = {
          'failures': [{
              'output_targets': output_targets,
              'rule': 'emerge',
          },],
          'failed_step': step_name
      }
    return build

  def _CreateBuildbucketBuildForTest(self,
                                     build_id,
                                     build_number,
                                     step_name=None):
    build = self._CreateBuildbucketBuild(build_id, build_number)

    if step_name == 'no spec':
      build.output.properties['test_failures'] = {
          'xx_test_failures': [{
              'failed_step': step_name,
          },],
      }
    else:
      build.output.properties['test_failures'] = {
          'xx_test_failures': [{
              'failed_step': step_name,
              'test_spec': 'test_spec',
              'suite': 'suite'
          },],
      }
    return build

  def testCompileStep(self):
    compile_step_name = 'install packages|installation results'
    build_id = 8765432109123
    build_number = 123
    build = self._CreateBuildbucketBuildForCompile(
        build_id,
        build_number,
        self.output_targets,
        step_name=compile_step_name)
    step = Step()
    step.name = compile_step_name
    log = step.logs.add()
    log.name = 'stdout'
    self.assertEqual(StepTypeEnum.COMPILE,
                     ChromeOSProjectAPI().ClassifyStepType(build, step))

  def testInfraStepFromABuildWithCompileFailure(self):
    compile_step_name = 'install packages|installation results'
    build_id = 8765432109123
    build_number = 123
    build = self._CreateBuildbucketBuildForCompile(
        build_id,
        build_number,
        self.output_targets,
        step_name=compile_step_name)
    step = Step()
    step.name = 'Failure Reason'
    log = step.logs.add()
    log.name = 'reason'
    self.assertEqual(StepTypeEnum.INFRA,
                     ChromeOSProjectAPI().ClassifyStepType(build, step))

  def testInfraStepFromABuildWithCompileFailureNoFailedStep(self):
    compile_step_name = 'install packages|installation results'
    build_id = 8765432109123
    build_number = 123
    build = self._CreateBuildbucketBuildForCompile(build_id, build_number,
                                                   self.output_targets)
    step = Step()
    step.name = compile_step_name
    log = step.logs.add()
    log.name = 'reason'
    self.assertEqual(StepTypeEnum.INFRA,
                     ChromeOSProjectAPI().ClassifyStepType(build, step))

  def testTestStep(self):
    step_name = 'results|xx test results|[FAILED] <suite1>'
    build_id = 8765432109123
    build_number = 123
    build = self._CreateBuildbucketBuildForTest(
        build_id, build_number, step_name=step_name)
    step = Step()
    step.name = step_name
    self.assertEqual(StepTypeEnum.TEST,
                     ChromeOSProjectAPI().ClassifyStepType(build, step))

  def testInfraStepFromABuildWithTestStep(self):
    step_name = 'results|xx test results|[FAILED] <suite1>'
    build_id = 8765432109123
    build_number = 123
    build = self._CreateBuildbucketBuildForTest(
        build_id, build_number, step_name=step_name)
    step = Step()
    step.name = 'another_step'
    self.assertEqual(StepTypeEnum.INFRA,
                     ChromeOSProjectAPI().ClassifyStepType(build, step))

  def testInfraStepFromABuildWithoutCompileFailure(self):
    step_name = 'test step'
    build_id = 8765432109123
    build_number = 123
    build = self._CreateBuildbucketBuildForCompile(build_id, build_number)
    step = Step()
    step.name = step_name
    log = step.logs.add()
    log.name = 'reason'
    self.assertEqual(StepTypeEnum.INFRA,
                     ChromeOSProjectAPI().ClassifyStepType(build, step))

  def testGetCompileFailures(self):
    step_name = 'install packages'
    build_id = 8765432109123
    build_number = 123
    build = self._CreateBuildbucketBuildForCompile(
        build_id, build_number, self.output_targets, step_name=step_name)
    step = Step()
    step.name = step_name

    expected_failures = {
        'install packages': {
            'failures': {
                frozenset(self.output_targets): {
                    'properties': {
                        'rule': 'emerge',
                    },
                    'first_failed_build': {
                        'id': build_id,
                        'number': build_number,
                        'commit_id': 'git_sha',
                    },
                    'last_passed_build': None,
                },
            },
            'first_failed_build': {
                'id': build_id,
                'number': build_number,
                'commit_id': 'git_sha',
            },
            'last_passed_build': None,
        },
    }

    self.assertEqual(expected_failures,
                     ChromeOSProjectAPI().GetCompileFailures(build, [step]))

  def testGetCompileFailuresNoFailedStep(self):
    step_name = 'install packages'
    build_id = 8765432109123
    build_number = 123
    output_target = json.dumps({
        'category': 'chromeos-base',
        'packageName': 'target2',
    })
    build = self._CreateBuildbucketBuildForCompile(build_id, build_number,
                                                   [output_target])
    step = Step()
    step.name = step_name

    self.assertEqual({}, ChromeOSProjectAPI().GetCompileFailures(build, [step]))

  def testGetCompileFailuresNoFailure(self):
    step_name = 'install packages'
    build_id = 8765432109123
    build_number = 123
    build = self._CreateBuildbucketBuildForCompile(
        build_id, build_number, [], step_name=step_name)
    step = Step()
    step.name = step_name

    self.assertEqual({}, ChromeOSProjectAPI().GetCompileFailures(build, [step]))

  def testGetRerunBuilderId(self):
    build = Build(builder=self.builder)
    build.output.properties['BISECT_BUILDER'] = 'builder-bisect'

    self.assertEqual('chromeos/postsubmit/builder-bisect',
                     ChromeOSProjectAPI().GetRerunBuilderId(build))

  def testGetCompileRerunBuildInputProperties(self):
    targets = {'install packages': [self.output_target1]}

    expected_prop = {
        '$chromeos/cros_bisect': {
            'compile': {
                'targets': [self.output_target1],
            },
        },
    }

    self.assertEqual(
        expected_prop,
        ChromeOSProjectAPI().GetCompileRerunBuildInputProperties(targets))

  def testGetCompileRerunBuildInputPropertiesOtherStep(self):
    self.assertIsNone(ChromeOSProjectAPI().GetCompileRerunBuildInputProperties(
        {}))

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
        'commit_id': 'git_sha_121',
    }

    first_failures_in_current_build = {
        'failures': {
            'install packages': {
                'atomic_failures': [frozenset([self.output_target1])],
                'last_passed_build': last_passed_build_info,
            },
        },
        'last_passed_build': last_passed_build_info,
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

    last_passed_build_info = {
        'id': 8000000000121,
        'number': 121,
        'commit_id': 'git_sha_121',
    }

    first_failures_in_current_build = {
        'failures': {
            'install packages': {
                'atomic_failures': [
                    frozenset([self.output_target1]),
                    frozenset([self.output_target2]),
                ],
                'last_passed_build':
                    last_passed_build_info,
            },
        },
        'last_passed_build': last_passed_build_info,
    }

    compile_failure = CompileFailure.Create(
        self.group_build.key,
        'install packages', [self.output_target1],
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
        'commit_id': 'git_sha_121',
    }

    first_failures_in_current_build = {
        'failures': {
            'install packages': {
                'atomic_failures': [frozenset(['target1']),],
                'last_passed_build': last_passed_build_info,
            },
        },
        'last_passed_build': last_passed_build_info,
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
            frozenset(['target1']): self.group_build_id,
        }
    }

    self.assertEqual(
        expected_failures_with_existing_group,
        ChromeOSProjectAPI().GetFailuresWithMatchingCompileFailureGroups(
            self.context, build, first_failures_in_current_build))

  def testGetTestFailures(self):
    step_name = 'results|xx test results|[FAILED] <suite1>'
    build_id = 8765432109123
    build_number = 123
    build = self._CreateBuildbucketBuildForTest(
        build_id, build_number, step_name=step_name)
    step = Step()
    step.name = step_name

    expected_failures = {
        step_name: {
            'failures': {},
            'first_failed_build': {
                'id': build_id,
                'number': build_number,
                'commit_id': 'git_sha',
            },
            'last_passed_build': None,
            'properties': {
                'failure_type': 'xx_test_failures',
                'test_spec': 'test_spec',
                'suite': 'suite',
            }
        },
    }

    self.assertEqual(expected_failures,
                     ChromeOSProjectAPI().GetTestFailures(build, [step]))

  def testGetTestFailuresMalFormedOutput(self):
    step_name = 'no spec'
    build_id = 8765432109123
    build_number = 123
    build = self._CreateBuildbucketBuildForTest(
        build_id, build_number, step_name=step_name)
    step = Step()
    step.name = step_name

    expected_failures = {}

    self.assertEqual(expected_failures,
                     ChromeOSProjectAPI().GetTestFailures(build, [step]))

  def testGetFailuresWithMatchingTestFailureGroupsNoExistingGroup(self):
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
            'step': {
                'atomic_failures': [],
                'last_passed_build': last_passed_build_info,
            },
        },
        'last_passed_build': last_passed_build_info,
    }

    self.assertEqual(
        {},
        ChromeOSProjectAPI().GetFailuresWithMatchingTestFailureGroups(
            self.context, build, first_failures_in_current_build))

  def testGetTestRerunBuildInputProperties(self):
    tests = {
        'step1': {
            'tests': [],
            'properties': {
                'failure_type': 'xx_test_failures',
                'test_spec': 'test_spec1',
            }
        },
        'step2': {
            'tests': [],
            'properties': {
                'failure_type': 'xx_test_failures',
                'test_spec': 'test_spec2',
            }
        }
    }

    expected_input = {
        '$chromeos/cros_bisect': {
            'test': {
                'xx_test_failures': [{
                    'test_spec': 'test_spec2'
                }, {
                    'test_spec': 'test_spec1'
                }],
            },
        },
    }

    self.assertEqual(
        expected_input,
        ChromeOSProjectAPI().GetTestRerunBuildInputProperties(tests))

  def testGetFailureKeysToAnalyzeTestFailures(self):
    failure_entities = []
    for i in xrange(2):
      test_failure = TestFailure.Create(
          failed_build_key=ndb.Key(LuciFailedBuild, 8000000000123),
          step_ui_name='step%d.suite' % i,
          test=None,
          properties={'suite': 'suite'})
      failure_entities.append(test_failure)
    ndb.put_multi(failure_entities)
    analyzed_failure_keys = ChromeOSProjectAPI(
    ).GetFailureKeysToAnalyzeTestFailures(failure_entities)
    self.assertEqual(1, len(analyzed_failure_keys))

    deduped_failure_keys = set([f.key for f in failure_entities
                               ]) - set(analyzed_failure_keys)
    self.assertEqual(analyzed_failure_keys[0],
                     deduped_failure_keys.pop().get().merged_failure_key)

  def testGetFailureKeysToAnalyzeTestFailuresDidderentSuites(self):
    failure_entities = []
    for i in xrange(2):
      test_failure = TestFailure.Create(
          failed_build_key=ndb.Key(LuciFailedBuild, 8000000000123),
          step_ui_name='step.suite%d' % i,
          test=None,
          properties={'suite': 'suite%d' % i})
      failure_entities.append(test_failure)
    ndb.put_multi(failure_entities)
    analyzed_failure_keys = ChromeOSProjectAPI(
    ).GetFailureKeysToAnalyzeTestFailures(failure_entities)
    self.assertEqual(2, len(analyzed_failure_keys))
