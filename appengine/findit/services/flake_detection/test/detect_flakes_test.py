# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from libs import time_util
from model.flake.detection.flake import Flake
from model.flake.detection.flake_occurrence import FlakeOccurrence
from model.flake.detection.flake_occurrence import FlakeType
from model.flake.detection.flake_issue import FlakeIssue
from services import bigquery_helper
from services.flake_detection import detect_flakes
from services.flake_detection import detection_filing_util

from waterfall.test import wf_testcase


class DetectFlakes(wf_testcase.WaterfallTestCase):

  def testMonorailProjectForCqName(self):
    self.assertEqual('webrtc',
                     detect_flakes.MonorailProjectForCqName('webrtc/src'))
    self.assertEqual('v8',
                     detect_flakes.MonorailProjectForCqName('chromium/v8/v8'))
    self.assertEqual('chromium',
                     detect_flakes.MonorailProjectForCqName('chromium'))

  @mock.patch.object(bigquery_helper, '_CreateBigqueryClient')
  @mock.patch.object(bigquery_helper, 'QueryRequest')
  @mock.patch.object(detection_filing_util, 'CheckAndFileBugForDetectedFlake')
  def testQueryAndStoreFlakes(self, mock_filing, mock_query_fn, _):
    step_name = 'step'
    test_name = 'test'
    build_id = 1

    flake = Flake.Create(step_name, test_name)
    flake.put()

    mock_query_fn.return_value = True, [{
        'attempt_ts': '2018-01-01 00:00:00.000 UTC',
        'master_name': 'm',
        'builder_name': 'b',
        'step_name': step_name,
        'test_name': test_name,
        'build_number': 1,
        'build_id': build_id,
        'flake_type': 'cq_false_rejection',
        'cq_name': 'chromium',
        'luci_project': 'chromium'
    }]

    detect_flakes.QueryAndStoreFlakes()
    flakes = Flake.query().fetch()
    self.assertEqual(1, len(flakes))

    occurrences = FlakeOccurrence.query(
        FlakeOccurrence.build_id == build_id, ancestor=flakes[0].key).fetch()
    self.assertEqual(1, len(occurrences))

    mock_filing.assert_called_once_with(flake)

  @mock.patch.object(bigquery_helper, '_CreateBigqueryClient')
  @mock.patch.object(bigquery_helper, 'QueryRequest')
  @mock.patch.object(detection_filing_util, 'CheckAndFileBugForDetectedFlake')
  def testQueryAndStoreFlakesWithDuplicateOccurrence(self, mock_filing,
                                                     mock_query_fn, _):
    step_name = 'step'
    test_name = 'test'
    build_id = 1
    master_name = 'm'
    builder_name = 'b'
    build_number = 100

    flake = Flake.Create(step_name, test_name)
    flake.put()

    occurrence = FlakeOccurrence.Create(
        step_name, test_name, build_id, master_name, builder_name, build_number,
        time_util.GetUTCNow(), FlakeType.CQ_FALSE_REJECTION)
    occurrence.put()

    mock_query_fn.return_value = True, [{
        'attempt_ts': '2018-01-01 00:00:00.000 UTC',
        'master_name': 'm',
        'builder_name': 'b',
        'step_name': step_name,
        'test_name': test_name,
        'build_number': 1,
        'build_id': build_id,
        'flake_type': 'cq_false_rejection',
        'cq_name': 'chromium',
        'luci_project': 'chromium'
    }]

    detect_flakes.QueryAndStoreFlakes()
    flakes = Flake.query().fetch()
    self.assertEqual(1, len(flakes))

    occurrences = FlakeOccurrence.query(
        FlakeOccurrence.build_id == build_id, ancestor=flakes[0].key).fetch()
    self.assertEqual(1, len(occurrences))

    mock_filing.assert_not_called()

  @mock.patch.object(bigquery_helper, '_CreateBigqueryClient')
  @mock.patch.object(bigquery_helper, 'QueryRequest')
  @mock.patch.object(detection_filing_util, 'CheckAndFileBugForDetectedFlake')
  def testQueryAndStoreFlakesWithFailedParse(self, mock_filing, mock_query_fn,
                                             _):
    step_name = 'step'
    test_name = 'test'
    build_id = 1

    mock_query_fn.return_value = True, [{
        'attempt_ts': None,
        'master_name': None,
        'builder_name': 'b',
        'step_name': step_name,
        'test_name': test_name,
        'build_number': 1,
        'build_id': build_id,
        'flake_type': 'cq_false_rejection',
        'cq_name': 'chromium',
        'luci_project': 'chromium'
    }]

    detect_flakes.QueryAndStoreFlakes()
    flakes = Flake.query().fetch()
    self.assertEqual(0, len(flakes))

    mock_filing.assert_not_called()

  @mock.patch.object(bigquery_helper, '_CreateBigqueryClient')
  @mock.patch.object(bigquery_helper, 'QueryRequest')
  @mock.patch.object(detection_filing_util, 'CheckAndFileBugForDetectedFlake')
  def testQueryAndStoreFlakesWithNewFlake(self, mock_filing, mock_query_fn, _):
    step_name = 'step'
    test_name = 'test'
    build_id = 1

    mock_query_fn.return_value = True, [{
        'attempt_ts': '2018-01-01 00:00:00.000 UTC',
        'master_name': 'm',
        'builder_name': 'b',
        'step_name': step_name,
        'test_name': test_name,
        'build_number': 1,
        'build_id': build_id,
        'flake_type': 'cq_false_rejection',
        'cq_name': 'chromium',
        'luci_project': 'chromium'
    }]

    detect_flakes.QueryAndStoreFlakes()
    flakes = Flake.query().fetch()
    self.assertEqual(1, len(flakes))

    occurrences = FlakeOccurrence.query(
        FlakeOccurrence.build_id == build_id, ancestor=flakes[0].key).fetch()
    self.assertEqual(1, len(occurrences))

    mock_filing.assert_called_once_with(flakes[0])
