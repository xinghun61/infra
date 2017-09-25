# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from gae_libs.pipeline_wrapper import pipeline_handlers
from libs import analysis_status
from libs.gitiles.gitiles_repository import GitilesRepository
from model import result_status
from model.wf_analysis import WfAnalysis
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from pipelines.compile_failure import (identify_compile_try_job_culprit_pipeline
                                       as culprit_pipeline)
from pipelines.compile_failure import (
    revert_and_notify_compile_culprit_pipeline as revert_pipeline)
from waterfall.test import wf_testcase


class IdentifyCompileTryJobCulpritPipelineTest(wf_testcase.WaterfallTestCase):
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
    super(IdentifyCompileTryJobCulpritPipelineTest, self).setUp()

    self.mock(GitilesRepository, 'GetChangeLog', self._MockGetChangeLog)

  def _CreateEntities(self,
                      master_name,
                      builder_name,
                      build_number,
                      try_job_id,
                      try_job_status=None,
                      compile_results=None):
    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    if try_job_status:
      try_job.status = try_job_status
    if compile_results:
      try_job.compile_results = compile_results
    try_job.put()

    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.put()

  @mock.patch.object(revert_pipeline, 'RevertAndNotifyCompileCulpritPipeline')
  def testIdentifyCulpritForCompileTryJobNoCulprit(self, mock_revert_pipeline):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'

    self._CreateEntities(master_name, builder_name, build_number, try_job_id)

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

    pipeline = culprit_pipeline.IdentifyCompileTryJobCulpritPipeline(
        master_name, builder_name, build_number, '1', None)
    pipeline.start()
    self.execute_queued_tasks()

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    try_job_data = WfTryJobData.Get(try_job_id)

    self.assertEqual(analysis_status.COMPLETED, try_job.status)
    self.assertEqual([], try_job.compile_results)
    self.assertIsNone(try_job_data.culprits)
    self.assertIsNone(analysis.result_status)
    self.assertIsNone(analysis.suspected_cls)
    mock_revert_pipeline.assert_not_called()

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
        revert_pipeline.RevertAndNotifyCompileCulpritPipeline,
        None,
        expected_args=[
            master_name, builder_name, build_number, {
                expected_culprit: expected_suspected_cl
            }, []
        ])
    pipeline = culprit_pipeline.IdentifyCompileTryJobCulpritPipeline(
        master_name, builder_name, build_number, '1', compile_result)
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
        revert_pipeline.RevertAndNotifyCompileCulpritPipeline,
        None,
        expected_args=[master_name, builder_name, build_number, {}, []])
    pipeline = culprit_pipeline.IdentifyCompileTryJobCulpritPipeline(
        master_name, builder_name, build_number, '1', compile_result)
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
        revert_pipeline.RevertAndNotifyCompileCulpritPipeline,
        None,
        expected_args=[master_name, builder_name, build_number, {}, []])
    pipeline = culprit_pipeline.IdentifyCompileTryJobCulpritPipeline(
        master_name, builder_name, build_number, '1', compile_result)
    pipeline.start()
    self.execute_queued_tasks()

    try_job = WfTryJob.Get(master_name, builder_name, build_number)

    self.assertEqual(analysis_status.COMPLETED, try_job.status)

    try_job_data = WfTryJobData.Get(try_job_id)
    self.assertIsNone(try_job_data.culprits)

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertEqual(result_status.FLAKY, analysis.result_status)
    self.assertEqual([], analysis.suspected_cls)
