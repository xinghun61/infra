# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from handlers.flake.detection import flake_detection_utils
from model.flake.flake import Flake
from model.flake.flake_issue import FlakeIssue
from model.flake.detection.flake_occurrence import (
    CQFalseRejectionFlakeOccurrence)
from waterfall.test.wf_testcase import WaterfallTestCase


class FlakeDetectionUtilsTest(WaterfallTestCase):

  def testGetFlakeInformation(self):
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=900)
    flake_issue.last_updated_time_by_flake_detection = datetime(2018, 1, 1)
    flake_issue.put()

    luci_project = 'chromium'
    step_ui_name = 'step'
    test_name = 'test'
    normalized_step_name = 'normalized_step_name'
    normalized_test_name = 'normalized_test_name'
    flake = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name)

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

    expected_flake_dict = {
        'luci_project':
            'chromium',
        'normalized_step_name':
            'normalized_step_name',
        'normalized_test_name':
            'normalized_test_name',
        'flake_issue_key':
            flake_issue.key,
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
            'time_happened': datetime(2018, 1, 1),
            'time_detected': datetime(2018, 1, 1),
            'gerrit_cl_id': gerrit_cl_id
        }],
    }

    self.assertEqual(expected_flake_dict,
                     flake_detection_utils.GetFlakeInformation(flake, 2))

  def testGetFlakeInformationNoOccurrences(self):

    luci_project = 'chromium'
    normalized_step_name = 'normalized_step_name'
    normalized_test_name = 'normalized_test_name_2'
    flake = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name)
    flake.put()

    self.assertIsNone(flake_detection_utils.GetFlakeInformation(flake, 2))

  def testGetFlakeInformationNoIssue(self):

    luci_project = 'chromium'
    step_ui_name = 'step'
    test_name = 'test'
    normalized_step_name = 'normalized_step_name'
    normalized_test_name = 'normalized_test_name_3'
    flake = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name)
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
        'flake_issue_key':
            None,
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
            'time_happened': datetime(2018, 1, 1),
            'time_detected': datetime(2018, 1, 1),
            'gerrit_cl_id': gerrit_cl_id
        }],
    }

    self.assertEqual(expected_flake_dict,
                     flake_detection_utils.GetFlakeInformation(flake, 2))
