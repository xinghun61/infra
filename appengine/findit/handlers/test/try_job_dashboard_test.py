# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
from datetime import timedelta
import json

import webapp2

from handlers import try_job_dashboard
from model.wf_try_job_data import WfTryJobData

from testing_utils import testing


class TryJobDashboardTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/try-job-dashboard', try_job_dashboard.TryJobDashboard),
  ], debug=True)

  def validateTryJobDisplayData(self, expected_try_job_data_list,
                                actual_try_job_data_list):
    self.assertEqual(
        len(expected_try_job_data_list), len(actual_try_job_data_list))

    # Validates each field in each expected data dict matches those in each
    # actual data dict. Note order matters in each list. Note a direct list
    # comparison is not possible since try jobs in progress will have
    # constantly-changing elapsed_time fields depending on the time the tests
    # are run, so we compare all other fields to avoid this.
    for i in range(len(expected_try_job_data_list)):
      expected_try_job_data = expected_try_job_data_list[i]
      actual_try_job_data = actual_try_job_data_list[i]

      for field, expected_data in expected_try_job_data.iteritems():
        self.assertEqual(expected_data, actual_try_job_data.get(field))

  def testFormatDuration(self):
    self.assertEqual(try_job_dashboard._FormatDuration(None, None),
                     try_job_dashboard.NOT_AVAILABLE)
    self.assertEqual(
        try_job_dashboard._FormatDuration(datetime(2016, 1, 2, 1, 2, 3), None),
        try_job_dashboard.NOT_AVAILABLE)
    self.assertEqual(
        try_job_dashboard._FormatDuration(None, datetime(2016, 1, 2, 1, 2, 3)),
        try_job_dashboard.NOT_AVAILABLE)
    self.assertEqual(
        try_job_dashboard._FormatDuration(datetime(2016, 1, 2, 1, 2, 3),
                                          datetime(2016, 1, 2, 1, 2, 4)),
        '00:00:01')

  def testPrepareBuildbucketResponseForDisplayNoData(self):
    self.assertEqual(
        try_job_dashboard._PrepareBuildbucketResponseForDisplay(None),
        None)
    self.assertEqual(
        try_job_dashboard._PrepareBuildbucketResponseForDisplay({}),
        {})

  def testPrepareBuildbucketResponseForDisplayWithJson(self):
    properties = {
        'a': 1,
        'b': 2
    }
    buildbucket_response = {
        'has_json': json.dumps(properties),
        'blabla': 'blabla'
    }
    self.assertEqual(
        try_job_dashboard._PrepareBuildbucketResponseForDisplay(
            buildbucket_response),
        {
            'blabla': 'blabla',
            'has_json': properties
        })

  def testGet(self):
    try_job_in_progress = WfTryJobData.Create(1)
    try_job_in_progress.master_name = 'm'
    try_job_in_progress.builder_name = 'b'
    try_job_in_progress.build_number = 1
    try_job_in_progress.try_job_type = 'compile'
    try_job_in_progress.start_time = datetime(2016, 5, 4, 0, 0, 1)
    try_job_in_progress.request_time = datetime(2016, 5, 4, 0, 0, 0)
    try_job_in_progress.try_job_url = 'url1'
    try_job_in_progress.last_buildbucket_response = {'status': 'STARTED'}
    try_job_in_progress.put()

    try_job_with_error = WfTryJobData.Create(2)
    try_job_with_error.master_name = 'm'
    try_job_with_error.builder_name = 'b'
    try_job_with_error.build_number = 2
    try_job_with_error.try_job_type = 'compile'
    try_job_with_error.start_time = datetime(2016, 5, 4, 0, 0, 1)
    try_job_with_error.request_time = datetime(2016, 5, 4, 0, 0, 0)
    try_job_with_error.end_time = datetime(2016, 5, 4, 0, 0, 2)
    try_job_with_error.try_job_url = 'url2'
    try_job_with_error.error = {
        'message': 'some error',
        'reason': 'some reason'
    }
    try_job_with_error.last_buildbucket_response = {
        'failure_reason': 'INFRA_FAILURE'
    }
    try_job_with_error.put()

    try_job_completed = WfTryJobData.Create(3)
    try_job_completed.master_name = 'm'
    try_job_completed.builder_name = 'b'
    try_job_completed.build_number = 3
    try_job_completed.try_job_type = 'compile'
    try_job_completed.start_time = datetime(2016, 5, 4, 0, 0, 1)
    try_job_completed.request_time = datetime(2016, 5, 4, 0, 0, 0)
    try_job_completed.end_time = datetime(2016, 5, 4, 0, 0, 2)
    try_job_completed.try_job_url = 'url3'
    try_job_completed.culprits = {
        'compile': {
            '12345': 'failed'
        }
    }
    try_job_completed.last_buildbucket_response = {
        'status': 'COMPLETED'
    }
    try_job_completed.put()

    expected_try_job_in_progress_display_data = {
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 1,
        'try_job_type': 'compile',
        'request_time': '2016-05-04 00:00:00 UTC',
        'try_job_url': 'url1',
        'status': 'running',
        'last_buildbucket_response': '{"status": "STARTED"}'
    }

    expected_try_job_with_error_display_data = {
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 2,
        'try_job_type': 'compile',
        'request_time': '2016-05-04 00:00:00 UTC',
        'try_job_url': 'url2',
        'error': 'some error',
        'last_buildbucket_response': '{"failure_reason": "INFRA_FAILURE"}'
    }

    expected_try_job_completed_display_data = {
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 3,
        'try_job_type': 'compile',
        'request_time': '2016-05-04 00:00:00 UTC',
        'try_job_url': 'url3',
        'culprit_found': True,
        'last_buildbucket_response': '{"status": "COMPLETED"}'
    }

    response = self.test_app.get(
        '/try-job-dashboard?format=json&start_date=2016-05-03')
    response_data = response.json_body
    try_jobs_in_progress = response_data.get('try_jobs_in_progress')
    try_jobs_with_error = response_data.get('try_jobs_with_error')
    successfully_completed_try_jobs = response_data.get(
        'successfully_completed_try_jobs')

    self.assertEqual(response.status_int, 200)
    self.validateTryJobDisplayData(
        [expected_try_job_in_progress_display_data],
        try_jobs_in_progress)
    self.validateTryJobDisplayData(
        [expected_try_job_with_error_display_data],
        try_jobs_with_error)
    self.validateTryJobDisplayData(
        [expected_try_job_completed_display_data],
        successfully_completed_try_jobs)
