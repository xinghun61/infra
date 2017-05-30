# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import mock
import re

import webapp2
import webtest

from google.appengine.api import users

from handlers.flake import check_flake
from handlers.flake.check_flake import CheckFlake
from libs import analysis_status
from libs.analysis_status import STATUS_TO_DESCRIPTION
from model.flake.flake_analysis_request import BuildStep
from model.flake.flake_analysis_request import FlakeAnalysisRequest
from model.flake.flake_culprit import FlakeCulprit
from model.flake.flake_try_job import FlakeTryJob
from model.flake.flake_try_job_data import FlakeTryJobData
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall import buildbot
from waterfall.flake import flake_analysis_service
from waterfall.test import wf_testcase


class CheckFlakeTest(wf_testcase.WaterfallTestCase):
  app_module = webapp2.WSGIApplication([
      ('/waterfall/flake', check_flake.CheckFlake),
  ], debug=True)

  @mock.patch.object(flake_analysis_service, 'ScheduleAnalysisForFlake',
                     return_value=True)
  def testCorpUserCanScheduleANewAnalysis(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = '123'
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number, step_name, test_name)
    analysis.Save()

    self.mock_current_user(user_email='test@google.com')

    response = self.test_app.get('/waterfall/flake', params={
        'url': buildbot.CreateBuildUrl(master_name, builder_name, build_number),
        'step_name': step_name,
        'test_name': test_name})

    self.assertEquals(200, response.status_int)

  def testNoneCorpUserCanNotScheduleANewAnalysis(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = '123'
    step_name = 's'
    test_name = 't'

    self.assertRaisesRegexp(
        webtest.app.AppError,
        re.compile('.*401 Unauthorized.*',
                   re.MULTILINE | re.DOTALL),
        self.test_app.get,
        '/waterfall/flake',
        params={
            'url': buildbot.CreateBuildUrl(
                master_name, builder_name, build_number),
            'step_name': step_name,
            'test_name': test_name
        })

  @mock.patch.object(check_flake, '_GetSuspectedFlakeInfo',
                     return_value={
                         'build_number': 100,
                         'commit_position': 12345,
                         'git_hash': 'git_hash_1',
                         'triage_result': 0})
  @mock.patch.object(check_flake, '_GetCoordinatesData',
                     return_value=[[12345, 0.9, '1', 100, 'git_hash_2',
                                    12344, 'git_hash_1']])
  def testAnyoneCanViewScheduledAnalysis(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = '123'
    step_name = 's'
    test_name = 't'
    success_rate = .9

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number, step_name, test_name)
    data_point = DataPoint()
    data_point.build_number = int(build_number)
    data_point.pass_rate = success_rate
    data_point.task_id = '1'
    analysis.data_points.append(data_point)
    analysis.status = analysis_status.COMPLETED
    analysis.suspected_flake_build_number = 100
    analysis.request_time = datetime.datetime(2016, 10, 01, 12, 10, 00)
    analysis.start_time = datetime.datetime(2016, 10, 01, 12, 10, 05)
    analysis.end_time = datetime.datetime(2016, 10, 01, 13, 10, 00)
    analysis.algorithm_parameters = {'iterations_to_rerun': 100}
    analysis.Save()

    self.mock_current_user(user_email='test@example.com')

    response = self.test_app.get('/waterfall/flake', params={
        'key': analysis.key.urlsafe(),
        'format': 'json'})

    expected_check_flake_result = {
        'key': analysis.key.urlsafe(),
        'pass_rates': [[12345, 0.9, '1', 100, 'git_hash_2', 12344,
                        'git_hash_1']],
        'analysis_status': STATUS_TO_DESCRIPTION.get(analysis.status),
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': int(build_number),
        'step_name': step_name,
        'test_name': test_name,
        'request_time': '2016-10-01 12:10:00 UTC',
        'build_level_number': 1,
        'revision_level_number': 0,
        'error': None,
        'iterations_to_rerun': 100,
        'pending_time': '00:00:05',
        'duration': '00:59:55',
        'suspected_flake': {
            'build_number': 100,
            'commit_position': 12345,
            'git_hash': 'git_hash_1',
            'triage_result': 0
        },
        'version_number': 1,
        'show_input_ui': False,
        'culprit': {},
        'try_job_status': None,
        'last_attempted_swarming_task': {
            'task_id': None,
            'build_number': None
        },
        'last_attempted_try_job': {},
    }

    self.assertEquals(200, response.status_int)
    self.assertEqual(expected_check_flake_result, response.json_body)

  def testUnauthorizedUserCannotScheduleNewAnalysis(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'

    self.assertRaisesRegexp(
        webtest.app.AppError,
        re.compile('.*401 Unauthorized.*', re.MULTILINE | re.DOTALL),
        self.test_app.get,
        '/waterfall/flake',
        params={
            'url': buildbot.CreateBuildUrl(
                master_name, builder_name, build_number),
            'step_name': step_name,
            'test_name': test_name,
            'format': 'json'})

  @mock.patch.object(flake_analysis_service, 'ScheduleAnalysisForFlake',
                     return_value=False)
  @mock.patch.object(check_flake, '_GetSuspectedFlakeInfo',
                     return_value={
                         'build_number': 100,
                         'commit_position': 12345,
                         'git_hash': 'a_git_hash',
                         'triage_result': 0})
  @mock.patch.object(check_flake, '_GetCoordinatesData',
                     return_value=[[12345, 0.9, '1', 100, 'git_hash_2',
                                    12344, 'git_hash_1']])
  def testRequestExistingAnalysis(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    success_rate = 0.9

    previous_analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number - 1, step_name, test_name)
    data_point = DataPoint()
    data_point.build_number = build_number - 1
    data_point.pass_rate = success_rate
    previous_analysis.data_points.append(data_point)
    previous_analysis.status = analysis_status.COMPLETED
    previous_analysis.suspected_flake_build_number = 100
    previous_analysis.request_time = datetime.datetime(2016, 10, 01, 12, 10, 00)
    previous_analysis.start_time = datetime.datetime(2016, 10, 01, 12, 10, 05)
    previous_analysis.end_time = datetime.datetime(2016, 10, 01, 13, 10, 00)
    previous_analysis.algorithm_parameters = {'iterations_to_rerun': 100}
    previous_analysis.Save()

    previous_request = FlakeAnalysisRequest.Create(test_name, False, None)
    build_step = BuildStep.Create(
        master_name, builder_name, build_number, step_name, None)
    build_step.wf_master_name = build_step.master_name
    build_step.wf_builder_name = build_step.builder_name
    build_step.wf_build_number = build_step.build_number
    build_step.wf_step_name = build_step.step_name
    previous_request.build_steps.append(build_step)
    previous_request.analyses.append(previous_analysis.key)
    previous_request.Save()

    self.mock_current_user(user_email='test@google.com')

    response = self.test_app.get('/waterfall/flake', params={
        'url': buildbot.CreateBuildUrl(master_name, builder_name, build_number),
        'step_name': step_name,
        'test_name': test_name,
        'format': 'json'})

    expected_check_flake_result = {
        'key': previous_analysis.key.urlsafe(),
        'pass_rates': [[12345, 0.9, '1', 100, 'git_hash_2', 12344,
                        'git_hash_1']],
        'analysis_status': STATUS_TO_DESCRIPTION.get(previous_analysis.status),
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number - 1,
        'step_name': step_name,
        'test_name': test_name,
        'request_time': '2016-10-01 12:10:00 UTC',
        'build_level_number': 1,
        'revision_level_number': 0,
        'error': None,
        'iterations_to_rerun': 100,
        'pending_time': '00:00:05',
        'duration': '00:59:55',
        'suspected_flake': {
            'build_number': 100,
            'commit_position': 12345,
            'git_hash': 'a_git_hash',
            'triage_result': 0
        },
        'version_number': 1,
        'show_input_ui': False,
        'culprit': {},
        'try_job_status': None,
        'last_attempted_swarming_task': {
            'task_id': None,
            'build_number': None
        },
        'last_attempted_try_job': {},
    }

    self.assertEqual(200, response.status_int)
    self.assertEqual(expected_check_flake_result, response.json_body)

  @mock.patch.object(flake_analysis_service, 'ScheduleAnalysisForFlake',
                     return_value=False)
  def testRequestUnsupportedAnalysis(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'

    previous_request = FlakeAnalysisRequest.Create(test_name, False, None)
    previous_request.AddBuildStep(
        master_name, builder_name, build_number, step_name, None)
    previous_request.swarmed = False
    previous_request.supported = False

    self.assertRaisesRegexp(
        webtest.app.AppError,
        re.compile('.*not supported.*', re.MULTILINE | re.DOTALL),
        self.test_app.get,
        '/waterfall/flake',
        params={
            'url': buildbot.CreateBuildUrl(
                master_name, builder_name, build_number),
            'step_name': step_name,
            'test_name': test_name,
            'format': 'json'})

  @mock.patch.object(check_flake, '_GetSuspectedFlakeInfo',
                     return_value={
                         'build_number': 100,
                         'commit_position': 12345,
                         'git_hash': 'a_git_hash',
                         'triage_result': 0})
  @mock.patch.object(check_flake, '_GetCoordinatesData',
                     return_value=[[12345, 0.9, '1', 100, 'git_hash_2',
                                    12344, 'git_hash_1']])
  @mock.patch.object(users, 'is_current_user_admin', return_value=True)
  @mock.patch.object(flake_analysis_service, 'ScheduleAnalysisForFlake',
                     return_value=True)
  def testGetTriageHistory(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = '123'
    step_name = 's'
    test_name = 't'
    suspected_flake_build_number = 123
    triage_result = 2
    user_name = 'test'

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number, step_name, test_name)
    analysis.status = analysis_status.COMPLETED
    analysis.suspected_flake_build_number = 100
    analysis.Save()
    analysis.UpdateTriageResult(
        triage_result, {'build_number': suspected_flake_build_number}, 'test')

    response = self.test_app.get('/waterfall/flake', params={
        'url': buildbot.CreateBuildUrl(master_name, builder_name, build_number),
        'step_name': step_name,
        'test_name': test_name,
        'format': 'json'})

    # Because TriagedResult uses auto_now=True, a direct dict comparison will
    # always fail. Instead only compare the relevant fields for trige_history.
    triage_history = response.json_body.get('triage_history')
    self.assertEqual(len(triage_history), 1)
    self.assertEqual(triage_history[0].get('triage_result'), 'Correct')
    self.assertEqual(triage_history[0].get('user_name'), user_name)
    self.assertEqual(
        triage_history[0].get('suspect_info', {}).get('build_number'),
        suspected_flake_build_number)

  def testValidateInput(self):
    self.assertIsNone(CheckFlake()._ValidateInput('s', 't', None))
    self.assertIsNone(CheckFlake()._ValidateInput('s', 't', '654321'))
    self.assertEqual(
        CheckFlake()._ValidateInput(
            None, 't', '').get('data', {}).get('error_message'),
        'Step name must be specified')
    self.assertEqual(
        CheckFlake()._ValidateInput(
            's', None, '').get('data', {}).get('error_message'),
        'Test name must be specified')
    self.assertEqual(
        CheckFlake()._ValidateInput(
            's', 't', 'a').get('data', {}).get('error_message'),
        'Bug id must be an int')

  def testGetSuspectedFlakeInfo(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.suspected_flake_build_number = 123
    data_point = DataPoint()
    data_point.build_number = 123
    data_point.pass_rate = 0.9
    data_point.commit_position = 2
    data_point.git_hash = 'git_hash_2'
    data_point.previous_build_commit_position = 1
    data_point.previous_build_git_hash = 'git_hash_1'
    analysis.data_points.append(data_point)
    analysis.confidence_in_suspected_build = 0
    analysis.Save()

    expected_result = {
        'confidence': 0,
        'build_number': analysis.suspected_flake_build_number,
        'commit_position': 2,
        'git_hash': 'git_hash_2',
        'lower_bound_commit_position': 1,
        'lower_bound_git_hash': 'git_hash_1',
        'triage_result': 0
    }
    self.assertEqual(expected_result,
                     check_flake._GetSuspectedFlakeInfo(analysis))

  def testGetCulpritInfo(self):
    commit_position = 2
    git_hash = 'git_hash_2'
    url = 'url'
    culprit = FlakeCulprit.Create('chromium', git_hash, commit_position, url)

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.culprit = culprit

    expected_result = {
        'commit_position': commit_position,
        'git_hash': git_hash,
        'url': url,
        'confidence': None,
    }
    self.assertEqual(expected_result,
                     check_flake._GetCulpritInfo(analysis))

  def testGetCoordinatesData(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    success_rate = .9
    try_job_url = 'try_job_url'
    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number, step_name, test_name)
    data_point_1 = DataPoint()
    data_point_1.build_number = build_number
    data_point_1.pass_rate = success_rate
    data_point_1.commit_position = 5
    data_point_1.git_hash = 'git_hash_5'
    data_point_1.previous_build_commit_position = 4
    data_point_1.previous_build_git_hash = 'git_hash_4'
    data_point_1.try_job_url = try_job_url
    analysis.data_points.append(data_point_1)

    data_point_2 = DataPoint()
    data_point_2.build_number = build_number - 3
    data_point_2.pass_rate = success_rate
    data_point_2.commit_position = 2
    data_point_2.git_hash = 'git_hash_2'
    data_point_2.previous_build_commit_position = 1
    data_point_2.previous_build_git_hash = 'git_hash_1'
    data_point_2.try_job_url = try_job_url
    analysis.data_points.append(data_point_2)
    analysis.Save()

    expected_result = [
        {
            'commit_position': 2,
            'pass_rate': success_rate,
            'task_id': None,
            'build_number': build_number - 3,
            'git_hash': 'git_hash_2',
            'try_job_url': try_job_url
        },
        {
            'commit_position': 5,
            'pass_rate': success_rate,
            'task_id': None,
            'build_number': build_number,
            'git_hash': 'git_hash_5',
            'lower_bound_commit_position': 2,
            'lower_bound_git_hash': 'git_hash_2',
            'try_job_url': try_job_url
        }
    ]
    self.assertEqual(expected_result, check_flake._GetCoordinatesData(analysis))

  def testGetNumbersOfDataPointGroups(self):
    data_point1 = DataPoint()
    data_point1.try_job_url = 'try_job_url'

    data_point2 = DataPoint()
    data_point2.build_number = 1

    data_points = [data_point1, data_point2]
    self.assertEqual((1, 1),
                     check_flake._GetNumbersOfDataPointGroups(data_points))

  def testGetLastAttemptedSwarmingTask(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.last_attempted_swarming_task_id = 'a1b2c3d4'
    analysis.last_attempted_build_number = 122
    expected_result = {
        'task_id': 'a1b2c3d4',
        'build_number': 122
    }
    self.assertEqual(
        expected_result,
        check_flake._GetLastAttemptedSwarmingTaskDetails(analysis))

  def testGetLastAttemptedTryJobDetailsNoRevision(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.last_attempted_revision = None
    self.assertEqual({}, check_flake._GetLastAttemptedTryJobDetails(analysis))

  def testGetLastAttemptedTryJobDetailsNoTryJob(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.last_attempted_revision = 'r1'
    self.assertEqual({}, check_flake._GetLastAttemptedTryJobDetails(analysis))

  def testGetLastAttemptedTryJobDetailsNoTryJobID(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    revision = 'r1'

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number, step_name, test_name)
    analysis.last_attempted_revision = revision
    try_job = FlakeTryJob.Create(
        master_name, builder_name, step_name, test_name, revision)
    try_job.put()
    self.assertEqual({}, check_flake._GetLastAttemptedTryJobDetails(analysis))

  def testGetLastAttemptedTryJobDetailsNoTryJobData(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    revision = 'r1'
    try_job_id = '12345'

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number, step_name, test_name)
    analysis.last_attempted_revision = revision
    try_job = FlakeTryJob.Create(
        master_name, builder_name, step_name, test_name, revision)
    try_job.try_job_ids = [try_job_id]
    try_job.put()
    self.assertEqual({}, check_flake._GetLastAttemptedTryJobDetails(analysis))

  def testGetLastAttemptedTryJobDetails(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    revision = 'r1'
    try_job_id = '12345'
    try_job_url = 'url'
    status = analysis_status.RUNNING

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number, step_name, test_name)
    analysis.last_attempted_revision = revision
    analysis.put()
    try_job = FlakeTryJob.Create(
        master_name, builder_name, step_name, test_name, revision)
    try_job.try_job_ids = [try_job_id]
    try_job.status = status
    try_job.put()

    try_job_data = FlakeTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.try_job_url = try_job_url
    try_job_data.put()
    self.assertEqual(
        {
            'url': try_job_url,
            'status': analysis_status.STATUS_TO_DESCRIPTION.get(status)
        },
        check_flake._GetLastAttemptedTryJobDetails(analysis))
