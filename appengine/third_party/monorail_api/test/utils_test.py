# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import unittest

from monorail_api.utils import parseDateTime


class UtilsTestCase(unittest.TestCase):
  def test_parses_date_with_microseconds(self):
    self.assertEquals(parseDateTime('2016-01-01T00:00:00.123456Z'),
                      datetime.datetime(2016, 1, 1, 0, 0, 0, 123456))

  def test_parses_date_without_microseconds(self):
    self.assertEquals(parseDateTime('2016-01-01T00:00:00'),
                      datetime.datetime(2016, 1, 1, 0, 0, 0))

  def test_none_date(self):
    self.assertIsNone(parseDateTime(None))
