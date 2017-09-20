# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import mock

from common.waterfall import failure_type
from libs import analysis_status
from model.wf_analysis import WfAnalysis
from pipelines.test_failure.detect_first_test_failure_pipeline import (
    DetectFirstTestFailurePipeline)
from services import ci_failure
from services.test_failure import ci_test_failure
from waterfall.test import wf_testcase


class DetectFirstTestFailureTest(wf_testcase.WaterfallTestCase):

  def _CreateAndSaveWfAnanlysis(self, master_name, builder_name, build_number,
                                status):
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.status = status
    analysis.put()

  @mock.patch.object(ci_test_failure, 'CheckFirstKnownFailureForSwarmingTests')
  @mock.patch.object(ci_failure, 'CheckForFirstKnownFailure')
  def testRunPipelineForTestFailure(self, mock_fn1, mock_fn2):
    master_name = 'm'
    builder_name = 'b'
    build_number = 25409

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.RUNNING)

    current_build_failure_info = {
        'failed': True,
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 25409,
        'chromium_revision': None,
        'builds': {
            25409: {
                'blame_list': [],
                'chromium_revision': None
            }
        },
        'failed_steps': {
            'a_test': {
                'current_failure': 25409,
                'first_failure': 25409
            }
        },
        'failure_type': failure_type.TEST,
        'parent_mastername': None,
        'parent_buildername': None,
    }
    expected_failure_info = copy.deepcopy(current_build_failure_info)

    pipeline = DetectFirstTestFailurePipeline()
    failure_info = pipeline.run(current_build_failure_info)

    self.assertEqual(failure_info, expected_failure_info)
    mock_fn1.assert_has_called_with(master_name, builder_name, build_number,
                                    current_build_failure_info['failed_steps'],
                                    current_build_failure_info['builds'])
    mock_fn2.assert_has_called_with(master_name, builder_name, build_number,
                                    current_build_failure_info['failed_steps'],
                                    current_build_failure_info['builds'])
