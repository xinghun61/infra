# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

import webapp2

from handlers import auto_revert_metrics
from model import revert_cl_status
from model.base_suspected_cl import RevertCL
from model.wf_suspected_cl import WfSuspectedCL

from testing_utils import testing


class AutoRevertMetricsTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/auto-revert-metrics', auto_revert_metrics.AutoRevertMetrics),
  ], debug=True)

  def testCalculateMetrics(self):
    expected_stats = {
        'average': '00:00:01',
        'total': 2,
        'ninetieth_percentile': '00:00:01',
        'seventieth_percentile': '00:00:01',
        'fiftieth_percentile': '00:00:01'
    }
    self.assertEqual(
        expected_stats, auto_revert_metrics._CalculateMetrics([1, 2]))

  def testGenerateMetrics(self):
    reverted_suspected_cl = WfSuspectedCL.Create('chromium', 'r1', 1)
    reverted_revert_cl = RevertCL()
    reverted_revert_cl.status = revert_cl_status.COMMITTED
    reverted_suspected_cl.revert_cl = reverted_revert_cl

    duplicate_fast_suspected_cl = WfSuspectedCL.Create('chromium', 'r2', 2)
    duplicate_revert_cl = RevertCL()
    duplicate_revert_cl.created_time = datetime(2017, 3, 15, 1)
    duplicate_revert_cl.status = revert_cl_status.DUPLICATE
    duplicate_fast_suspected_cl.revert_cl = duplicate_revert_cl
    duplicate_fast_suspected_cl.sheriff_action_time = datetime(2017, 3, 15, 2)

    duplicate_slow_suspected_cl = WfSuspectedCL.Create('chromium', 'r3', 3)
    duplicate_revert_cl = RevertCL()
    duplicate_revert_cl.created_time = datetime(2017, 3, 15, 2)
    duplicate_revert_cl.status = revert_cl_status.DUPLICATE
    duplicate_slow_suspected_cl.revert_cl = duplicate_revert_cl
    duplicate_slow_suspected_cl.sheriff_action_time = datetime(2017, 3, 15, 1)

    false_positive_suspected_cl = WfSuspectedCL.Create('chromium', 'r4', 4)
    false_positive_revert_cl = RevertCL()
    false_positive_revert_cl.status = revert_cl_status.FALSE_POSITIVE
    false_positive_suspected_cl.revert_cl = false_positive_revert_cl

    slow_suspected_cl = WfSuspectedCL.Create('chromium', 'r5', 5)
    slow_suspected_cl.identified_time = datetime(2017, 3, 15, 2)
    slow_suspected_cl.should_be_reverted = True
    slow_suspected_cl.sheriff_action_time = datetime(2017, 3, 15, 1)

    false_positive_suspected_cl_no_revert = WfSuspectedCL.Create(
        'chromium', 'r6', 6)

    expected_metrics = {
        'revert_cls_detected': 5,
        'revert_cls_created': 4,
        'revert_cls_committed': 1,
        'duplicate_revert_cls': 2,
        'sheriffs_faster': 2,
        'false_positives': 1,
        'findit_faster': 1,
        'faster_than_sheriff_metrics': {
            'ninetieth_percentile': '01:00:00',
            'average': '01:00:00',
            'total': 1,
            'fiftieth_percentile': '01:00:00',
            'seventieth_percentile': '01:00:00'
        },
        'slower_than_sheriff_metrics': {
            'ninetieth_percentile': '01:00:00',
            'average': '01:00:00',
            'total': 2,
            'fiftieth_percentile': '01:00:00',
            'seventieth_percentile': '01:00:00'
        }
    }

    metrics = auto_revert_metrics._GenerateMetrics(
        [reverted_suspected_cl, duplicate_fast_suspected_cl,
         duplicate_slow_suspected_cl, false_positive_suspected_cl,
         slow_suspected_cl, false_positive_suspected_cl_no_revert])

    self.assertEqual(expected_metrics, metrics)
