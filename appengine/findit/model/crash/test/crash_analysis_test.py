# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
from datetime import datetime

from crash.type_enums import CrashClient
from crash.test.predator_testcase import PredatorTestCase
from model import analysis_status
from model import result_status
from model import triage_status
from model.crash.crash_analysis import CrashAnalysis
from model.crash.fracas_crash_analysis import FracasCrashAnalysis


class CrashAnalysisTest(PredatorTestCase):
  def testCrashAnalysisStatusIsCompleted(self):
    for status in (analysis_status.COMPLETED, analysis_status.ERROR):
      analysis = CrashAnalysis()
      analysis.status = status
      self.assertTrue(analysis.completed)

  def testCrashAnalysisStatusIsNotCompleted(self):
    for status in (analysis_status.PENDING, analysis_status.RUNNING):
      analysis = CrashAnalysis()
      analysis.status = status
      self.assertFalse(analysis.completed)

  def testCrashAnalysisDurationWhenNotCompleted(self):
    analysis = CrashAnalysis()
    analysis.status = analysis_status.RUNNING
    self.assertIsNone(analysis.duration)

  def testCrashAnalysisDurationWhenStartTimeNotSet(self):
    analysis = CrashAnalysis()
    analysis.status = analysis_status.COMPLETED
    analysis.started_time = datetime(2015, 07, 30, 21, 15, 30, 40)
    analysis.completed_time = datetime(2015, 07, 30, 21, 16, 15, 50)
    self.assertEqual(45, analysis.duration)

  def testCrashAnalysisStatusIsFailed(self):
    analysis = CrashAnalysis()
    analysis.status = analysis_status.ERROR
    self.assertTrue(analysis.failed)

  def testCrashAnalysisStatusIsNotFailed(self):
    for status in (analysis_status.PENDING, analysis_status.RUNNING,
                   analysis_status.COMPLETED):
      analysis = CrashAnalysis()
      analysis.status = status
      self.assertFalse(analysis.failed)

  def testCrashAnalysisReset(self):
    analysis = CrashAnalysis()
    analysis.pipeline_status_path = ''
    analysis.status = analysis_status.COMPLETED
    analysis.requested_time = datetime.utcnow()
    analysis.started_time = datetime.utcnow()
    analysis.findit_version = ''
    analysis.has_regression_range = True
    analysis.found_suspects = True
    analysis.solution = ''
    analysis.Reset()
    self.assertIsNone(analysis.pipeline_status_path)
    self.assertEqual(analysis_status.PENDING, analysis.status)
    self.assertIsNone(analysis.requested_time)
    self.assertIsNone(analysis.started_time)
    self.assertIsNone(analysis.findit_version)
    self.assertIsNone(analysis.has_regression_range)
    self.assertIsNone(analysis.found_suspects)
    self.assertIsNone(analysis.solution)
    self.assertEqual(analysis.result, None)
    self.assertEqual(analysis.regression_range_triage_status,
                     triage_status.UNTRIAGED)
    self.assertEqual(analysis.suspected_cls_triage_status,
                     triage_status.UNTRIAGED)
    self.assertEqual(analysis.suspected_project_triage_status,
                     triage_status.UNTRIAGED)
    self.assertEqual(analysis.suspected_components_triage_status,
                     triage_status.UNTRIAGED)
    self.assertEqual(analysis.culprit_regression_range, None)
    self.assertEqual(analysis.culprit_cls, None)
    self.assertEqual(analysis.culprit_project, None)
    self.assertEqual(analysis.culprit_components, None)
    self.assertEqual(analysis.triage_history, None)
    self.assertEqual(analysis.note, None)

  def testUpdateCrashAnalysis(self):
    update = {'note': 'dummy'}
    analysis = CrashAnalysis()
    analysis.Update(update)
    self.assertEqual(analysis.note, update['note'])

  def testUpdateCrashAnalysisWithNonExistentProperty(self):
    update = {'dummy': 'dummy_content'}
    analysis = CrashAnalysis()
    analysis.Update(update)
    self.assertFalse(hasattr(analysis, 'dummy'))

  def testCreateCrashAnalysis(self):
    crash_identifiers = {'signature': 'sig'}
    analysis = CrashAnalysis.Create(crash_identifiers)
    analysis.put()
    self.assertIsNotNone(analysis)
    self.assertEqual(CrashAnalysis.Get(crash_identifiers), analysis)
