# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

from common.git_repository import GitRepository
from model import analysis_status
from model import result_status
from model.wf_analysis import WfAnalysis
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from waterfall import identify_try_job_culprit_pipeline
from waterfall.identify_try_job_culprit_pipeline import(
    IdentifyTryJobCulpritPipeline)
from waterfall.try_job_type import TryJobType


class IdentifyTryJobCulpritPipelineTest(testing.AppengineTestCase):

  def _MockGetChangeLog(self, revision):
    class MockedChangeLog(object):

      def __init__(self, commit_position, code_review_url):
        self.commit_position = commit_position
        self.code_review_url = code_review_url

    mock_change_logs = {}
    mock_change_logs['rev1'] = MockedChangeLog('1', 'url_1')
    mock_change_logs['rev2'] = MockedChangeLog('2', 'url_2')
    return mock_change_logs.get(revision)

  def setUp(self):
    super(IdentifyTryJobCulpritPipelineTest, self).setUp()

    self.mock(GitRepository, 'GetChangeLog', self._MockGetChangeLog)

  def testGetFailedRevisionFromResultsDict(self):
    self.assertIsNone(
        identify_try_job_culprit_pipeline._GetFailedRevisionFromResultsDict({}))
    self.assertEqual(
        None,
        identify_try_job_culprit_pipeline._GetFailedRevisionFromResultsDict(
            {'rev1': 'passed'}))
    self.assertEqual(
        'rev1',
        identify_try_job_culprit_pipeline._GetFailedRevisionFromResultsDict(
            {'rev1': 'failed'}))
    self.assertEqual(
        'rev2',
        identify_try_job_culprit_pipeline._GetFailedRevisionFromResultsDict(
            {'rev1': 'passed', 'rev2': 'failed'}))

  def testGetFailedRevisionFromCompileResult(self):
    self.assertIsNone(
        identify_try_job_culprit_pipeline._GetFailedRevisionFromCompileResult(
            None))
    self.assertIsNone(
        identify_try_job_culprit_pipeline._GetFailedRevisionFromCompileResult(
            {'report': {}}))
    self.assertIsNone(
        identify_try_job_culprit_pipeline._GetFailedRevisionFromCompileResult(
            {
                'report': {
                    'result': {
                        'rev1': 'passed'
                    }
                }
            }))
    self.assertEqual(
        'rev2',
        identify_try_job_culprit_pipeline._GetFailedRevisionFromCompileResult(
            {
                'report': {
                    'result': {
                        'rev1': 'passed',
                        'rev2': 'failed'
                    }
                }
            }))
    self.assertEqual(
        'rev1',
        identify_try_job_culprit_pipeline._GetFailedRevisionFromCompileResult(
            {
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
                'commit_position': '1',
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
                'commit_position': '1',
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
                'commit_position': '1',
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
                'commit_position': '1',
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
                'commit_position': '1',
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
        'commit_position': '1',
        'url': 'url_1',
        'repo_name': 'chromium'
    }

    compile_suspected_cl = {
        'revision': 'rev2',
        'commit_position': '2',
        'url': 'url_2',
        'repo_name': 'chromium'
    }

    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.suspected_cls = [heuristic_suspected_cl]
    analysis.put()

    result = {
        'culprit': {
            'compile': compile_suspected_cl
        }
    }

    self.assertEqual(
        identify_try_job_culprit_pipeline._GetSuspectedCLs(analysis, result),
        [heuristic_suspected_cl, compile_suspected_cl])

  def testGetSuspectedCLsForTestTryJobAndHeuristicResultsSame(self):
    suspected_cl = {
        'revision': 'rev1',
        'commit_position': '1',
        'url': 'url_1',
        'repo_name': 'chromium'
    }

    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.suspected_cls = [suspected_cl]
    analysis.put()

    result = {
        'culprit': {
            'compile': suspected_cl
        }
    }

    self.assertEqual(
        identify_try_job_culprit_pipeline._GetSuspectedCLs(analysis, result),
        [suspected_cl])

  def testGetSuspectedCLsForTestTryJob(self):
    suspected_cl1 = {
        'revision': 'rev1',
        'commit_position': '1',
        'url': 'url_1',
        'repo_name': 'chromium'
    }
    suspected_cl2 = {
        'revision': 'rev2',
        'commit_position': '2',
        'url': 'url_2',
        'repo_name': 'chromium'
    }
    suspected_cl3 = {
        'revision': 'rev3',
        'commit_position': '3',
        'url': 'url_3',
        'repo_name': 'chromium'
    }

    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.suspected_cls = []
    analysis.put()

    result = {
        'culprit': {
            'a_test': {
                'tests': {
                    'a_test1': suspected_cl1,
                    'a_test2': suspected_cl1
                }
            },
            'b_test': {
                'tests': {
                    'b_test1': suspected_cl2
                }
            },
            'c_test': {
                'revision': 'rev3',
                'commit_position': '3',
                'url': 'url_3',
                'repo_name': 'chromium',
                'tests': {}
            }
        }
    }

    self.assertEqual(
        identify_try_job_culprit_pipeline._GetSuspectedCLs(analysis, result),
        [suspected_cl3, suspected_cl2, suspected_cl1])

  def testGetSuspectedCLsForTestTryJobWithHeuristicResult(self):
    suspected_cl = {
        'revision': 'rev1',
        'commit_position': '1',
        'url': 'url_1',
        'repo_name': 'chromium'
    }

    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.suspected_cls = [suspected_cl]
    analysis.put()

    result = {
        'culprit': {
            'a_test': {
                'revision': 'rev1',
                'commit_position': '1',
                'url': 'url_1',
                'repo_name': 'chromium',
                'tests': {}
            }
        }
    }
    self.assertEqual(
        identify_try_job_culprit_pipeline._GetSuspectedCLs(analysis, result),
        [suspected_cl])

  def testIdentifyCulpritForCompileTryJobNoCulprit(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.put()
    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.put()

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

    pipeline = IdentifyTryJobCulpritPipeline()
    culprit = pipeline.run(
        master_name, builder_name, build_number, ['rev1'],
        TryJobType.COMPILE, '1', None)
    try_job = WfTryJob.Get(master_name, builder_name, build_number)

    self.assertEqual(analysis_status.COMPLETED, try_job.status)
    self.assertEqual([], try_job.compile_results)
    self.assertIsNone(culprit)
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
        },
    }

    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.put()

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.status = analysis_status.RUNNING
    try_job.compile_results = [{
        'report': {
            'result': {
                'rev1': 'passed',
                'rev2': 'failed'
            },
        },
        'try_job_id': try_job_id,
    }]
    try_job.put()
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

    pipeline = IdentifyTryJobCulpritPipeline()
    culprit = pipeline.run(
        master_name, builder_name, build_number, ['rev1'],
        TryJobType.COMPILE, '1', compile_result)

    expected_culprit = 'rev2'
    expected_suspected_cl = {
        'revision': 'rev2',
        'commit_position': '2',
        'url': 'url_2',
        'repo_name': 'chromium'
    }
    expected_compile_result = {
        'report': {
            'result': {
                'rev1': 'passed',
                'rev2': 'failed'
            }
        },
        'try_job_id': try_job_id,
        'culprit': {
            'compile': expected_suspected_cl
        }
    }

    self.assertEqual(expected_compile_result['culprit'], culprit)

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(expected_compile_result, try_job.compile_results[-1])
    self.assertEqual(analysis_status.COMPLETED, try_job.status)

    try_job_data = WfTryJobData.Get(try_job_id)
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertEqual({'compile': expected_culprit}, try_job_data.culprits)
    self.assertEqual(analysis.result_status,
                     result_status.FOUND_UNTRIAGED)
    self.assertEqual(analysis.suspected_cls,
                     [expected_suspected_cl])

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

    WfTryJobData.Create(try_job_id).put()
    WfTryJob.Create(master_name, builder_name, build_number).put()
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

    pipeline = IdentifyTryJobCulpritPipeline()
    culprit = pipeline.run(
        master_name, builder_name, build_number, ['rev1'],
        TryJobType.COMPILE, '1', compile_result)
    try_job = WfTryJob.Get(master_name, builder_name, build_number)

    self.assertIsNone(culprit)
    self.assertEqual(analysis_status.COMPLETED, try_job.status)

    try_job_data = WfTryJobData.Get(try_job_id)
    self.assertIsNone(try_job_data.culprits)

    self.assertIsNone(analysis.result_status)
    self.assertIsNone(analysis.suspected_cls)

  def testIdentifyCulpritForTestTryJobNoTryJobResultNoHeuristicResult(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'

    WfTryJobData.Create(try_job_id).put()
    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.status = analysis_status.RUNNING
    try_job.put()
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

    pipeline = IdentifyTryJobCulpritPipeline()
    culprit = pipeline.run(
        master_name, builder_name, build_number, ['rev1', 'rev2'],
        TryJobType.TEST, '1', None)

    self.assertIsNone(culprit)

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
        'commit_position': '1',
        'url': 'url_1',
        'repo_name': 'chromium'
    }

    WfTryJobData.Create(try_job_id).put()
    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.status = analysis_status.RUNNING
    try_job.put()

    # Heuristic analysis already provided some results.
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.result_status = result_status.FOUND_UNTRIAGED
    analysis.suspected_cls = [suspected_cl]
    analysis.put()

    pipeline = IdentifyTryJobCulpritPipeline()
    culprit = pipeline.run(
        master_name, builder_name, build_number, ['rev1', 'rev2'],
        TryJobType.TEST, '1', None)

    self.assertIsNone(culprit)

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

    WfTryJobData.Create(try_job_id).put()
    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.status = analysis_status.RUNNING
    try_job.put()
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

    pipeline = IdentifyTryJobCulpritPipeline()
    culprit = pipeline.run(
        master_name, builder_name, build_number, [], TryJobType.TEST, '1',
        test_result)

    self.assertIsNone(culprit)

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
            }
        },
        'url': 'url',
        'try_job_id': try_job_id
    }

    WfTryJobData.Create(try_job_id).put()
    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.status = analysis_status.RUNNING
    try_job.put()
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

    pipeline = IdentifyTryJobCulpritPipeline()
    culprit = pipeline.run(
        master_name, builder_name, build_number, ['rev3'], TryJobType.TEST,
        '1', test_result)

    expected_suspected_cl = {
        'revision': 'rev3',
        'repo_name': 'chromium'
    }

    expected_culprit = {
        'a_test': {
            'tests': {
                'a_test1': expected_suspected_cl
            }
        }
    }
    self.assertEqual(expected_culprit, culprit)

    try_job_data = WfTryJobData.Get(try_job_id)
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    expected_culprit_data = {
        'a_test': {
            'a_test1': 'rev3'
        }
    }
    self.assertEqual(expected_culprit_data, try_job_data.culprits)
    self.assertEqual(analysis.result_status,
                     result_status.FOUND_UNTRIAGED)
    self.assertEqual(analysis.suspected_cls, [expected_suspected_cl])

  def testIdentifyCulpritForTestTryJobSuccess(self):
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
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1']
                    },
                    'c_test': {
                        'status': 'passed',
                        'valid': True
                    }
                },
                'rev2': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['a_test1', 'a_test2']
                    },
                    'b_test': {
                        'status': 'passed',
                        'valid': True
                    },
                    'c_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': []
                    }
                }
            }
        },
        'url': 'url',
        'try_job_id': try_job_id
    }

    WfTryJobData.Create(try_job_id).put()
    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.status = analysis_status.RUNNING
    try_job.test_results = [test_result]
    try_job.put()
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

    pipeline = IdentifyTryJobCulpritPipeline()
    culprit = pipeline.run(
        master_name, builder_name, build_number, ['rev1', 'rev2'],
        TryJobType.TEST, '1', test_result)

    a_test1_suspected_cl = {
        'revision': 'rev1',
        'commit_position': '1',
        'url': 'url_1',
        'repo_name': 'chromium'
    }
    a_test2_suspected_cl = {
        'revision': 'rev2',
        'commit_position': '2',
        'url': 'url_2',
        'repo_name': 'chromium'
    }

    b_test1_suspected_cl = a_test1_suspected_cl

    expected_test_result = {
        'report': {
            'result': {
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
                    },
                    'c_test': {
                        'status': 'passed',
                        'valid': True
                    }
                },
                'rev2': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['a_test1', 'a_test2']
                    },
                    'b_test': {
                        'status': 'passed',
                        'valid': True
                    },
                    'c_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': []
                    }
                }
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
            },
            'b_test': {
                'tests': {
                    'b_test1': b_test1_suspected_cl
                }
            },
            'c_test': {
                'revision': 'rev2',
                'commit_position': '2',
                'url': 'url_2',
                'repo_name': 'chromium',
                'tests': {}
            }
        }
    }

    self.assertEqual(expected_test_result['culprit'], culprit)

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(expected_test_result, try_job.test_results[-1])
    self.assertEqual(analysis_status.COMPLETED, try_job.status)

    try_job_data = WfTryJobData.Get(try_job_id)
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    expected_culprit_data = {
        'a_test': {
            'a_test1': 'rev1',
            'a_test2': 'rev2',
        },
        'b_test': {
            'b_test1': 'rev1',
        },
        'c_test': 'rev2'
        }
    self.assertEqual(expected_culprit_data, try_job_data.culprits)
    self.assertEqual(analysis.result_status,
                     result_status.FOUND_UNTRIAGED)
    self.assertEqual(analysis.suspected_cls,
                     [a_test2_suspected_cl, a_test1_suspected_cl])

  def testAnalysisIsUpdatedOnlyIfStatusOrSuspectedCLsChanged(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'

    suspected_cl = {
        'revision': 'rev1',
        'commit_position': '1',
        'url': 'url_1',
        'repo_name': 'chromium'
    }

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.suspected_cls = [suspected_cl]
    analysis.result_status = result_status.FOUND_UNTRIAGED
    analysis.put()
    version = analysis.version
    compile_result = {
        'report': {
            'result': {
                'rev1': 'failed',
            },
        },
    }

    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.put()

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.status = analysis_status.RUNNING
    try_job.compile_results = [{
        'report': {
            'result': {
                'rev1': 'failed',
            },
        },
        'try_job_id': try_job_id,
    }]

    try_job.put()

    pipeline = IdentifyTryJobCulpritPipeline()
    pipeline.run(master_name, builder_name, build_number, ['rev1'],
                 TryJobType.COMPILE, '1', compile_result)

    self.assertEqual(analysis.result_status,
                     result_status.FOUND_UNTRIAGED)
    self.assertEqual(analysis.suspected_cls, [suspected_cl])
    self.assertEqual(version, analysis.version)  # No update to analysis.

  def testFindCulpritForEachTestFailureRevisionNotRun(self):
    blame_list = ['rev1']
    result = {
        'report': {
            'result': {
                'rev2': 'passed'
            }
        }
    }

    pipeline = IdentifyTryJobCulpritPipeline()
    culprit_map, failed_revisions = pipeline._FindCulpritForEachTestFailure(
        blame_list, result)
    self.assertEqual(culprit_map, {})
    self.assertEqual(failed_revisions, [])

  def testFindCulpritForEachTestFailureCulpritsReturned(self):
    blame_list = ['rev1']
    result = {
        'report': {
            'culprits': {
                'a_tests': {
                    'Test1': 'rev1'
                }
            }
        }
    }

    pipeline = IdentifyTryJobCulpritPipeline()
    culprit_map, failed_revisions = pipeline._FindCulpritForEachTestFailure(
        blame_list, result)

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

  def testNotifyCulprits(self):
    instances = []
    class Mocked_SendNotificationForCulpritPipeline(object):
      def __init__(self, *args):
        self.args = args
        self.started = False
        instances.append(self)

      def start(self):
        self.started = True

    self.mock(
        identify_try_job_culprit_pipeline, 'SendNotificationForCulpritPipeline',
        Mocked_SendNotificationForCulpritPipeline)

    culprits = {
        'r1': {
            'repo_name': 'chromium',
            'revision': 'r1',
        }
    }

    identify_try_job_culprit_pipeline._NotifyCulprits('m', 'b', 1, culprits)
    self.assertEqual(1, len(instances))
    self.assertTrue(instances[0].started)
