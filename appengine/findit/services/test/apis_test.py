# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import mock

from google.appengine.api import taskqueue

from model.flake.analysis.flake_analysis_request import FlakeAnalysisRequest
from model.flake.detection.flake_occurrence import (
    CQFalseRejectionFlakeOccurrence)
from services import apis
from waterfall.test.wf_testcase import WaterfallTestCase


class ApisTest(WaterfallTestCase):

  def setUp(self):
    super(ApisTest, self).setUp()
    self.taskqueue_requests = []

    def Mocked_taskqueue_add(**kwargs):
      self.taskqueue_requests.append(kwargs)

    self.mock(taskqueue, 'add', Mocked_taskqueue_add)

  def testAnalyzeDetectedFlakeOccurrence(self):
    occurrence = CQFalseRejectionFlakeOccurrence.Create(
        build_id=111,
        step_name='step1',
        test_name='test1',
        luci_project='chromium',
        luci_bucket='try',
        luci_builder='tryserver.chromium.linux',
        legacy_master_name='linux_chromium_rel_ng',
        legacy_build_number=999,
        reference_succeeded_build_id=456,
        time_happened=None,
        gerrit_cl_id=98765,
        parent_flake_key=None)
    apis.AnalyzeDetectedFlakeOccurrence(occurrence, 12345)
    self.assertEqual(1, len(self.taskqueue_requests))

  def testAsyncProcessFlakeReport(self):
    analysis_request = FlakeAnalysisRequest.Create('t', False, 12345)
    apis.AsyncProcessFlakeReport(analysis_request, 'foo@fake.com', False)
    self.assertEqual(1, len(self.taskqueue_requests))
