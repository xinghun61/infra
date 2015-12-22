# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from testing_utils import testing

from handlers import try_job_result
from model.wf_analysis import WfAnalysis
from model import wf_analysis_status
from model.wf_try_job import WfTryJob
from waterfall import buildbot


class TryJobResultTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/try-job-result', try_job_result.TryJobResult),], debug=True)

  def setUp(self):
    super(TryJobResultTest, self).setUp()
    self.master_name = 'm'
    self.builder_name = 'b'
    self.build_number = 121
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)

  def testGetTryJobResultReturnNoneIfNoFailureResultMap(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.put()

    result = try_job_result._GetTryJobResult(
        self.master_name, self.builder_name, self.build_number)

    self.assertEqual({}, result)

  def testGetTryJobResultReturnNoneIfNoCompileFailure(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.failure_result_map = {
        'browser_tests': 'm/b/121'
    }
    analysis.put()

    result = try_job_result._GetTryJobResult(
        self.master_name, self.builder_name, self.build_number)

    self.assertEqual({}, result)

  def testGetTryJobResultReturnNoneIfNoTryJob(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.failure_result_map = {
        'compile': 'm/b/121'
    }
    analysis.put()

    result = try_job_result._GetTryJobResult(
        self.master_name, self.builder_name, self.build_number)

    self.assertEqual({}, result)


  def testGetTryJobResultOnlyReturnStatusIfPending(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.failure_result_map = {
        'compile': 'm/b/121'
    }
    analysis.put()

    try_job = WfTryJob.Create(
      self.master_name, self.builder_name, self.build_number)
    try_job.put()

    result = try_job_result._GetTryJobResult(
        self.master_name, self.builder_name, self.build_number)

    expected_result = {
        'status': 'Pending'
    }

    self.assertEqual(expected_result, result)

  def testGetTryJobResultOnlyReturnUrlIfStarts(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.failure_result_map = {
        'compile': 'm/b/121'
    }
    analysis.put()

    try_job = WfTryJob.Create(
      self.master_name, self.builder_name, self.build_number)
    try_job.status = wf_analysis_status.ANALYZING
    try_job.compile_results = [
        {
            'result': None,
            'url': 'url'
        }
    ]
    try_job.put()

    result = try_job_result._GetTryJobResult(
        self.master_name, self.builder_name, self.build_number)

    expected_result = {
        'status': 'Analyzing',
        'try_job_url': 'url'
    }

    self.assertEqual(expected_result, result)

  def testGetTryJobResultOnlyReturnStatusIfError(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.failure_result_map = {
        'compile': 'm/b/121'
    }
    analysis.put()

    try_job = WfTryJob.Create(
      self.master_name, self.builder_name, self.build_number)
    try_job.status = wf_analysis_status.ERROR
    try_job.compile_results = [
        {
            'try_job_id': '1'
        }
    ]
    try_job.put()

    result = try_job_result._GetTryJobResult(
        self.master_name, self.builder_name, self.build_number)

    expected_result = {
        'status': 'Error'
    }

    self.assertEqual(expected_result, result)

  def testGetTryJobResultWhenTryJobCompleted(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.failure_result_map = {
        'compile': 'm/b/121'
    }
    analysis.put()

    try_job = WfTryJob.Create(
      self.master_name, self.builder_name, self.build_number)
    try_job.status = wf_analysis_status.ANALYZED
    try_job.compile_results = [
        {
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
    ]
    try_job.put()

    result = try_job_result._GetTryJobResult(
        self.master_name, self.builder_name, self.build_number)

    expected_result = {
        'status': 'Analyzed',
        'try_job_url': 'url',
        'revision': 'rev2',
        'commit_position': '2',
        'review_url': 'url_2'
    }

    self.assertEqual(expected_result, result)

  def testGetTryJobResultWhenTryJobCompletedAllPassed(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.failure_result_map = {
        'compile': 'm/b/121'
    }
    analysis.put()

    try_job = WfTryJob.Create(
      self.master_name, self.builder_name, self.build_number)
    try_job.status = wf_analysis_status.ANALYZED
    try_job.compile_results = [
        {
            'result': [
                ['rev1', 'passed'],
                ['rev2', 'passed']
            ],
            'url': 'url'
        }
    ]
    try_job.put()

    result = try_job_result._GetTryJobResult(
        self.master_name, self.builder_name, self.build_number)

    expected_result = {
        'status': 'Analyzed',
        'try_job_url': 'url'
    }

    self.assertEqual(expected_result, result)

  def testTryJobResultHandler(self):
    build_url = buildbot.CreateBuildUrl(
        self.master_name, self.builder_name, self.build_number)
    response = self.test_app.get('/try-job-result', params={'url':build_url})
    expected_results = {}

    self.assertEqual(200, response.status_int)
    self.assertEqual(expected_results, response.json_body)
