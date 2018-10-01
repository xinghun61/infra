# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import mock
import webapp2

from google.appengine.api import users

from handlers.flake import check_flake
from handlers.flake.check_flake import CheckFlake
from libs import analysis_status
from libs import time_util
from libs.analysis_status import STATUS_TO_DESCRIPTION
from model.flake.analysis.flake_analysis_request import BuildStep
from model.flake.analysis.flake_analysis_request import FlakeAnalysisRequest
from model.flake.analysis.flake_culprit import FlakeCulprit
from model.flake.analysis.flake_try_job import FlakeTryJob
from model.flake.analysis.flake_try_job_data import FlakeTryJobData
from model.flake.analysis.master_flake_analysis import DataPoint
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from pipelines.flake_failure.analyze_flake_pipeline import AnalyzeFlakePipeline
from waterfall import buildbot
from waterfall.flake import flake_analysis_service
from waterfall.test import wf_testcase


class CheckFlakeTest(wf_testcase.WaterfallTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/waterfall/flake', check_flake.CheckFlake),
      ], debug=True)

  @mock.patch.object(
      check_flake.auth_util, 'GetUserEmail', return_value='email')
  @mock.patch.object(
      check_flake.token, 'ValidateAuthToken', return_value=(True, False))
  def testPostWithBadUrl(self, *_):
    response = self.test_app.post(
        '/waterfall/flake',
        params={
            'url': 'this is not a valid build url',
            'step_name': 's',
            'test_name': 't',
            'xsrf_token': 'abc',
            'format': 'json',
        },
        status=400)
    self.assertEqual('Unknown build info!',
                     response.json_body.get('error_message'))

  @mock.patch.object(
      check_flake.auth_util, 'GetUserEmail', return_value='email')
  @mock.patch.object(
      check_flake.token, 'ValidateAuthToken', return_value=(True, False))
  def testPostWithoutStepName(self, *_):
    response = self.test_app.post(
        '/waterfall/flake',
        params={
            'url': buildbot.CreateBuildUrl('m', 'b', 1),
            'test_name': 't',
            'xsrf_token': 'abc',
            'format': 'json',
        },
        status=400)
    self.assertEqual('Step name must be specified',
                     response.json_body.get('error_message'))

  @mock.patch.object(
      check_flake.auth_util, 'GetUserEmail', return_value='email')
  @mock.patch.object(
      flake_analysis_service, 'ScheduleAnalysisForFlake', return_value=False)
  @mock.patch.object(
      check_flake.token, 'ValidateAuthToken', return_value=(True, False))
  def testNotScheduleAnalysisButExistingAnalysisWasDeleted(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'

    previous_analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number - 1, step_name, test_name)
    previous_analysis.Save()

    previous_request = FlakeAnalysisRequest.Create(test_name, False, None)
    build_step = BuildStep.Create(master_name, builder_name, build_number - 1,
                                  step_name, None)
    build_step.wf_master_name = build_step.master_name
    build_step.wf_builder_name = build_step.builder_name
    build_step.wf_build_number = build_step.build_number - 1
    build_step.wf_step_name = build_step.step_name
    previous_request.build_steps.append(build_step)
    previous_request.analyses.append(previous_analysis.key)
    previous_request.Save()

    # Simulate an expected deletion.
    previous_analysis.key.delete()

    self.mock_current_user(user_email='test@google.com', is_admin=False)

    response = self.test_app.post(
        '/waterfall/flake',
        params={
            'url':
                buildbot.CreateBuildUrl(master_name, builder_name,
                                        build_number),
            'step_name':
                step_name,
            'test_name':
                test_name,
            'xsrf_token':
                'abc',
            'format':
                'json',
        },
        status=404)
    self.assertEqual('Flake analysis was deleted unexpectedly!',
                     response.json_body.get('error_message'))

  @mock.patch.object(
      check_flake.auth_util, 'GetUserEmail', return_value='test@google.com')
  @mock.patch.object(
      flake_analysis_service, 'ScheduleAnalysisForFlake', return_value=True)
  @mock.patch.object(
      check_flake.token, 'ValidateAuthToken', return_value=(True, False))
  def testCorpUserCanScheduleANewAnalysis(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = '123'
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    response = self.test_app.post(
        '/waterfall/flake',
        params={
            'url':
                buildbot.CreateBuildUrl(master_name, builder_name,
                                        build_number),
            'step_name':
                step_name,
            'test_name':
                test_name,
            'xsrf_token':
                'abc',
        },
        status=302)
    expected_url_surfix = (
        '/waterfall/flake?redirect=1&key=%s' % analysis.key.urlsafe())
    self.assertTrue(
        response.headers.get('Location', '').endswith(expected_url_surfix))

  @mock.patch.object(
      check_flake.auth_util, 'GetUserEmail', return_value='test@chromium.org')
  @mock.patch.object(
      check_flake.token, 'ValidateAuthToken', return_value=(True, False))
  def testNoneCorpUserCanNotScheduleANewAnalysis(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = '123'
    step_name = 's'
    test_name = 't'

    response = self.test_app.post(
        '/waterfall/flake',
        params={
            'url':
                buildbot.CreateBuildUrl(master_name, builder_name,
                                        build_number),
            'step_name':
                step_name,
            'test_name':
                test_name,
            'format':
                'json',
        },
        status=403)
    self.assertEqual(('No permission to schedule an analysis for flaky test. '
                      'Please log in with your @google.com account first.'),
                     response.json_body.get('error_message'))

  def testMissingKeyGet(self):
    response = self.test_app.get(
        '/waterfall/flake', params={'format': 'json'}, status=404)
    self.assertEqual('No key was provided.',
                     response.json_body.get('error_message'))

  @mock.patch.object(
      check_flake.auth_util, 'GetUserEmail', return_value='test@google.com')
  @mock.patch.object(
      check_flake.auth_util, 'IsCurrentUserAdmin', return_value=True)
  @mock.patch.object(
      check_flake.token, 'ValidateAuthToken', return_value=(True, False))
  def testMissingKeyPost(self, *_):
    response = self.test_app.post(
        '/waterfall/flake', params={
            'format': 'json',
            'rerun': '1'
        }, status=404)
    self.assertEqual('No key was provided.',
                     response.json_body.get('error_message'))

  def testAnalysisNotFoundGet(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.Save()

    # Simulate a deletion.
    analysis.key.delete()

    response = self.test_app.get(
        '/waterfall/flake',
        params={
            'format': 'json',
            'key': analysis.key.urlsafe()
        },
        status=404)
    self.assertEqual('Analysis of flake is not found.',
                     response.json_body.get('error_message'))

  @mock.patch.object(
      check_flake.auth_util, 'GetUserEmail', return_value='test@google.com')
  @mock.patch.object(
      check_flake.auth_util, 'IsCurrentUserAdmin', return_value=True)
  @mock.patch.object(
      check_flake.token, 'ValidateAuthToken', return_value=(True, False))
  def testRerunAnalysisNotFoundPost(self, *_):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.Save()

    # Simulate a deletion.
    analysis.key.delete()

    response = self.test_app.post(
        '/waterfall/flake',
        params={
            'format': 'json',
            'rerun': '1',
            'key': analysis.key.urlsafe()
        },
        status=404)
    self.assertEqual('Analysis of flake is not found.',
                     response.json_body.get('error_message'))

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2017, 1, 1))
  @mock.patch.object(
      check_flake,
      '_GetSuspectedFlakeInfo',
      return_value={
          'build_number': 100,
          'commit_position': 200,
          'git_hash': 'git_hash_1',
          'triage_result': 0,
      })
  @mock.patch.object(
      check_flake,
      '_GetCoordinatesData',
      return_value=[[12345, 0.9, '1', 100, 'git_hash_2', 12344, 'git_hash_1']])
  def testAnyoneCanViewScheduledAnalysis(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    culprit_git_hash = 'git_hash_1'
    culprit_url = 'url'
    culprit_commit_position = 200
    lower_commit_position = 100
    success_rate = .9

    suspect = FlakeCulprit.Create('repo', culprit_git_hash,
                                  culprit_commit_position, culprit_url)
    suspect.put()
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.original_master_name = master_name
    analysis.original_builder_name = builder_name
    analysis.original_build_number = build_number
    analysis.original_step_name = step_name
    analysis.original_test_name = test_name
    data_point1 = DataPoint()
    data_point1.build_number = 101
    data_point1.pass_rate = success_rate
    data_point1.task_ids = ['task_id1']
    data_point1.commit_position = culprit_commit_position
    data_point1.git_hash = culprit_git_hash
    analysis.data_points.append(data_point1)
    data_point2 = DataPoint()
    data_point2.build_number = 100
    data_point2.pass_rate = 1.0
    data_point2.task_ids = ['task_id2']
    data_point2.commit_position = lower_commit_position
    data_point2.git_hash = culprit_git_hash
    analysis.data_points.append(data_point2)
    analysis.status = analysis_status.COMPLETED
    analysis.suspected_flake_build_number = 100
    analysis.updated_time = datetime.datetime(2016, 1, 1)
    analysis.request_time = datetime.datetime(2016, 10, 01, 12, 10, 00)
    analysis.start_time = datetime.datetime(2016, 10, 01, 12, 10, 05)
    analysis.end_time = datetime.datetime(2016, 10, 01, 13, 10, 00)
    analysis.pipeline_status_path = 'pipelinestatus'
    analysis.suspect_urlsafe_keys.append(suspect.key.urlsafe())
    analysis.Save()

    self.mock_current_user(user_email='test@example.com', is_admin=False)

    response = self.test_app.get(
        '/waterfall/flake',
        params={
            'key': analysis.key.urlsafe(),
            'format': 'json'
        })

    expected_check_flake_result = {
        'key':
            analysis.key.urlsafe(),
        'pass_rates': [[
            12345, 0.9, '1', 100, 'git_hash_2', 12344, 'git_hash_1'
        ]],
        'master_name':
            master_name,
        'builder_name':
            builder_name,
        'build_number':
            int(build_number),
        'step_name':
            step_name,
        'test_name':
            test_name,
        'request_time':
            '2016-10-01 12:10:00 UTC',
        'ended_days_ago':
            '91 days, 10:50:00',
        'duration':
            '00:59:55',
        'analysis_complete':
            True,
        'build_level_number':
            2,
        'revision_level_number':
            0,
        'error':
            None,
        'pending_time':
            '00:00:05',
        'suspected_flake': {
            'build_number': 100,
            'commit_position': 200,
            'git_hash': 'git_hash_1',
            'triage_result': 0
        },
        'suspected_culprits': [{
            'commit_position': culprit_commit_position,
            'git_hash': culprit_git_hash,
            'url': culprit_url,
        }],
        'version_number':
            1,
        'show_admin_options':
            False,
        'culprit': {},
        'last_attempted_swarming_task': {
            'task_id': None,
            'build_number': None
        },
        'last_attempted_try_job': {},
        'pipeline_status_path':
            'pipelinestatus',
        'show_debug_options':
            False,
        'bug_id':
            '',
        'culprit_confidence':
            '',
        'culprit_revision':
            '',
        'culprit_url':
            '',
        'regression_range_lower':
            lower_commit_position,
        'regression_range_upper':
            culprit_commit_position
    }

    self.assertEquals(200, response.status_int)
    self.assertDictContainsSubset(expected_check_flake_result,
                                  response.json_body)

  @mock.patch.object(
      check_flake.auth_util, 'GetUserEmail', return_value='test@google.com')
  @mock.patch.object(
      check_flake.token, 'ValidateAuthToken', return_value=(False, False))
  def testRejectRequestWithInvalidXSRFToken(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'

    response = self.test_app.post(
        '/waterfall/flake',
        params={
            'url':
                buildbot.CreateBuildUrl(master_name, builder_name,
                                        build_number),
            'step_name':
                step_name,
            'test_name':
                test_name,
            'format':
                'json'
        },
        status=403)

    self.assertEqual(
        'Invalid XSRF token. Please log in or refresh the page first.',
        response.json_body.get('error_message'))

  @mock.patch.object(
      check_flake.auth_util, 'GetUserEmail', return_value='test@google.com')
  @mock.patch.object(
      check_flake.token, 'ValidateAuthToken', return_value=(True, False))
  @mock.patch.object(
      flake_analysis_service, 'ScheduleAnalysisForFlake', return_value=False)
  def testRequestAnalysisWhenThereIsExistingAnalysis(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'

    previous_analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number - 1, step_name, test_name)
    previous_analysis.Save()

    previous_request = FlakeAnalysisRequest.Create(test_name, False, None)
    build_step = BuildStep.Create(master_name, builder_name, build_number,
                                  step_name, None)
    build_step.wf_master_name = build_step.master_name
    build_step.wf_builder_name = build_step.builder_name
    build_step.wf_build_number = build_step.build_number
    build_step.wf_step_name = build_step.step_name
    previous_request.build_steps.append(build_step)
    previous_request.analyses.append(previous_analysis.key)
    previous_request.Save()

    response = self.test_app.post(
        '/waterfall/flake',
        params={
            'url':
                buildbot.CreateBuildUrl(master_name, builder_name,
                                        build_number),
            'step_name':
                step_name,
            'test_name':
                test_name,
            'format':
                'json'
        },
        status=302)
    expected_url_surfix = (
        '/waterfall/flake?redirect=1&key=%s' % previous_analysis.key.urlsafe())
    self.assertTrue(
        response.headers.get('Location', '').endswith(expected_url_surfix))

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2017, 1, 1))
  @mock.patch.object(
      check_flake,
      '_GetSuspectedFlakeInfo',
      return_value={
          'build_number': 100,
          'commit_position': 12345,
          'git_hash': 'a_git_hash',
          'triage_result': 0
      })
  @mock.patch.object(
      check_flake,
      '_GetCoordinatesData',
      return_value=[[12345, 0.9, '1', 100, 'git_hash_2', 12344, 'git_hash_1']])
  def testAnyoneCanViewExistingAnalysis(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    success_rate = 0.9

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number - 1, step_name, test_name)
    analysis.original_master_name = master_name
    analysis.original_builder_name = builder_name
    analysis.original_build_number = build_number - 1
    analysis.original_step_name = step_name
    analysis.original_test_name = test_name
    data_point1 = DataPoint()
    data_point1.build_number = 101
    data_point1.pass_rate = success_rate
    data_point1.task_ids = ['task_id1']
    data_point1.commit_position = 12345
    data_point1.git_hash = 'hash1'
    data_point1.commit_position_landed_time = datetime.datetime(2016, 12, 31)
    analysis.data_points.append(data_point1)
    data_point2 = DataPoint()
    data_point2.build_number = 100
    data_point2.pass_rate = 1.0
    data_point2.task_ids = ['task_id2']
    data_point2.commit_position = 12340
    data_point2.git_hash = 'hash2'
    analysis.data_points.append(data_point2)
    analysis.status = analysis_status.RUNNING
    analysis.suspected_flake_build_number = 100
    analysis.updated_time = datetime.datetime(2016, 1, 1)
    analysis.request_time = datetime.datetime(2016, 10, 01, 12, 10, 00)
    analysis.start_time = datetime.datetime(2016, 10, 01, 12, 10, 05)
    analysis.end_time = datetime.datetime(2016, 10, 01, 13, 10, 00)
    analysis.pipeline_status_path = 'pipelinestatus'
    analysis.Save()

    response = self.test_app.get(
        '/waterfall/flake',
        params={
            'key': analysis.key.urlsafe(),
            'format': 'json'
        })

    expected_check_flake_result = {
        'key':
            analysis.key.urlsafe(),
        'pass_rates': [[
            12345, 0.9, '1', 100, 'git_hash_2', 12344, 'git_hash_1'
        ]],
        'master_name':
            master_name,
        'builder_name':
            builder_name,
        'build_number':
            build_number - 1,
        'step_name':
            step_name,
        'test_name':
            test_name,
        'request_time':
            '2016-10-01 12:10:00 UTC',
        'ended_days_ago':
            '91 days, 10:50:00',
        'duration':
            '00:59:55',
        'analysis_complete':
            False,
        'build_level_number':
            2,
        'revision_level_number':
            0,
        'error':
            None,
        'pending_time':
            '00:00:05',
        'suspected_flake': {
            'build_number': 100,
            'commit_position': 12345,
            'git_hash': 'a_git_hash',
            'triage_result': 0
        },
        'suspected_culprits': [],
        'version_number':
            1,
        'show_admin_options':
            False,
        'culprit': {},
        'last_attempted_swarming_task': {
            'task_id': None,
            'build_number': None
        },
        'last_attempted_try_job': {},
        'pipeline_status_path':
            'pipelinestatus',
        'show_debug_options':
            False,
        'bug_id':
            '',
        'culprit_confidence':
            '',
        'culprit_revision':
            '',
        'culprit_url':
            '',
        'regression_range_lower':
            12340,
        'regression_range_upper':
            12345,
        'most_recent_flakiness': {
            'blame_list': [],
            'error': None,
            'commit_position': 12345,
            'previous_build_git_hash': None,
            'pass_rate': 0.9,
            'build_url': None,
            'previous_build_commit_position': None,
            'try_job_url': None,
            'elapsed_seconds': 0,
            'has_valid_artifact': True,
            'iterations': None,
            'commit_position_landed_time': '2016-12-31 00:00:00',
            'task_ids': ['task_id1'],
            'swarm_task': 'task_id1',
            'build_number': 101,
            'git_hash': 'hash1',
            'failed_swarming_task_attempts': 0,
            'committed_days_ago': '1 day, 0:00:00'
        },
    }

    self.assertEqual(200, response.status_int)
    self.assertDictContainsSubset(expected_check_flake_result,
                                  response.json_body)

  @mock.patch.object(
      check_flake.auth_util, 'GetUserEmail', return_value='test@google.com')
  @mock.patch.object(
      flake_analysis_service, 'ScheduleAnalysisForFlake', return_value=False)
  @mock.patch.object(
      check_flake.token, 'ValidateAuthToken', return_value=(True, False))
  def testRequestUnsupportedAnalysis(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'

    previous_request = FlakeAnalysisRequest.Create(test_name, False, None)
    previous_request.AddBuildStep(master_name, builder_name, build_number,
                                  step_name, None)
    previous_request.swarmed = False
    previous_request.supported = False

    response = self.test_app.post(
        '/waterfall/flake',
        params={
            'url':
                buildbot.CreateBuildUrl(master_name, builder_name,
                                        build_number),
            'step_name':
                step_name,
            'test_name':
                test_name,
            'format':
                'json',
            'xsrf_token':
                'abc',
        },
        status=400,
    )
    self.assertEqual(
        ('Flake analysis is not supported for "s/t". Either '
         'the test type is not supported or the test is not swarmed yet.'),
        response.json_body.get('error_message'))

  @mock.patch.object(
      check_flake,
      '_GetSuspectedFlakeInfo',
      return_value={
          'build_number': 100,
          'commit_position': 12345,
          'git_hash': 'a_git_hash',
          'triage_result': 0
      })
  @mock.patch.object(
      check_flake,
      '_GetCoordinatesData',
      return_value=[[12345, 0.9, '1', 100, 'git_hash_2', 12344, 'git_hash_1']])
  @mock.patch.object(users, 'is_current_user_admin', return_value=True)
  @mock.patch.object(
      flake_analysis_service, 'ScheduleAnalysisForFlake', return_value=True)
  def testGetTriageHistory(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = '123'
    step_name = 's'
    test_name = 't'
    suspected_flake_build_number = 123
    triage_result = 2
    user_name = 'test'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.COMPLETED
    analysis.suspected_flake_build_number = 100
    analysis.Save()
    analysis.UpdateTriageResult(
        triage_result, {'build_number': suspected_flake_build_number}, 'test')

    response = self.test_app.get(
        '/waterfall/flake',
        params={
            'key': analysis.key.urlsafe(),
            'format': 'json'
        })

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
        CheckFlake()._ValidateInput(None, 't', '').get(
            'data', {}).get('error_message'), 'Step name must be specified')
    self.assertEqual(
        CheckFlake()._ValidateInput('s', None, '').get(
            'data', {}).get('error_message'), 'Test name must be specified')
    self.assertEqual(
        CheckFlake()._ValidateInput('s', 't', 'a').get(
            'data', {}).get('error_message'), 'Bug id must be an int')

  def testGetSuspectedFlakeInfoWhenNoSuspectedBuildNumber(self):
    self.assertEqual({}, check_flake._GetSuspectedFlakeInfo(None))
    analysis = MasterFlakeAnalysis()
    analysis.suspected_flake_build_number = None
    self.assertEqual({}, check_flake._GetSuspectedFlakeInfo(analysis))

  def testGetSuspectedFlakeInfo(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.suspected_flake_build_number = 123
    data_point = DataPoint()
    data_point.build_number = 123
    data_point.pass_rate = 0.9
    data_point.commit_position = 2
    data_point.git_hash = 'git_hash_2'
    analysis.data_points.append(data_point)
    analysis.Save()

    expected_result = {
        'build_number': analysis.suspected_flake_build_number,
        'commit_position': 2,
        'git_hash': 'git_hash_2',
        'triage_result': 0
    }

    self.assertEqual(expected_result,
                     check_flake._GetSuspectedFlakeInfo(analysis))

  def testGetSuspectInfo(self):
    suspect = FlakeCulprit.Create('repo', 'r1', 12345, 'url')
    suspect.put()

    expected_suspect_info = {
        'commit_position': 12345,
        'git_hash': 'r1',
        'url': 'url'
    }

    self.assertEqual(expected_suspect_info,
                     check_flake._GetSuspectInfo(suspect.key.urlsafe()))

  def testGetSuspectsForAnalysisInfo(self):
    suspect = FlakeCulprit.Create('repo', 'r1', 12345, 'url')
    suspect.put()
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.suspect_urlsafe_keys.append(suspect.key.urlsafe())
    analysis.put()

    expected_suspects_info = [{
        'commit_position': 12345,
        'git_hash': 'r1',
        'url': 'url'
    }]

    self.assertEqual(expected_suspects_info,
                     check_flake._GetSuspectsInfoForAnalysis(analysis))

  def testGetCulpritInfo(self):
    commit_position = 2
    git_hash = 'git_hash_2'
    url = 'url'
    culprit = FlakeCulprit.Create('chromium', git_hash, commit_position, url)

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.put()

    culprit.flake_analysis_urlsafe_keys.append(analysis.key.urlsafe())
    culprit.put()

    expected_result = {
        'commit_position': commit_position,
        'git_hash': git_hash,
        'url': url,
        'confidence': None,
    }
    self.assertEqual(expected_result, check_flake._GetCulpritInfo(analysis))

  def testGetCoordinatesDataNoDataPoints(self):
    self.assertEqual([], check_flake._GetCoordinatesData(None))
    analysis = MasterFlakeAnalysis()
    analysis.data_points = []
    self.assertEqual([], check_flake._GetCoordinatesData(analysis))

  def testGetCoordinatesData(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    success_rate = .9
    try_job_url = 'try_job_url'
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    data_point_1 = DataPoint()
    data_point_1.build_number = build_number
    data_point_1.pass_rate = success_rate
    data_point_1.commit_position = 5
    data_point_1.git_hash = 'git_hash_5'
    data_point_1.try_job_url = try_job_url
    analysis.data_points.append(data_point_1)

    data_point_2 = DataPoint()
    data_point_2.build_number = build_number - 3
    data_point_2.pass_rate = success_rate
    data_point_2.commit_position = 2
    data_point_2.git_hash = 'git_hash_2'
    data_point_2.try_job_url = try_job_url
    analysis.data_points.append(data_point_2)
    analysis.Save()

    expected_result = [{
        'commit_position': 2,
        'pass_rate': success_rate,
        'task_ids': [],
        'build_number': build_number - 3,
        'git_hash': 'git_hash_2',
        'try_job_url': try_job_url
    }, {
        'commit_position': 5,
        'pass_rate': success_rate,
        'task_ids': [],
        'build_number': build_number,
        'git_hash': 'git_hash_5',
        'try_job_url': try_job_url
    }]
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
    expected_result = {'task_id': 'a1b2c3d4', 'build_number': 122}
    self.assertEqual(expected_result,
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

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.last_attempted_revision = revision
    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
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

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.last_attempted_revision = revision
    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
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

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.last_attempted_revision = revision
    analysis.put()
    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
    try_job.try_job_ids = [try_job_id]
    try_job.status = status
    try_job.put()

    try_job_data = FlakeTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.try_job_url = try_job_url
    try_job_data.put()
    self.assertEqual({
        'url': try_job_url,
        'status': analysis_status.STATUS_TO_DESCRIPTION.get(status)
    }, check_flake._GetLastAttemptedTryJobDetails(analysis))

  def testGetDurationForAnalysisWhenPending(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.status = analysis_status.PENDING
    self.assertIsNone(check_flake._GetDurationForAnalysis(analysis))

  def testGetDurationForAnalysisWhenStillRunning(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.start_time = datetime.datetime(2017, 06, 06, 00, 00, 00)
    self.MockUTCNow(datetime.datetime(2017, 06, 06, 00, 43, 00))
    self.assertEqual('00:43:00', check_flake._GetDurationForAnalysis(analysis))

  def testGetDurationForAnalysisWhenCompleted(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.start_time = datetime.datetime(2017, 06, 06, 00, 00, 00)
    analysis.end_time = datetime.datetime(2017, 06, 06, 00, 43, 00)
    self.assertEqual('00:43:00', check_flake._GetDurationForAnalysis(analysis))

  @mock.patch.object(
      check_flake.auth_util, 'GetUserEmail', return_value='test@google.com')
  @mock.patch.object(
      check_flake.token, 'ValidateAuthToken', return_value=(True, False))
  def testRerunFailsWhenUnauthorized(self, *_):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.Save()

    self.mock_current_user(user_email='test@google.com', is_admin=False)

    response = self.test_app.post(
        '/waterfall/flake',
        params={
            'format': 'json',
            'rerun': '1',
            'key': analysis.key.urlsafe()
        },
        status=403)
    self.assertEqual('Only admin is allowed to rerun.',
                     response.json_body.get('error_message'))

  @mock.patch.object(
      check_flake.auth_util, 'GetUserEmail', return_value='test@google.com')
  @mock.patch.object(
      check_flake.auth_util, 'IsCurrentUserAdmin', return_value=True)
  @mock.patch.object(
      check_flake.token, 'ValidateAuthToken', return_value=(True, False))
  def testRerunFailsWhenAlreadyRunning(self, *_):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.status = analysis_status.RUNNING
    analysis.Save()

    response = self.test_app.post(
        '/waterfall/flake',
        params={
            'format': 'json',
            'rerun': '1',
            'key': analysis.key.urlsafe()
        },
        status=400)
    self.assertEqual(
        'Cannot rerun analysis if one is currently running or pending.',
        response.json_body.get('error_message'))

  @mock.patch.object(
      check_flake.auth_util, 'GetUserEmail', return_value='test@google.com')
  @mock.patch.object(
      check_flake.auth_util, 'IsCurrentUserAdmin', return_value=True)
  @mock.patch.object(
      check_flake.token, 'ValidateAuthToken', return_value=(True, False))
  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2018, 6, 12, 0))
  def testRequestRerunWhenAuthorized(self, *_):
    original_master_name = 'tryserver.m'
    original_builder_name = 'tryserver.b'
    original_build_number = 100
    original_step_name = 's (with patch)'
    original_test_name = 't'

    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.original_master_name = original_master_name
    analysis.original_builder_name = original_builder_name
    analysis.original_build_number = original_build_number
    analysis.original_step_name = original_step_name
    analysis.original_test_name = original_test_name
    analysis.bug_id = 1
    analysis.status = analysis_status.COMPLETED
    analysis.Save()

    original_key = analysis.key

    request = FlakeAnalysisRequest.Create(analysis.original_test_name, False,
                                          analysis.bug_id)
    request.build_steps = [
        BuildStep(
            build_number=original_build_number,
            builder_name=original_builder_name,
            master_name=original_master_name,
            reported_time=datetime.datetime(2018, 6, 12, 0),
            step_name=original_step_name)
    ]

    with mock.patch.object(
        CheckFlake,
        '_CreateAndScheduleFlakeAnalysis',
        return_value=(analysis, True)) as scheduler:
      self.test_app.post(
          '/waterfall/flake',
          params={
              'key': analysis.key.urlsafe(),
              'rerun': '1',
              'format': 'json'
          })
      scheduler.assert_called_with(request, master_name, builder_name,
                                   build_number, step_name, test_name, 1, True)
      self.assertEqual(original_key, analysis.key)

  @mock.patch.object(
      check_flake.token, 'ValidateAuthToken', return_value=(True, False))
  @mock.patch.object(AnalyzeFlakePipeline, 'from_id', mock.MagicMock())
  def testRequestCancelWhenAuthorized(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    root_pipeline_id = '1fdsalkj9o93290'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.bug_id = 1
    analysis.root_pipeline_id = root_pipeline_id
    analysis.status = analysis_status.RUNNING
    analysis.Save()

    original_key = analysis.key

    self.mock_current_user(user_email='test@google.com', is_admin=True)

    self.test_app.post(
        '/waterfall/flake',
        params={
            'key': analysis.key.urlsafe(),
            'cancel': '1',
            'format': 'json'
        })
    self.assertEqual(original_key, analysis.key)
    self.assertEqual(analysis_status.ERROR, analysis.status)

  @mock.patch.object(
      check_flake.token, 'ValidateAuthToken', return_value=(True, False))
  def testRequestCancelWhenUnauthorized(self, *_):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.Save()

    self.mock_current_user(user_email='test@google.com', is_admin=False)

    response = self.test_app.post(
        '/waterfall/flake',
        params={
            'format': 'json',
            'cancel': '1',
            'key': analysis.key.urlsafe()
        },
        status=403)
    self.assertEqual('Only admin is allowed to cancel.',
                     response.json_body.get('error_message'))

  @mock.patch.object(
      check_flake.token, 'ValidateAuthToken', return_value=(True, False))
  def testRequestCancelWhenNoKeyWasProvided(self, *_):
    self.mock_current_user(user_email='test@google.com', is_admin=True)

    response = self.test_app.post(
        '/waterfall/flake',
        params={
            'format': 'json',
            'cancel': '1'
        },
        status=404)
    self.assertEqual('No key was provided.',
                     response.json_body.get('error_message'))

  @mock.patch.object(
      check_flake.token, 'ValidateAuthToken', return_value=(True, False))
  def testRequestCancelWhenNoAnalysisIsFound(self, *_):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.Save()

    # Simulate a deletion.
    analysis.key.delete()

    self.mock_current_user(user_email='test@google.com', is_admin=True)

    response = self.test_app.post(
        '/waterfall/flake',
        params={
            'format': 'json',
            'cancel': '1',
            'key': analysis.key.urlsafe()
        },
        status=404)
    self.assertEqual('Analysis of flake is not found.',
                     response.json_body.get('error_message'))

  @mock.patch.object(
      check_flake.token, 'ValidateAuthToken', return_value=(True, False))
  @mock.patch.object(AnalyzeFlakePipeline, 'from_id', mock.MagicMock())
  def testRequestCancelWhenAnalysisCompleted(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    root_pipeline_id = '1fdsalkj9o93290'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.bug_id = 1
    analysis.root_pipeline_id = root_pipeline_id
    analysis.status = analysis_status.COMPLETED
    analysis.Save()

    self.mock_current_user(user_email='test@google.com', is_admin=True)

    response = self.test_app.post(
        '/waterfall/flake',
        params={
            'key': analysis.key.urlsafe(),
            'cancel': '1',
            'format': 'json'
        },
        status=400)
    self.assertEqual('Can\'t cancel an analysis that\'s complete',
                     response.json_body.get('error_message'))

  @mock.patch.object(
      check_flake.token, 'ValidateAuthToken', return_value=(True, False))
  @mock.patch.object(AnalyzeFlakePipeline, 'from_id', mock.MagicMock())
  def testRequestCancelWhenNoRootId(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    root_pipeline_id = None

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.bug_id = 1
    analysis.root_pipeline_id = root_pipeline_id
    analysis.status = analysis_status.RUNNING
    analysis.Save()

    self.mock_current_user(user_email='test@google.com', is_admin=True)

    response = self.test_app.post(
        '/waterfall/flake',
        params={
            'key': analysis.key.urlsafe(),
            'cancel': '1',
            'format': 'json'
        },
        status=404)

    self.assertEqual('No root pipeline found for analysis.',
                     response.json_body.get('error_message'))

  @mock.patch.object(
      check_flake.token, 'ValidateAuthToken', return_value=(True, False))
  @mock.patch.object(AnalyzeFlakePipeline, 'from_id', return_value=None)
  def testRequestCancelWhenRootPipelineCannotBeFound(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    root_pipeline_id = '1fdsalkj9o93290'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.bug_id = 1
    analysis.root_pipeline_id = root_pipeline_id
    analysis.status = analysis_status.RUNNING
    analysis.Save()

    self.mock_current_user(user_email='test@google.com', is_admin=True)

    response = self.test_app.post(
        '/waterfall/flake',
        params={
            'key': analysis.key.urlsafe(),
            'cancel': '1',
            'format': 'json'
        },
        status=404)
    self.assertEqual('Root pipeline couldn\'t be found.',
                     response.json_body.get('error_message'))
