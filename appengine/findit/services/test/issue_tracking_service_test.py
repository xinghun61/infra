# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import copy
import datetime
import mock
import textwrap

from libs import analysis_status
from libs import time_util
from model.flake.flake_culprit import FlakeCulprit
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from monorail_api import Issue
from services import issue_tracking_service
from waterfall.test import wf_testcase
from waterfall.test.wf_testcase import DEFAULT_CONFIG_DATA


class IssueTrackingServiceTest(wf_testcase.WaterfallTestCase):

  def testAddFinditLabelToIssue(self):
    issue = mock.MagicMock()
    issue.labels = []
    issue_tracking_service.AddFinditLabelToIssue(issue)
    self.assertEqual(['Test-Findit-Analyzed'], issue.labels)
    issue_tracking_service.AddFinditLabelToIssue(issue)
    self.assertEqual(['Test-Findit-Analyzed'], issue.labels)

  def testGenerateAnalysisLink(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    self.assertIn(analysis.key.urlsafe(),
                  issue_tracking_service.GenerateAnalysisLink(analysis))

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

  def testGenerateWrongResultLink(self):
    test_name = 'test_name'
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', test_name)
    self.assertIn(test_name,
                  issue_tracking_service.GenerateWrongResultLink(analysis))

  def testGetMinimumConfidenceToFileBugs(self):
    self.UpdateUnitTestConfigSettings(
        'check_flake_settings', {'minimum_confidence_to_create_bugs': 0.9})
    self.assertEqual(0.9,
                     issue_tracking_service.GetMinimumConfidenceToFileBugs())

  def testGetMinimumConfidenceToUpdateBugs(self):
    self.UpdateUnitTestConfigSettings('check_flake_settings',
                                      {'minimum_confidence_to_update_cr': 0.8})
    self.assertEqual(0.8,
                     issue_tracking_service.GetMinimumConfidenceToUpdateBugs())

  def testIsBugFilingEnabled(self):
    self.UpdateUnitTestConfigSettings('check_flake_settings',
                                      {'create_monorail_bug': False})
    self.assertFalse(issue_tracking_service.IsBugFilingEnabled())

    self.UpdateUnitTestConfigSettings('check_flake_settings',
                                      {'create_monorail_bug': True})
    self.assertTrue(issue_tracking_service.IsBugFilingEnabled())

  def testIsBugUpdatingEnabled(self):
    self.UpdateUnitTestConfigSettings('check_flake_settings',
                                      {'update_monorail_bug': False})
    self.assertFalse(issue_tracking_service.IsBugUpdatingEnabled())

    self.UpdateUnitTestConfigSettings('check_flake_settings',
                                      {'update_monorail_bug': True})
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
      'BugAlreadyExistsForCustomField',
      return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'OpenBugAlreadyExistsForTest', return_value=False)
  def testShouldFileBugForAnalysis(self, test_exists_fn, field_exists_fn,
                                   id_exists_fn, sufficient_confidence_fn,
                                   previous_attempt_fn, feature_enabled_fn,
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
    id_exists_fn.assert_not_called()
    sufficient_confidence_fn.assert_called()
    previous_attempt_fn.assert_called()
    feature_enabled_fn.assert_called()
    under_limit_fn.assert_called()
    field_exists_fn.assert_called()
    test_exists_fn.assert_called()

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
      issue_tracking_service, 'OpenBugAlreadyExistsForId', return_value=False)
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
    self.assertEqual(('summary:test is:open label:Test-Flaky',), args)
    mock_api.reset_mock()

    mock_issue = mock.MagicMock()
    mock_issue.open = True
    mock_issue.updated = datetime.datetime(2017, 1, 1)
    mock_issue.summary = 'test is flaky'
    mock_api.return_value.getIssues.return_value = [mock_issue]
    self.assertTrue(issue_tracking_service.OpenBugAlreadyExistsForTest('test'))
    self.assertTrue(mock_api.return_value.getIssues.called)
    args, _ = mock_api.return_value.getIssues.call_args
    self.assertEqual(('summary:test is:open label:Test-Flaky',), args)
    mock_api.reset_mock()

    mock_issue = mock.MagicMock()
    mock_issue.open = True
    mock_issue.updated = datetime.datetime(2017, 1, 1)
    mock_issue.summary = 'test flaked'
    mock_api.return_value.getIssues.return_value = [mock_issue]
    self.assertTrue(issue_tracking_service.OpenBugAlreadyExistsForTest('test'))
    self.assertTrue(mock_api.return_value.getIssues.called)
    args, _ = mock_api.return_value.getIssues.call_args
    self.assertEqual(('summary:test is:open label:Test-Flaky',), args)
    mock_api.reset_mock()

  @mock.patch.object(issue_tracking_service, '_GetOpenIssues')
  def testGetExistingOpenBugIdForTestReturnsEarliestBug(self,
                                                        mock_get_open_issues):
    issue1 = mock.Mock()
    issue1.id = 456
    issue2 = mock.Mock()
    issue2.id = 123
    mock_get_open_issues.return_value = [issue1, issue2]
    self.assertEqual(123,
                     issue_tracking_service.GetExistingOpenBugIdForTest('t'))

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
    self.assertEqual('Pri-1',
                     issue_tracking_service.GetPriorityLabelForConfidence(.9))
    self.assertEqual('Pri-1',
                     issue_tracking_service.GetPriorityLabelForConfidence(.85))

  @mock.patch.object(issue_tracking_service, 'CreateBug')
  def testCreateBugForFlakeDetection(self, mock_create_bug_fn):

    def assign_issue_id(issue, _):
      issue.id = 12345
      return issue.id

    mock_create_bug_fn.side_effect = assign_issue_id

    normalized_step_name = 'target'
    normalized_test_name = 'suite.test'
    num_occurrences = 5
    monorail_project = 'chromium'
    flake_url = 'https://findit-for-me-staging.com/flake/detection/show-flake?key=1212'  # pylint: disable=line-too-long
    previous_tracking_bug_id = None

    issue_id = issue_tracking_service.CreateBugForFlakeDetection(
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name,
        num_occurrences=num_occurrences,
        monorail_project=monorail_project,
        flake_url=flake_url,
        previous_tracking_bug_id=previous_tracking_bug_id)
    mock_create_bug_fn.assert_called_once()
    self.assertEqual(12345, issue_id)

    expected_status = 'Untriaged'
    expected_summary = 'suite.test is flaky'

    expected_description = textwrap.dedent("""
target: suite.test is flaky.

Findit detected 5 flake occurrences of this test within the past
24 hours. List of all flake occurrences can be found at:
https://findit-for-me-staging.com/flake/detection/show-flake?key=1212.

Flaky tests should be disabled within 30 minutes unless culprit CL is found and
reverted, please disable it first and then find an appropriate owner.

Automatically posted by the findit-for-me app (https://goo.gl/Ot9f7N). If this
result was incorrect, please apply the label Test-Findit-Wrong and mark the bug
as untriaged.""")

    expected_labels = [
        'Test-Findit-Detected', 'Sheriff-Chromium', 'Pri-1', 'Type-Bug',
        'Test-Flaky'
    ]

    issue = mock_create_bug_fn.call_args_list[0][0][0]
    self.assertEqual(expected_status, issue.status)
    self.assertEqual(expected_summary, issue.summary)
    self.assertEqual(expected_description, issue.description)
    self.assertEqual(expected_labels, issue.labels)
    self.assertEqual(1, len(issue.field_values))
    self.assertEqual('Flaky-Test', issue.field_values[0].to_dict()['fieldName'])
    self.assertEqual('suite.test',
                     issue.field_values[0].to_dict()['fieldValue'])

  @mock.patch.object(issue_tracking_service, 'CreateBug')
  def testCreateBugForFlakeDetectionWithPreviousBugId(self, mock_create_bug_fn):
    normalized_step_name = 'target'
    normalized_test_name = 'suite.test'
    num_occurrences = 5
    monorail_project = 'chromium'
    previous_tracking_bug_id = 56789
    flake_url = 'https://findit-for-me-staging.com/flake/detection/show-flake?key=1212'  # pylint: disable=line-too-long

    issue_tracking_service.CreateBugForFlakeDetection(
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name,
        num_occurrences=num_occurrences,
        monorail_project=monorail_project,
        flake_url=flake_url,
        previous_tracking_bug_id=previous_tracking_bug_id)

    expected_previous_bug_description = (
        '\n\nThis flaky test was previously tracked in bug 56789.\n\n')
    issue = mock_create_bug_fn.call_args_list[0][0][0]
    self.assertIn(expected_previous_bug_description, issue.description)

  @mock.patch.object(issue_tracking_service, 'GetBugForId')
  @mock.patch.object(issue_tracking_service, 'UpdateBug')
  def testUpdateBugForFlakeDetection(self, mock_update_bug_fn,
                                     mock_get_bug_for_id):
    normalized_test_name = 'suite.test'
    num_occurrences = 5
    monorail_project = 'chromium'
    flake_url = 'https://findit-for-me-staging.com/flake/detection/show-flake?key=1212'  # pylint: disable=line-too-long
    issue_id = 12345
    issue = Issue({
        'status': 'Available',
        'summary': 'summary',
        'description': 'description',
        'projectId': monorail_project,
        'labels': [],
        'fieldValues': [],
        'state': 'open',
    })

    mock_get_bug_for_id.return_value = issue
    issue_tracking_service.UpdateBugForFlakeDetection(
        bug_id=issue_id,
        normalized_test_name=normalized_test_name,
        num_occurrences=num_occurrences,
        monorail_project=monorail_project,
        flake_url=flake_url)

    expected_labels = ['Test-Findit-Detected', 'Sheriff-Chromium', 'Test-Flaky']
    issue = mock_update_bug_fn.call_args_list[0][0][0]
    self.assertEqual(expected_labels, issue.labels)
    self.assertEqual(1, len(issue.field_values))
    self.assertEqual('Flaky-Test', issue.field_values[0].to_dict()['fieldName'])
    self.assertEqual('suite.test',
                     issue.field_values[0].to_dict()['fieldValue'])

    expected_comment = textwrap.dedent("""
Findit detected 5 new flake occurrences of this test. To see the
list of flake occurrences, please visit:
https://findit-for-me-staging.com/flake/detection/show-flake?key=1212.

Since flakiness is ongoing, the issue was moved back into the Sheriff Bug Queue
(unless already there).

Automatically posted by the findit-for-me app (https://goo.gl/Ot9f7N).
Feedback is welcome! Please use component Tools>Test>FindIt>Flakiness.""")

    comment = mock_update_bug_fn.call_args_list[0][0][1]
    self.assertEqual(expected_comment, comment)

  @mock.patch.object(issue_tracking_service, 'GetBugForId')
  @mock.patch.object(issue_tracking_service, 'UpdateBug')
  def testUpdateBugForFlakeDetectionWithPreviousBugId(self, mock_update_bug_fn,
                                                      mock_get_bug_for_id):
    normalized_test_name = 'suite.test'
    num_occurrences = 5
    monorail_project = 'chromium'
    flake_url = 'https://findit-for-me-staging.com/flake/detection/show-flake?key=1212'  # pylint: disable=line-too-long
    issue_id = 12345
    previous_tracking_bug_id = 56789
    issue = Issue({
        'status': 'Available',
        'summary': 'summary',
        'description': 'description',
        'projectId': monorail_project,
        'labels': [],
        'fieldValues': [],
        'state': 'open',
    })

    mock_get_bug_for_id.return_value = issue
    issue_tracking_service.UpdateBugForFlakeDetection(
        bug_id=issue_id,
        normalized_test_name=normalized_test_name,
        num_occurrences=num_occurrences,
        monorail_project=monorail_project,
        flake_url=flake_url,
        previous_tracking_bug_id=previous_tracking_bug_id)

    expected_previous_bug_description = (
        '\n\nThis flaky test was previously tracked in bug 56789.\n\n')
    comment = mock_update_bug_fn.call_args_list[0][0][1]
    self.assertIn(expected_previous_bug_description, comment)
