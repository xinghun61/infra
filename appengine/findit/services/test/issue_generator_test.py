# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import mock

from libs import analysis_status
from model.flake.analysis.flake_culprit import FlakeCulprit
from model.flake.analysis.data_point import DataPoint
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from services import issue_generator
from waterfall.test.wf_testcase import WaterfallTestCase


class IssueGeneratorTest(WaterfallTestCase):

  def testGenerateAnalysisLink(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    self.assertIn(analysis.key.urlsafe(),
                  issue_generator._GenerateAnalysisLink(analysis))

  def testGenerateWrongResultLink(self):
    test_name = 'test_name'
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', test_name)
    self.assertIn(test_name, issue_generator._GenerateWrongResultLink(analysis))

  def testGenerateMessageTextWithCulprit(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    task_id = 'task_id'
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.original_master_name = master_name
    analysis.original_builder_name = builder_name
    analysis.original_build_number = build_number
    analysis.status = analysis_status.COMPLETED
    analysis.data_points = [DataPoint.Create(task_ids=[task_id])]
    culprit = FlakeCulprit.Create('c', 'r', 123, 'http://')
    culprit.flake_analysis_urlsafe_keys.append(analysis.key.urlsafe())
    culprit.put()
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.confidence_in_culprit = 0.6713
    comment = issue_generator._GenerateMessageText(analysis)
    self.assertIn('67.1% confidence', comment)
    self.assertIn('r123', comment)
    self.assertIn(task_id, comment)

  @mock.patch.object(
      MasterFlakeAnalysis,
      'GetRepresentativeSwarmingTaskId',
      return_value='task_id')
  def testGenerateMessageTextNoCulprit(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.original_master_name = master_name
    analysis.original_builder_name = builder_name
    analysis.original_build_number = build_number
    analysis.status = analysis_status.COMPLETED
    comment = issue_generator._GenerateMessageText(analysis)
    self.assertTrue('longstanding' in comment, comment)
