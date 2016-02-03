# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import unittest

from model.flake import Flake
from status import util


class UtilTestCase(unittest.TestCase):
  def test_adds_occurrence_time_to_flake(self):
    flake = Flake(name='foo.bar', last_time_seen=datetime.datetime.min)

    now = datetime.datetime.utcnow()
    util.add_occurrence_time_to_flake(flake, now)

    self.assertEqual(flake.last_time_seen, now)
    self.assertEqual(flake.count_hour, 1)
    self.assertEqual(flake.count_day, 1)
    self.assertEqual(flake.count_week, 1)
    self.assertEqual(flake.count_month, 1)
    self.assertEqual(flake.last_hour, True)
    self.assertEqual(flake.last_day, True)
    self.assertEqual(flake.last_week, True)
    self.assertEqual(flake.last_month, True)

  def test_does_not_modify_flake(self):
    little_time_ago = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
    flake = Flake(name='foo.bar', last_time_seen=little_time_ago)

    long_time_ago = datetime.datetime.utcnow() - datetime.timedelta(days=60)
    util.add_occurrence_time_to_flake(flake, long_time_ago)

    self.assertEqual(flake.last_time_seen, little_time_ago)
    self.assertEqual(flake.count_hour, 0)
    self.assertEqual(flake.count_day, 0)
    self.assertEqual(flake.count_week, 0)
    self.assertEqual(flake.count_month, 0)
    self.assertEqual(flake.last_hour, False)
    self.assertEqual(flake.last_day, False)
    self.assertEqual(flake.last_week, False)
    self.assertEqual(flake.last_month, False)
