# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from gae_libs.testcase import TestCase
from model.flake.detection.flake import Flake
from model.flake.detection.flake_occurrence import BuildConfiguration
from model.flake.detection.flake_occurrence import CQFalseRejectionFlakeOccurrence  # pylint: disable=line-too-long


class CQFalseRejectionFlakeOccurrenceTest(TestCase):

  def testGetId(self):
    step_name = 'step'
    test_name = 'test'
    build_id = 123
    self.assertEqual(
        '123@step@test',
        CQFalseRejectionFlakeOccurrence.GetId(
            build_id=build_id, step_name=step_name, test_name=test_name))

  def testGet(self):
    luci_project = 'chromium'
    step_name = 'step'
    test_name = 'test'

    # Create parent Flake entity.
    normalized_step_name = Flake.NormalizeStepName(step_name)
    normalized_test_name = Flake.NormalizeTestName(test_name)
    flake = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name)
    flake.put()

    # Create the build configuration.
    luci_bucket = 'try'
    luci_builder = 'luci builder'
    legacy_master_name = 'buildbot master'
    build_configuration = BuildConfiguration(
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder=luci_builder,
        legacy_master_name=legacy_master_name)

    # Create a flake occurrence that is associated with the Flake entity and the
    # build configuration.
    build_id = 123
    reference_succeeded_build_id = 456
    time_happened = datetime.datetime(2018, 1, 1)
    flake_occurrence = CQFalseRejectionFlakeOccurrence(
        build_id=build_id,
        step_name=step_name,
        test_name=test_name,
        build_configuration=build_configuration,
        reference_succeeded_build_id=reference_succeeded_build_id,
        time_happened=time_happened,
        id=CQFalseRejectionFlakeOccurrence.GetId(build_id, step_name,
                                                 test_name),
        parent=flake.key)
    flake_occurrence.put()

    self.assertEqual(
        flake_occurrence,
        CQFalseRejectionFlakeOccurrence.Get(
            build_id=build_id,
            step_name=step_name,
            test_name=test_name,
            parent_flake_key=flake.key))

  def testCreate(self):
    luci_project = 'chromium'
    step_name = 'step'
    test_name = 'test'

    normalized_step_name = Flake.NormalizeStepName(step_name)
    normalized_test_name = Flake.NormalizeTestName(test_name)
    flake = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name)
    flake.put()

    build_id = 123
    luci_bucket = 'try'
    luci_builder = 'luci builder'
    legacy_master_name = 'buildbot master'
    reference_succeeded_build_id = 456
    time_happened = datetime.datetime(2018, 1, 1)

    flake_occurrence = CQFalseRejectionFlakeOccurrence.Create(
        build_id=build_id,
        step_name=step_name,
        test_name=test_name,
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder=luci_builder,
        legacy_master_name=legacy_master_name,
        reference_succeeded_build_id=reference_succeeded_build_id,
        time_happened=time_happened,
        parent_flake_key=flake.key)
    flake_occurrence.put()

    fetched_flake_occurrence = CQFalseRejectionFlakeOccurrence.Get(
        build_id, step_name, test_name, parent_flake_key=flake.key)
    self.assertEqual(flake_occurrence, fetched_flake_occurrence)
    self.assertTrue(fetched_flake_occurrence.time_detected)
