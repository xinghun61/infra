# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from common.findit_testcase import FinditTestCase
from model import analysis_status
from model.flake.flake_analysis_request import BuildStep
from model.flake.flake_analysis_request import FlakeAnalysisRequest
from model.flake.master_flake_analysis import MasterFlakeAnalysis


class FlakeAnalysisRequestTest(FinditTestCase):

  def testStripMasterPrefix(self):
    cases = {
        'master.tryserver.chromium.linux': 'tryserver.chromium.linux',
        'chromium.linux': 'chromium.linux',
    }
    for original_name, expected_name in cases.iteritems():
      self.assertEqual(expected_name,
                       BuildStep._StripMasterPrefix(original_name))

  def testBuildStapHasMatchingWaterfallStep(self):
    build_step = BuildStep.Create('m', 'b', 0, 's', datetime.utcnow())
    self.assertFalse(build_step.has_matching_waterfall_step)
    build_step.wf_master_name = 'm'
    build_step.wf_builder_name = 'b'
    build_step.wf_build_number = 0
    build_step.wf_step_name = 's'
    self.assertTrue(build_step.has_matching_waterfall_step)

  def testAddBuildStep(self):
    t1 = datetime(2016, 10, 1, 0, 0, 0)
    t2 = datetime(2016, 10, 2, 0, 0, 0)
    t3 = datetime(2016, 10, 2, 1, 0, 0)
    t4 = datetime(2016, 10, 2, 0, 30, 0)
    request = FlakeAnalysisRequest.Create('flaky_test', False, 123)
    self.assertTrue(request.AddBuildStep('m', 'b1', 1, 's', t1))
    self.assertTrue(request.AddBuildStep('m', 'b2', 10, 's', t2))
    self.assertFalse(request.AddBuildStep('m', 'b2', 11, 's', t3))
    self.assertTrue(request.AddBuildStep('m', 'b2', 9, 's', t4))
    self.assertEqual(2, len(request.build_steps), request.build_steps)
    self.assertEqual(BuildStep.Create('m', 'b1', 1, 's', t1),
                     request.build_steps[0])
    self.assertEqual(BuildStep.Create('m', 'b2', 9, 's', t4),
                     request.build_steps[1])

  def testCopyFrom(self):
    request1 = FlakeAnalysisRequest.Create('flaky_test', False, 123)

    request2 = FlakeAnalysisRequest.Create('flaky_test', True, 456)
    request2.AddBuildStep('m', 'b1', 1, 's', datetime(2016, 10, 1))
    request2.user_emails = ['email']
    analysis = MasterFlakeAnalysis.Create('m', 'b', 100, 's', 't')
    analysis.Save()
    request2.analyses.append(analysis.key)

    request1.CopyFrom(request2)

    self.assertEqual(request2.is_step, request1.is_step)
    self.assertEqual(request2.bug_id, request1.bug_id)
    self.assertEqual(request2.user_emails, request1.user_emails)
    self.assertEqual(request2.build_steps, request1.build_steps)
    self.assertEqual(request2.analyses, request1.analyses)
