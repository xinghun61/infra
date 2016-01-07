# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

from common.git_repository import GitRepository
from model import wf_analysis_status
from model.wf_try_job import WfTryJob
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

  def testIdentifyCulpritForCompileReturnNoneIfNoCompileResult(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'
    compile_result = None

    WfTryJob.Create(master_name, builder_name, build_number).put()
    pipeline = IdentifyTryJobCulpritPipeline()
    culprit = pipeline.run(
        master_name, builder_name, build_number, try_job_id, compile_result)
    try_job = WfTryJob.Get(master_name, builder_name, build_number)

    self.assertIsNone(culprit)
    self.assertEqual(wf_analysis_status.ANALYZED, try_job.status)

  def testIdentifyCulpritForCompileReturnNoneIfNoTryJobResultForCompile(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'
    compile_result = {
        'result': [],
        'url': 'url',
        'try_job_id': '1',
    }
    WfTryJob.Create(master_name, builder_name, build_number).put()

    pipeline = IdentifyTryJobCulpritPipeline()
    culprit = pipeline.run(
        master_name, builder_name, build_number, try_job_id, compile_result)
    try_job = WfTryJob.Get(master_name, builder_name, build_number)

    self.assertIsNone(culprit)
    self.assertEqual(wf_analysis_status.ANALYZED, try_job.status)

  def testIdentifyCulpritForCompileReturnNoneIfAllPassed(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'
    compile_result = {
        'result': [
            ['rev1', 'passed'],
            ['rev2', 'passed']
        ],
        'url': 'url',
        'try_job_id': '1',
    }
    WfTryJob.Create(master_name, builder_name, build_number).put()

    pipeline = IdentifyTryJobCulpritPipeline()
    culprit = pipeline.run(
        master_name, builder_name, build_number, try_job_id, compile_result)
    try_job = WfTryJob.Get(master_name, builder_name, build_number)

    self.assertIsNone(culprit)
    self.assertEqual(wf_analysis_status.ANALYZED, try_job.status)

  def testIdentifyCulpritForCompileReturnNoneIfNoChangeLog(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'
    compile_result = {
        'result': [
            ['rev1', 'failed']
        ],
        'url': 'url',
        'try_job_id': '1',
    }

    self.mock(GitRepository, 'GetChangeLog', self._MockGetChangeLog)
    WfTryJob.Create(master_name, builder_name, build_number).put()

    pipeline = IdentifyTryJobCulpritPipeline()
    culprit = pipeline.run(
        master_name, builder_name, build_number, try_job_id, compile_result)
    try_job = WfTryJob.Get(master_name, builder_name, build_number)

    self.assertIsNone(culprit)
    self.assertEqual(wf_analysis_status.ANALYZED, try_job.status)

  def testIdentifyCulpritForCompileTryJobSuccess(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'
    compile_result = {
        'result': [
            ['rev1', 'passed'],
            ['rev2', 'failed']
        ],
        'url': 'url',
        'try_job_id': '1',
    }

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.status = wf_analysis_status.ANALYZING
    try_job.compile_results = [{
        'result': [
            ['rev1', 'passed'],
            ['rev2', 'failed']
        ],
        'url': 'url',
        'try_job_id': '1',
    }]
    try_job.put()

    self.mock(GitRepository, 'GetChangeLog', self._MockGetChangeLog)

    pipeline = IdentifyTryJobCulpritPipeline()
    culprit = pipeline.run(
        master_name, builder_name, build_number, try_job_id, compile_result)

    expected_compile_result = {
        'result': [
            ['rev1', 'passed'],
            ['rev2', 'failed']
        ],
        'url': 'url',
        'try_job_id': '1',
        'culprit': {
            'revision': 'rev2',
            'commit_position': '2',
            'review_url': 'url_2'
        }
    }

    self.assertEqual(expected_compile_result['culprit'], culprit)

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(expected_compile_result, try_job.compile_results[-1])
    self.assertEqual(wf_analysis_status.ANALYZED, try_job.status)
