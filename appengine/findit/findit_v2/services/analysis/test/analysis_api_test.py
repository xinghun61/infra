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
from findit_v2.model.compile_failure import CompileFailure
from findit_v2.model.compile_failure import CompileFailureAnalysis
from findit_v2.model.compile_failure import CompileFailureGroup
from findit_v2.model.gitiles_commit import GitilesCommit
from findit_v2.model.luci_build import LuciFailedBuild
from findit_v2.services.analysis.compile_failure.compile_analysis_api import (
    CompileAnalysisAPI)
from findit_v2.services.chromium_api import ChromiumProjectAPI
from findit_v2.services.context import Context
from findit_v2.services.failure_type import StepTypeEnum
from services import git
from waterfall.test import wf_testcase


class AnalysisAPITest(wf_testcase.TestCase):

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
    super(AnalysisAPITest, self).setUp()
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
        build_failure_type=StepTypeEnum.COMPILE)
    self.build_entity.put()

    self.compile_failure_1 = CompileFailure.Create(self.build_entity.key,
                                                   'compile', ['a.o'], 'CC')
    self.compile_failure_1.put()
    self.compile_failure_2 = CompileFailure.Create(self.build_entity.key,
                                                   'compile', ['b.o'], 'CC')
    self.compile_failure_2.put()

    self.commits = []
    for i in xrange(0, 11):
      self.commits.append(self._CreateGitilesCommit('r%d' % i, 100 + i))

    self.analysis_api = CompileAnalysisAPI()

  def _CreateGitilesCommit(self, gitiles_id, commit_position):
    return GitilesCommit(
        gitiles_host=self.gitiles_host,
        gitiles_project=self.gitiles_project,
        gitiles_ref=self.gitiles_ref,
        gitiles_id=gitiles_id,
        commit_position=commit_position)

  @mock.patch.object(ChromiumProjectAPI, 'GetCompileFailures')
  @mock.patch.object(buildbucket_client, 'GetV2Build')
  @mock.patch.object(buildbucket_client, 'SearchV2BuildsOnBuilder')
  def testUpdateFailuresWithFirstFailureInfo(
      self, mock_prev_builds, mock_get_build, mock_prev_failures):
    """Test for the most common case: found both first_failed_build_id and
      last_passed_build_id."""
    mock_step = Step()
    mock_step.name = 'compile'
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
        frozenset(['target1', 'target2']): {
            'properties': {
                'rule': 'CXX'
            },
            'first_failed_build': self.build_info,
            'last_passed_build': None,
        },
    }

    mock_prev_failures.return_value = {
        'compile': {
            'failures': failures,
            'first_failed_build': build_122_info,
            'last_passed_build': None,
        },
    }

    detailed_compile_failures = {
        'compile': {
            'failures': failures,
            'first_failed_build': self.build_info,
            'last_passed_build': None,
        },
    }

    self.analysis_api.UpdateFailuresWithFirstFailureInfo(
        self.context, self.build, detailed_compile_failures)

    expected_failures = {
        'compile': {
            'failures': failures,
            'first_failed_build': build_122_info,
            'last_passed_build': build_121_info,
        },
    }

    self.assertEqual(expected_failures, detailed_compile_failures)

  @mock.patch.object(buildbucket_client, 'GetV2Build')
  @mock.patch.object(buildbucket_client, 'SearchV2BuildsOnBuilder')
  def testUpdateFailuresWithFirstFailureInfoPrevBuildDifferentStep(
      self, mock_prev_builds, mock_get_build):
    """Test for previous build failed with different steps."""
    mock_step = Step()
    mock_step.name = 'test'
    mock_step.status = common_pb2.FAILURE
    mock_step1 = Step()
    mock_step1.name = 'compile'
    mock_step1.status = common_pb2.SUCCESS
    build_122 = self._MockBuild(122)
    build_122.steps.extend([mock_step, mock_step1])
    build_122.input.gitiles_commit.id = 'git_sha_122'

    build_121 = self._MockBuild(121, build_status=common_pb2.SUCCESS)

    mock_prev_builds.return_value = SearchBuildsResponse(
        builds=[build_122, build_121])
    mock_get_build.return_value = build_122

    failures = {
        frozenset(['target1', 'target2']): {
            'properties': {
                'rule': 'CXX'
            },
            'first_failed_build': self.build_info,
            'last_passed_build': None,
        },
    }

    detailed_compile_failures = {
        'compile': {
            'failures': failures,
            'first_failed_build': self.build_info,
            'last_passed_build': None,
        },
    }

    self.analysis_api.UpdateFailuresWithFirstFailureInfo(
        self.context, self.build, detailed_compile_failures)

    expected_failures = {
        'compile': {
            'failures': failures,
            'first_failed_build': self.build_info,
            'last_passed_build': self._GetBuildInfo(122),
        },
    }
    self.assertEqual(expected_failures, detailed_compile_failures)

  @mock.patch.object(buildbucket_client, 'GetV2Build')
  @mock.patch.object(buildbucket_client, 'SearchV2BuildsOnBuilder')
  def testUpdateFailuresWithFirstFailureInfoPrevBuildNoCompile(
      self, mock_prev_builds, mock_get_build):
    """Test for previous build didn't run compile."""
    mock_step = Step()
    mock_step.name = 'test'
    mock_step.status = common_pb2.FAILURE
    build_122 = self._MockBuild(122)
    build_122.steps.extend([mock_step])

    build_121 = self._MockBuild(121, build_status=common_pb2.SUCCESS)

    mock_prev_builds.return_value = SearchBuildsResponse(
        builds=[build_122, build_121])
    mock_get_build.return_value = build_122

    failure = {
        frozenset(['target1', 'target2']): {
            'properties': {
                'rule': 'CXX'
            },
            'first_failed_build': self.build_info,
            'last_passed_build': None,
        },
    }
    detailed_compile_failures = {
        'compile': {
            'failures': failure,
            'first_failed_build': self.build_info,
            'last_passed_build': None,
        },
    }

    self.analysis_api.UpdateFailuresWithFirstFailureInfo(
        self.context, self.build, detailed_compile_failures)

    expected_failures = {
        'compile': {
            'failures': failure,
            'first_failed_build': self.build_info,
            'last_passed_build': self._GetBuildInfo(121),
        },
    }
    self.assertEqual(expected_failures, detailed_compile_failures)

  @mock.patch.object(ChromiumProjectAPI, 'GetCompileFailures')
  @mock.patch.object(buildbucket_client, 'GetV2Build')
  @mock.patch.object(buildbucket_client, 'SearchV2BuildsOnBuilder')
  def testUpdateFailuresWithFirstFailureInfoDifferentFirstFailure(
      self, mock_prev_builds, mock_get_build, mock_prev_failures):
    """Test for targets in current build failed from different builds."""
    mock_step = Step()
    mock_step.name = 'compile'
    mock_step.status = common_pb2.FAILURE
    build_122 = self._MockBuild(122)
    build_122.steps.extend([mock_step])
    build_122_info = self._GetBuildInfo(122)

    mock_step1 = Step()
    mock_step1.name = 'compile'
    mock_step1.status = common_pb2.FAILURE
    build_121 = self._MockBuild(121)
    build_121.steps.extend([mock_step1])
    build_121_info = self._GetBuildInfo(121)

    mock_step2 = Step()
    mock_step2.name = 'compile'
    mock_step2.status = common_pb2.FAILURE
    build_120 = self._MockBuild(120)
    build_120.steps.extend([mock_step2])
    build_120_info = self._GetBuildInfo(120)

    mock_prev_builds.return_value = SearchBuildsResponse(
        builds=[build_122, build_121, build_120])
    mock_get_build.side_effect = [build_122, build_121, build_120]

    # Failed compiling target3 but successfully compiled target1&2.
    failures_122 = {
        'compile': {
            'failures': {
                frozenset(['target3']): {
                    'properties': {
                        'rule': 'ACTION'
                    },
                    'first_failed_build': build_122_info,
                    'last_passed_build': None,
                },
            },
            'first_failed_build': build_122_info,
            'last_passed_build': None,
        },
    }
    # Has the same failed targets as current build.
    failures_121 = {
        'compile': {
            'failures': {
                frozenset(['target3']): {
                    'properties': {
                        'rule': 'ACTION'
                    },
                    'first_failed_build': build_121_info,
                    'last_passed_build': None,
                },
                frozenset(['target1', 'target2']): {
                    'properties': {
                        'rule': 'CXX'
                    },
                    'first_failed_build': build_121_info,
                    'last_passed_build': None,
                },
            },
            'first_failed_build': build_121_info,
            'last_passed_build': None,
        },
    }
    # Failed compile step, but only different targets.
    failures_120 = {
        'compile': {
            'failures': {
                frozenset(['target4']): {
                    'properties': {
                        'rule': 'CC'
                    },
                    'first_failed_build': build_120_info,
                    'last_passed_build': None,
                },
            },
            'first_failed_build': build_120_info,
            'last_passed_build': None,
        },
    }
    mock_prev_failures.side_effect = [failures_122, failures_121, failures_120]

    detailed_compile_failures = {
        'compile': {
            'failures': {
                frozenset(['target1', 'target2']): {
                    'properties': {
                        'rule': 'CXX'
                    },
                    'first_failed_build': self.build_info,
                    'last_passed_build': None,
                },
                frozenset(['target3']): {
                    'properties': {
                        'rule': 'ACTION'
                    },
                    'first_failed_build': self.build_info,
                    'last_passed_build': None,
                },
            },
            'first_failed_build': self.build_info,
            'last_passed_build': None,
        },
    }

    self.analysis_api.UpdateFailuresWithFirstFailureInfo(
        self.context, self.build, detailed_compile_failures)

    expected_failures = {
        'compile': {
            'failures': {
                frozenset(['target1', 'target2']): {
                    'properties': {
                        'rule': 'CXX'
                    },
                    'first_failed_build': self.build_info,
                    'last_passed_build': build_122_info,
                },
                frozenset(['target3']): {
                    'properties': {
                        'rule': 'ACTION'
                    },
                    'first_failed_build': build_121_info,
                    'last_passed_build': build_120_info,
                },
            },
            'first_failed_build': build_121_info,
            'last_passed_build': build_120_info,
        },
    }

    self.assertEqual(expected_failures, detailed_compile_failures)

  @mock.patch.object(buildbucket_client, 'GetV2Build')
  @mock.patch.object(buildbucket_client, 'SearchV2BuildsOnBuilder')
  def testUpdateFailuresWithFirstFailureInfoPrevBuildInfraFailure(
      self, mock_prev_builds, mock_get_build):
    """Test for previous build failed with different steps."""
    mock_step1 = Step()
    mock_step1.name = 'compile'
    mock_step1.status = common_pb2.INFRA_FAILURE
    build_122 = self._MockBuild(122)
    build_122.steps.extend([mock_step1])

    build_121 = self._MockBuild(121, build_status=common_pb2.SUCCESS)
    build_121_info = self._GetBuildInfo(121)

    mock_prev_builds.return_value = SearchBuildsResponse(
        builds=[build_122, build_121])
    mock_get_build.return_value = build_122

    detailed_compile_failures = {
        'compile': {
            'failures': {
                frozenset(['target1', 'target2']): {
                    'properties': {
                        'rule': 'CXX'
                    },
                    'first_failed_build': self.build_info,
                    'last_passed_build': None,
                },
            },
            'first_failed_build': self.build_info,
            'last_passed_build': None,
        },
    }

    self.analysis_api.UpdateFailuresWithFirstFailureInfo(
        self.context, self.build, detailed_compile_failures)

    expected_failures = {
        'compile': {
            'failures': {
                frozenset(['target1', 'target2']): {
                    'properties': {
                        'rule': 'CXX'
                    },
                    'first_failed_build': self.build_info,
                    'last_passed_build': build_121_info,
                },
            },
            'first_failed_build': self.build_info,
            'last_passed_build': build_121_info,
        },
    }
    self.assertEqual(expected_failures, detailed_compile_failures)

  def testGetFirstFailuresInCurrentBuild(self):
    build_122_info = self._GetBuildInfo(122)

    failures = {
        'compile': {
            'failures': {
                frozenset(['target1', 'target2']): {
                    'properties': {
                        'rule': 'CXX'
                    },
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
            'compile': {
                'atomic_failures': [{'target1', 'target2'}],
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
        'compile': {
            'failures': {
                frozenset(['target1', 'target2']): {
                    'properties': {
                        'rule': 'CXX'
                    },
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
        'compile': {
            'failures': {
                frozenset(['target1', 'target2']): {
                    'properties': {
                        'rule': 'CXX'
                    },
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
        'compile': {
            'failures': {},
            'first_failed_build': self.build_info,
            'last_passed_build': build_122_info,
        },
    }

    expected_res = {
        'failures': {
            'compile': {
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
    failures = {
        'compile': {
            'failures': {},
            'first_failed_build': self._GetBuildInfo(122),
            'last_passed_build': self._GetBuildInfo(121),
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
        'compile': {
            'failures': {
                frozenset(['target1', 'target2']): {
                    'properties': {
                        'rule': 'CXX'
                    },
                    'first_failed_build': self.build_info,
                    'last_passed_build': build_122_info,
                },
                frozenset(['target3']): {
                    'properties': {
                        'rule': 'ACTION'
                    },
                    'first_failed_build': build_122_info,
                    'last_passed_build': None,
                },
                frozenset(['target4']): {
                    'properties': {
                        'rule': 'ACTION'
                    },
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
            'compile': {
                'atomic_failures': [{'target4'}, {'target1', 'target2'}],
                'last_passed_build': build_121_info,
            },
        },
        'last_passed_build': build_121_info
    }
    print expected_res
    self.assertEqual(
        expected_res,
        self.analysis_api.GetFirstFailuresInCurrentBuild(
            self.context, self.build, failures))

  @mock.patch.object(git, 'GetCommitPositionFromRevision', return_value=67890)
  def testSaveFailures(self, _):
    detailed_compile_failures = {
        'compile': {
            'failures': {
                frozenset(['target1', 'target2']): {
                    'properties': {
                        'rule': 'CXX'
                    },
                    'first_failed_build': self._GetBuildInfo(121),
                    'last_passed_build': self._GetBuildInfo(120),
                },
            },
            'first_failed_build': self._GetBuildInfo(121),
            'last_passed_build': self._GetBuildInfo(120),
        },
    }

    # Prepares data for existing failure group.
    group_build = self._MockBuild(
        12134, 8000003400121, 'git_sha_121', builder_name='Mac')
    group_build_entity = luci_build.SaveFailedBuild(self.context, group_build,
                                                    StepTypeEnum.COMPILE)
    group_failure = CompileFailure.Create(group_build_entity.key, 'compile',
                                          ['target1', 'target2'], 'CXX')
    group_failure.put()

    # Prepares data for first failed build.
    first_failed_build = self._MockBuild(121)
    first_failed_build_entity = luci_build.SaveFailedBuild(
        self.context, first_failed_build, StepTypeEnum.COMPILE)
    first_failure = CompileFailure.Create(
        first_failed_build_entity.key, 'compile', ['target1', 'target2'], 'CXX')
    first_failure.merged_failure_key = group_failure.key
    first_failure.put()

    self.analysis_api.SaveFailures(self.context, self.build,
                                   detailed_compile_failures)

    build = LuciFailedBuild.get_by_id(self.build_id)
    self.assertIsNotNone(build)

    compile_failures = CompileFailure.query(ancestor=build.key).fetch()
    self.assertEqual(1, len(compile_failures))
    self.assertEqual(
        self._GetBuildIdByNumber(121),
        compile_failures[0].first_failed_build_id)
    self.assertEqual(group_failure.key, compile_failures[0].merged_failure_key)
    self.assertEqual('CXX', compile_failures[0].rule)

  @mock.patch.object(git, 'GetCommitPositionFromRevision', return_value=67890)
  def testSaveFailuresOnlyStepLevelFailures(self, _):
    detailed_compile_failures = {
        'compile': {
            'failures': {},
            'first_failed_build': self._GetBuildInfo(121),
            'last_passed_build': self._GetBuildInfo(120),
        },
    }

    # Prepares data for first failed build.
    first_failed_build = self._MockBuild(121)
    first_failed_build_entity = luci_build.SaveFailedBuild(
        self.context, first_failed_build, StepTypeEnum.COMPILE)
    first_failure = CompileFailure.Create(first_failed_build_entity.key,
                                          'compile', None, 'CXX')
    first_failure.put()

    self.analysis_api.SaveFailures(self.context, self.build,
                                   detailed_compile_failures)

    build_entity = LuciFailedBuild.get_by_id(self.build_id)
    self.assertIsNotNone(build_entity)

    compile_failures = CompileFailure.query(ancestor=build_entity.key).fetch()
    self.assertEqual(1, len(compile_failures))
    self.assertEqual(
        self._GetBuildIdByNumber(121),
        compile_failures[0].first_failed_build_id)
    self.assertEqual([], compile_failures[0].output_targets)
    self.assertEqual(first_failure.key, compile_failures[0].merged_failure_key)

  @mock.patch.object(
      ChromiumProjectAPI,
      'GetRerunBuilderId',
      return_value='chromium/findit/findit_variables')
  @mock.patch.object(
      git, 'GetCommitPositionFromRevision', side_effect=[66680, 66666, 66680])
  def testSaveFailureAnalysis(self, *_):
    build_120_info = self._GetBuildInfo(120)

    detailed_compile_failures = {
        'compile': {
            'failures': {
                frozenset(['target1', 'target2']): {
                    'properties': {
                        'properties': {
                            'rule': 'CXX'
                        },
                    },
                    'first_failed_build': self.build_info,
                    'last_passed_build': build_120_info,
                },
                frozenset(['target3']): {
                    'properties': {
                        'properties': {
                            'rule': 'ACTION'
                        },
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
                                   detailed_compile_failures)

    first_failures_in_current_build = {
        'failures': {
            'compile': {
                'atomic_failures': [{'target1', 'target2'}],
                'last_passed_build': build_120_info,
            },
        },
        'last_passed_build': build_120_info
    }
    self.analysis_api.SaveFailureAnalysis(
        self.context, self.build, first_failures_in_current_build, False)

    analysis = CompileFailureAnalysis.GetVersion(self.build_id)
    self.assertIsNotNone(analysis)
    self.assertEqual('git_sha_120', analysis.last_passed_commit.gitiles_id)
    self.assertEqual(66666, analysis.last_passed_commit.commit_position)
    self.assertEqual('chromium/findit/findit_variables',
                     analysis.rerun_builder_id)
    self.assertEqual(1, len(analysis.compile_failure_keys))
    self.assertItemsEqual(['target1', 'target2'],
                          analysis.compile_failure_keys[0].get().output_targets)

  @mock.patch.object(
      ChromiumProjectAPI,
      'GetRerunBuilderId',
      return_value='chromium/findit/findit_variables')
  @mock.patch.object(
      git, 'GetCommitPositionFromRevision', side_effect=[66680, 66666, 66680])
  def testSaveFailureAnalysisWithGroup(self, *_):
    build_120_info = self._GetBuildInfo(120)

    detailed_compile_failures = {
        'compile': {
            'failures': {
                frozenset(['target1', 'target2']): {
                    'properties': {
                        'properties': {
                            'rule': 'CXX'
                        },
                    },
                    'first_failed_build': self.build_info,
                    'last_passed_build': build_120_info,
                },
                frozenset(['target3']): {
                    'properties': {
                        'properties': {
                            'rule': 'ACTION'
                        },
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
                                   detailed_compile_failures)

    first_failures_in_current_build = {
        'failures': {
            'compile': {
                'atomic_failures': [{'target1', 'target2'}],
                'last_passed_build': build_120_info,
            },
        },
        'last_passed_build': build_120_info
    }
    self.analysis_api.SaveFailureAnalysis(self.context, self.build,
                                          first_failures_in_current_build, True)

    analysis = CompileFailureAnalysis.GetVersion(self.build_id)
    self.assertIsNotNone(analysis)
    self.assertEqual('git_sha_120', analysis.last_passed_commit.gitiles_id)
    self.assertEqual(66666, analysis.last_passed_commit.commit_position)
    self.assertEqual('chromium/findit/findit_variables',
                     analysis.rerun_builder_id)
    self.assertEqual(1, len(analysis.compile_failure_keys))
    self.assertItemsEqual(['target1', 'target2'],
                          analysis.compile_failure_keys[0].get().output_targets)

    group = CompileFailureGroup.get_by_id(self.build_id)
    self.assertIsNotNone(group)
    self.assertEqual('git_sha_120', analysis.last_passed_commit.gitiles_id)
    self.assertEqual(self.build_info['commit_id'],
                     analysis.first_failed_commit.gitiles_id)

  @mock.patch.object(
      ChromiumProjectAPI,
      'GetFailuresWithMatchingCompileFailureGroups',
      return_value={})
  def testGetFirstFailuresInCurrentBuildWithoutGroupNoExistingGroup(self, _):
    self.assertEqual(
        {},
        self.analysis_api.GetFirstFailuresInCurrentBuildWithoutGroup(
            self.context, self.build, {}))

  @mock.patch.object(
      git, 'GetCommitPositionFromRevision', side_effect=[66680, 66666, 66680])
  @mock.patch.object(
      ChromiumProjectAPI,
      'GetFailuresWithMatchingCompileFailureGroups',
      return_value={
          'compile': {
              frozenset(['target1']): 8000000000134,
              frozenset(['target2']): 8000000000134
          }
      })
  def testGetFirstFailuresInCurrentBuildWithoutGroup(self, *_):
    build_121_info = self._GetBuildInfo(121)
    first_failures_in_current_build = {
        'failures': {
            'compile': {
                'atomic_failures': [
                    frozenset(['target1']),
                    frozenset(['target2'])
                ],
                'last_passed_build':
                    build_121_info,
            },
        },
        'last_passed_build': build_121_info
    }

    # Creates and saves entities of the existing group.
    detailed_compile_failures = {
        'compile': {
            'failures': {
                frozenset(['target1']): {
                    'properties': {
                        'properties': {
                            'rule': 'CXX'
                        },
                    },
                    'first_failed_build': self.build_info,
                    'last_passed_build': build_121_info,
                },
                frozenset(['target2']): {
                    'properties': {
                        'properties': {
                            'rule': 'ACTION'
                        },
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
                                   detailed_compile_failures)

    # Prepares data for existing failure group.
    group_build = self._MockBuild(
        12134, 8000000000134, 'git_sha_134', builder_name='Mac')
    group_build_entity = luci_build.SaveFailedBuild(self.context, group_build,
                                                    StepTypeEnum.COMPILE)
    group_failure1 = CompileFailure.Create(group_build_entity.key, 'compile',
                                           ['target1'], 'CXX')
    group_failure1.put()
    group_failure2 = CompileFailure.Create(group_build_entity.key, 'compile',
                                           ['target2'], 'ACTION')
    group_failure2.put()

    self.assertEqual(
        {
            'failures': {},
            'last_passed_build': None
        },
        self.analysis_api.GetFirstFailuresInCurrentBuildWithoutGroup(
            self.context, self.build, first_failures_in_current_build))

    build = LuciFailedBuild.get_by_id(self.build_id)
    compile_failures = CompileFailure.query(ancestor=build.key).fetch()
    self.assertEqual(2, len(compile_failures))

    for failure in compile_failures:
      if failure.output_targets == ['target1']:
        self.assertEqual(group_failure1.key, failure.merged_failure_key)
      else:
        self.assertEqual(group_failure2.key, failure.merged_failure_key)

  @mock.patch.object(
      git, 'GetCommitPositionFromRevision', side_effect=[66680, 66666, 66680])
  @mock.patch.object(
      ChromiumProjectAPI,
      'GetFailuresWithMatchingCompileFailureGroups',
      return_value={'compile': {
          frozenset(['target1']): 8000000000077
      }})
  def testGetFirstFailuresInCurrentBuildWithoutGroupExistingGroupForSameBuild(
      self, *_):
    build_121_info = self._GetBuildInfo(121)
    first_failures_in_current_build = {
        'failures': {
            'compile': {
                'atomic_failures': [
                    frozenset(['target1']),
                    frozenset(['target2'])
                ],
                'last_passed_build':
                    build_121_info,
            },
        },
        'last_passed_build': build_121_info
    }

    # Creates and saves entities of the existing group.
    detailed_compile_failures = {
        'compile': {
            'failures': {
                frozenset(['target1']): {
                    'properties': {
                        'rule': 'CXX',
                    },
                    'first_failed_build': self.build_info,
                    'last_passed_build': build_121_info,
                },
                frozenset(['target2']): {
                    'properties': {
                        'rule': 'ACTION',
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
                                   detailed_compile_failures)

    expected_result = {
        'failures': {
            'compile': {
                'atomic_failures': [
                    frozenset(['target1']),
                    frozenset(['target2'])
                ],
                'last_passed_build':
                    build_121_info,
            },
        },
        'last_passed_build': build_121_info
    }
    print expected_result
    print self.analysis_api.GetFirstFailuresInCurrentBuildWithoutGroup(
        self.context, self.build, first_failures_in_current_build)

    self.assertEqual(
        expected_result,
        self.analysis_api.GetFirstFailuresInCurrentBuildWithoutGroup(
            self.context, self.build, first_failures_in_current_build))
