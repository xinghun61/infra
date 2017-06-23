# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from google.appengine.ext import ndb
import webapp2

from handlers import auto_revert_metrics
from model import revert_cl_status
from model.base_suspected_cl import RevertCL
from model.tree_closure import TreeClosure
from model.wf_suspected_cl import WfSuspectedCL

from testing_utils import testing


class AutoRevertMetricsTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/auto-revert-metrics', auto_revert_metrics.AutoRevertMetrics),
      ],
      debug=True)

  def testCalculateMetrics(self):
    expected_stats = {
        'average': '00:00:01',
        'total': 2,
        'ninetieth_percentile': '00:00:01',
        'seventieth_percentile': '00:00:01',
        'fiftieth_percentile': '00:00:01'
    }
    self.assertEqual(expected_stats,
                     auto_revert_metrics._CalculateMetrics([1, 2]))

  def testGetAnalysesWithinDateRange(self):
    start_date = datetime(2017, 4, 8, 0, 0)
    end_date = datetime(2017, 4, 9, 0, 0)

    suspected_cl_1 = WfSuspectedCL.Create('chromium', 'r1', 1)
    suspected_cl_1.identified_time = datetime(2017, 4, 8, 0, 1)
    suspected_cl_1.put()

    suspected_cl_2 = WfSuspectedCL.Create('chromium', 'r2', 2)
    suspected_cl_2.identified_time = datetime(2017, 4, 8, 0, 2)
    suspected_cl_2.put()

    suspected_cl_3 = WfSuspectedCL.Create('chromium', 'r3', 3)
    suspected_cl_3.identified_time = datetime(2017, 4, 9, 0, 2)
    suspected_cl_3.put()

    self.assertEqual([suspected_cl_1, suspected_cl_2],
                     auto_revert_metrics._GetAnalysesWithinDateRange(
                         start_date, end_date, 1))

  def testGenerateFinditMetrics(self):
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
    slow_suspected_cl.cr_notification_time = datetime(2017, 3, 15, 2)
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

    metrics = auto_revert_metrics._GenerateFinditMetrics([
        reverted_suspected_cl, duplicate_fast_suspected_cl,
        duplicate_slow_suspected_cl, false_positive_suspected_cl,
        slow_suspected_cl, false_positive_suspected_cl_no_revert
    ])

    self.assertEqual(expected_metrics, metrics)

  def testGenerateTreeClosureMetrics(self):
    ndb.put_multi([
        TreeClosure(
            tree_name='skia',
            closed_time=datetime(2017, 03, 15),
            auto_closed=True,
            auto_opened=False,
            possible_flake=True,
            has_revert=False,
            step_name='compile',),
        TreeClosure(
            tree_name='chromium',
            closed_time=datetime(2017, 03, 15),
            auto_closed=True,
            auto_opened=False,
            possible_flake=True,
            has_revert=False,
            step_name='bot_update',),
        TreeClosure(
            tree_name='chromium',
            closed_time=datetime(2017, 03, 15, 10, 10, 10),
            auto_closed=True,
            auto_opened=True,
            possible_flake=False,
            has_revert=False,
            step_name='compile',),
        TreeClosure(
            tree_name='chromium',
            closed_time=datetime(2017, 03, 15, 17, 10, 10),
            auto_closed=True,
            auto_opened=False,
            possible_flake=False,
            has_revert=False,
            step_name='compile',),
        TreeClosure(
            tree_name='chromium',
            closed_time=datetime(2017, 03, 15, 19, 10, 10),
            auto_closed=True,
            auto_opened=False,
            possible_flake=True,
            has_revert=False,
            step_name='compile',),
        TreeClosure(
            tree_name='chromium',
            closed_time=datetime(2017, 03, 16, 21, 10, 10),
            auto_closed=True,
            auto_opened=False,
            possible_flake=False,
            has_revert=True,
            step_name='compile',),
        TreeClosure(
            tree_name='chromium',
            closed_time=datetime(2017, 04, 15, 17, 10, 10),
            auto_closed=True,
            auto_opened=False,
            possible_flake=False,
            has_revert=False,
            step_name='compile',),
    ])

    metrics = auto_revert_metrics._GenerateTreeClosureMetrics(
        'chromium', 'compile', datetime(2017, 03, 13), datetime(2017, 04, 01))
    expected_metrics = {
        'total': 4,
        'manually_closed_or_auto_opened': 1,
        'flakes': 1,
        'reverts': 1,
        'others': 1,
    }
    self.assertEqual(expected_metrics, metrics)
