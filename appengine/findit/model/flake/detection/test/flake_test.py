# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import mock

from gae_libs.testcase import TestCase

from model.flake.detection.flake import Flake
from model.flake.detection.flake_occurrence import FlakeOccurrence
from model.flake.detection.flake_occurrence import FlakeType


class FlakeTest(TestCase):

  def testGetId(self):
    step_name = 's'
    test_name = 't'
    flake_id = '{}/{}'.format(step_name, test_name)

    self.assertEqual(flake_id, Flake.GetId(step_name, test_name))

  def testGet(self):
    step_name = 's'
    test_name = 't'

    # Create the parent flake.
    flake = Flake(
        step_name=step_name,
        test_name=test_name,
        id='{}/{}'.format(step_name, test_name))
    flake.put()

    self.assertEqual(Flake.Get(step_name, test_name), flake)

  def testCreate(self):
    step_name = 's'
    test_name = 't'

    # Create the parent flake.
    flake = Flake.Create(step_name, test_name)
    flake.put()

    flakes = Flake.query(Flake.step_name == step_name,
                         Flake.test_name == test_name).fetch()
    self.assertEqual(1, len(flakes))
    self.assertEqual(flake, flakes[0])
