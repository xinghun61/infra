# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from common import constants
from model.flake.flake_analysis_request import BuildStep
from model.flake.flake_analysis_request import FlakeAnalysisRequest
from waterfall.flake import flake_analysis_service
from waterfall.flake import triggering_sources
from waterfall.test import wf_testcase
from waterfall.test_info import TestInfo


class FlakeAnalysisServiceTest(wf_testcase.WaterfallTestCase):

  def testCheckFlakeSwarmedAndSupportedWhenNotSupported(self):
    request = FlakeAnalysisRequest.Create('flake', False, 123)
    step1 = BuildStep.Create('m', 'b1', 10, 's', datetime(2016, 10, 01))
    step1.swarmed = False
    step1.supported = False
    step2 = BuildStep.Create('m', 'b2', 10, 's', datetime(2016, 10, 01))
    step2.swarmed = False
    step2.supported = False
    request.build_steps = [step1, step2]

    self.assertEqual(
        (False, False, None),
        flake_analysis_service._CheckFlakeSwarmedAndSupported(request))

  def testNeedNewAnalysisWhenNoPreviousOneAndNotStepLevelFlake(self):
    request = FlakeAnalysisRequest.Create('flake', False, 123)
    step1 = BuildStep.Create('m', 'b1', 10, 's', datetime(2016, 10, 01))
    step1.swarmed = False
    step1.supported = False
    step2 = BuildStep.Create('m', 'b2', 10, 's', datetime(2016, 10, 01))
    step2.swarmed = True
    step2.supported = True
    request.build_steps = [step1, step2]
    request.user_emails = ['test@google.com']

    mocked_now = datetime(2017, 05, 01, 10, 10, 10)
    self.MockUTCNow(mocked_now)

    version, step = flake_analysis_service._CheckForNewAnalysis(request)

    self.assertEqual(1, version)
    new_request = FlakeAnalysisRequest.GetVersion(key='flake', version=version)
    self.assertEqual(['test@google.com'], new_request.user_emails)
    self.assertFalse(new_request.user_emails_obscured)
    self.assertEqual(mocked_now, new_request.user_emails_last_edit)

    self.assertIsNotNone(step)
    self.assertTrue(step.scheduled)

  def testNeedNewAnalysisWhenPreviousOneWasForAnotherBug(self):
    existing_request = FlakeAnalysisRequest.Create('flake', False, 123)
    existing_request.user_emails = ['test1@google.com']
    existing_request.Save()

    request = FlakeAnalysisRequest.Create('flake', False, 456)
    step1 = BuildStep.Create('m', 'b1', 10, 's', datetime(2016, 10, 01))
    step1.swarmed = False
    step1.supported = False
    step2 = BuildStep.Create('m', 'b2', 10, 's', datetime(2016, 10, 01))
    step2.swarmed = True
    step2.supported = True
    request.build_steps = [step1, step2]
    request.user_emails = ['test2@google.com']

    mocked_now = datetime(2017, 05, 01, 10, 10, 10)
    self.MockUTCNow(mocked_now)

    version, step = flake_analysis_service._CheckForNewAnalysis(request)

    self.assertEqual(2, version)
    new_request = FlakeAnalysisRequest.GetVersion(key='flake', version=version)
    self.assertEqual(['xxxxx@google.com', 'test2@google.com'],
                     new_request.user_emails)
    self.assertFalse(new_request.user_emails_obscured)
    self.assertEqual(mocked_now, new_request.user_emails_last_edit)

    self.assertIsNotNone(step)
    self.assertTrue(step.scheduled)
    self.assertTrue(step.swarmed)
    self.assertTrue(step.supported)

  def testNotNeedNewAnalysisForStepLevelFlake(self):
    request = FlakeAnalysisRequest.Create('flake', True, 123)
    step1 = BuildStep.Create('m', 'b1', 10, 's', datetime(2016, 10, 01))
    step1.swarmed = True
    step1.supported = True
    request.build_steps = [step1]

    version, step = flake_analysis_service._CheckForNewAnalysis(request)

    self.assertEqual(0, version)
    self.assertIsNone(step)

  def testNeedNewAnalysisWithADifferentNewStep(self):
    existing_request = FlakeAnalysisRequest.Create('flake', False, 123)
    step1 = BuildStep.Create('m', 'b1', 11, 's', datetime(2016, 10, 01))
    step1.swarmed = True
    step1.supported = True
    step1.scheduled = True
    step2 = BuildStep.Create('m', 'b2', 12, 's', datetime(2016, 10, 01))
    step2.swarmed = True
    step2.supported = True
    step2.scheduled = False
    existing_request.supported = True
    existing_request.swarmed = True
    existing_request.build_steps = [step1, step2]
    existing_request.user_emails = ['test1@google.com']
    existing_request.Save()

    request = FlakeAnalysisRequest.Create('flake', False, 123)
    step3 = BuildStep.Create('m', 'b3', 13, 's', datetime(2016, 10, 01))
    step3.swarmed = True
    step3.supported = True
    request.build_steps = [step3]
    request.user_emails = ['test2@google.com']

    mocked_now = datetime(2017, 05, 01, 10, 10, 10)
    self.MockUTCNow(mocked_now)

    version, step = flake_analysis_service._CheckForNewAnalysis(request)

    self.assertEqual(1, version)
    new_request = FlakeAnalysisRequest.GetVersion(key='flake', version=version)
    self.assertEqual(['xxxxx@google.com', 'test2@google.com'],
                     new_request.user_emails)
    self.assertFalse(new_request.user_emails_obscured)
    self.assertEqual(mocked_now, new_request.user_emails_last_edit)

    self.assertIsNotNone(step)
    self.assertTrue(step.scheduled)
    self.assertEqual('b3', step.builder_name)

  def testNeedNewAnalysisWithADifferentFormerReportedStep(self):
    existing_request = FlakeAnalysisRequest.Create('flake', False, 123)
    step1 = BuildStep.Create('m', 'b1', 11, 's', datetime(2016, 10, 01))
    step1.swarmed = True
    step1.supported = True
    step1.scheduled = True
    step2 = BuildStep.Create('m', 'b2', 12, 's', datetime(2016, 10, 01))
    step2.swarmed = True
    step2.supported = True
    step2.scheduled = False
    existing_request.supported = True
    existing_request.swarmed = True
    existing_request.build_steps = [step1, step2]
    existing_request.Save()

    request = FlakeAnalysisRequest.Create('flake', False, 123)
    step3 = BuildStep.Create('m', 'b3', 13, 's', datetime(2016, 10, 01))
    step3.swarmed = False
    step3.supported = False
    request.build_steps = [step3]

    version, step = flake_analysis_service._CheckForNewAnalysis(request)

    self.assertEqual(1, version)
    self.assertIsNotNone(step)
    self.assertTrue(step.scheduled)
    self.assertEqual('b2', step.builder_name)

  def testNotNeedNewAnalysisWithFreshEnoughPreviousAnalysis(self):
    existing_request = FlakeAnalysisRequest.Create('flake', False, 123)
    step1 = BuildStep.Create('m', 'b1', 11, 's', datetime(2016, 10, 01))
    step1.swarmed = True
    step1.supported = True
    step1.scheduled = True
    step2 = BuildStep.Create('m', 'b2', 12, 's', datetime(2016, 10, 01))
    step2.swarmed = True
    step2.supported = True
    step2.scheduled = True
    existing_request.supported = True
    existing_request.swarmed = True
    existing_request.build_steps = [step1, step2]
    existing_request.Save()

    request = FlakeAnalysisRequest.Create('flake', False, 123)
    step3 = BuildStep.Create('m', 'b2', 20, 's', datetime(2016, 10, 03))
    step3.swarmed = True
    step3.supported = True
    request.build_steps = [step3]

    version, step = flake_analysis_service._CheckForNewAnalysis(request)

    self.assertEqual(0, version)
    self.assertIsNone(step)

  def testNeedNewAnalysisWithFreshEnoughPreviousAnalysisWithRerunFlag(self):
    existing_request = FlakeAnalysisRequest.Create('flake', False, 123)
    step1 = BuildStep.Create('m', 'b1', 11, 's', datetime(2016, 10, 01))
    step1.swarmed = True
    step1.supported = True
    step1.scheduled = True
    step2 = BuildStep.Create('m', 'b2', 12, 's', datetime(2016, 10, 01))
    step2.swarmed = True
    step2.supported = True
    step2.scheduled = True
    existing_request.supported = True
    existing_request.swarmed = True
    existing_request.build_steps = [step1, step2]
    existing_request.Save()

    request = FlakeAnalysisRequest.Create('flake', False, 123)
    step3 = BuildStep.Create('m', 'b2', 20, 's', datetime(2016, 10, 01))
    step3.swarmed = True
    step3.supported = True
    request.build_steps = [step3]
    request.user_emails = ['test@google.com']

    mocked_now = datetime(2016, 10, 01)
    self.MockUTCNow(mocked_now)

    version, step = flake_analysis_service._CheckForNewAnalysis(request, True)

    self.assertEqual(1, version)
    new_request = FlakeAnalysisRequest.GetVersion(key='flake', version=version)
    self.assertEqual(['test@google.com'], new_request.user_emails)
    self.assertFalse(new_request.user_emails_obscured)
    self.assertEqual(datetime(2016, 10, 01), new_request.user_emails_last_edit)

    self.assertIsNotNone(step)
    self.assertTrue(step.scheduled)

  def testNeedNewAnalysisWithTooOldPreviousAnalysis(self):
    existing_request = FlakeAnalysisRequest.Create('flake', False, None)
    step1 = BuildStep.Create('m', 'b1', 11, 's', datetime(2016, 10, 01))
    step1.swarmed = True
    step1.supported = True
    step1.scheduled = True
    step2 = BuildStep.Create('m', 'b2', 12, 's', datetime(2016, 10, 01))
    step2.swarmed = True
    step2.supported = True
    step2.scheduled = True
    existing_request.supported = True
    existing_request.swarmed = True
    existing_request.user_emails = ['test@google.com']
    existing_request.build_steps = [step1, step2]
    existing_request.Save()

    request = FlakeAnalysisRequest.Create('flake', False, 123)
    step3 = BuildStep.Create('m', 'b2', 80, 's', datetime(2016, 10, 20))
    step3.swarmed = True
    step3.supported = True
    request.build_steps = [step3]
    request.user_emails = ['test@google.com']

    version, step = flake_analysis_service._CheckForNewAnalysis(request)

    self.assertEqual(1, version)
    self.assertIsNotNone(step)
    self.assertEqual(80, step.build_number)

    request = FlakeAnalysisRequest.GetVersion(key='flake')
    self.assertEqual(['xxxx@google.com', 'test@google.com'],
                     request.user_emails)

  def testUnauthorizedAccess(self):
    request = FlakeAnalysisRequest.Create('flake', False, 123)
    step = BuildStep.Create('m', 'b2', 80, 's', datetime(2016, 10, 20))
    request.build_steps = [step]

    self.assertIsNone(flake_analysis_service.ScheduleAnalysisForFlake(
        request, 'test@chromium.org', False, triggering_sources.FINDIT_UI))

  @mock.patch.object(
      flake_analysis_service, '_CheckForNewAnalysis', return_value=(0, None))
  @mock.patch.object(
      flake_analysis_service.step_mapper, 'FindMatchingWaterfallStep')
  def testAuthorizedAccessButNoNewAnalysisNeeded(self, _mock1, _mock2):
    request = FlakeAnalysisRequest.Create('flake', False, 123)
    step = BuildStep.Create('m', 'b2', 80, 's', datetime(2016, 10, 20))
    request.build_steps = [step]

    self.assertFalse(flake_analysis_service.ScheduleAnalysisForFlake(
        request, 'test@chromium.org', True, triggering_sources.FINDIT_UI))

  @mock.patch.object(
      flake_analysis_service.step_mapper, 'FindMatchingWaterfallStep')
  def testAuthorizedAccessAndNewAnalysisNeededAndTriggered(self, _mock):
    step = BuildStep.Create('m', 'b', 80, 's', datetime(2016, 10, 20))
    request = FlakeAnalysisRequest.Create('flake', False, 123)
    request.build_steps = [step]
    user_email = 'test@chromium.org'
    triggering_source = triggering_sources.FINDIT_UI

    def CheckForNewAnalysis(*_):
      step.wf_master_name = 'wf_m'
      step.wf_builder_name = 'wf_b'
      step.wf_build_number = 100
      step.wf_step_name = 'wf_s'
      return 1, step

    mocked_analysis = mock.Mock(key='key')
    mocked_request = mock.Mock()

    normalized_test = TestInfo('wf_m', 'wf_b', 100, 'wf_s', 'flake')
    original_test = TestInfo('m', 'b', 80, 's', 'flake')

    with mock.patch.object(
        flake_analysis_service, '_CheckForNewAnalysis',
        side_effect=CheckForNewAnalysis) as (
            mocked_CheckForNewAnalysis), mock.patch.object(
                flake_analysis_service.initialize_flake_pipeline,
                'ScheduleAnalysisIfNeeded', return_value=mocked_analysis) as (
                    mocked_ScheduleAnalysisIfNeeded), mock.patch.object(
                        flake_analysis_service.FlakeAnalysisRequest,
                        'GetVersion', return_value=mocked_request) as (
                            mocked_GetVersion):
      self.assertTrue(flake_analysis_service.ScheduleAnalysisForFlake(
          request, user_email, True, triggering_source))
      mocked_CheckForNewAnalysis.assert_called_once_with(request, False)
      mocked_ScheduleAnalysisIfNeeded.assert_called_once_with(
          normalized_test, original_test, bug_id=123,
          allow_new_analysis=True, manually_triggered=False,
          user_email=user_email, triggering_source=triggering_source,
          queue_name=constants.WATERFALL_ANALYSIS_QUEUE, force=False)
      mocked_GetVersion.assert_called_once_with(key='flake', version=1)
      mocked_request.assert_has_calls([
          mock.call.analyses.append('key'),
          mock.call.put(),
      ])

  @mock.patch.object(
      flake_analysis_service.step_mapper, 'FindMatchingWaterfallStep')
  def testAuthorizedAccessAndNewAnalysisNeededButNotTriggered(self, _mock):
    step = BuildStep.Create('m', 'b', 80, 's', datetime(2016, 10, 20))
    request = FlakeAnalysisRequest.Create('flake', False, 123)
    request.build_steps = [step]
    user_email = 'test@chromium.org'
    triggering_source = triggering_sources.FINDIT_UI

    def CheckForNewAnalysis(*_):
      step.wf_master_name = 'wf_m'
      step.wf_builder_name = 'wf_b'
      step.wf_build_number = 100
      step.wf_step_name = 'wf_s'
      return 1, step

    normalized_test = TestInfo('wf_m', 'wf_b', 100, 'wf_s', 'flake')
    original_test = TestInfo('m', 'b', 80, 's', 'flake')
    with mock.patch.object(
        flake_analysis_service, '_CheckForNewAnalysis',
        side_effect=CheckForNewAnalysis) as (
            mocked_CheckForNewAnalysis), mock.patch.object(
                flake_analysis_service.initialize_flake_pipeline,
                'ScheduleAnalysisIfNeeded', return_value=None) as (
                    mocked_ScheduleAnalysisIfNeeded), mock.patch.object(
                        flake_analysis_service.FlakeAnalysisRequest,
                        'GetVersion', return_value=None) as mocked_GetVersion:
      self.assertFalse(flake_analysis_service.ScheduleAnalysisForFlake(
          request, user_email, True, triggering_sources.FINDIT_UI))
      mocked_CheckForNewAnalysis.assert_called_once_with(request, False)
      mocked_ScheduleAnalysisIfNeeded.assert_called_once_with(
          normalized_test, original_test, bug_id=123,
          allow_new_analysis=True, manually_triggered=False,
          user_email=user_email, triggering_source=triggering_source,
          queue_name=constants.WATERFALL_ANALYSIS_QUEUE, force=False)
      mocked_GetVersion.assert_not_called()
