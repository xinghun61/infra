# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from gae_libs.testcase import TestCase
from model.flake.detection.flake_occurrence import FlakeOccurrence
from model.flake.flake import Flake
from model.flake.flake_type import FlakeType


class FlakeOccurrenceTest(TestCase):

  def testGetId(self):
    step_ui_name = 'step'
    test_name = 'test'
    build_id = 123
    self.assertEqual(
        'CQ_FALSE_REJECTION@123@step@test',
        FlakeOccurrence.GetId(
            FlakeType.CQ_FALSE_REJECTION,
            build_id=build_id,
            step_ui_name=step_ui_name,
            test_name=test_name))

    self.assertEqual(
        'RETRY_WITH_PATCH@123@step@test',
        FlakeOccurrence.GetId(
            FlakeType.RETRY_WITH_PATCH,
            build_id=build_id,
            step_ui_name=step_ui_name,
            test_name=test_name))

  def testCreate(self):
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
        test_label_name=test_label_name)
    flake.put()

    build_id = 123
    luci_bucket = 'try'
    luci_builder = 'luci builder'
    legacy_master_name = 'buildbot master'
    legacy_build_number = 999
    time_happened = datetime.datetime(2018, 1, 1)
    gerrit_cl_id = 98765

    cq_false_rejection_occurrence = FlakeOccurrence.Create(
        FlakeType.CQ_FALSE_REJECTION,
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
    cq_false_rejection_occurrence.put()

    retry_with_patch_occurrence = FlakeOccurrence.Create(
        FlakeType.RETRY_WITH_PATCH,
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
    retry_with_patch_occurrence.put()

    fetched_flake_occurrences = FlakeOccurrence.query().fetch()
    self.assertEqual(2, len(fetched_flake_occurrences))
    self.assertIn(cq_false_rejection_occurrence, fetched_flake_occurrences)
    self.assertIn(retry_with_patch_occurrence, fetched_flake_occurrences)
    self.assertIsNotNone(fetched_flake_occurrences[0].time_detected)
    self.assertIsNotNone(fetched_flake_occurrences[1].time_detected)
