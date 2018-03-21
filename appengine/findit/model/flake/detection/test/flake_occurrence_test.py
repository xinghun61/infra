# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import mock

from gae_libs.testcase import TestCase

from model.flake.detection.flake import Flake
from model.flake.detection.flake_occurrence import FlakeOccurrence
from model.flake.detection.flake_occurrence import FlakeType


class FlakeOccurrenceTest(TestCase):

  def testGet(self):
    step_name = 's'
    test_name = 't'
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    build_id = 100
    time_reported = datetime.datetime(2018, 1, 1)
    flake_type = FlakeType.OUTRIGHT_FLAKE

    # Create the parent flake.
    flake = Flake.Create(step_name, test_name)
    flake.put()

    # Put the occurrence under it.
    occurrence = FlakeOccurrence(
        master_name=master_name,
        builder_name=builder_name,
        build_number=build_number,
        build_id=build_id,
        time_reported=time_reported,
        flake_type=flake_type,
        parent=flake.key)
    occurrence.put()

    self.assertEqual(occurrence,
                     FlakeOccurrence.Get(step_name, test_name, build_id))

  def testCreate(self):
    step_name = 's'
    test_name = 't'
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    build_id = 100
    time_reported = datetime.datetime(2018, 1, 1)
    flake_type = FlakeType.OUTRIGHT_FLAKE

    # Create the parent flake.
    flake = Flake.Create(step_name, test_name)
    flake.put()

    # Put the occurrence under it.
    occurrence = FlakeOccurrence.Create(
        step_name=step_name,
        test_name=test_name,
        master_name=master_name,
        builder_name=builder_name,
        build_number=build_number,
        build_id=build_id,
        time_reported=time_reported,
        flake_type=flake_type)
    occurrence.put()

    occurrences = FlakeOccurrence.query(
        FlakeOccurrence.build_id == build_id, ancestor=flake.key).fetch()
    self.assertEqual(1, len(occurrences))
    self.assertEqual(occurrence, occurrences[0])
