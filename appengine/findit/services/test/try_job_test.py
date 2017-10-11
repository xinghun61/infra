# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
from datetime import timedelta
import mock

from common.findit_http_client import FinditHttpClient
from common.waterfall import failure_type
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs import time_util
from model import result_status
from model.wf_analysis import WfAnalysis
from model.wf_build import WfBuild
from model.wf_failure_group import WfFailureGroup
from model.wf_try_job import WfTryJob
from services import try_job as try_job_util
from waterfall.test import wf_testcase

_GIT_REPO = CachedGitilesRepository(
    FinditHttpClient(), 'https://chromium.googlesource.com/chromium/src.git')


class TryJobUtilTest(wf_testcase.WaterfallTestCase):

  def testShouldBailOutIfBuildHasNoStartTime(self):
    build = WfBuild.Create('m', 'b', 1)
    build.start_time = None
    self.assertTrue(try_job_util._ShouldBailOutForOutdatedBuild(build))

  def testShouldBailOutforOutdatedBuild(self):
    yesterday = datetime.utcnow() - timedelta(days=1)
    build = WfBuild.Create('m', 'b', 1)
    build.start_time = yesterday
    self.assertTrue(try_job_util._ShouldBailOutForOutdatedBuild(build))

    build.start_time = yesterday + timedelta(hours=1)
    self.assertFalse(try_job_util._ShouldBailOutForOutdatedBuild(build))

  def testGetSuspectedCLsWithFailuresNoHeuristicResult(self):
    heuristic_result = None
    expected_suspected_revisions = []
    self.assertEqual(
        expected_suspected_revisions,
        sorted(try_job_util._GetSuspectedCLsWithFailures(heuristic_result)))

  def testGetSuspectedCLsWithFailuresEmptyHeuristicResult(self):
    heuristic_result = {}
    expected_suspected_revisions = []
    self.assertEqual(
        expected_suspected_revisions,
        sorted(try_job_util._GetSuspectedCLsWithFailures(heuristic_result)))

  def testGetSuspectedCLsWithFailures(self):
    heuristic_result = {
        'failures': [{
            'step_name': 'step1',
            'suspected_cls': [],
        }, {
            'step_name': 'step2',
            'suspected_cls': [
                {
                    'revision': 'r1',
                },
                {
                    'revision': 'r2',
                },
            ],
        }, {
            'step_name':
                'step3',
            'suspected_cls': [{
                'revision': 'r3',
            }],
            'tests': [{
                'test_name': 'super_test_1',
                'suspected_cls': [{
                    'revision': 'abc'
                }]
            }, {
                'test_name': 'super_test_2',
                'suspected_cls': [{
                    'revision': 'def'
                }, {
                    'revision': 'ghi'
                }]
            }]
        }]
    }
    expected_suspected_revisions = [['step2', 'r1', None], [
        'step2', 'r2', None
    ], ['step3', 'abc', 'super_test_1'], ['step3', 'def', 'super_test_2'],
                                    ['step3', 'ghi', 'super_test_2']]
    self.assertEqual(
        expected_suspected_revisions,
        sorted(try_job_util._GetSuspectedCLsWithFailures(heuristic_result)))

  def testBlameListsIntersect(self):
    self.assertFalse(try_job_util._BlameListsIntersection(['0'], ['1']))
    self.assertFalse(try_job_util._BlameListsIntersection(['1'], []))
    self.assertFalse(try_job_util._BlameListsIntersection([], []))
    self.assertTrue(try_job_util._BlameListsIntersection(['1'], ['1']))
    self.assertTrue(
        try_job_util._BlameListsIntersection(['0', '1'], ['1', '2']))
    self.assertTrue(try_job_util._BlameListsIntersection(['1'], ['1', '2']))

  def testLinkAnalysisToBuildFailureGroup(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1

    failure_group_key = ['m2', 'b2', 2]
    WfAnalysis.Create(master_name, builder_name, build_number).put()
    try_job_util._LinkAnalysisToBuildFailureGroup(
        master_name, builder_name, build_number, failure_group_key)
    self.assertEqual(failure_group_key,
                     WfAnalysis.Get(master_name, builder_name,
                                    build_number).failure_group_key)

  def testNotNeedANewWaterfallTryJobIfBuilderIsNotSupportedYet(self):
    master_name = 'master3'
    builder_name = 'builder3'
    build_number = 223
    WfAnalysis.Create(master_name, builder_name, build_number).put()

    self.assertFalse(
        try_job_util.NeedANewWaterfallTryJob(master_name, builder_name,
                                             build_number, False))

  @mock.patch.object(
      try_job_util, '_ShouldBailOutForOutdatedBuild', return_value=True)
  def testBailOutForTryJobWithOutdatedTimestamp(self, _):
    master_name = 'master1'
    builder_name = 'builder1'
    build_number = 223
    WfAnalysis.Create(master_name, builder_name, build_number).put()

    yesterday = datetime.utcnow() - timedelta(days=1)
    build = WfBuild.Create(master_name, builder_name, build_number)
    build.start_time = yesterday
    build.put()

    self.assertFalse(
        try_job_util.NeedANewWaterfallTryJob(master_name, builder_name,
                                             build_number, False))

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2017, 9, 6, 0, 0, 0))
  def testNeedANewWaterfallTryJob(self, _):
    master_name = 'master1'
    builder_name = 'builder1'
    build_number = 223
    WfAnalysis.Create(master_name, builder_name, build_number).put()

    yesterday = datetime(2017, 9, 5, 20, 0, 0, 0)
    build = WfBuild.Create(master_name, builder_name, build_number)
    build.start_time = yesterday
    build.put()

    self.assertTrue(
        try_job_util.NeedANewWaterfallTryJob(master_name, builder_name,
                                             build_number, False))

  def testNeedANewWaterfallTryJobForce(self):
    master_name = 'master1'
    builder_name = 'builder1'
    build_number = 223

    self.assertTrue(
        try_job_util.NeedANewWaterfallTryJob(master_name, builder_name,
                                             build_number, True))

  def testSecondAnalysisFailureGroupKeySet(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1
    master_name_2 = 'm2'
    blame_list = ['a']
    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed output nodes.
    # Observe new group creation.
    self.assertTrue(
        try_job_util.IsBuildFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.COMPILE,
            blame_list, None, []))

    groups = WfFailureGroup.query(
        WfFailureGroup.build_failure_type == failure_type.COMPILE).fetch()
    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have the same failed output nodes.
    # Observe no new group creation.
    self.assertFalse(
        try_job_util.IsBuildFailureUniqueAcrossPlatforms(
            master_name_2, builder_name, build_number, failure_type.COMPILE,
            blame_list, None, groups))
    analysis_2 = WfAnalysis.Get(master_name_2, builder_name, build_number)
    self.assertEqual([master_name, builder_name, build_number],
                     analysis_2.failure_group_key)

  def testGetMatchingFailureGroups(self):
    self.assertEqual(
        [], try_job_util.GetMatchingFailureGroups(failure_type.UNKNOWN))

  @mock.patch.object(try_job_util, '_BlameListsIntersection')
  def testGetMatchingGroup(self, mock_fn):
    group1 = WfFailureGroup.Create('m', 'b1', 123)
    group1.suspected_tuples = [['m', 'b1', 123]]
    group1.put()
    group2 = WfFailureGroup.Create('m', 'b2', 123)
    group2.suspected_tuples = [['m', 'b2', 123]]
    group2.put()
    group3 = WfFailureGroup.Create('m', 'b3', 123)
    group3.suspected_tuples = [['m', 'b3', 123]]
    group3.put()
    groups = [group1, group2, group3]
    mock_fn.side_effect = [False, True, True]
    self.assertEqual(group3,
                     try_job_util._GetMatchingGroup(groups, [],
                                                    [['m', 'b3', 123]]))

  def testReviveOrCreateTryJobEntityNoTryJob(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1
    result, try_job_key = try_job_util.ReviveOrCreateTryJobEntity(
        master_name, builder_name, build_number, False)
    self.assertTrue(result)
    self.assertIsNotNone(try_job_key)

  def testReviveOrCreateTryJobEntityForce(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1

    WfTryJob.Create(master_name, builder_name, build_number).put()
    result, try_job_key = try_job_util.ReviveOrCreateTryJobEntity(
        master_name, builder_name, build_number, True)

    self.assertTrue(result)
    self.assertIsNotNone(try_job_key)

  def testReviveOrCreateTryJobEntityNoNeed(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1

    WfTryJob.Create(master_name, builder_name, build_number).put()
    result, try_job_key = try_job_util.ReviveOrCreateTryJobEntity(
        master_name, builder_name, build_number, False)

    self.assertFalse(result)
    self.assertIsNotNone(try_job_key)

  def testGetSuspectsFromHeuristicResult(self):
    heuristic_result = {
        'failures': [
            {
                'step_name': 'compile',
                'suspected_cls': [
                    {
                        'revision': 'r1',
                    },
                    {
                        'revision': 'r2',
                    },
                ],
            },
        ]
    }
    expected_suspected_revisions = ['r1', 'r2']
    self.assertEqual(
        expected_suspected_revisions,
        try_job_util.GetSuspectsFromHeuristicResult(heuristic_result))

  def testNoSuspectsIfNoHeuristicResult(self):
    self.assertEqual([], try_job_util.GetSuspectsFromHeuristicResult({}))

  def testGetResultAnalysisStatusWithTryJobCulpritNotFoundUntriaged(self):
    # Heuristic analysis provided no results, but the try job found a culprit.
    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.result_status = result_status.NOT_FOUND_UNTRIAGED
    analysis.put()

    result = {
        'culprit': {
            'compile': {
                'revision': 'rev1',
                'commit_position': 1,
                'url': 'url_1',
                'repo_name': 'chromium'
            }
        }
    }

    status = try_job_util.GetResultAnalysisStatus(analysis, result)

    self.assertEqual(status, result_status.FOUND_UNTRIAGED)

  def testGetResultAnalysisStatusWithTryJobCulpritNotFoundCorrect(self):
    # Heuristic analysis found no results, which was correct. In this case, the
    # try job result is actually a false positive.
    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.result_status = result_status.NOT_FOUND_CORRECT
    analysis.put()

    result = {
        'culprit': {
            'compile': {
                'revision': 'rev1',
                'commit_position': 1,
                'url': 'url_1',
                'repo_name': 'chromium'
            }
        }
    }

    status = try_job_util.GetResultAnalysisStatus(analysis, result)

    self.assertEqual(status, result_status.FOUND_UNTRIAGED)

  def testGetResultanalysisStatusWithTryJobCulpritNotFoundIncorrect(self):
    # Heuristic analysis found no results and was triaged to incorrect before a
    # try job result was found. In this case the try job result should override
    # the heuristic result.
    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.result_status = result_status.NOT_FOUND_INCORRECT
    analysis.put()

    result = {
        'culprit': {
            'compile': {
                'revision': 'rev1',
                'commit_position': 1,
                'url': 'url_1',
                'repo_name': 'chromium'
            }
        }
    }

    status = try_job_util.GetResultAnalysisStatus(analysis, result)

    self.assertEqual(status, result_status.FOUND_UNTRIAGED)

  def testGetResultanalysisStatusWithTryJobCulpritNoHeuristicResult(self):
    # In this case, the try job found a result before the heuristic result is
    # available. This case should generally never happen, as heuristic analysis
    # is usually much faster than try jobs.
    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.put()

    result = {
        'culprit': {
            'compile': {
                'revision': 'rev1',
                'commit_position': 1,
                'url': 'url_1',
                'repo_name': 'chromium'
            }
        }
    }

    status = try_job_util.GetResultAnalysisStatus(analysis, result)

    self.assertEqual(status, result_status.FOUND_UNTRIAGED)

  def testGetResultanalysisStatusWithNoTryJobCulpritNoHeuristicResult(self):
    # In this case, the try job completed faster than heuristic analysis
    # (which should never happen) but no results were found.
    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.put()

    result = {}

    status = try_job_util.GetResultAnalysisStatus(analysis, result)
    self.assertIsNone(status)

  def testGetResultanalysisStatusWithTryJobCulpritAndHeuristicResult(self):
    # In this case, heuristic analysis found the correct culprit. The try job
    # result should not overwrite it.
    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.result_status = result_status.FOUND_CORRECT
    analysis.put()

    result = {
        'culprit': {
            'compile': {
                'revision': 'rev1',
                'commit_position': 1,
                'url': 'url_1',
                'repo_name': 'chromium'
            }
        }
    }

    status = try_job_util.GetResultAnalysisStatus(analysis, result)
    self.assertEqual(status, result_status.FOUND_CORRECT)

  def testGetResultanalysisStatusWithNoCulpritTriagedCorrect(self):
    # In this case, heuristic analysis correctly found no culprit and was
    # triaged, and the try job came back with nothing. The try job result should
    # not overwrite the heuristic result.
    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.result_status = result_status.NOT_FOUND_CORRECT
    analysis.put()

    result = {}

    status = try_job_util.GetResultAnalysisStatus(analysis, result)
    self.assertEqual(status, result_status.NOT_FOUND_CORRECT)

  def testGetResultanalysisStatusWithNoCulpritTriagedIncorrect(self):
    # In this case, heuristic analysis correctly found no culprit and was
    # triaged, and the try job came back with nothing. The try job result should
    # not overwrite the heuristic result.
    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.result_status = result_status.NOT_FOUND_INCORRECT
    analysis.put()

    result = {}
    status = try_job_util.GetResultAnalysisStatus(analysis, result)
    self.assertEqual(status, result_status.NOT_FOUND_INCORRECT)

  def testGetUpdatedAnalysisResultNoAnalysis(self):
    result, flaky = try_job_util.GetUpdatedAnalysisResult(None, None)
    self.assertEqual({}, result)
    self.assertFalse(flaky)

  def testGetUpdatedAnalysisResult(self):
    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.result = {
        'failures': [
            {
                'step_name': 'compile',
                'suspected_cls': [
                    {
                        'revision': 'r1',
                    },
                ],
            },
        ]
    }
    analysis.put()

    flaky_failures = {'compile': []}

    expected_result = {
        'failures': [
            {
                'step_name': 'compile',
                'suspected_cls': [
                    {
                        'revision': 'r1',
                    },
                ],
                'flaky': True
            },
        ]
    }

    result, flaky = try_job_util.GetUpdatedAnalysisResult(
        analysis, flaky_failures)
    self.assertEqual(expected_result, result)
    self.assertTrue(flaky)

  def _MockGetChangeLog(self, revision):

    class MockedChangeLog(object):

      def __init__(self, commit_position, code_review_url):
        self.commit_position = commit_position
        self.code_review_url = code_review_url
        self.change_id = str(commit_position)

    mock_change_logs = {}
    mock_change_logs['rev1'] = None
    mock_change_logs['rev2'] = MockedChangeLog(123, 'url')
    return mock_change_logs.get(revision)

  def testGetCulpritInfo(self):
    failed_revisions = ['rev1', 'rev2']

    self.mock(CachedGitilesRepository, 'GetChangeLog', self._MockGetChangeLog)

    expected_culprits = {
        'rev1': {
            'revision': 'rev1',
            'repo_name': 'chromium'
        },
        'rev2': {
            'revision': 'rev2',
            'repo_name': 'chromium',
            'commit_position': 123,
            'url': 'url'
        }
    }
    self.assertEqual(expected_culprits,
                     try_job_util.GetCulpritInfo(failed_revisions))
