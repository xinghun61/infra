# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import datetime
import mock

from libs import analysis_status
from libs import time_util
from model.flake.analysis.data_point import DataPoint
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from services import flake_issue_util
from services import monorail_util
from services.flake_failure import flake_bug_util
from waterfall.test.wf_testcase import WaterfallTestCase


class FlakeBugUtilTest(WaterfallTestCase):

  def testGetMinimumConfidenceToUpdateEndpoints(self):
    self.UpdateUnitTestConfigSettings(
        'action_settings', {'minimum_confidence_to_update_endpoints': 0.9})
    self.assertEqual(0.9,
                     flake_bug_util.GetMinimumConfidenceToUpdateEndpoints())

  @mock.patch.object(flake_bug_util, 'UnderDailyLimit', return_value=True)
  @mock.patch.object(flake_bug_util, 'HasPreviousAttempt', return_value=False)
  @mock.patch.object(
      flake_bug_util, 'HasSufficientConfidenceInCulprit', return_value=True)
  @mock.patch.object(
      monorail_util, 'OpenBugAlreadyExistsForId', return_value=False)
  @mock.patch.object(
      flake_issue_util,
      'OpenIssueAlreadyExistsForFlakyTest',
      return_value=False)
  def testShouldFileBugForAnalysis(self, test_exists_fn, id_exists_fn,
                                   sufficient_confidence_fn,
                                   previous_attempt_fn, under_limit_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    self.assertTrue(flake_bug_util.ShouldFileBugForAnalysis(analysis))
    id_exists_fn.assert_not_called()
    sufficient_confidence_fn.assert_called()
    previous_attempt_fn.assert_called()
    test_exists_fn.assert_called()
    under_limit_fn.assert_called_with()

  @mock.patch.object(flake_bug_util, 'UnderDailyLimit', return_value=True)
  @mock.patch.object(flake_bug_util, 'HasPreviousAttempt', return_value=False)
  @mock.patch.object(
      flake_bug_util, 'HasSufficientConfidenceInCulprit', return_value=True)
  @mock.patch.object(
      monorail_util, 'OpenBugAlreadyExistsForId', return_value=True)
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

    self.assertFalse(flake_bug_util.ShouldFileBugForAnalysis(analysis))
    self.assertTrue(id_exists_fn.called)

  @mock.patch.object(flake_bug_util, 'UnderDailyLimit', return_value=True)
  @mock.patch.object(flake_bug_util, 'HasPreviousAttempt', return_value=False)
  @mock.patch.object(
      monorail_util, 'OpenBugAlreadyExistsForId', return_value=False)
  @mock.patch.object(
      flake_bug_util, 'HasSufficientConfidenceInCulprit', return_value=False)
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

    self.assertFalse(flake_bug_util.ShouldFileBugForAnalysis(analysis))
    self.assertTrue(confidence_fn.called)

  @mock.patch.object(flake_bug_util, 'UnderDailyLimit', return_value=True)
  @mock.patch.object(
      monorail_util, 'OpenBugAlreadyExistsForId', return_value=False)
  @mock.patch.object(
      flake_bug_util, 'HasSufficientConfidenceInCulprit', return_value=True)
  @mock.patch.object(flake_bug_util, 'HasPreviousAttempt', return_value=True)
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

    self.assertFalse(flake_bug_util.ShouldFileBugForAnalysis(analysis))
    self.assertTrue(attempt_fn.called)

  @mock.patch.object(
      monorail_util, 'OpenBugAlreadyExistsForId', return_value=False)
  @mock.patch.object(
      flake_bug_util, 'HasSufficientConfidenceInCulprit', return_value=True)
  @mock.patch.object(flake_bug_util, 'HasPreviousAttempt', return_value=False)
  @mock.patch.object(flake_bug_util, 'UnderDailyLimit', return_value=False)
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

    self.assertFalse(flake_bug_util.ShouldFileBugForAnalysis(analysis))
    daily_limit_fn.assert_called_with()

  @mock.patch.object(
      monorail_util, 'OpenBugAlreadyExistsForId', return_value=False)
  @mock.patch.object(
      flake_bug_util, 'HasSufficientConfidenceInCulprit', return_value=True)
  @mock.patch.object(flake_bug_util, 'HasPreviousAttempt', return_value=False)
  @mock.patch.object(flake_bug_util, 'UnderDailyLimit', return_value=True)
  @mock.patch.object(
      flake_issue_util, 'OpenIssueAlreadyExistsForFlakyTest', return_value=True)
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

    self.assertFalse(flake_bug_util.ShouldFileBugForAnalysis(analysis))
    self.assertTrue(test_exists_Fn.called)

  def testShouldUpdateBugForAnalysisNoBugId(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.data_points = [DataPoint(), DataPoint(), DataPoint()]
    analysis.confidence_in_culprit = 0.9
    self.UpdateUnitTestConfigSettings(
        'action_settings',
        {'minimum_confidence_score_to_update_endpoints': 0.6})

    self.assertFalse(flake_bug_util.ShouldUpdateBugForAnalysis(analysis))

  def testShouldUpdateBugForAnalysisNoBugIdWithCulprit(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.original_master_name = master_name
    analysis.original_builder_name = builder_name
    analysis.original_build_number = build_number
    analysis.status = analysis_status.COMPLETED
    analysis.culprit_urlsafe_key = 'c'
    analysis.data_points = [DataPoint(), DataPoint(), DataPoint()]
    analysis.confidence_in_culprit = 0.9
    self.UpdateUnitTestConfigSettings(
        'action_settings', {'minimum_confidence_to_update_endpoints': 0.6})

    self.assertFalse(flake_bug_util.ShouldUpdateBugForAnalysis(analysis))

  def testShouldUpdateBugForAnalysisInsufficientDataPoints(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.data_points = [DataPoint()]
    analysis.bug_id = 123
    analysis.confidence_in_culprit = 0.9
    self.UpdateUnitTestConfigSettings(
        'action_settings',
        {'minimum_confidence_score_to_update_endpoints': 0.6})

    self.assertFalse(flake_bug_util.ShouldUpdateBugForAnalysis(analysis))

  @mock.patch.object(
      flake_bug_util, 'HasSufficientConfidenceInCulprit', return_value=False)
  def testShouldUpdateBugForAnalysisInsufficientConfidence(self, _):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.bug_id = 123
    analysis.data_points = [DataPoint(), DataPoint(), DataPoint()]
    analysis.confidence_in_culprit = 0.4
    analysis.culprit_urlsafe_key = 'c'

    self.UpdateUnitTestConfigSettings(
        'action_settings',
        {'minimum_confidence_score_to_update_endpoints': 0.6})

    self.assertFalse(flake_bug_util.ShouldUpdateBugForAnalysis(analysis))

  def testShouldUpdateBugForAnalysis(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.bug_id = 123
    analysis.data_points = [DataPoint(), DataPoint(), DataPoint()]
    analysis.confidence_in_culprit = 0.9
    self.UpdateUnitTestConfigSettings(
        'action_settings',
        {'minimum_confidence_score_to_update_endpoints': 0.6})

    self.assertTrue(flake_bug_util.ShouldUpdateBugForAnalysis(analysis))

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
    self.assertTrue(flake_bug_util.HasPreviousAttempt(analysis))

    analysis.has_attempted_filing = False
    analysis.put()
    self.assertFalse(flake_bug_util.HasPreviousAttempt(analysis))

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
        flake_bug_util.HasSufficientConfidenceInCulprit(analysis, 0.5))

    analysis.confidence_in_culprit = 1.0
    analysis.Save()
    self.assertTrue(
        flake_bug_util.HasSufficientConfidenceInCulprit(analysis, 1.0))

    analysis.confidence_in_culprit = .9
    analysis.put()
    self.assertTrue(
        flake_bug_util.HasSufficientConfidenceInCulprit(analysis, 0.9))

    analysis.confidence_in_culprit = .8
    analysis.put()
    self.assertFalse(
        flake_bug_util.HasSufficientConfidenceInCulprit(analysis, 0.9))

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
    analysis.Save()

    self.assertTrue(flake_bug_util.UnderDailyLimit())

  @mock.patch.object(
      time_util,
      'GetMostRecentUTCMidnight',
      return_value=datetime.datetime(2017, 1, 1))
  def testUnderDailyLimitIfOver(self, _):
    self.UpdateUnitTestConfigSettings(
        config_property='action_settings',
        override_data={'max_flake_detection_bug_updates_per_day': 2})
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
    analysis.put()

    self.assertFalse(flake_bug_util.UnderDailyLimit())
