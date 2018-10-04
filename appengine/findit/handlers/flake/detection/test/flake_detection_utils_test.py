# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from handlers.flake.detection import flake_detection_utils
from libs import time_util
from model.flake.flake import Flake
from model.flake.flake import TestLocation
from model.flake.flake_issue import FlakeIssue
from model.flake.detection.flake_occurrence import (
    CQFalseRejectionFlakeOccurrence)
from waterfall.test.wf_testcase import WaterfallTestCase


class FlakeDetectionUtilsTest(WaterfallTestCase):

  @mock.patch.object(time_util, 'GetUTCNow', return_value=datetime(2018, 1, 3))
  def testGetFlakeInformation(self, _):
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=900)
    flake_issue.last_updated_time_by_flake_detection = datetime(2018, 1, 1)
    flake_issue.put()

    luci_project = 'chromium'
    step_ui_name = 'step'
    test_name = 'test'
    normalized_step_name = 'normalized_step_name'
    normalized_test_name = 'normalized_test_name'
    test_label_name = 'test_label'
    flake = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name,
        test_label_name=test_label_name,
    )

    flake.component = 'Mock>Component'
    flake.test_location = TestLocation()
    flake.test_location.file_path = '../../some/test/path/a.cc'
    flake.test_location.line_number = 42
    flake.flake_issue_key = flake_issue.key
    flake.put()

    build_id = 123
    luci_bucket = 'try'
    luci_builder = 'luci builder'
    legacy_master_name = 'buildbot master'
    legacy_build_number = 999
    time_happened = datetime(2018, 1, 1)
    gerrit_cl_id = 98765
    occurrence = CQFalseRejectionFlakeOccurrence.Create(
        build_id=build_id,
        step_ui_name=step_ui_name,
        test_name=test_name,
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder=luci_builder,
        legacy_master_name=legacy_master_name,
        legacy_build_number=legacy_build_number,
        time_happened=time_happened,
        gerrit_cl_id=gerrit_cl_id,
        parent_flake_key=flake.key)
    occurrence.time_detected = datetime(2018, 1, 1)
    occurrence.put()

    occurrence2 = CQFalseRejectionFlakeOccurrence.Create(
        build_id=124,
        step_ui_name=step_ui_name,
        test_name=test_name,
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder='luci builder 2',
        legacy_master_name=legacy_master_name,
        legacy_build_number=legacy_build_number,
        time_happened=datetime(2018, 1, 2),
        gerrit_cl_id=gerrit_cl_id,
        parent_flake_key=flake.key)
    occurrence2.time_detected = datetime(2018, 1, 2)
    occurrence2.put()

    occurrence3 = CQFalseRejectionFlakeOccurrence.Create(
        build_id=125,
        step_ui_name=step_ui_name,
        test_name=test_name,
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder='luci builder 2',
        legacy_master_name=legacy_master_name,
        legacy_build_number=legacy_build_number,
        time_happened=datetime(2018, 1, 2, 2),
        gerrit_cl_id=gerrit_cl_id,
        parent_flake_key=flake.key)
    occurrence3.time_detected = datetime(2018, 1, 2, 2)
    occurrence3.put()

    expected_flake_dict = {
        'luci_project':
            'chromium',
        'normalized_step_name':
            'normalized_step_name',
        'normalized_test_name':
            'normalized_test_name',
        'test_suite_name':
            None,
        'test_label_name':
            'test_label',
        'flake_issue_key':
            flake_issue.key,
        'last_occurred_time':
            None,
        'false_rejection_count_last_week':
            0,
        'impacted_cl_count_last_week':
            0,
        'flake_issue': {
            'monorail_project':
                'chromium',
            'issue_id':
                900,
            'last_updated_time_by_flake_detection':
                datetime(2018, 1, 1),
            'issue_link': ('https://monorail-prod.appspot.com/p/chromium/'
                           'issues/detail?id=900')
        },
        'component':
            'Mock>Component',
        'test_location': {
            'file_path': '../../some/test/path/a.cc',
            'line_number': 42,
        },
        'occurrences': [{
            'group_by_field':
                'luci builder 2',
            'occurrences': [{
                'build_id': '125',
                'step_ui_name': step_ui_name,
                'test_name': test_name,
                'build_configuration': {
                    'luci_project': 'chromium',
                    'luci_bucket': 'try',
                    'luci_builder': 'luci builder 2',
                    'legacy_master_name': 'buildbot master',
                    'legacy_build_number': 999
                },
                'time_happened': '2018-01-02 02:00:00 UTC',
                'time_detected': '2018-01-02 02:00:00 UTC',
                'gerrit_cl_id': gerrit_cl_id
            }, {
                'build_id': '124',
                'step_ui_name': step_ui_name,
                'test_name': test_name,
                'build_configuration': {
                    'luci_project': 'chromium',
                    'luci_bucket': 'try',
                    'luci_builder': 'luci builder 2',
                    'legacy_master_name': 'buildbot master',
                    'legacy_build_number': 999
                },
                'time_happened': '2018-01-02 00:00:00 UTC',
                'time_detected': '2018-01-02 00:00:00 UTC',
                'gerrit_cl_id': gerrit_cl_id
            }]
        }, {
            'group_by_field':
                'luci builder',
            'occurrences': [{
                'build_id': '123',
                'step_ui_name': step_ui_name,
                'test_name': test_name,
                'build_configuration': {
                    'luci_project': 'chromium',
                    'luci_bucket': 'try',
                    'luci_builder': 'luci builder',
                    'legacy_master_name': 'buildbot master',
                    'legacy_build_number': 999
                },
                'time_happened': '2018-01-01 00:00:00 UTC',
                'time_detected': '2018-01-01 00:00:00 UTC',
                'gerrit_cl_id': gerrit_cl_id
            }]
        }],
    }
    self.assertEqual(expected_flake_dict,
                     flake_detection_utils.GetFlakeInformation(flake, 5))

  def testGetFlakeInformationNoOccurrences(self):

    luci_project = 'chromium'
    normalized_step_name = 'normalized_step_name'
    normalized_test_name = 'normalized_test_name_2'
    test_label_name = 'test_label'
    flake = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name,
        test_label_name=test_label_name)
    flake.put()

    self.assertIsNone(flake_detection_utils.GetFlakeInformation(flake, None))

  @mock.patch.object(time_util, 'GetUTCNow', return_value=datetime(2018, 1, 3))
  def testGetFlakeInformationNoIssue(self, _):

    luci_project = 'chromium'
    step_ui_name = 'step'
    test_name = 'test'
    normalized_step_name = 'normalized_step_name'
    normalized_test_name = 'normalized_test_name_3'
    test_label_name = 'test_label'
    flake = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name,
        test_label_name=test_label_name)
    flake.put()

    build_id = 123
    luci_bucket = 'try'
    luci_builder = 'luci builder'
    legacy_master_name = 'buildbot master'
    legacy_build_number = 999
    time_happened = datetime(2018, 1, 1)
    gerrit_cl_id = 98765
    occurrence = CQFalseRejectionFlakeOccurrence.Create(
        build_id=build_id,
        step_ui_name=step_ui_name,
        test_name=test_name,
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder=luci_builder,
        legacy_master_name=legacy_master_name,
        legacy_build_number=legacy_build_number,
        time_happened=time_happened,
        gerrit_cl_id=gerrit_cl_id,
        parent_flake_key=flake.key)
    occurrence.time_detected = datetime(2018, 1, 1)
    occurrence.put()

    expected_flake_dict = {
        'luci_project':
            'chromium',
        'normalized_step_name':
            normalized_step_name,
        'normalized_test_name':
            normalized_test_name,
        'test_suite_name':
            None,
        'test_label_name':
            test_label_name,
        'flake_issue_key':
            None,
        'last_occurred_time':
            None,
        'false_rejection_count_last_week':
            0,
        'impacted_cl_count_last_week':
            0,
        'component':
            None,
        'test_location':
            None,
        'occurrences': [{
            'group_by_field':
                'luci builder',
            'occurrences': [{
                'build_id': '123',
                'step_ui_name': step_ui_name,
                'test_name': test_name,
                'build_configuration': {
                    'luci_project': 'chromium',
                    'luci_bucket': 'try',
                    'luci_builder': 'luci builder',
                    'legacy_master_name': 'buildbot master',
                    'legacy_build_number': 999
                },
                'time_happened': '2018-01-01 00:00:00 UTC',
                'time_detected': '2018-01-01 00:00:00 UTC',
                'gerrit_cl_id': gerrit_cl_id
            }]
        }],
    }

    self.assertEqual(expected_flake_dict,
                     flake_detection_utils.GetFlakeInformation(flake, 2))
