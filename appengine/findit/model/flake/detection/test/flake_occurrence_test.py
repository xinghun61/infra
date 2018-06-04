# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from gae_libs.testcase import TestCase
from model.flake.detection.flake import Flake
from model.flake.detection.flake_occurrence import CQFalseRejectionFlakeOccurrence  # pylint: disable=line-too-long


class CQFalseRejectionFlakeOccurrenceTest(TestCase):

  def testCreate(self):
    luci_project = 'chromium'
    step_name = 'step'
    test_type = 'type'
    test_name = 'test'
    flake = Flake.Create(luci_project, step_name, test_type, test_name)
    flake.put()

    build_id = 123
    luci_bucket = 'try'
    luci_builder = 'luci builder'
    legacy_master_name = 'buildbot master'
    reference_succeeded_build_id = 456
    time_happened = datetime.datetime(2018, 1, 1)

    flake_occurrence = CQFalseRejectionFlakeOccurrence.Create(
        build_id=build_id,
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder=luci_builder,
        legacy_master_name=legacy_master_name,
        reference_succeeded_build_id=reference_succeeded_build_id,
        time_happened=time_happened,
        parent_flake_key=flake.key)
    flake_occurrence.put()

    fetched_flake_occurrence = CQFalseRejectionFlakeOccurrence.get_by_id(
        build_id, parent=flake.key)
    self.assertEqual(flake_occurrence, fetched_flake_occurrence)
    self.assertTrue(fetched_flake_occurrence.time_detected)
