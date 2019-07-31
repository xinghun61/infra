# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
from datetime import timedelta
import mock

from buildbucket_proto import common_pb2
from buildbucket_proto.build_pb2 import Build
from buildbucket_proto.build_pb2 import BuilderID
from buildbucket_proto.rpc_pb2 import SearchBuildsResponse
from buildbucket_proto.step_pb2 import Step

from common.waterfall import buildbucket_client
from findit_v2.model import luci_build
from findit_v2.model.gitiles_commit import GitilesCommit
from findit_v2.model.luci_build import LuciFailedBuild
from findit_v2.model.test_failure import TestFailure
from findit_v2.model.test_failure import TestFailureAnalysis
from findit_v2.model.test_failure import TestFailureGroup
from findit_v2.services.analysis.test_failure.test_analysis_api import (
    TestAnalysisAPI)
from findit_v2.services.chromium_api import ChromiumProjectAPI
from findit_v2.services.context import Context
from findit_v2.services.failure_type import StepTypeEnum
from services import git
from waterfall.test import wf_testcase


class TestAnalysisAPITest(wf_testcase.TestCase):

  def _GetBuildIdByNumber(self, build_number):
    """Mocks build_id by build_number to show monotonically decreasing."""
    return 8000000000200 - build_number

  def _MockBuild(self,
                 build_number,
                 build_id=None,
                 gitiles_commit_id=None,
                 builder_name='Linux Tests',
                 build_status=common_pb2.FAILURE):
    builder = BuilderID(project='chromium', bucket='ci', builder=builder_name)
    build_id = build_id or self._GetBuildIdByNumber(build_number)
    gitiles_commit_id = gitiles_commit_id or 'git_sha_%d' % build_number
    build = Build(
        id=build_id, builder=builder, number=build_number, status=build_status)
    build.input.gitiles_commit.host = 'gitiles.host.com'
    build.input.gitiles_commit.project = 'project/name'
    build.input.gitiles_commit.ref = 'ref/heads/master'
    build.input.gitiles_commit.id = gitiles_commit_id
    build.create_time.FromDatetime(self.create_time)
    build.start_time.FromDatetime(self.create_time + timedelta(minutes=1))
    build.end_time.FromDatetime(self.create_time + timedelta(minutes=30))
    return build

  def _GetBuildInfo(self, build_number):
    return {
        'id': self._GetBuildIdByNumber(build_number),
        'number': build_number,
        'commit_id': 'git_sha_%d' % build_number
    }

  def setUp(self):
    super(TestAnalysisAPITest, self).setUp()
    self.luci_project = 'chromium'
    self.gitiles_host = 'gitiles.host.com'
    self.gitiles_project = 'project/name'
    self.gitiles_ref = 'ref/heads/master'
    self.gitiles_id = 'git_sha_123'
    self.build_number = 123
    self.build_id = self._GetBuildIdByNumber(self.build_number)
    self.create_time = datetime(2019, 4, 9)

    self.context = Context(
        luci_project_name=self.luci_project,
        gitiles_host=self.gitiles_host,
        gitiles_project=self.gitiles_project,
        gitiles_ref=self.gitiles_ref,
        gitiles_id=self.gitiles_id)

    self.builder = BuilderID(
        project=self.luci_project, bucket='ci', builder='Linux Tests')

    self.build_info = self._GetBuildInfo(self.build_number)

    self.build = self._MockBuild(self.build_number)

    self.build_entity = LuciFailedBuild.Create(
        luci_project=self.luci_project,
        luci_bucket='ci',
        luci_builder='Linux Builder',
        build_id=9876543210,
        legacy_build_number=self.build_number,
        gitiles_host='chromium.googlesource.com',
        gitiles_project='chromium/src',
        gitiles_ref='refs/heads/master',
        gitiles_id=self.gitiles_id,
        commit_position=65450,
        status=20,
        create_time=datetime(2019, 3, 28),
        start_time=datetime(2019, 3, 28, 0, 1),
        end_time=datetime(2019, 3, 28, 1),
        build_failure_type=StepTypeEnum.TEST)
    self.build_entity.put()

    self.test_failure_1 = TestFailure.Create(
        failed_build_key=self.build_entity.key,
        step_ui_name='step_ui_name',
        test='test1',
        first_failed_build_id=self.build_id,
        failure_group_build_id=None)
    self.test_failure_1.put()
    self.test_failure_2 = TestFailure.Create(
        failed_build_key=self.build_entity.key,
        step_ui_name='step_ui_name',
        test='test2',
        first_failed_build_id=self.build_id,
        failure_group_build_id=None)
    self.test_failure_2.put()

    self.commits = []
    for i in xrange(0, 11):
      self.commits.append(self._CreateGitilesCommit('r%d' % i, 6000000 + i))

    self.analysis = TestFailureAnalysis.Create(
        luci_project=self.context.luci_project_name,
        luci_bucket=self.build.builder.bucket,
        luci_builder=self.build.builder.builder,
        build_id=self.build_id,
        gitiles_host=self.context.gitiles_host,
        gitiles_project=self.context.gitiles_project,
        gitiles_ref=self.context.gitiles_ref,
        last_passed_gitiles_id='left_sha',
        last_passed_commit_position=6000000,
        first_failed_gitiles_id=self.context.gitiles_id,
        first_failed_commit_position=6000005,
        rerun_builder_id='chromium/findit/findit-variables',
        test_failure_keys=[self.test_failure_1.key, self.test_failure_2.key])
    self.analysis.Save()

    self.analysis_api = TestAnalysisAPI()

  def _CreateGitilesCommit(self, gitiles_id, commit_position):
    return GitilesCommit(
        gitiles_host=self.context.gitiles_host,
        gitiles_project=self.context.gitiles_project,
        gitiles_ref=self.context.gitiles_ref,
        gitiles_id=gitiles_id,
        commit_position=commit_position)

  @mock.patch.object(ChromiumProjectAPI, 'GetTestFailures')
  @mock.patch.object(buildbucket_client, 'GetV2Build')
  @mock.patch.object(buildbucket_client, 'SearchV2BuildsOnBuilder')
  def testUpdateFailuresWithFirstFailureInfo(
      self, mock_prev_builds, mock_get_build, mock_prev_failures):
    """Test for the most common case: found both first_failed_build_id and
      last_passed_build_id."""
    mock_step = Step()
    mock_step.name = 'step_ui_name'
    mock_step.status = common_pb2.FAILURE
    build_122 = self._MockBuild(122)
    build_122.steps.extend([mock_step])
    build_122_info = self._GetBuildInfo(122)

    build_121 = self._MockBuild(121, build_status=common_pb2.SUCCESS)
    build_121_info = self._GetBuildInfo(121)

    mock_prev_builds.return_value = SearchBuildsResponse(
        builds=[build_122, build_121])
    mock_get_build.return_value = build_122

    failures = {
        frozenset(['test3']): {
            'properties': {},
            'first_failed_build': self.build_info,
            'last_passed_build': None,
        },
    }

    mock_prev_failures.return_value = {
        'step_ui_name': {
            'failures': failures,
            'first_failed_build': build_122_info,
            'last_passed_build': None,
        },
    }

    detailed_test_failures = {
        'step_ui_name': {
            'failures': failures,
            'first_failed_build': self.build_info,
            'last_passed_build': None,
        },
    }

    self.analysis_api.UpdateFailuresWithFirstFailureInfo(
        self.context, self.build, detailed_test_failures)

    expected_failures = {
        'step_ui_name': {
            'failures': failures,
            'first_failed_build': build_122_info,
            'last_passed_build': build_121_info,
        },
    }

    self.assertEqual(expected_failures, detailed_test_failures)

  @mock.patch.object(buildbucket_client, 'GetV2Build')
  @mock.patch.object(buildbucket_client, 'SearchV2BuildsOnBuilder')
  def testUpdateFailuresWithFirstFailureInfoPrevBuildDifferentStep(
      self, mock_prev_builds, mock_get_build):
    """Test for previous build failed with different steps."""
    mock_step = Step()
    mock_step.name = 'test'
    mock_step.status = common_pb2.FAILURE
    mock_step1 = Step()
    mock_step1.name = 'step_ui_name'
    mock_step1.status = common_pb2.SUCCESS
    build_122 = self._MockBuild(122)
    build_122.steps.extend([mock_step, mock_step1])
    build_122_info = self._GetBuildInfo(122)

    build_121 = self._MockBuild(121, build_status=common_pb2.SUCCESS)

    mock_prev_builds.return_value = SearchBuildsResponse(
        builds=[build_122, build_121])
    mock_get_build.return_value = build_122

    failures = {
        frozenset(['test3']): {
            'properties': {},
            'first_failed_build': self.build_info,
            'last_passed_build': None,
        },
    }

    detailed_test_failures = {
        'step_ui_name': {
            'failures': failures,
            'first_failed_build': self.build_info,
            'last_passed_build': None,
        },
    }

    self.analysis_api.UpdateFailuresWithFirstFailureInfo(
        self.context, self.build, detailed_test_failures)

    expected_failures = {
        'step_ui_name': {
            'failures': failures,
            'first_failed_build': self.build_info,
            'last_passed_build': build_122_info,
        },
    }
    self.assertEqual(expected_failures, detailed_test_failures)

  @mock.patch.object(buildbucket_client, 'GetV2Build')
  @mock.patch.object(buildbucket_client, 'SearchV2BuildsOnBuilder')
  def testUpdateFailuresWithFirstFailureInfoPrevBuildNoSameStep(
      self, mock_prev_builds, mock_get_build):
    """Test for previous build didn't run the same step."""
    mock_step = Step()
    mock_step.name = 'test'
    mock_step.status = common_pb2.FAILURE
    build_122 = self._MockBuild(122)
    build_122.steps.extend([mock_step])

    build_121 = self._MockBuild(121, build_status=common_pb2.SUCCESS)
    build_121_info = self._GetBuildInfo(121)

    mock_prev_builds.return_value = SearchBuildsResponse(
        builds=[build_122, build_121])
    mock_get_build.return_value = build_122

    failure = {
        frozenset(['test3']): {
            'properties': {},
            'first_failed_build': self.build_info,
            'last_passed_build': None,
        },
    }
    detailed_test_failures = {
        'step_ui_name': {
            'failures': failure,
            'first_failed_build': self.build_info,
            'last_passed_build': None,
        },
    }

    self.analysis_api.UpdateFailuresWithFirstFailureInfo(
        self.context, self.build, detailed_test_failures)

    expected_failures = {
        'step_ui_name': {
            'failures': failure,
            'first_failed_build': self.build_info,
            'last_passed_build': build_121_info,
        },
    }
    self.assertEqual(expected_failures, detailed_test_failures)

  @mock.patch.object(ChromiumProjectAPI, 'GetTestFailures')
  @mock.patch.object(buildbucket_client, 'GetV2Build')
  @mock.patch.object(buildbucket_client, 'SearchV2BuildsOnBuilder')
  def testUpdateFailuresWithFirstFailureInfoDifferentFirstFailure(
      self, mock_prev_builds, mock_get_build, mock_prev_failures):
    """Test for same tests in current build failed from different builds."""
    mock_step = Step()
    mock_step.name = 'step_ui_name'
    mock_step.status = common_pb2.FAILURE
    build_122 = self._MockBuild(122)
    build_122.steps.extend([mock_step])
    build_122_info = self._GetBuildInfo(122)

    mock_step1 = Step()
    mock_step1.name = 'step_ui_name'
    mock_step1.status = common_pb2.FAILURE
    build_121 = self._MockBuild(121)
    build_121.steps.extend([mock_step1])
    build_121_info = self._GetBuildInfo(121)

    mock_step2 = Step()
    mock_step2.name = 'step_ui_name'
    mock_step2.status = common_pb2.FAILURE
    build_120 = self._MockBuild(120)
    build_120.steps.extend([mock_step2])
    build_120_info = self._GetBuildInfo(120)

    mock_prev_builds.return_value = SearchBuildsResponse(
        builds=[build_122, build_121, build_120])
    mock_get_build.side_effect = [build_122, build_121, build_120]

    # Test4 failed but test3 passed.
    failures_122 = {
        'step_ui_name': {
            'failures': {
                frozenset(['test4']): {
                    'properties': {},
                    'first_failed_build': build_122_info,
                    'last_passed_build': None,
                },
            },
            'first_failed_build': build_122_info,
            'last_passed_build': None,
        },
    }
    # Has the same failed tests as current build.
    failures_121 = {
        'step_ui_name': {
            'failures': {
                frozenset(['test4']): {
                    'properties': {},
                    'first_failed_build': build_121_info,
                    'last_passed_build': None,
                },
                frozenset(['test3']): {
                    'properties': {},
                    'first_failed_build': build_121_info,
                    'last_passed_build': None,
                },
            },
            'first_failed_build': build_121_info,
            'last_passed_build': None,
        },
    }
    # The same step failed, but with a different test.
    failures_120 = {
        'step_ui_name': {
            'failures': {
                frozenset(['test5']): {
                    'properties': {},
                    'first_failed_build': build_120_info,
                    'last_passed_build': None,
                },
            },
            'first_failed_build': build_120_info,
            'last_passed_build': None,
        },
    }
    mock_prev_failures.side_effect = [failures_122, failures_121, failures_120]

    detailed_test_failures = {
        'step_ui_name': {
            'failures': {
                frozenset(['test3']): {
                    'properties': {},
                    'first_failed_build': self.build_info,
                    'last_passed_build': None,
                },
                frozenset(['test4']): {
                    'properties': {},
                    'first_failed_build': self.build_info,
                    'last_passed_build': None,
                },
            },
            'first_failed_build': self.build_info,
            'last_passed_build': None,
        },
    }

    self.analysis_api.UpdateFailuresWithFirstFailureInfo(
        self.context, self.build, detailed_test_failures)

    expected_failures = {
        'step_ui_name': {
            'failures': {
                frozenset(['test3']): {
                    'properties': {},
                    'first_failed_build': self.build_info,
                    'last_passed_build': build_122_info,
                },
                frozenset(['test4']): {
                    'properties': {},
                    'first_failed_build': build_121_info,
                    'last_passed_build': build_120_info,
                },
            },
            'first_failed_build': build_121_info,
            'last_passed_build': build_120_info,
        },
    }

    self.assertEqual(expected_failures, detailed_test_failures)

  @mock.patch.object(buildbucket_client, 'GetV2Build')
  @mock.patch.object(buildbucket_client, 'SearchV2BuildsOnBuilder')
  def testUpdateFailuresWithFirstFailureInfoPrevBuildInfraFailure(
      self, mock_prev_builds, mock_get_build):
    """Test for previous build failed with different steps."""
    mock_step1 = Step()
    mock_step1.name = 'step_ui_name'
    mock_step1.status = common_pb2.INFRA_FAILURE
    build_122 = self._MockBuild(122)
    build_122.steps.extend([mock_step1])

    build_121 = self._MockBuild(121, build_status=common_pb2.SUCCESS)
    build_121_info = self._GetBuildInfo(121)

    mock_prev_builds.return_value = SearchBuildsResponse(
        builds=[build_122, build_121])
    mock_get_build.return_value = build_122

    detailed_test_failures = {
        'step_ui_name': {
            'failures': {
                frozenset(['test3']): {
                    'properties': {},
                    'first_failed_build': self.build_info,
                    'last_passed_build': None,
                },
            },
            'first_failed_build': self.build_info,
            'last_passed_build': None,
        },
    }

    self.analysis_api.UpdateFailuresWithFirstFailureInfo(
        self.context, self.build, detailed_test_failures)

    expected_failures = {
        'step_ui_name': {
            'failures': {
                frozenset(['test3']): {
                    'properties': {},
                    'first_failed_build': self.build_info,
                    'last_passed_build': build_121_info,
                },
            },
            'first_failed_build': self.build_info,
            'last_passed_build': build_121_info,
        },
    }
    self.assertEqual(expected_failures, detailed_test_failures)

  def testGetFirstFailuresInCurrentBuild(self):
    build_122_info = self._GetBuildInfo(122)

    failures = {
        'step_ui_name': {
            'failures': {
                frozenset(['test3']): {
                    'properties': {},
                    'first_failed_build': self.build_info,
                    'last_passed_build': build_122_info,
                },
            },
            'first_failed_build': self.build_info,
            'last_passed_build': build_122_info,
        },
    }

    expected_res = {
        'failures': {
            'step_ui_name': {
                'atomic_failures': [frozenset(['test3'])],
                'last_passed_build': build_122_info,
            },
        },
        'last_passed_build': build_122_info
    }

    self.assertEqual(
        expected_res,
        self.analysis_api.GetFirstFailuresInCurrentBuild(
            self.context, self.build, failures))

  def testGetFirstFailuresInCurrentBuildNoFirstFailures(self):
    build_122_info = self._GetBuildInfo(122)
    build_121_info = self._GetBuildInfo(121)

    failures = {
        'step_ui_name': {
            'failures': {
                frozenset(['test3']): {
                    'properties': {},
                    'first_failed_build': build_122_info,
                    'last_passed_build': build_121_info,
                },
            },
            'first_failed_build': build_122_info,
            'last_passed_build': build_121_info,
        },
    }

    expected_res = {'failures': {}, 'last_passed_build': None}

    self.assertEqual(
        expected_res,
        self.analysis_api.GetFirstFailuresInCurrentBuild(
            self.context, self.build, failures))

  def testGetFirstFailuresInCurrentBuildNoLastPass(self):

    failures = {
        'step_ui_name': {
            'failures': {
                frozenset(['test3']): {
                    'properties': {},
                    'first_failed_build': self.build_info,
                    'last_passed_build': None,
                },
            },
            'first_failed_build': self.build_info,
            'last_passed_build': None,
        },
    }

    expected_res = {'failures': {}, 'last_passed_build': None}

    self.assertEqual(
        expected_res,
        self.analysis_api.GetFirstFailuresInCurrentBuild(
            self.context, self.build, failures))

  def testGetFirstFailuresInCurrentBuildOnlyStep(self):
    build_122_info = self._GetBuildInfo(122)

    failures = {
        'step_ui_name': {
            'failures': {},
            'first_failed_build': self.build_info,
            'last_passed_build': build_122_info,
        },
    }

    expected_res = {
        'failures': {
            'step_ui_name': {
                'atomic_failures': [],
                'last_passed_build': build_122_info,
            },
        },
        'last_passed_build': build_122_info
    }

    self.assertEqual(
        expected_res,
        self.analysis_api.GetFirstFailuresInCurrentBuild(
            self.context, self.build, failures))

  def testGetFirstFailuresInCurrentBuildOnlyStepFailedBefore(self):
    build_122_info = self._GetBuildInfo(122)
    build_121_info = self._GetBuildInfo(121)

    failures = {
        'step_ui_name': {
            'failures': {},
            'first_failed_build': build_122_info,
            'last_passed_build': build_121_info,
        },
    }

    expected_res = {'failures': {}, 'last_passed_build': None}

    self.assertEqual(
        expected_res,
        self.analysis_api.GetFirstFailuresInCurrentBuild(
            self.context, self.build, failures))

  def testGetFirstFailuresInCurrentBuildFailureStartedInDifferentBuild(self):
    build_122_info = self._GetBuildInfo(122)
    build_121_info = self._GetBuildInfo(121)

    failures = {
        'step_ui_name': {
            'failures': {
                frozenset(['test3']): {
                    'properties': {},
                    'first_failed_build': self.build_info,
                    'last_passed_build': build_122_info,
                },
                frozenset(['test4']): {
                    'properties': {},
                    'first_failed_build': build_122_info,
                    'last_passed_build': None,
                },
                frozenset(['test5']): {
                    'properties': {},
                    'first_failed_build': self.build_info,
                    'last_passed_build': build_121_info,
                },
            },
            'first_failed_build': build_122_info,
            'last_passed_build': None,
        },
    }

    expected_res = {
        'failures': {
            'step_ui_name': {
                'atomic_failures': [frozenset(['test5']),
                                    frozenset(['test3'])],
                'last_passed_build':
                    build_121_info,
            },
        },
        'last_passed_build': build_121_info
    }
    self.assertEqual(
        expected_res,
        self.analysis_api.GetFirstFailuresInCurrentBuild(
            self.context, self.build, failures))

  @mock.patch.object(git, 'GetCommitPositionFromRevision', return_value=67890)
  def testSaveFailures(self, _):
    build_121_info = self._GetBuildInfo(121)
    build_120_info = self._GetBuildInfo(120)
    detailed_test_failures = {
        'step_ui_name': {
            'failures': {
                frozenset(['test3']): {
                    'properties': {},
                    'first_failed_build': build_121_info,
                    'last_passed_build': build_120_info,
                },
            },
            'first_failed_build': build_121_info,
            'last_passed_build': build_120_info,
        },
    }

    # Prepares data for existing failure group.
    group_build = self._MockBuild(
        12134, 8000003412134, 'git_sha_121', builder_name='Mac')
    group_build_entity = luci_build.SaveFailedBuild(self.context, group_build,
                                                    StepTypeEnum.TEST)
    group_failure = TestFailure.Create(group_build_entity.key, 'step_ui_name',
                                       'test3')
    group_failure.put()

    # Prepares data for first failed build.
    first_failed_build = self._MockBuild(121)
    first_failed_build_entity = luci_build.SaveFailedBuild(
        self.context, first_failed_build, StepTypeEnum.TEST)
    first_failure = TestFailure.Create(first_failed_build_entity.key,
                                       'step_ui_name', 'test3')
    first_failure.merged_failure_key = group_failure.key
    first_failure.put()

    self.analysis_api.SaveFailures(self.context, self.build,
                                   detailed_test_failures)

    build = LuciFailedBuild.get_by_id(self.build_id)
    self.assertIsNotNone(build)

    test_failures = TestFailure.query(ancestor=build.key).fetch()
    self.assertEqual(1, len(test_failures))
    self.assertEqual(
        self._GetBuildIdByNumber(121), test_failures[0].first_failed_build_id)
    self.assertEqual(group_failure.key, test_failures[0].merged_failure_key)

  @mock.patch.object(git, 'GetCommitPositionFromRevision', return_value=67890)
  def testSaveFailuresOnlyStepLevelFailures(self, _):
    detailed_test_failures = {
        'step_ui_name': {
            'failures': {},
            'first_failed_build': self._GetBuildInfo(121),
            'last_passed_build': self._GetBuildInfo(120),
        },
    }

    # Prepares data for first failed build.
    first_failed_build = self._MockBuild(121)
    first_failed_build_entity = luci_build.SaveFailedBuild(
        self.context, first_failed_build, StepTypeEnum.TEST)
    first_failure = TestFailure.Create(first_failed_build_entity.key,
                                       'step_ui_name', None)
    first_failure.put()

    self.analysis_api.SaveFailures(self.context, self.build,
                                   detailed_test_failures)

    build_entity = LuciFailedBuild.get_by_id(self.build_id)
    self.assertIsNotNone(build_entity)

    test_failures = TestFailure.query(ancestor=build_entity.key).fetch()
    self.assertEqual(1, len(test_failures))
    self.assertEqual(
        self._GetBuildIdByNumber(121), test_failures[0].first_failed_build_id)
    self.assertEqual(frozenset([]), test_failures[0].GetFailureIdentifier())
    self.assertEqual(first_failure.key, test_failures[0].merged_failure_key)

  @mock.patch.object(
      ChromiumProjectAPI,
      'GetRerunBuilderId',
      return_value='chromium/findit/findit_variables')
  @mock.patch.object(
      git, 'GetCommitPositionFromRevision', side_effect=[66680, 66666, 66680])
  def testSaveFailureAnalysis(self, *_):
    build_120_info = self._GetBuildInfo(120)

    detailed_test_failures = {
        'step_ui_name': {
            'failures': {
                frozenset(['test3']): {
                    'properties': {
                        'properties': {},
                    },
                    'first_failed_build': self.build_info,
                    'last_passed_build': build_120_info,
                },
                frozenset(['test4']): {
                    'properties': {
                        'properties': {},
                    },
                    'first_failed_build': self.build_info,
                    'last_passed_build': None,
                },
            },
            'first_failed_build': self.build_info,
            'last_passed_build': build_120_info,
        },
    }

    self.analysis_api.SaveFailures(self.context, self.build,
                                   detailed_test_failures)

    first_failures_in_current_build = {
        'failures': {
            'step_ui_name': {
                'atomic_failures': [frozenset(['test3'])],
                'last_passed_build': build_120_info,
            },
        },
        'last_passed_build': build_120_info
    }
    self.analysis_api.SaveFailureAnalysis(
        ChromiumProjectAPI(), self.context, self.build,
        first_failures_in_current_build, False)

    analysis = TestFailureAnalysis.GetVersion(self.build_id)
    self.assertIsNotNone(analysis)
    self.assertEqual('git_sha_120', analysis.last_passed_commit.gitiles_id)
    self.assertEqual(66666, analysis.last_passed_commit.commit_position)
    self.assertEqual('chromium/findit/findit_variables',
                     analysis.rerun_builder_id)
    self.assertEqual(1, len(analysis.test_failure_keys))
    self.assertItemsEqual('test3', analysis.test_failure_keys[0].get().test)

  @mock.patch.object(
      ChromiumProjectAPI,
      'GetRerunBuilderId',
      return_value='chromium/findit/findit_variables')
  @mock.patch.object(
      git, 'GetCommitPositionFromRevision', side_effect=[66680, 66666, 66680])
  def testSaveFailureAnalysisWithGroup(self, *_):
    build_120_info = self._GetBuildInfo(120)

    detailed_test_failures = {
        'step_ui_name': {
            'failures': {
                frozenset(['test3']): {
                    'properties': {
                        'properties': {},
                    },
                    'first_failed_build': self.build_info,
                    'last_passed_build': build_120_info,
                },
                frozenset(['test4']): {
                    'properties': {
                        'properties': {},
                    },
                    'first_failed_build': self.build_info,
                    'last_passed_build': None,
                },
            },
            'first_failed_build': self.build_info,
            'last_passed_build': build_120_info,
        },
    }

    self.analysis_api.SaveFailures(self.context, self.build,
                                   detailed_test_failures)

    first_failures_in_current_build = {
        'failures': {
            'step_ui_name': {
                'atomic_failures': [frozenset(['test3'])],
                'last_passed_build': build_120_info,
            },
        },
        'last_passed_build': build_120_info
    }
    self.analysis_api.SaveFailureAnalysis(ChromiumProjectAPI(), self.context,
                                          self.build,
                                          first_failures_in_current_build, True)

    analysis = TestFailureAnalysis.GetVersion(self.build_id)
    self.assertIsNotNone(analysis)
    self.assertEqual('git_sha_120', analysis.last_passed_commit.gitiles_id)
    self.assertEqual(66666, analysis.last_passed_commit.commit_position)
    self.assertEqual('chromium/findit/findit_variables',
                     analysis.rerun_builder_id)
    self.assertEqual(1, len(analysis.test_failure_keys))
    self.assertItemsEqual('test3', analysis.test_failure_keys[0].get().test)

    group = TestFailureGroup.get_by_id(self.build_id)
    self.assertIsNotNone(group)
    self.assertEqual('git_sha_120', analysis.last_passed_commit.gitiles_id)
    self.assertEqual(self.build_info['commit_id'],
                     analysis.first_failed_commit.gitiles_id)

  @mock.patch.object(
      ChromiumProjectAPI,
      'GetFailuresWithMatchingTestFailureGroups',
      return_value={})
  def testGetFirstFailuresInCurrentBuildWithoutGroupNoExistingGroup(self, _):
    self.assertEqual(
        {},
        self.analysis_api.GetFirstFailuresInCurrentBuildWithoutGroup(
            ChromiumProjectAPI(), self.context, self.build, {}))

  @mock.patch.object(
      git, 'GetCommitPositionFromRevision', side_effect=[66680, 66666, 66680])
  @mock.patch.object(
      ChromiumProjectAPI,
      'GetFailuresWithMatchingTestFailureGroups',
      return_value={
          'step_ui_name': {
              frozenset(['test1']): 8000000000134,
              frozenset(['test2']): 8000000000134
          }
      })
  def testGetFirstFailuresInCurrentBuildWithoutGroup(self, *_):
    build_121_info = self._GetBuildInfo(121)
    first_failures_in_current_build = {
        'failures': {
            'step_ui_name': {
                'atomic_failures': [frozenset(['test1']),
                                    frozenset(['test2'])],
                'last_passed_build':
                    build_121_info,
            },
        },
        'last_passed_build': build_121_info
    }

    # Creates and saves entities of the existing group.
    detailed_test_failures = {
        'step_ui_name': {
            'failures': {
                frozenset(['test1']): {
                    'properties': {
                        'properties': {},
                    },
                    'first_failed_build': self.build_info,
                    'last_passed_build': build_121_info,
                },
                frozenset(['test2']): {
                    'properties': {
                        'properties': {},
                    },
                    'first_failed_build': self.build_info,
                    'last_passed_build': build_121_info,
                },
            },
            'first_failed_build': self.build_info,
            'last_passed_build': build_121_info,
        },
    }

    self.analysis_api.SaveFailures(self.context, self.build,
                                   detailed_test_failures)

    # Prepares data for existing failure group.
    group_build = self._MockBuild(
        12134,
        build_id=8000000000134,
        gitiles_commit_id='git_sha_134',
        builder_name='Mac')
    group_build_entity = luci_build.SaveFailedBuild(self.context, group_build,
                                                    StepTypeEnum.TEST)
    group_failure1 = TestFailure.Create(group_build_entity.key, 'step_ui_name',
                                        'test1')
    group_failure1.put()
    group_failure2 = TestFailure.Create(group_build_entity.key, 'step_ui_name',
                                        'test2')
    group_failure2.put()

    self.assertEqual(
        {
            'failures': {},
            'last_passed_build': None
        },
        self.analysis_api.GetFirstFailuresInCurrentBuildWithoutGroup(
            ChromiumProjectAPI(), self.context, self.build,
            first_failures_in_current_build))

    build = LuciFailedBuild.get_by_id(self.build_id)
    test_failures = TestFailure.query(ancestor=build.key).fetch()
    self.assertEqual(2, len(test_failures))

    for failure in test_failures:
      if failure.test == 'test1':
        self.assertEqual(group_failure1.key, failure.merged_failure_key)
      else:
        self.assertEqual(group_failure2.key, failure.merged_failure_key)

  @mock.patch.object(
      git, 'GetCommitPositionFromRevision', side_effect=[66680, 66666, 66680])
  @mock.patch.object(ChromiumProjectAPI,
                     'GetFailuresWithMatchingTestFailureGroups')
  def testGetFirstFailuresInCurrentBuildWithoutGroupExistingGroupForSameBuild(
      self, mock_get_failures_w_group, _):
    build_121_info = self._GetBuildInfo(121)
    first_failures_in_current_build = {
        'failures': {
            'step_ui_name': {
                'atomic_failures': [frozenset(['test1']),
                                    frozenset(['test2'])],
                'last_passed_build':
                    build_121_info,
            },
        },
        'last_passed_build': build_121_info
    }

    # Creates and saves entities of the existing group.
    detailed_test_failures = {
        'step_ui_name': {
            'failures': {
                frozenset(['test1']): {
                    'properties': {},
                    'first_failed_build': self.build_info,
                    'last_passed_build': build_121_info,
                },
                frozenset(['test2']): {
                    'properties': {},
                    'first_failed_build': self.build_info,
                    'last_passed_build': build_121_info,
                },
            },
            'first_failed_build': self.build_info,
            'last_passed_build': build_121_info,
        },
    }

    mock_get_failures_w_group.return_value = {
        'step_ui_name': {
            frozenset(['test1']): self._GetBuildIdByNumber(123)
        }
    }

    self.analysis_api.SaveFailures(self.context, self.build,
                                   detailed_test_failures)

    expected_result = {
        'failures': {
            'step_ui_name': {
                'atomic_failures': [frozenset(['test1']),
                                    frozenset(['test2'])],
                'last_passed_build':
                    build_121_info,
            },
        },
        'last_passed_build': build_121_info
    }
    self.assertEqual(
        expected_result,
        self.analysis_api.GetFirstFailuresInCurrentBuildWithoutGroup(
            ChromiumProjectAPI(), self.context, self.build,
            first_failures_in_current_build))
