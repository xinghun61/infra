# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import copy
import datetime
import mock

from libs import analysis_status
from libs import time_util
from model.flake.flake_culprit import FlakeCulprit
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from services import issue_tracking_service
from services.flake_failure import flake_report_util
from waterfall.test.wf_testcase import WaterfallTestCase
from waterfall.test.wf_testcase import DEFAULT_CONFIG_DATA


class FlakeReportUtilTest(WaterfallTestCase):

  def testGenerateAnalysisLink(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    self.assertIn(analysis.key.urlsafe(),
                  flake_report_util.GenerateAnalysisLink(analysis))

  def testGenerateCommentWithCulprit(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.status = analysis_status.COMPLETED
    culprit = FlakeCulprit.Create('c', 'r', 123, 'http://')
    culprit.flake_analysis_urlsafe_keys.append(analysis.key.urlsafe())
    culprit.put()
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.confidence_in_culprit = 0.6713
    comment = flake_report_util.GenerateBugComment(analysis)
    self.assertTrue('culprit r123 with confidence 67.1%' in comment, comment)

  def testGenerateCommentForLongstandingFlake(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.status = analysis_status.COMPLETED
    comment = flake_report_util.GenerateBugComment(analysis)
    self.assertTrue('longstanding' in comment, comment)

  def testGenerateWrongResultLink(self):
    test_name = 'test_name'
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', test_name)
    self.assertIn(test_name,
                  flake_report_util.GenerateWrongResultLink(analysis))

  def testGetMinimumConfidenceToFileBugs(self):
    self.UpdateUnitTestConfigSettings(
        'check_flake_settings', {'minimum_confidence_to_create_bugs': 0.9})
    self.assertEqual(0.9, flake_report_util.GetMinimumConfidenceToFileBugs())

  def testGetMinimumConfidenceToUpdateBugs(self):
    self.UpdateUnitTestConfigSettings('check_flake_settings',
                                      {'minimum_confidence_to_update_cr': 0.8})
    self.assertEqual(0.8, flake_report_util.GetMinimumConfidenceToUpdateBugs())

  def testIsBugFilingEnabled(self):
    self.UpdateUnitTestConfigSettings('check_flake_settings',
                                      {'create_monorail_bug': False})
    self.assertFalse(flake_report_util.IsBugFilingEnabled())

    self.UpdateUnitTestConfigSettings('check_flake_settings',
                                      {'create_monorail_bug': True})
    self.assertTrue(flake_report_util.IsBugFilingEnabled())

  def testIsBugUpdatingEnabled(self):
    self.UpdateUnitTestConfigSettings('check_flake_settings',
                                      {'update_monorail_bug': False})
    self.assertFalse(flake_report_util.IsBugUpdatingEnabled())

    self.UpdateUnitTestConfigSettings('check_flake_settings',
                                      {'update_monorail_bug': True})
    self.assertTrue(flake_report_util.IsBugUpdatingEnabled())

  @mock.patch.object(flake_report_util, 'UnderDailyLimit', return_value=True)
  @mock.patch.object(flake_report_util, 'IsBugFilingEnabled', return_value=True)
  @mock.patch.object(
      flake_report_util, 'HasPreviousAttempt', return_value=False)
  @mock.patch.object(
      flake_report_util, 'HasSufficientConfidenceInCulprit', return_value=True)
  @mock.patch.object(
      issue_tracking_service, 'OpenBugAlreadyExistsForId', return_value=False)
  @mock.patch.object(
      issue_tracking_service,
      'OpenIssueAlreadyExistsForFlakyTest',
      return_value=False)
  def testShouldFileBugForAnalysis(
      self, test_exists_fn, id_exists_fn, sufficient_confidence_fn,
      previous_attempt_fn, feature_enabled_fn, under_limit_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    self.assertTrue(flake_report_util.ShouldFileBugForAnalysis(analysis))
    id_exists_fn.assert_not_called()
    sufficient_confidence_fn.assert_called()
    previous_attempt_fn.assert_called()
    feature_enabled_fn.assert_called()
    under_limit_fn.assert_called()
    test_exists_fn.assert_called()

  @mock.patch.object(flake_report_util, 'UnderDailyLimit', return_value=True)
  @mock.patch.object(
      flake_report_util, 'HasPreviousAttempt', return_value=False)
  @mock.patch.object(
      flake_report_util, 'HasSufficientConfidenceInCulprit', return_value=True)
  @mock.patch.object(
      issue_tracking_service, 'OpenBugAlreadyExistsForId', return_value=False)
  @mock.patch.object(
      flake_report_util, 'IsBugFilingEnabled', return_value=False)
  def testShouldFileBugForAnalysisWhenFeatureDisabled(self, feature_enabled_fn,
                                                      *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.bug_id = 1
    analysis.Save()

    self.assertFalse(flake_report_util.ShouldFileBugForAnalysis(analysis))
    self.assertTrue(feature_enabled_fn.called)

  @mock.patch.object(flake_report_util, 'UnderDailyLimit', return_value=True)
  @mock.patch.object(flake_report_util, 'IsBugFilingEnabled', return_value=True)
  @mock.patch.object(
      flake_report_util, 'HasPreviousAttempt', return_value=False)
  @mock.patch.object(
      flake_report_util, 'HasSufficientConfidenceInCulprit', return_value=True)
  @mock.patch.object(
      issue_tracking_service, 'OpenBugAlreadyExistsForId', return_value=True)
  def testShouldFileBugForAnalysisWhenBugIdExists(self, id_exists_fn, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.bug_id = 1
    analysis.Save()

    self.assertFalse(flake_report_util.ShouldFileBugForAnalysis(analysis))
    self.assertTrue(id_exists_fn.called)

  @mock.patch.object(flake_report_util, 'UnderDailyLimit', return_value=True)
  @mock.patch.object(flake_report_util, 'IsBugFilingEnabled', return_value=True)
  @mock.patch.object(
      flake_report_util, 'HasPreviousAttempt', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'OpenBugAlreadyExistsForId', return_value=False)
  @mock.patch.object(
      flake_report_util, 'HasSufficientConfidenceInCulprit', return_value=False)
  def testShouldFileBugForAnalysisWithoutSufficientConfidence(
      self, confidence_fn, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.confidence_in_culprit = 0.5
    analysis.Save()

    self.assertFalse(flake_report_util.ShouldFileBugForAnalysis(analysis))
    self.assertTrue(confidence_fn.called)

  @mock.patch.object(flake_report_util, 'UnderDailyLimit', return_value=True)
  @mock.patch.object(flake_report_util, 'IsBugFilingEnabled', return_value=True)
  @mock.patch.object(
      issue_tracking_service, 'OpenBugAlreadyExistsForId', return_value=False)
  @mock.patch.object(
      flake_report_util, 'HasSufficientConfidenceInCulprit', return_value=True)
  @mock.patch.object(flake_report_util, 'HasPreviousAttempt', return_value=True)
  def testShouldFileBugForAnalysisWithPreviousAttempt(self, attempt_fn, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.confidence_in_culprit = 0.5
    analysis.Save()

    self.assertFalse(flake_report_util.ShouldFileBugForAnalysis(analysis))
    self.assertTrue(attempt_fn.called)

  @mock.patch.object(flake_report_util, 'IsBugFilingEnabled', return_value=True)
  @mock.patch.object(
      issue_tracking_service, 'OpenBugAlreadyExistsForId', return_value=False)
  @mock.patch.object(
      flake_report_util, 'HasSufficientConfidenceInCulprit', return_value=True)
  @mock.patch.object(
      flake_report_util, 'HasPreviousAttempt', return_value=False)
  @mock.patch.object(flake_report_util, 'UnderDailyLimit', return_value=False)
  def testShouldFileBugForAnalysisWhenOverLimit(self, daily_limit_fn, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.confidence_in_culprit = 0.5
    analysis.Save()

    self.assertFalse(flake_report_util.ShouldFileBugForAnalysis(analysis))
    self.assertTrue(daily_limit_fn.called)

  @mock.patch.object(flake_report_util, 'IsBugFilingEnabled', return_value=True)
  @mock.patch.object(
      issue_tracking_service, 'OpenBugAlreadyExistsForId', return_value=False)
  @mock.patch.object(
      flake_report_util, 'HasSufficientConfidenceInCulprit', return_value=True)
  @mock.patch.object(
      flake_report_util, 'HasPreviousAttempt', return_value=False)
  @mock.patch.object(flake_report_util, 'UnderDailyLimit', return_value=True)
  @mock.patch.object(
      issue_tracking_service,
      'OpenIssueAlreadyExistsForFlakyTest',
      return_value=True)
  def testShouldFileBugForAnalysisWhenBugExistsForTest(self, test_exists_Fn,
                                                       *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.confidence_in_culprit = 0.5
    analysis.Save()

    self.assertFalse(flake_report_util.ShouldFileBugForAnalysis(analysis))
    self.assertTrue(test_exists_Fn.called)

  def testShouldUpdateBugForAnalysisConfiguredFalse(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.bug_id = 123
    analysis.data_points = [DataPoint(), DataPoint(), DataPoint()]
    analysis.suspected_flake_build_number = 1
    analysis.algorithm_parameters = {'update_monorail_bug': False}
    self.assertFalse(flake_report_util.ShouldUpdateBugForAnalysis(analysis))

  def testShouldUpdateBugForAnalysisNoBugId(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.data_points = [DataPoint(), DataPoint(), DataPoint()]
    analysis.confidence_in_culprit = 0.9
    self.UpdateUnitTestConfigSettings('check_flake_settings', {
        'update_monorail_bug': True,
        'minimum_confidence_score_to_update_cr': 0.6
    })

    self.assertFalse(flake_report_util.ShouldUpdateBugForAnalysis(analysis))

  def testShouldUpdateBugForAnalysisNoBugIdWithCulprit(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.culprit_urlsafe_key = 'c'
    analysis.data_points = [DataPoint(), DataPoint(), DataPoint()]
    analysis.confidence_in_culprit = 0.9
    self.UpdateUnitTestConfigSettings('check_flake_settings', {
        'update_monorail_bug': True,
        'minimum_confidence_score_to_update_cr': 0.6
    })

    self.assertFalse(flake_report_util.ShouldUpdateBugForAnalysis(analysis))

  def testShouldUpdateBugForAnalysisInsufficientDataPoints(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.data_points = [DataPoint()]
    analysis.bug_id = 123
    analysis.confidence_in_culprit = 0.9
    self.UpdateUnitTestConfigSettings('check_flake_settings', {
        'update_monorail_bug': True,
        'minimum_confidence_score_to_update_cr': 0.6
    })

    self.assertFalse(flake_report_util.ShouldUpdateBugForAnalysis(analysis))

  @mock.patch.object(
      flake_report_util, 'HasSufficientConfidenceInCulprit', return_value=False)
  def testShouldUpdateBugForAnalysisInsufficientConfidence(self, _):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.bug_id = 123
    analysis.data_points = [DataPoint(), DataPoint(), DataPoint()]
    analysis.confidence_in_culprit = 0.4
    analysis.culprit_urlsafe_key = 'c'

    self.UpdateUnitTestConfigSettings('check_flake_settings', {
        'update_monorail_bug': True,
        'minimum_confidence_score_to_update_cr': 0.6
    })

    self.assertFalse(flake_report_util.ShouldUpdateBugForAnalysis(analysis))

  def testShouldUpdateBugForAnalysisConfiguredFalseWithCulprit(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.bug_id = 123
    analysis.culprit_urlsafe_key = 'c'
    analysis.data_points = [DataPoint(), DataPoint(), DataPoint()]
    analysis.confidence_in_culprit = 0.9
    self.UpdateUnitTestConfigSettings('check_flake_settings', {
        'update_monorail_bug': False,
        'minimum_confidence_score_to_update_cr': 0.6
    })

    self.assertFalse(flake_report_util.ShouldUpdateBugForAnalysis(analysis))

  def testShouldUpdateBugForAnalysis(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.bug_id = 123
    analysis.data_points = [DataPoint(), DataPoint(), DataPoint()]
    analysis.confidence_in_culprit = 0.9
    self.UpdateUnitTestConfigSettings('check_flake_settings', {
        'update_monorail_bug': True,
        'minimum_confidence_score_to_update_cr': 0.6
    })

    self.assertTrue(flake_report_util.ShouldUpdateBugForAnalysis(analysis))

  def testHasPreviousAttempt(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.has_attempted_filing = True
    analysis.Save()
    self.assertTrue(flake_report_util.HasPreviousAttempt(analysis))

    analysis.has_attempted_filing = False
    analysis.put()
    self.assertFalse(flake_report_util.HasPreviousAttempt(analysis))

  def testHasSufficientConfidenceInCulprit(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)

    analysis.confidence_in_culprit = None
    analysis.Save()
    self.assertFalse(
        flake_report_util.HasSufficientConfidenceInCulprit(analysis, 0.5))

    analysis.confidence_in_culprit = 1.0
    analysis.Save()
    self.assertTrue(
        flake_report_util.HasSufficientConfidenceInCulprit(analysis, 1.0))

    analysis.confidence_in_culprit = .9
    analysis.put()
    self.assertTrue(
        flake_report_util.HasSufficientConfidenceInCulprit(analysis, 0.9))

    analysis.confidence_in_culprit = .8
    analysis.put()
    self.assertFalse(
        flake_report_util.HasSufficientConfidenceInCulprit(analysis, 0.9))

  @mock.patch.object(
      time_util,
      'GetMostRecentUTCMidnight',
      return_value=datetime.datetime(2017, 1, 2))
  def testUnderDailyLimit(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.bug_id = 1234
    analysis.has_attempted_filing = True
    analysis.request_time = datetime.datetime(2017, 1, 1, 1)
    analysis.Save()

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number + 1, step_name, test_name)
    analysis.bug_id = 12345
    analysis.has_attempted_filing = True
    analysis.request_time = datetime.datetime(2017, 1, 1, 1)
    analysis.Save()

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number + 2, step_name, test_name)
    analysis.bug_id = 1234
    analysis.has_attempted_filing = True
    analysis.request_time = datetime.datetime(2017, 1, 1, 1)
    analysis.Save()

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number + 3, step_name, test_name)
    analysis.bug_id = 1234
    analysis.has_attempted_filing = True
    analysis.request_time = datetime.datetime(2017, 1, 2, 1)
    analysis.Save()

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number + 4, step_name, test_name)
    analysis.bug_id = 12345
    analysis.has_attempted_filing = False
    analysis.request_time = datetime.datetime(2017, 1, 2, 1)
    analysis.Save()

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number + 5, step_name, test_name)
    analysis.bug_id = None
    analysis.has_attempted_filing = True
    analysis.request_time = datetime.datetime(2017, 1, 2, 1)
    analysis.Save()

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number + 6, step_name, test_name)
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.Save()

    self.assertTrue(flake_report_util.UnderDailyLimit(analysis))

  @mock.patch.object(
      time_util,
      'GetMostRecentUTCMidnight',
      return_value=datetime.datetime(2017, 1, 1))
  def testUnderDailyLimitIfOver(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.bug_id = 1234
    analysis.has_attempted_filing = True
    analysis.request_time = datetime.datetime(2017, 1, 1, 1)
    analysis.put()

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.bug_id = 12345
    analysis.has_attempted_filing = True
    analysis.request_time = datetime.datetime(2017, 1, 1, 1)
    analysis.put()

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.bug_id = 1234
    analysis.has_attempted_filing = True
    analysis.request_time = datetime.datetime(2017, 1, 1, 1)
    analysis.put()

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.put()

    self.assertFalse(flake_report_util.UnderDailyLimit(analysis))

  def testGetPriorityLabelForConfidence(self):
    self.assertEqual('Pri-1',
                     flake_report_util.GetPriorityLabelForConfidence(1.0))
    self.assertEqual('Pri-1',
                     flake_report_util.GetPriorityLabelForConfidence(.98))
    self.assertEqual('Pri-1',
                     flake_report_util.GetPriorityLabelForConfidence(.9))
    self.assertEqual('Pri-1',
                     flake_report_util.GetPriorityLabelForConfidence(.85))
