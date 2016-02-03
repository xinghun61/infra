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


class IdentifyTryJobCulpritPipelineTest(testing.AppengineTestCase):

  def _MockGetChangeLog(self, revision):
    class MockedChangeLog(object):

      def __init__(self, commit_position, code_review_url):
        self.commit_position = commit_position
        self.code_review_url = code_review_url

    mock_change_logs = {}
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
    self.assertEqual(
        'rev2',
        IdentifyTryJobCulpritPipeline._GetFailedRevisionFromCompileResult(
            {
                'report': [
                    ['rev1', 'passed'],
                    ['rev2', 'failed']
                ]
            }))

  def testGetCulpritFromFailedRevision(self):
    self.mock(GitRepository, 'GetChangeLog', self._MockGetChangeLog)
    self.assertIsNone(
        IdentifyTryJobCulpritPipeline._GetCulpritFromFailedRevision(None))
    self.assertIsNone(
        IdentifyTryJobCulpritPipeline._GetCulpritFromFailedRevision(
            'revision_with_no_change_log'))
    self.assertEqual(
        {
            'revision': 'rev2',
            'commit_position': '2',
            'review_url': 'url_2'
        },
        IdentifyTryJobCulpritPipeline._GetCulpritFromFailedRevision('rev2'))

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
        master_name, builder_name, build_number, try_job_id, None)

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
        'try_job_id': '1',
    }]
    try_job.put()

    self.mock(GitRepository, 'GetChangeLog', self._MockGetChangeLog)

    pipeline = IdentifyTryJobCulpritPipeline()
    culprit = pipeline.run(
        master_name, builder_name, build_number, try_job_id, compile_result)

    expected_culprit = 'rev2'
    expected_compile_result = {
        'report': {
            'result': {
                'rev1': 'passed',
                'rev2': 'failed'
            }
        },
        'try_job_id': '1',
        'culprit': {
            'revision': expected_culprit,
            'commit_position': '2',
            'review_url': 'url_2'
        }
    }

    self.assertEqual(expected_compile_result['culprit'], culprit)

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(expected_compile_result, try_job.compile_results[-1])
    self.assertEqual(wf_analysis_status.ANALYZED, try_job.status)

    try_job_data = WfTryJobData.Get(try_job_id)
    self.assertEqual({'compile': expected_culprit}, try_job_data.culprits)
