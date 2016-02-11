# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

from common.git_repository import GitRepository
from model import wf_analysis_status
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
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

  def testGetFailedRevisionFromResultsDict(self):
    self.assertIsNone(
        IdentifyTryJobCulpritPipeline._GetFailedRevisionFromResultsDict({}))
    self.assertEqual(
        None,
        IdentifyTryJobCulpritPipeline._GetFailedRevisionFromResultsDict(
            {'rev1': 'passed'}))
    self.assertEqual(
        'rev1',
        IdentifyTryJobCulpritPipeline._GetFailedRevisionFromResultsDict(
            {'rev1': 'failed'}))
    self.assertEqual(
        'rev2',
        IdentifyTryJobCulpritPipeline._GetFailedRevisionFromResultsDict(
            {'rev1': 'passed', 'rev2': 'failed'}))

  def testGetFailedRevisionFromCompileResult(self):
    self.assertIsNone(
        IdentifyTryJobCulpritPipeline._GetFailedRevisionFromCompileResult(
            None))
    self.assertIsNone(
        IdentifyTryJobCulpritPipeline._GetFailedRevisionFromCompileResult(
            {'report': {}}))
    self.assertIsNone(
        IdentifyTryJobCulpritPipeline._GetFailedRevisionFromCompileResult(
            {
                'report': {
                    'result': {
                        'rev1': 'passed'
                    }
                }
            }))
    self.assertEqual(
        'rev2',
        IdentifyTryJobCulpritPipeline._GetFailedRevisionFromCompileResult(
            {
                'report': {
                    'result': {
                        'rev1': 'passed',
                        'rev2': 'failed'
                    }
                }
            }))

  def testIdentifyCulpritForCompileTryJobNoCulprit(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.put()
    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.put()

    pipeline = IdentifyTryJobCulpritPipeline()
    culprit = pipeline.run(
        master_name, builder_name, build_number, ['rev1'],
        TryJobType.COMPILE, '1', None)
    try_job = WfTryJob.Get(master_name, builder_name, build_number)

    self.assertEqual(wf_analysis_status.ANALYZED, try_job.status)
    self.assertEqual([], try_job.compile_results)
    self.assertIsNone(culprit)
    self.assertIsNone(try_job_data.culprits)

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
    try_job.status = wf_analysis_status.ANALYZING
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

    self.mock(GitRepository, 'GetChangeLog', self._MockGetChangeLog)

    pipeline = IdentifyTryJobCulpritPipeline()
    culprit = pipeline.run(
        master_name, builder_name, build_number, ['rev1'],
        TryJobType.COMPILE, '1', compile_result)

    expected_culprit = 'rev2'
    expected_compile_result = {
        'report': {
            'result': {
                'rev1': 'passed',
                'rev2': 'failed'
            }
        },
        'try_job_id': try_job_id,
        'culprit': {
            'compile': {
                'revision': 'rev2',
                'commit_position': '2',
                'review_url': 'url_2'
            }
        }
    }

    self.assertEqual(expected_compile_result['culprit'], culprit)

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(expected_compile_result, try_job.compile_results[-1])
    self.assertEqual(wf_analysis_status.ANALYZED, try_job.status)

    try_job_data = WfTryJobData.Get(try_job_id)
    self.assertEqual({'compile': expected_culprit}, try_job_data.culprits)

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

    pipeline = IdentifyTryJobCulpritPipeline()
    culprit = pipeline.run(
        master_name, builder_name, build_number, ['rev1'],
        TryJobType.COMPILE, '1', compile_result)
    try_job = WfTryJob.Get(master_name, builder_name, build_number)

    self.assertIsNone(culprit)
    self.assertEqual(wf_analysis_status.ANALYZED, try_job.status)

    try_job_data = WfTryJobData.Get(try_job_id)
    self.assertIsNone(try_job_data.culprits)

  def testIdentifyCulpritForTestTryJobReturnNoneIfNoTryJobResult(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'

    WfTryJobData.Create(try_job_id).put()
    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.status = wf_analysis_status.ANALYZING
    try_job.put()

    pipeline = IdentifyTryJobCulpritPipeline()
    culprit = pipeline.run(
        master_name, builder_name, build_number, ['rev1', 'rev2'],
        TryJobType.TEST, '1', None)

    self.assertIsNone(culprit)

    try_job_data = WfTryJobData.Get(try_job_id)
    self.assertIsNone(try_job_data.culprits)

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
    try_job.status = wf_analysis_status.ANALYZING
    try_job.put()

    pipeline = IdentifyTryJobCulpritPipeline()
    culprit = pipeline.run(
        master_name, builder_name, build_number, [], TryJobType.TEST, '1',
        test_result)

    self.assertIsNone(culprit)

    try_job_data = WfTryJobData.Get(try_job_id)
    self.assertIsNone(try_job_data.culprits)

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
    try_job.status = wf_analysis_status.ANALYZING
    try_job.put()

    pipeline = IdentifyTryJobCulpritPipeline()
    culprit = pipeline.run(
        master_name, builder_name, build_number, ['rev3'], TryJobType.TEST,
        '1', test_result)

    expected_culprit = {
        'a_test': {
            'tests': {
                'a_test1': {
                    'revision': 'rev3'
                }
            }
        }
    }
    self.assertEqual(expected_culprit, culprit)

    try_job_data = WfTryJobData.Get(try_job_id)
    expected_culprit_data = {
        'a_test': {
            'a_test1': 'rev3'
        }
    }
    self.assertEqual(expected_culprit_data, try_job_data.culprits)

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
    try_job.status = wf_analysis_status.ANALYZING
    try_job.test_results = [test_result]
    try_job.put()

    self.mock(GitRepository, 'GetChangeLog', self._MockGetChangeLog)

    pipeline = IdentifyTryJobCulpritPipeline()
    culprit = pipeline.run(
        master_name, builder_name, build_number, ['rev1', 'rev2'],
        TryJobType.TEST, '1', test_result)

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
                    'a_test1': {
                        'revision': 'rev1',
                        'commit_position': '1',
                        'review_url': 'url_1'
                    },
                    'a_test2': {
                        'revision': 'rev2',
                        'commit_position': '2',
                        'review_url': 'url_2'
                    }
                }
            },
            'b_test': {
                'tests': {
                    'b_test1': {
                        'revision': 'rev1',
                        'commit_position': '1',
                        'review_url': 'url_1'
                    }
                }
            },
            'c_test': {
                'revision': 'rev2',
                'commit_position': '2',
                'review_url': 'url_2',
                'tests': {}
            }
        }
    }

    self.assertEqual(expected_test_result['culprit'], culprit)

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(expected_test_result, try_job.test_results[-1])
    self.assertEqual(wf_analysis_status.ANALYZED, try_job.status)

    try_job_data = WfTryJobData.Get(try_job_id)
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
