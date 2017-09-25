# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.waterfall import failure_type
from gae_libs.pipeline_wrapper import pipeline_handlers
from libs import analysis_status
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from model import analysis_approach_type
from model import result_status
from model.wf_analysis import WfAnalysis
from model.wf_suspected_cl import WfSuspectedCL
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from waterfall import build_util
from waterfall import identify_try_job_culprit_pipeline
from waterfall.identify_try_job_culprit_pipeline import (
    IdentifyTryJobCulpritPipeline)
from waterfall.revert_and_notify_culprit_pipeline import (
    RevertAndNotifyCulpritPipeline)
from waterfall.test import wf_testcase


class IdentifyTryJobCulpritPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def _MockGetChangeLog(self, revision):

    class MockedChangeLog(object):

      def __init__(self, commit_position, code_review_url):
        self.commit_position = commit_position
        self.code_review_url = code_review_url
        self.change_id = str(commit_position)

    mock_change_logs = {}
    mock_change_logs['rev1'] = MockedChangeLog(1, 'url_1')
    mock_change_logs['rev2'] = MockedChangeLog(2, 'url_2')
    return mock_change_logs.get(revision)

  def setUp(self):
    super(IdentifyTryJobCulpritPipelineTest, self).setUp()

    self.mock(CachedGitilesRepository, 'GetChangeLog', self._MockGetChangeLog)

  def _CreateEntities(self,
                      master_name,
                      builder_name,
                      build_number,
                      try_job_id,
                      try_job_status=None,
                      compile_results=None,
                      test_results=None):
    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    if try_job_status:
      try_job.status = try_job_status
    if compile_results:
      try_job.compile_results = compile_results
    if test_results:
      try_job.test_results = test_results
    try_job.put()

    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.put()

  def testGetFailedRevisionFromCompileResult(self):
    self.assertIsNone(
        identify_try_job_culprit_pipeline._GetFailedRevisionFromCompileResult(
            None))
    self.assertIsNone(
        identify_try_job_culprit_pipeline._GetFailedRevisionFromCompileResult({
            'report': {}
        }))
    self.assertIsNone(
        identify_try_job_culprit_pipeline._GetFailedRevisionFromCompileResult({
            'report': {
                'result': {
                    'rev1': 'passed'
                }
            }
        }))
    self.assertIsNone(
        identify_try_job_culprit_pipeline._GetFailedRevisionFromCompileResult({
            'report': {
                'result': {
                    'rev1': 'passed',
                    'rev2': 'failed'
                }
            }
        }))
    self.assertEqual(
        'rev1',
        identify_try_job_culprit_pipeline._GetFailedRevisionFromCompileResult({
            'report': {
                'result': {
                    'rev1': 'failed',
                    'rev2': 'failed'
                },
                'culprit': 'rev1',
            }
        }))

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

    status = identify_try_job_culprit_pipeline._GetResultAnalysisStatus(
        analysis, result)

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

    status = identify_try_job_culprit_pipeline._GetResultAnalysisStatus(
        analysis, result)

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

    status = identify_try_job_culprit_pipeline._GetResultAnalysisStatus(
        analysis, result)

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

    status = identify_try_job_culprit_pipeline._GetResultAnalysisStatus(
        analysis, result)

    self.assertEqual(status, result_status.FOUND_UNTRIAGED)

  def testGetResultanalysisStatusWithNoTryJobCulpritNoHeuristicResult(self):
    # In this case, the try job completed faster than heuristic analysis
    # (which should never happen) but no results were found.
    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.put()

    result = {}

    status = identify_try_job_culprit_pipeline._GetResultAnalysisStatus(
        analysis, result)
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

    status = identify_try_job_culprit_pipeline._GetResultAnalysisStatus(
        analysis, result)
    self.assertEqual(status, result_status.FOUND_CORRECT)

  def testGetResultanalysisStatusWithNoCulpritTriagedCorrect(self):
    # In this case, heuristic analysis correctly found no culprit and was
    # triaged, and the try job came back with nothing. The try job result should
    # not overwrite the heuristic result.
    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.result_status = result_status.NOT_FOUND_CORRECT
    analysis.put()

    result = {}

    status = identify_try_job_culprit_pipeline._GetResultAnalysisStatus(
        analysis, result)
    self.assertEqual(status, result_status.NOT_FOUND_CORRECT)

  def testGetResultanalysisStatusWithNoCulpritTriagedIncorrect(self):
    # In this case, heuristic analysis correctly found no culprit and was
    # triaged, and the try job came back with nothing. The try job result should
    # not overwrite the heuristic result.
    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.result_status = result_status.NOT_FOUND_INCORRECT
    analysis.put()

    result = {}

    status = identify_try_job_culprit_pipeline._GetResultAnalysisStatus(
        analysis, result)
    self.assertEqual(status, result_status.NOT_FOUND_INCORRECT)

  def testGetSuspectedCLsForCompileTryJob(self):
    heuristic_suspected_cl = {
        'revision': 'rev1',
        'commit_position': 1,
        'url': 'url_1',
        'repo_name': 'chromium',
        'failures': {
            'compile': []
        },
        'top_score': 5
    }

    compile_suspected_cl = {
        'revision': 'rev2',
        'commit_position': 2,
        'url': 'url_2',
        'repo_name': 'chromium'
    }

    try_job_type = failure_type.COMPILE

    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.suspected_cls = [heuristic_suspected_cl]
    analysis.put()

    try_job_suspected_cls = {'rev2': compile_suspected_cl}

    expected_cls = [
        heuristic_suspected_cl, {
            'revision': 'rev2',
            'commit_position': 2,
            'url': 'url_2',
            'repo_name': 'chromium',
            'failures': {
                'compile': []
            },
            'top_score': None
        }
    ]

    self.assertEqual(
        identify_try_job_culprit_pipeline._GetSuspectedCLs(
            analysis, try_job_type, None, try_job_suspected_cls), expected_cls)

  def testGetSuspectedCLsForTestTryJobAndHeuristicResultsSame(self):
    suspected_cl = {
        'revision': 'rev1',
        'commit_position': 1,
        'url': 'url_1',
        'repo_name': 'chromium'
    }

    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.suspected_cls = [suspected_cl]
    analysis.put()

    try_job_suspected_cls = {'rev1': suspected_cl}

    updated_cls = identify_try_job_culprit_pipeline._GetSuspectedCLs(
        analysis, failure_type.TEST, None, try_job_suspected_cls)

    self.assertEqual(updated_cls, [suspected_cl])

  def testGetSuspectedCLsForTestTryJob(self):
    suspected_cl1 = {
        'revision': 'rev1',
        'commit_position': 1,
        'url': 'url_1',
        'repo_name': 'chromium'
    }
    suspected_cl2 = {
        'revision': 'rev2',
        'commit_position': 2,
        'url': 'url_2',
        'repo_name': 'chromium'
    }
    suspected_cl3 = {
        'revision': 'rev3',
        'commit_position': 3,
        'url': 'url_3',
        'repo_name': 'chromium'
    }

    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.suspected_cls = [suspected_cl3]
    analysis.put()

    try_job_suspected_cls = {'rev1': suspected_cl1, 'rev2': suspected_cl2}

    result = {
        'report': {
            'result': {
                'rev1': {
                    'step1': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['test1']
                    }
                },
                'rev2': {
                    'step1': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['test2']
                    }
                }
            }
        }
    }

    expected_cls = [
        suspected_cl3, {
            'revision': 'rev1',
            'commit_position': 1,
            'url': 'url_1',
            'repo_name': 'chromium',
            'failures': {
                'step1': ['test1']
            },
            'top_score': None
        }, {
            'revision': 'rev2',
            'commit_position': 2,
            'url': 'url_2',
            'repo_name': 'chromium',
            'failures': {
                'step1': ['test2']
            },
            'top_score': None
        }
    ]

    cl_result = identify_try_job_culprit_pipeline._GetSuspectedCLs(
        analysis, failure_type.TEST, result, try_job_suspected_cls)
    self.assertEqual(cl_result, expected_cls)

  def testGetSuspectedCLsForTestTryJobWithHeuristicResult(self):
    suspected_cl = {
        'revision': 'rev1',
        'commit_position': 1,
        'url': 'url_1',
        'repo_name': 'chromium',
        'failures': {
            'step1': ['test1']
        },
        'top_score': 2
    }

    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.suspected_cls = [suspected_cl]
    analysis.put()

    result = {
        'report': {
            'result': {
                'rev1': {
                    'step1': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['test1']
                    }
                }
            }
        }
    }

    self.assertEqual(
        identify_try_job_culprit_pipeline._GetSuspectedCLs(
            analysis, failure_type.TEST, result, {}), [suspected_cl])

  def testIdentifyCulpritForCompileTryJobNoCulprit(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'

    self._CreateEntities(master_name, builder_name, build_number, try_job_id)

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

    self.MockPipeline(
        RevertAndNotifyCulpritPipeline,
        None,
        expected_args=[
            master_name, builder_name, build_number, None, [],
            failure_type.COMPILE
        ])
    pipeline = IdentifyTryJobCulpritPipeline(master_name, builder_name,
                                             build_number, failure_type.COMPILE,
                                             '1', None)
    pipeline.start()
    self.execute_queued_tasks()

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    try_job_data = WfTryJobData.Get(try_job_id)

    self.assertEqual(analysis_status.COMPLETED, try_job.status)
    self.assertEqual([], try_job.compile_results)
    self.assertIsNone(try_job_data.culprits)
    self.assertIsNone(analysis.result_status)
    self.assertIsNone(analysis.suspected_cls)

  def testIdentifyCulpritForCompileTryJobSuccess(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'

    compile_result = {
        'report': {
            'result': {
                'rev1': 'passed',
                'rev2': 'failed'
            },
            'culprit': 'rev2'
        },
        'try_job_id': try_job_id,
    }

    self._CreateEntities(
        master_name,
        builder_name,
        build_number,
        try_job_id,
        try_job_status=analysis_status.RUNNING,
        compile_results=[compile_result])
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

    expected_culprit = 'rev2'
    expected_suspected_cl = {
        'revision': 'rev2',
        'commit_position': 2,
        'url': 'url_2',
        'repo_name': 'chromium'
    }
    expected_compile_result = {
        'report': {
            'result': {
                'rev1': 'passed',
                'rev2': 'failed'
            },
            'culprit': 'rev2'
        },
        'try_job_id': try_job_id,
        'culprit': {
            'compile': expected_suspected_cl
        }
    }
    expected_analysis_suspected_cls = [{
        'revision': 'rev2',
        'commit_position': 2,
        'url': 'url_2',
        'repo_name': 'chromium',
        'failures': {
            'compile': []
        },
        'top_score': None
    }]

    self.MockPipeline(
        RevertAndNotifyCulpritPipeline,
        None,
        expected_args=[
            master_name, builder_name, build_number, {
                expected_culprit: expected_suspected_cl
            }, [], failure_type.COMPILE
        ])
    pipeline = IdentifyTryJobCulpritPipeline(master_name, builder_name,
                                             build_number, failure_type.COMPILE,
                                             '1', compile_result)
    pipeline.start()
    self.execute_queued_tasks()

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(expected_compile_result, try_job.compile_results[-1])
    self.assertEqual(analysis_status.COMPLETED, try_job.status)

    try_job_data = WfTryJobData.Get(try_job_id)
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertEqual({'compile': expected_culprit}, try_job_data.culprits)
    self.assertEqual(analysis.result_status, result_status.FOUND_UNTRIAGED)
    self.assertEqual(analysis.suspected_cls, expected_analysis_suspected_cls)

  def testIdentifyCulpritForCompileReturnNoneIfAllPassed(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'

    compile_result = {
        'report': {
            'result': {
                'rev1': 'passed',
                'rev2': 'passed'
            }
        },
        'url': 'url',
        'try_job_id': try_job_id,
    }

    self._CreateEntities(master_name, builder_name, build_number, try_job_id)

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

    self.MockPipeline(
        RevertAndNotifyCulpritPipeline,
        None,
        expected_args=[
            master_name, builder_name, build_number, {}, [],
            failure_type.COMPILE
        ])
    pipeline = IdentifyTryJobCulpritPipeline(master_name, builder_name,
                                             build_number, failure_type.COMPILE,
                                             '1', compile_result)
    pipeline.start()
    self.execute_queued_tasks()

    try_job = WfTryJob.Get(master_name, builder_name, build_number)

    self.assertEqual(analysis_status.COMPLETED, try_job.status)

    try_job_data = WfTryJobData.Get(try_job_id)
    self.assertIsNone(try_job_data.culprits)

    self.assertIsNone(analysis.result_status)
    self.assertIsNone(analysis.suspected_cls)

  def testIdentifyCulpritForFlakyCompile(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'

    compile_result = {
        'report': {
            'result': {
                'rev1': 'failed',
                'rev2': 'failed'
            },
            'metadata': {
                'sub_ranges': [[None, 'rev2']]
            }
        },
        'url': 'url',
        'try_job_id': try_job_id,
    }

    self._CreateEntities(master_name, builder_name, build_number, try_job_id)

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.result = {
        'failures': [{
            'step_name': 'compile',
            'suspected_cls': []
        }]
    }
    analysis.put()

    self.MockPipeline(
        RevertAndNotifyCulpritPipeline,
        None,
        expected_args=[
            master_name, builder_name, build_number, {}, [],
            failure_type.COMPILE
        ])
    pipeline = IdentifyTryJobCulpritPipeline(master_name, builder_name,
                                             build_number, failure_type.COMPILE,
                                             '1', compile_result)
    pipeline.start()
    self.execute_queued_tasks()

    try_job = WfTryJob.Get(master_name, builder_name, build_number)

    self.assertEqual(analysis_status.COMPLETED, try_job.status)

    try_job_data = WfTryJobData.Get(try_job_id)
    self.assertIsNone(try_job_data.culprits)

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertEqual(result_status.FLAKY, analysis.result_status)
    self.assertEqual([], analysis.suspected_cls)

  def testIdentifyCulpritForTestTryJobNoTryJobResultNoHeuristicResult(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'

    self._CreateEntities(
        master_name,
        builder_name,
        build_number,
        try_job_id,
        try_job_status=analysis_status.RUNNING)

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

    self.MockPipeline(
        RevertAndNotifyCulpritPipeline,
        None,
        expected_args=[
            master_name, builder_name, build_number, None, [], failure_type.TEST
        ])
    pipeline = IdentifyTryJobCulpritPipeline(
        master_name, builder_name, build_number, failure_type.TEST, '1', None)
    pipeline.start()
    self.execute_queued_tasks()

    try_job_data = WfTryJobData.Get(try_job_id)
    self.assertIsNone(try_job_data.culprits)
    self.assertIsNone(analysis.result_status)
    self.assertIsNone(analysis.suspected_cls)

  def testIdentifyCulpritForTestTryJobNoTryJobResultWithHeuristicResult(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'

    suspected_cl = {
        'revision': 'rev1',
        'commit_position': 1,
        'url': 'url_1',
        'repo_name': 'chromium'
    }

    self._CreateEntities(
        master_name,
        builder_name,
        build_number,
        try_job_id,
        try_job_status=analysis_status.RUNNING)

    # Heuristic analysis already provided some results.
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.result_status = result_status.FOUND_UNTRIAGED
    analysis.suspected_cls = [suspected_cl]
    analysis.put()

    self.MockPipeline(
        RevertAndNotifyCulpritPipeline,
        None,
        expected_args=[
            master_name, builder_name, build_number, None,
            [['chromium', 'rev1']], failure_type.TEST
        ])
    pipeline = IdentifyTryJobCulpritPipeline(
        master_name, builder_name, build_number, failure_type.TEST, '1', None)
    pipeline.start()
    self.execute_queued_tasks()

    try_job_data = WfTryJobData.Get(try_job_id)
    self.assertIsNone(try_job_data.culprits)

    # Ensure analysis results are not updated since no culprit from try job.
    self.assertEqual(analysis.result_status, result_status.FOUND_UNTRIAGED)
    self.assertEqual(analysis.suspected_cls, [suspected_cl])

  def testIdentifyCulpritForTestTryJobReturnNoneIfNoRevisionToCheck(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'

    test_result = {
        'report': {
            'result': {
                'rev1': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['a_test1']
                    }
                }
            }
        },
        'url': 'url',
        'try_job_id': try_job_id
    }

    self._CreateEntities(
        master_name,
        builder_name,
        build_number,
        try_job_id,
        try_job_status=analysis_status.RUNNING)

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

    self.MockPipeline(
        RevertAndNotifyCulpritPipeline,
        None,
        expected_args=[
            master_name, builder_name, build_number, {}, [], failure_type.TEST
        ])
    pipeline = IdentifyTryJobCulpritPipeline(master_name, builder_name,
                                             build_number, failure_type.TEST,
                                             '1', test_result)
    pipeline.start()
    self.execute_queued_tasks()

    try_job_data = WfTryJobData.Get(try_job_id)
    self.assertIsNone(try_job_data.culprits)

    self.assertIsNone(analysis.result_status)
    self.assertIsNone(analysis.suspected_cls)

  def testIdentifyCulpritForTestTryJobReturnRevisionIfNoCulpritInfo(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'

    test_result = {
        'report': {
            'result': {
                'rev3': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['a_test1']
                    }
                }
            },
            'culprits': {
                'a_test': {
                    'a_test1': 'rev3'
                }
            }
        },
        'url': 'url',
        'try_job_id': try_job_id
    }

    self._CreateEntities(
        master_name,
        builder_name,
        build_number,
        try_job_id,
        try_job_status=analysis_status.RUNNING)

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

    expected_suspected_cl = {'revision': 'rev3', 'repo_name': 'chromium'}

    expected_analysis_suspected_cls = [{
        'revision': 'rev3',
        'repo_name': 'chromium',
        'failures': {
            'a_test': ['a_test1']
        },
        'top_score': None
    }]

    self.MockPipeline(
        RevertAndNotifyCulpritPipeline,
        None,
        expected_args=[
            master_name, builder_name, build_number, {
                'rev3': expected_suspected_cl
            }, [], failure_type.TEST
        ])
    pipeline = IdentifyTryJobCulpritPipeline(master_name, builder_name,
                                             build_number, failure_type.TEST,
                                             '1', test_result)
    pipeline.start()
    self.execute_queued_tasks()

    try_job_data = WfTryJobData.Get(try_job_id)
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    expected_culprit_data = {'a_test': {'a_test1': 'rev3'}}
    self.assertEqual(expected_culprit_data, try_job_data.culprits)
    self.assertEqual(analysis.result_status, result_status.FOUND_UNTRIAGED)
    self.assertEqual(analysis.suspected_cls, expected_analysis_suspected_cls)

  def testIdentifyCulpritForTestTryJobSuccess(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'

    test_result = {
        'report': {
            'result': {
                'rev0': {
                    'a_test': {
                        'status': 'passed',
                        'valid': True,
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1']
                    }
                },
                'rev1': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['a_test1']
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1']
                    }
                },
                'rev2': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['a_test1', 'a_test2']
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1']
                    }
                }
            },
            'culprits': {
                'a_test': {
                    'a_test1': 'rev1',
                    'a_test2': 'rev2'
                },
            },
            'flakes': {
                'b_test': ['b_test1']
            }
        },
        'url': 'url',
        'try_job_id': try_job_id
    }

    self._CreateEntities(
        master_name,
        builder_name,
        build_number,
        try_job_id,
        try_job_status=analysis_status.RUNNING,
        test_results=[test_result])

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

    a_test1_suspected_cl = {
        'revision': 'rev1',
        'commit_position': 1,
        'url': 'url_1',
        'repo_name': 'chromium'
    }
    a_test2_suspected_cl = {
        'revision': 'rev2',
        'commit_position': 2,
        'url': 'url_2',
        'repo_name': 'chromium'
    }

    expected_test_result = {
        'report': {
            'result': {
                'rev0': {
                    'a_test': {
                        'status': 'passed',
                        'valid': True,
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1']
                    }
                },
                'rev1': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['a_test1']
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1']
                    }
                },
                'rev2': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['a_test1', 'a_test2']
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1']
                    }
                }
            },
            'culprits': {
                'a_test': {
                    'a_test1': 'rev1',
                    'a_test2': 'rev2'
                },
            },
            'flakes': {
                'b_test': ['b_test1']
            }
        },
        'url': 'url',
        'try_job_id': try_job_id,
        'culprit': {
            'a_test': {
                'tests': {
                    'a_test1': a_test1_suspected_cl,
                    'a_test2': a_test2_suspected_cl
                }
            }
        }
    }

    expected_culprits = {
        'rev1': a_test1_suspected_cl,
        'rev2': a_test2_suspected_cl
    }

    self.MockPipeline(
        RevertAndNotifyCulpritPipeline,
        None,
        expected_args=[
            master_name, builder_name, build_number, expected_culprits, [],
            failure_type.TEST
        ])
    pipeline = IdentifyTryJobCulpritPipeline(master_name, builder_name,
                                             build_number, failure_type.TEST,
                                             '1', test_result)
    pipeline.start()
    self.execute_queued_tasks()

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(expected_test_result, try_job.test_results[-1])
    self.assertEqual(analysis_status.COMPLETED, try_job.status)

    try_job_data = WfTryJobData.Get(try_job_id)
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    expected_culprit_data = {
        'a_test': {
            'a_test1': 'rev1',
            'a_test2': 'rev2',
        }
    }

    expected_cls = [{
        'revision': 'rev1',
        'commit_position': 1,
        'url': 'url_1',
        'repo_name': 'chromium',
        'failures': {
            'a_test': ['a_test1'],
            'b_test': ['b_test1'],
        },
        'top_score': None
    }, {
        'revision': 'rev2',
        'commit_position': 2,
        'url': 'url_2',
        'repo_name': 'chromium',
        'failures': {
            'a_test': ['a_test1', 'a_test2'],
            'b_test': ['b_test1'],
        },
        'top_score': None
    }]
    self.assertEqual(expected_culprit_data, try_job_data.culprits)
    self.assertEqual(analysis.result_status, result_status.FOUND_UNTRIAGED)
    self.assertEqual(analysis.suspected_cls, expected_cls)

  def testAnalysisIsUpdatedOnlyIfStatusOrSuspectedCLsChanged(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'
    repo_name = 'chromium'
    revision = 'rev1'
    commit_position = 1

    heuristic_suspected_cl = {
        'revision': revision,
        'commit_position': commit_position,
        'url': 'url_1',
        'repo_name': repo_name
    }

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.suspected_cls = [heuristic_suspected_cl]
    analysis.result_status = result_status.FOUND_UNTRIAGED
    analysis.put()
    version = analysis.version

    build_key = build_util.CreateBuildId(master_name, builder_name,
                                         build_number)
    suspected_cl = WfSuspectedCL.Create(repo_name, revision, commit_position)
    suspected_cl.approaches = [analysis_approach_type.HEURISTIC]
    suspected_cl.builds = {
        build_key: {
            'approaches': [analysis_approach_type.HEURISTIC],
            'failure_type': failure_type.COMPILE,
            'failures': {
                'compile': []
            },
            'status': None,
            'top_score': 4
        }
    }
    suspected_cl.put()

    compile_result = {
        'report': {
            'result': {
                revision: 'failed',
            },
            'culprit': revision
        },
        'try_job_id': try_job_id,
    }

    self._CreateEntities(
        master_name,
        builder_name,
        build_number,
        try_job_id,
        try_job_status=analysis_status.RUNNING,
        compile_results=[compile_result])

    self.MockPipeline(
        RevertAndNotifyCulpritPipeline,
        None,
        expected_args=[
            master_name, builder_name, build_number, {
                revision: heuristic_suspected_cl
            }, [[repo_name, revision]], failure_type.COMPILE
        ])
    pipeline = IdentifyTryJobCulpritPipeline(master_name, builder_name,
                                             build_number, failure_type.COMPILE,
                                             '1', compile_result)
    pipeline.start()
    self.execute_queued_tasks()

    self.assertEqual(analysis.result_status, result_status.FOUND_UNTRIAGED)
    self.assertEqual(analysis.suspected_cls, [heuristic_suspected_cl])
    self.assertEqual(version, analysis.version)  # No update to analysis.

    expected_approaches = [
        analysis_approach_type.HEURISTIC, analysis_approach_type.TRY_JOB
    ]
    expected_builds = {
        build_key: {
            'approaches': expected_approaches,
            'failure_type': failure_type.COMPILE,
            'failures': {
                'compile': []
            },
            'status': None,
            'top_score': 4
        }
    }
    suspected_cl = WfSuspectedCL.Get(repo_name, revision)
    self.assertEqual(expected_approaches, suspected_cl.approaches)
    self.assertEqual(expected_builds, suspected_cl.builds)

  def testFindCulpritForEachTestFailureRevisionNotRun(self):
    result = {'report': {'result': {'rev2': 'passed'}}}

    pipeline = IdentifyTryJobCulpritPipeline()
    culprit_map, failed_revisions = pipeline._FindCulpritForEachTestFailure(
        result)
    self.assertEqual(culprit_map, {})
    self.assertEqual(failed_revisions, [])

  def testFindCulpritForEachTestFailureCulpritsReturned(self):
    result = {'report': {'culprits': {'a_tests': {'Test1': 'rev1'}}}}

    pipeline = IdentifyTryJobCulpritPipeline()
    culprit_map, failed_revisions = pipeline._FindCulpritForEachTestFailure(
        result)

    expected_culprit_map = {
        'a_tests': {
            'tests': {
                'Test1': {
                    'revision': 'rev1'
                }
            }
        }
    }

    self.assertEqual(culprit_map, expected_culprit_map)
    self.assertEqual(failed_revisions, ['rev1'])

  def testReturnNoneIfNoTryJob(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 8

    WfTryJob.Create(master_name, builder_name, build_number).put()

    self.MockPipeline(
        RevertAndNotifyCulpritPipeline,
        None,
        expected_args=[
            master_name, builder_name, build_number, None, [], failure_type.TEST
        ])
    pipeline = IdentifyTryJobCulpritPipeline(
        master_name, builder_name, build_number, failure_type.TEST, None, None)
    pipeline.start()
    self.execute_queued_tasks()

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(try_job.test_results, [])
    self.assertEqual(try_job.status, analysis_status.COMPLETED)

  def testGetTestFailureCausedByCL(self):
    self.assertIsNone(
        identify_try_job_culprit_pipeline._GetTestFailureCausedByCL(None))

  def testGetTestFailureCausedByCLPassed(self):
    result = {
        'a_test': {
            'status': 'passed',
            'valid': True,
        },
        'b_test': {
            'status': 'failed',
            'valid': True,
            'failures': ['b_test1']
        }
    }

    expected_failures = {'b_test': ['b_test1']}

    self.assertEqual(
        expected_failures,
        identify_try_job_culprit_pipeline._GetTestFailureCausedByCL(result))

  def testCompileFailureIsFlakyInvalidResult(self):
    self.assertFalse(
        identify_try_job_culprit_pipeline._CompileFailureIsFlaky(None))
