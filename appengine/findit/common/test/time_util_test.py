# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from common import time_util
from datetime import datetime
from datetime import timedelta

import pytz


class DiffTest(unittest.TestCase):
  def testRemoveMicrosecondsFromDelta(self):
    date1 = datetime(2016, 5, 1, 1, 1, 1, 1)
    date2 = datetime(2016, 5, 1, 1, 1, 1, 2)
    delta = date2 - date1

    self.assertEqual(
        time_util.RemoveMicrosecondsFromDelta(delta).microseconds,
        0)

  def testFormatTimedelta(self):
    self.assertIsNone(time_util.FormatTimedelta(None))
    self.assertEqual(time_util.FormatTimedelta(timedelta(0, 1)),
                     '00:00:01')
    self.assertEqual(time_util.FormatTimedelta(timedelta(0, 60)),
                     '00:01:00')
    self.assertEqual(time_util.FormatTimedelta(timedelta(0, 3600)),
                     '01:00:00')
    self.assertEqual(time_util.FormatTimedelta(timedelta(0, 0, 1)),
                     '00:00:00')

  def testFormatDatetime(self):
    self.assertIsNone(time_util.FormatDatetime(None))
    self.assertEqual(
        time_util.FormatDatetime(datetime(2016, 1, 2, 1, 2, 3)),
        '2016-01-02 01:02:03 UTC')

  def testGetDateTimeInTimezone(self):
    utc_datetime = datetime(2016, 9, 27, 20, 46, 18, 1, pytz.utc)
    result_pst_datetime = time_util.GetDatetimeInTimezone(
        'US/Pacific', utc_datetime)
    expected_pst_datetime = datetime(2016, 9, 27, 13, 46, 18, 1,
                                     pytz.timezone('US/Pacific'))
    self.assertEqual(result_pst_datetime.date(), expected_pst_datetime.date())
    self.assertEqual(result_pst_datetime.time(), expected_pst_datetime.time())
