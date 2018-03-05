# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import copy
import mock
import datetime

from monorail_api import CustomizedField
from monorail_api import Issue
from waterfall.test import wf_testcase
from libs import analysis_status
from libs import time_util
from model.flake.detection.flake import Flake
from model.flake.detection.flake_issue import FlakeIssue
from model.flake.flake_culprit import FlakeCulprit
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis

from services import issue_tracking_service
from waterfall.flake import flake_constants
from waterfall.test.wf_testcase import DEFAULT_CONFIG_DATA


class IssueTrackingServiceTest(wf_testcase.WaterfallTestCase):

  def testAddFinditLabelToIssue(self):
    issue = mock.MagicMock()
    issue.labels = []
    issue_tracking_service.AddFinditLabelToIssue(issue)
    self.assertEqual(['Test-Findit-Analyzed'], issue.labels)
    issue_tracking_service.AddFinditLabelToIssue(issue)
    self.assertEqual(['Test-Findit-Analyzed'], issue.labels)

  def testGenerateCommentWithCulprit(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.status = analysis_status.COMPLETED
    culprit = FlakeCulprit.Create('c', 'r', 123, 'http://')
    culprit.flake_analysis_urlsafe_keys.append(analysis.key.urlsafe())
    culprit.put()
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.confidence_in_culprit = 0.6713
    comment = issue_tracking_service.GenerateBugComment(analysis)
    self.assertTrue('culprit r123 with confidence 67.1%' in comment, comment)

  def testGenerateCommentForLongstandingFlake(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.status = analysis_status.COMPLETED
    comment = issue_tracking_service.GenerateBugComment(analysis)
    self.assertTrue('longstanding' in comment, comment)

  def testGetMinimumConfidenceToFileBugs(self):
    self.UpdateUnitTestConfigSettings('check_flake_settings', {
        'minimum_confidence_to_create_bugs': 0.9
    })
    self.assertEqual(0.9,
                     issue_tracking_service.GetMinimumConfidenceToFileBugs())

  def testGetMinimumConfidenceToUpdateBugs(self):
    self.UpdateUnitTestConfigSettings('check_flake_settings', {
        'minimum_confidence_to_update_cr': 0.8
    })
    self.assertEqual(0.8,
                     issue_tracking_service.GetMinimumConfidenceToUpdateBugs())

  def testIsBugFilingEnabled(self):
    self.UpdateUnitTestConfigSettings('check_flake_settings', {
        'create_monorail_bug': False
    })
    self.assertFalse(issue_tracking_service.IsBugFilingEnabled())

    self.UpdateUnitTestConfigSettings('check_flake_settings', {
        'create_monorail_bug': True
    })
    self.assertTrue(issue_tracking_service.IsBugFilingEnabled())

  def testIsBugUpdatingEnabled(self):
    self.UpdateUnitTestConfigSettings('check_flake_settings', {
        'update_monorail_bug': False
    })
    self.assertFalse(issue_tracking_service.IsBugUpdatingEnabled())

    self.UpdateUnitTestConfigSettings('check_flake_settings', {
        'update_monorail_bug': True
    })
    self.assertTrue(issue_tracking_service.IsBugUpdatingEnabled())

  @mock.patch.object(
      issue_tracking_service, 'UnderDailyLimit', return_value=True)
  @mock.patch.object(
      issue_tracking_service, 'IsBugFilingEnabled', return_value=True)
  @mock.patch.object(
      issue_tracking_service, '_HasPreviousAttempt', return_value=False)
  @mock.patch.object(
      issue_tracking_service,
      'HasSufficientConfidenceInCulprit',
      return_value=True)
  @mock.patch.object(
      issue_tracking_service, 'OpenBugAlreadyExistsForId', return_value=False)
  @mock.patch.object(
      issue_tracking_service,
      'OpenBugAlreadyExistsForLabel',
      return_value=False)
  @mock.patch.object(
      issue_tracking_service,
      'BugAlreadyExistsForCustomField',
      return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'OpenBugAlreadyExistsForTest', return_value=False)
  def testShouldFileBugForAnalysis(
      self, test_exists_fn, field_exists_fn, label_exists_fn, id_exists_fn,
      sufficient_confidence_fn, previous_attempt_fn, feature_enabled_fn,
      under_limit_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    self.assertTrue(issue_tracking_service.ShouldFileBugForAnalysis(analysis))
    self.assertTrue(label_exists_fn.called)
    self.assertTrue(id_exists_fn.called)
    self.assertTrue(sufficient_confidence_fn.called)
    self.assertTrue(previous_attempt_fn.called)
    self.assertTrue(feature_enabled_fn.called)
    self.assertTrue(under_limit_fn.called)
    self.assertTrue(field_exists_fn.called)
    self.assertTrue(test_exists_fn.called)

  @mock.patch.object(
      issue_tracking_service, 'OpenBugAlreadyExistsForTest', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'UnderDailyLimit', return_value=True)
  @mock.patch.object(
      issue_tracking_service, '_HasPreviousAttempt', return_value=False)
  @mock.patch.object(
      issue_tracking_service,
      'HasSufficientConfidenceInCulprit',
      return_value=True)
  @mock.patch.object(
      issue_tracking_service,
      'OpenBugAlreadyExistsForLabel',
      return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'OpenBugAlreadyExistsForId', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'IsBugFilingEnabled', return_value=False)
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

    self.assertFalse(issue_tracking_service.ShouldFileBugForAnalysis(analysis))
    self.assertTrue(feature_enabled_fn.called)

  @mock.patch.object(
      issue_tracking_service, 'OpenBugAlreadyExistsForTest', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'UnderDailyLimit', return_value=True)
  @mock.patch.object(
      issue_tracking_service, 'IsBugFilingEnabled', return_value=True)
  @mock.patch.object(
      issue_tracking_service, '_HasPreviousAttempt', return_value=False)
  @mock.patch.object(
      issue_tracking_service,
      'HasSufficientConfidenceInCulprit',
      return_value=True)
  @mock.patch.object(
      issue_tracking_service,
      'OpenBugAlreadyExistsForLabel',
      return_value=False)
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

    self.assertFalse(issue_tracking_service.ShouldFileBugForAnalysis(analysis))
    self.assertTrue(id_exists_fn.called)

  @mock.patch.object(
      issue_tracking_service, 'OpenBugAlreadyExistsForTest', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'UnderDailyLimit', return_value=True)
  @mock.patch.object(
      issue_tracking_service, 'IsBugFilingEnabled', return_value=True)
  @mock.patch.object(
      issue_tracking_service, '_HasPreviousAttempt', return_value=False)
  @mock.patch.object(
      issue_tracking_service,
      'HasSufficientConfidenceInCulprit',
      return_value=True)
  @mock.patch.object(
      issue_tracking_service, 'OpenBugAlreadyExistsForId', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'OpenBugAlreadyExistsForLabel', return_value=True)
  def testShouldFileBugForAnalysisWhenLabelExists(self, label_exists_fn, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    self.assertFalse(issue_tracking_service.ShouldFileBugForAnalysis(analysis))
    self.assertTrue(label_exists_fn.called)

  @mock.patch.object(
      issue_tracking_service, 'OpenBugAlreadyExistsForTest', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'UnderDailyLimit', return_value=True)
  @mock.patch.object(
      issue_tracking_service, 'IsBugFilingEnabled', return_value=True)
  @mock.patch.object(
      issue_tracking_service, '_HasPreviousAttempt', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'OpenBugAlreadyExistsForId', return_value=False)
  @mock.patch.object(
      issue_tracking_service,
      'OpenBugAlreadyExistsForLabel',
      return_value=False)
  @mock.patch.object(
      issue_tracking_service,
      'HasSufficientConfidenceInCulprit',
      return_value=False)
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

    self.assertFalse(issue_tracking_service.ShouldFileBugForAnalysis(analysis))
    self.assertTrue(confidence_fn.called)

  @mock.patch.object(
      issue_tracking_service, 'OpenBugAlreadyExistsForTest', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'UnderDailyLimit', return_value=True)
  @mock.patch.object(
      issue_tracking_service, 'IsBugFilingEnabled', return_value=True)
  @mock.patch.object(
      issue_tracking_service, 'OpenBugAlreadyExistsForId', return_value=False)
  @mock.patch.object(
      issue_tracking_service,
      'OpenBugAlreadyExistsForLabel',
      return_value=False)
  @mock.patch.object(
      issue_tracking_service,
      'HasSufficientConfidenceInCulprit',
      return_value=True)
  @mock.patch.object(
      issue_tracking_service, '_HasPreviousAttempt', return_value=True)
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

    self.assertFalse(issue_tracking_service.ShouldFileBugForAnalysis(analysis))
    self.assertTrue(attempt_fn.called)

  @mock.patch.object(
      issue_tracking_service, 'OpenBugAlreadyExistsForTest', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'IsBugFilingEnabled', return_value=True)
  @mock.patch.object(
      issue_tracking_service, 'OpenBugAlreadyExistsForId', return_value=False)
  @mock.patch.object(
      issue_tracking_service,
      'OpenBugAlreadyExistsForLabel',
      return_value=False)
  @mock.patch.object(
      issue_tracking_service,
      'HasSufficientConfidenceInCulprit',
      return_value=True)
  @mock.patch.object(
      issue_tracking_service, '_HasPreviousAttempt', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'UnderDailyLimit', return_value=False)
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

    self.assertFalse(issue_tracking_service.ShouldFileBugForAnalysis(analysis))
    self.assertTrue(daily_limit_fn.called)

  @mock.patch.object(
      issue_tracking_service, 'IsBugFilingEnabled', return_value=True)
  @mock.patch.object(
      issue_tracking_service, 'OpenBugAlreadyExistsForId', return_value=False)
  @mock.patch.object(
      issue_tracking_service,
      'OpenBugAlreadyExistsForLabel',
      return_value=False)
  @mock.patch.object(
      issue_tracking_service,
      'HasSufficientConfidenceInCulprit',
      return_value=True)
  @mock.patch.object(
      issue_tracking_service, '_HasPreviousAttempt', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'UnderDailyLimit', return_value=True)
  @mock.patch.object(
      issue_tracking_service, 'OpenBugAlreadyExistsForTest', return_value=False)
  @mock.patch.object(
      issue_tracking_service,
      'BugAlreadyExistsForCustomField',
      return_value=True)
  def testShouldFileBugForAnalysisWhenBugExistsForCustomField(
      self, custom_field_exists, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.confidence_in_culprit = 0.5
    analysis.Save()

    self.assertFalse(issue_tracking_service.ShouldFileBugForAnalysis(analysis))
    self.assertTrue(custom_field_exists.called)

  @mock.patch.object(
      issue_tracking_service, 'IsBugFilingEnabled', return_value=True)
  @mock.patch.object(
      issue_tracking_service, 'OpenBugAlreadyExistsForId', return_value=False)
  @mock.patch.object(
      issue_tracking_service,
      'OpenBugAlreadyExistsForLabel',
      return_value=False)
  @mock.patch.object(
      issue_tracking_service,
      'HasSufficientConfidenceInCulprit',
      return_value=True)
  @mock.patch.object(
      issue_tracking_service, '_HasPreviousAttempt', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'UnderDailyLimit', return_value=True)
  @mock.patch.object(
      issue_tracking_service,
      'BugAlreadyExistsForCustomField',
      return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'OpenBugAlreadyExistsForTest', return_value=True)
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

    self.assertFalse(issue_tracking_service.ShouldFileBugForAnalysis(analysis))
    self.assertTrue(test_exists_Fn.called)

  def testShouldUpdateBugForAnalysisConfiguredFalse(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.bug_id = 123
    analysis.data_points = [DataPoint(), DataPoint(), DataPoint()]
    analysis.suspected_flake_build_number = 1
    analysis.algorithm_parameters = {'update_monorail_bug': False}
    self.assertFalse(
        issue_tracking_service.ShouldUpdateBugForAnalysis(analysis))

  def testShouldUpdateBugForAnalysisNoBugId(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.data_points = [DataPoint(), DataPoint(), DataPoint()]
    analysis.confidence_in_culprit = 0.9
    self.UpdateUnitTestConfigSettings('check_flake_settings', {
        'update_monorail_bug': True,
        'minimum_confidence_score_to_update_cr': 0.6
    })

    self.assertFalse(
        issue_tracking_service.ShouldUpdateBugForAnalysis(analysis))

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

    self.assertFalse(
        issue_tracking_service.ShouldUpdateBugForAnalysis(analysis))

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

    self.assertFalse(
        issue_tracking_service.ShouldUpdateBugForAnalysis(analysis))

  @mock.patch.object(
      issue_tracking_service,
      'HasSufficientConfidenceInCulprit',
      return_value=False)
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

    self.assertFalse(
        issue_tracking_service.ShouldUpdateBugForAnalysis(analysis))

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

    self.assertFalse(
        issue_tracking_service.ShouldUpdateBugForAnalysis(analysis))

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

    self.assertTrue(issue_tracking_service.ShouldUpdateBugForAnalysis(analysis))

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2017, 1, 3))
  @mock.patch('services.issue_tracking_service.IssueTrackerAPI')
  def testOpenBugAlreadyExistsForId(self, mock_api, _):
    mock_api.return_value.getIssue.return_value = None
    self.assertFalse(issue_tracking_service.OpenBugAlreadyExistsForId(None))
    self.assertFalse(mock_api.return_value.getIssue.called)
    mock_api.reset_mock()

    mock_api.return_value.getIssue.return_value = None
    self.assertFalse(issue_tracking_service.OpenBugAlreadyExistsForId(1234))
    self.assertTrue(mock_api.return_value.getIssue.called)
    args, _ = mock_api.return_value.getIssue.call_args
    self.assertEqual((1234,), args)
    mock_api.reset_mock()

    mock_issue = mock.MagicMock()
    mock_issue.open = True
    mock_issue.updated = datetime.datetime(2017, 1, 1)
    mock_issue.merged_into = None
    mock_api.return_value.getIssue.return_value = mock_issue
    self.assertTrue(issue_tracking_service.OpenBugAlreadyExistsForId(1234))
    self.assertTrue(mock_api.return_value.getIssue.called)
    args, _ = mock_api.return_value.getIssue.call_args
    self.assertEqual((1234,), args)
    mock_api.reset_mock()

    mock_issue = mock.MagicMock()
    mock_issue.open = False
    mock_issue.updated = datetime.datetime(2017, 1, 2)
    mock_issue.merged_into = None
    mock_api.return_value.getIssue.return_value = mock_issue
    self.assertFalse(issue_tracking_service.OpenBugAlreadyExistsForId(1234))
    self.assertTrue(mock_api.return_value.getIssue.called)
    args, _ = mock_api.return_value.getIssue.call_args
    self.assertEqual((1234,), args)
    mock_api.reset_mock()

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2017, 1, 3))
  @mock.patch('services.issue_tracking_service.IssueTrackerAPI')
  def testOpenBugAlreadyExistsForLabel(self, mock_api, _):
    with self.assertRaises(AssertionError):
      issue_tracking_service.OpenBugAlreadyExistsForLabel(None)

    mock_api.return_value.getIssues.return_value = None
    self.assertFalse(
        issue_tracking_service.OpenBugAlreadyExistsForLabel('test'))
    self.assertTrue(mock_api.return_value.getIssues.called)
    args, _ = mock_api.return_value.getIssues.call_args
    self.assertEqual(('label:test',), args)
    mock_api.reset_mock()

    mock_issue = mock.MagicMock()
    mock_issue.open = True
    mock_issue.updated = datetime.datetime(2017, 1, 1)
    mock_api.return_value.getIssues.return_value = [mock_issue]
    self.assertTrue(issue_tracking_service.OpenBugAlreadyExistsForLabel('test'))
    self.assertTrue(mock_api.return_value.getIssues.called)
    args, _ = mock_api.return_value.getIssues.call_args
    self.assertEqual(('label:test',), args)
    mock_api.reset_mock()

    mock_issue_1 = mock.MagicMock()
    mock_issue_1.open = True
    mock_issue_1.updated = datetime.datetime(2017, 1, 1)
    mock_issue_2 = mock.MagicMock()
    mock_issue_2.open = False
    mock_issue_2.updated = datetime.datetime(2017, 1, 1)
    mock_api.return_value.getIssues.return_value = [mock_issue_1, mock_issue_2]
    self.assertTrue(issue_tracking_service.OpenBugAlreadyExistsForLabel('test'))
    self.assertTrue(mock_api.return_value.getIssues.called)
    args, _ = mock_api.return_value.getIssues.call_args
    self.assertEqual(('label:test',), args)
    mock_api.reset_mock()

    mock_issue_1 = mock.MagicMock()
    mock_issue_1.open = False
    mock_issue_1.updated = datetime.datetime(2017, 1, 2)
    mock_issue_2 = mock.MagicMock()
    mock_issue_2.open = False
    mock_issue_2.updated = datetime.datetime(2017, 1, 1)
    mock_api.return_value.getIssues.return_value = [mock_issue_1, mock_issue_2]
    self.assertFalse(
        issue_tracking_service.OpenBugAlreadyExistsForLabel('test'))
    self.assertTrue(mock_api.return_value.getIssues.called)
    args, _ = mock_api.return_value.getIssues.call_args
    self.assertEqual(('label:test',), args)
    mock_api.reset_mock()

  @mock.patch.object(issue_tracking_service,
                     'GetExistingBugIdForCustomizedField')
  def testBugAlreadyExistsForCustomField(self, mock_get_fn):
    mock_get_fn.return_value = None
    self.assertEqual(False,
                     issue_tracking_service.BugAlreadyExistsForCustomField('f'))
    self.assertTrue(mock_get_fn.called)
    mock_get_fn.reset_mock()

    mock_get_fn.return_value = 1234
    self.assertEqual(True,
                     issue_tracking_service.BugAlreadyExistsForCustomField('f'))
    self.assertTrue(mock_get_fn.called)

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2017, 1, 3))
  @mock.patch.object(issue_tracking_service, 'TraverseMergedIssues')
  @mock.patch('services.issue_tracking_service.IssueTrackerAPI')
  def testGetExistingBugIdForCustomizedField(self, mock_api,
                                             mock_traverse_issues, _):
    with self.assertRaises(AssertionError):
      issue_tracking_service.GetExistingBugIdForCustomizedField(None)

    mock_api.return_value.getIssues.return_value = None
    self.assertEqual(
        None, issue_tracking_service.GetExistingBugIdForCustomizedField('test'))
    self.assertTrue(mock_api.return_value.getIssues.called)
    args, _ = mock_api.return_value.getIssues.call_args
    self.assertEqual(('Flaky-Test=test is:open',), args)
    mock_api.reset_mock()

    mock_issue = mock.MagicMock()
    mock_issue.open = True
    mock_issue.updated = datetime.datetime(2017, 1, 1)
    mock_issue.summary = 'test is flaky'
    mock_issue.id = 1234
    mock_api.return_value.getIssues.return_value = [mock_issue]
    mock_traverse_issues.return_value = mock_issue
    self.assertEqual(
        mock_issue.id,
        issue_tracking_service.GetExistingBugIdForCustomizedField('test'))
    self.assertTrue(mock_api.return_value.getIssues.called)
    args, _ = mock_api.return_value.getIssues.call_args
    self.assertEqual(('Flaky-Test=test is:open',), args)
    mock_api.reset_mock()

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2017, 1, 3))
  @mock.patch('services.issue_tracking_service.IssueTrackerAPI')
  def testOpenBugAlreadyExistsForTest(self, mock_api, _):
    with self.assertRaises(AssertionError):
      issue_tracking_service.OpenBugAlreadyExistsForTest(None)

    mock_api.return_value.getIssues.return_value = None
    self.assertFalse(issue_tracking_service.OpenBugAlreadyExistsForTest('test'))
    self.assertTrue(mock_api.return_value.getIssues.called)
    args, _ = mock_api.return_value.getIssues.call_args
    self.assertEqual(('summary:test is:open',), args)
    mock_api.reset_mock()

    mock_issue = mock.MagicMock()
    mock_issue.open = True
    mock_issue.updated = datetime.datetime(2017, 1, 1)
    mock_issue.summary = 'test is flaky'
    mock_api.return_value.getIssues.return_value = [mock_issue]
    self.assertTrue(issue_tracking_service.OpenBugAlreadyExistsForTest('test'))
    self.assertTrue(mock_api.return_value.getIssues.called)
    args, _ = mock_api.return_value.getIssues.call_args
    self.assertEqual(('summary:test is:open',), args)
    mock_api.reset_mock()

    mock_issue = mock.MagicMock()
    mock_issue.open = True
    mock_issue.updated = datetime.datetime(2017, 1, 1)
    mock_issue.summary = 'test flaked'
    mock_api.return_value.getIssues.return_value = [mock_issue]
    self.assertTrue(issue_tracking_service.OpenBugAlreadyExistsForTest('test'))
    self.assertTrue(mock_api.return_value.getIssues.called)
    args, _ = mock_api.return_value.getIssues.call_args
    self.assertEqual(('summary:test is:open',), args)
    mock_api.reset_mock()

  @mock.patch('services.issue_tracking_service.IssueTrackerAPI')
  def testCreateBug(self, mock_api):
    summary = 'test summary'
    description = 'test description'
    project_id = 'proj'
    issue = Issue({
        'status': 'Available',
        'summary': summary,
        'description': description,
        'projectId': 'chromium',
        'state': 'open',
    })

    issue_tracking_service.CreateBug(issue, project_id=project_id)
    mock_api.assert_has_calls(mock.call(project_id, use_staging=False))
    mock_api.return_value.create.assert_has_calls(mock.call(issue))

  @mock.patch('services.issue_tracking_service.IssueTrackerAPI')
  def testUpdateBug(self, mock_api):
    summary = 'test summary'
    description = 'test description'
    project_id = 'proj'
    comment = 'test comment'
    issue = Issue({
        'status': 'Available',
        'summary': summary,
        'description': description,
        'projectId': 'chromium',
        'state': 'open',
    })

    issue_tracking_service.UpdateBug(issue, comment, project_id=project_id)
    mock_api.assert_has_calls(mock.call(project_id, use_staging=False))
    mock_api.return_value.update.assert_has_calls(
        mock.call(issue, comment, send_email=True))

  @mock.patch.object(issue_tracking_service, 'CreateBug')
  def testCreateBugForFlakeAnalyzer(self, mock_create_bug_fn):
    with self.assertRaises(AssertionError):
      issue_tracking_service.CreateBugForFlakeAnalyzer(None, None, None)
    with self.assertRaises(AssertionError):
      issue_tracking_service.CreateBugForFlakeAnalyzer('test', None, None)
    with self.assertRaises(AssertionError):
      issue_tracking_service.CreateBugForFlakeAnalyzer(None, 'subject', None)
    with self.assertRaises(AssertionError):
      issue_tracking_service.CreateBugForFlakeAnalyzer(None, None, 'body')

    issue_tracking_service.CreateBugForFlakeAnalyzer('test', 'subject', 'body')
    self.assertTrue(mock_create_bug_fn.called)

  def testTraverseMergedIssuesWithoutMergeInto(self):
    issue_tracker = mock.Mock()
    expected_issue = Issue({'id': 123})
    issue_tracker.getIssue.return_value = expected_issue

    issue = issue_tracking_service.TraverseMergedIssues(123, issue_tracker)
    self.assertEqual(expected_issue, issue)
    issue_tracker.assert_has_calls([mock.call.getIssue(123)])

  def testTraverseMergedIssuesWithMergeInto(self):
    issue_tracker = mock.Mock()
    expected_issue = Issue({'id': 345})
    issue_tracker.getIssue.side_effect = [
        Issue({
            'id': 123,
            'mergedInto': {
                'issueId': 234
            }
        }),
        Issue({
            'id': 234,
            'mergedInto': {
                'issueId': 345
            }
        }),
        expected_issue,
    ]

    issue = issue_tracking_service.TraverseMergedIssues(123, issue_tracker)
    self.assertEqual(expected_issue, issue)
    issue_tracker.assert_has_calls([
        mock.call.getIssue(123),
        mock.call.getIssue(234),
        mock.call.getIssue(345)
    ])

  def testTraverseMergedIssuesWithMergeInACircle(self):
    issue_tracker = mock.Mock()
    expected_issue = Issue({'id': 123})
    issue_tracker.getIssue.side_effect = [
        Issue({
            'id': 123,
            'mergedInto': {
                'issueId': 234
            }
        }),
        Issue({
            'id': 234,
            'mergedInto': {
                'issueId': 123
            }
        }),
        expected_issue,
    ]

    issue = issue_tracking_service.TraverseMergedIssues(123, issue_tracker)
    self.assertEqual(expected_issue, issue)
    issue_tracker.assert_has_calls([
        mock.call.getIssue(123),
        mock.call.getIssue(234),
        mock.call.getIssue(123)
    ])

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
    self.assertTrue(issue_tracking_service._HasPreviousAttempt(analysis))

    analysis.has_attempted_filing = False
    analysis.put()
    self.assertFalse(issue_tracking_service._HasPreviousAttempt(analysis))

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
        issue_tracking_service.HasSufficientConfidenceInCulprit(analysis, 0.5))

    analysis.confidence_in_culprit = 1.0
    analysis.Save()
    self.assertTrue(
        issue_tracking_service.HasSufficientConfidenceInCulprit(analysis, 1.0))

    analysis.confidence_in_culprit = .9
    analysis.put()
    self.assertTrue(
        issue_tracking_service.HasSufficientConfidenceInCulprit(analysis, 0.9))

    analysis.confidence_in_culprit = .8
    analysis.put()
    self.assertFalse(
        issue_tracking_service.HasSufficientConfidenceInCulprit(analysis, 0.9))

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

    self.assertTrue(issue_tracking_service.UnderDailyLimit(analysis))

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

    self.assertFalse(issue_tracking_service.UnderDailyLimit(analysis))

  def testGetPriorityLabelForConfidence(self):
    self.assertEqual('Pri-1',
                     issue_tracking_service.GetPriorityLabelForConfidence(1.0))
    self.assertEqual('Pri-1',
                     issue_tracking_service.GetPriorityLabelForConfidence(.98))
    self.assertEqual('Pri-3',
                     issue_tracking_service.GetPriorityLabelForConfidence(.9))
    self.assertEqual('Pri-3',
                     issue_tracking_service.GetPriorityLabelForConfidence(.85))

  @mock.patch.object(issue_tracking_service, 'UpdateBug')
  @mock.patch.object(issue_tracking_service, 'GetBugForId')
  def testUpdateBugForDetectedFlake(self, mock_get_bug_fn, mock_update_bug_fn):
    occurrence_count = 10
    step_name = 'step_foobar'
    test_name = 'test_foobar'
    issue_id = '100'
    issue = Issue({
        'status':
            'Available',
        'summary':
            'summary',
        'description':
            'description',
        'projectId':
            'chromium',
        'labels': [
            'Sheriff-Chromium',
            issue_tracking_service._FINDIT_DETECTED_LABEL_TEXT
        ],
        'fieldValues': [CustomizedField('Flaky-Test', test_name)],
        'state':
            'open',
    })

    comment = issue_tracking_service._FLAKE_DETECTION_COMMENT_BODY.format(
        flake_count=occurrence_count,
        test_name=test_name,
        flake_url='dummy url')

    flake_issue = FlakeIssue(issue_id=issue_id)
    flake = Flake(
        step_name=step_name,
        test_name=test_name,
        flake_issue=flake_issue,
        project_id='chromium')
    flake.put()

    mock_get_bug_fn.return_value = issue
    issue_tracking_service.UpdateBugForDetectedFlake(flake, occurrence_count)
    mock_update_bug_fn.assert_has_calls(
        mock.call(issue, comment, flake.project_id))

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2018, 1, 1))
  @mock.patch.object(issue_tracking_service, 'UpdateBug')
  @mock.patch.object(issue_tracking_service, 'GetBugForId')
  def testUpdateBugForDetectedFlakeWithMissingFields(self, mock_get_bug_fn,
                                                     mock_update_bug_fn, _):
    occurrence_count = 10
    step_name = 'step_foobar'
    test_name = 'test_foobar'
    issue_id = '100'
    issue = Issue({
        'status': 'Available',
        'summary': 'summary',
        'description': 'description',
        'projectId': 'chromium',
        'state': 'open',
    })

    comment = issue_tracking_service._FLAKE_DETECTION_COMMENT_BODY.format(
        flake_count=occurrence_count,
        test_name=test_name,
        flake_url='dummy url')

    flake_issue = FlakeIssue(issue_id=issue_id)
    flake = Flake(
        step_name=step_name,
        test_name=test_name,
        flake_issue=flake_issue,
        project_id='chromium')
    flake.put()

    mock_get_bug_fn.return_value = issue
    issue_tracking_service.UpdateBugForDetectedFlake(flake, occurrence_count)
    mock_update_bug_fn.assert_has_calls(
        mock.call(issue, comment, flake.project_id))
    self.assertListEqual(
        sorted(issue.labels),
        sorted([
            'Sheriff-Chromium',
            issue_tracking_service._FINDIT_DETECTED_LABEL_TEXT
        ]))
    self.assertEqual(issue.field_values[0].field_name, 'Flaky-Test')
    self.assertEqual(issue.field_values[0].field_value, test_name)
    self.assertEqual(flake.flake_issue.last_updated_time,
                     datetime.datetime(2018, 1, 1))

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2018, 1, 1))
  @mock.patch.object(issue_tracking_service, 'CreateBug')
  def testCreateBugForDetectedFlake(self, create_bug_fn, _):
    occurrence_count = 10
    step_name = 'step_foobar'
    test_name = 'test_foobar'

    flake = Flake(
        step_name=step_name, test_name=test_name, project_id='chromium')
    flake.put()

    def assign_id(issue, _):
      issue.id = '100'

    create_bug_fn.side_effect = assign_id

    issue_tracking_service.CreateBugForDetectedFlake(flake, occurrence_count)
    self.assertTrue(create_bug_fn.called)
    self.assertEqual(flake.flake_issue.issue_id, '100')
    self.assertEqual(flake.flake_issue.last_updated_time,
                     datetime.datetime(2018, 1, 1))

    issue = create_bug_fn.call_args_list[0][0][0]
    flake_url = 'dummy url'
    summary = issue_tracking_service._FLAKE_DETECTION_BUG_TITLE.format(
        test_name=flake.test_name)
    body_header = (
        issue_tracking_service._FLAKE_DETECTION_CREATE_BUG_BODY_HEADER.format(
            test_name=flake.test_name))
    body_content = (
        issue_tracking_service._FLAKE_DETECTION_CREATE_BUG_BODY.format(
            flake_count=occurrence_count, flake_url=flake_url))
    description = '{}\n\n{}'.format(body_header, body_content)
    description = '{}\n\n{}'.format(
        description,
        issue_tracking_service._FLAKE_DETECTION_CREATE_BUG_BODY_FOOTER)
    self.assertEqual(issue.id, '100')
    self.assertEqual(issue.summary, summary)
    self.assertEqual(issue.description, description)

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2018, 1, 1))
  @mock.patch.object(issue_tracking_service, 'CreateBug')
  def testCreateBugForDetectedFlakeWithOldBug(self, create_bug_fn, _):
    occurrence_count = 10
    step_name = 'step_foobar'
    test_name = 'test_foobar'

    flake = Flake(
        step_name=step_name, test_name=test_name, project_id='chromium')
    flake.put()

    def assign_id(issue, _):
      issue.id = '100'

    create_bug_fn.side_effect = assign_id

    issue_tracking_service.CreateBugForDetectedFlake(flake, occurrence_count)
    self.assertTrue(create_bug_fn.called)
    self.assertEqual(flake.flake_issue.issue_id, '100')
    self.assertEqual(flake.flake_issue.last_updated_time,
                     datetime.datetime(2018, 1, 1))

    issue = create_bug_fn.call_args_list[0][0][0]
    flake_url = 'dummy url'
    summary = issue_tracking_service._FLAKE_DETECTION_BUG_TITLE.format(
        test_name=flake.test_name)
    body_header = (
        issue_tracking_service._FLAKE_DETECTION_CREATE_BUG_BODY_HEADER.format(
            test_name=flake.test_name))
    body_content = (
        issue_tracking_service._FLAKE_DETECTION_CREATE_BUG_BODY.format(
            flake_count=occurrence_count, flake_url=flake_url))
    description = '{}\n\n{}'.format(body_header, body_content)
    description = '{}\n\n{}'.format(
        description,
        issue_tracking_service._FLAKE_DETECTION_CREATE_BUG_BODY_FOOTER)
    self.assertEqual(issue.id, '100')
    self.assertEqual(issue.summary, summary)
    self.assertEqual(issue.description, description)
