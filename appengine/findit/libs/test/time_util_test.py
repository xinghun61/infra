# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import unittest

from libs import time_util
from datetime import datetime
from datetime import timedelta


class TimeUtilTest(unittest.TestCase):

  def testConvertToTimestamp(self):
    self.assertEqual(
        1490918400,
        time_util.ConvertToTimestamp(datetime(2017, 03, 31, 0, 0, 0)))

  def testRemoveMicrosecondsFromDelta(self):
    date1 = datetime(2016, 5, 1, 1, 1, 1, 1)
    date2 = datetime(2016, 5, 1, 1, 1, 1, 2)
    delta = date2 - date1

    self.assertEqual(
        time_util.RemoveMicrosecondsFromDelta(delta).microseconds,
        0)

  def testFormatTimedelta(self):
    self.assertIsNone(time_util.FormatTimedelta(None))
    self.assertEqual(time_util.FormatTimedelta(timedelta(0, 0)),
                     '00:00:00')
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

  @mock.patch('libs.time_util.pytz')
  def testGetDateTimeInTimezoneWithGivenDatetime(self, mocked_pytz_module):
    mocked_datetime = mock.MagicMock()
    mocked_datetime.astimezone.return_value = 'expected'

    self.assertEqual('expected',
                     time_util.GetDatetimeInTimezone('PST', mocked_datetime))
    mocked_pytz_module.timezone.assert_called_with('PST')

  def testFormatDuration(self):
    date1 = datetime(2016, 5, 1, 1, 1, 1)
    date2 = datetime(2016, 5, 1, 1, 2, 1)
    self.assertIsNone(time_util.FormatDuration(None, date1))
    self.assertIsNone(time_util.FormatDuration(date1, None))
    self.assertEqual('00:01:00', time_util.FormatDuration(date1, date2))

  def testMicrosecondsToDatetime(self):
    self.assertEqual(
        datetime(2016, 2, 1, 22, 59, 34),
        time_util.MicrosecondsToDatetime(1454367574000000))
    self.assertIsNone(time_util.MicrosecondsToDatetime(None))

  def testTimeZoneInfo(self):
    naive_time = datetime(2016, 9, 1, 10, 0, 0)

    tz = time_util.TimeZoneInfo('+0800')
    self.assertEqual(tz.LocalToUTC(naive_time), datetime(2016, 9, 1, 2, 0, 0))

    tz_negative = time_util.TimeZoneInfo('-0700')
    self.assertEqual(tz_negative.LocalToUTC(naive_time),
                     datetime(2016, 9, 1, 17, 0, 0))

  def testDatetimeFromString(self):
    self.assertEqual(None, time_util.DatetimeFromString('None'))
    self.assertEqual(None, time_util.DatetimeFromString(None))
    iso_time_str = '2016-01-02T01:02:03.123456'
    iso_time_datetime = time_util.DatetimeFromString(iso_time_str)
    # Check that our function reverses datetime.isoformat
    self.assertEqual(iso_time_datetime.isoformat(), iso_time_str)
    self.assertEqual(iso_time_datetime, time_util.DatetimeFromString(
        iso_time_datetime))
    with self.assertRaises(ValueError):
      time_util.DatetimeFromString('Yesterday, at 5 o\'clock')

  def testSecondsToHMS(self):
    self.assertIsNone(time_util.SecondsToHMS(None))
    self.assertEqual('00:00:00', time_util.SecondsToHMS(0))
    self.assertEqual('00:00:01', time_util.SecondsToHMS(1))
    self.assertEqual('00:01:01', time_util.SecondsToHMS(61))

  def testGetMostRecentUTCMidnight(self):
    self.assertEqual(
        datetime,
        type(time_util.GetMostRecentUTCMidnight()))

  @mock.patch.object(time_util, 'GetMostRecentUTCMidnight',
                     return_value=datetime(2017, 3, 19, 0, 0, 0))
  def testGetStartEndDates(self, _):
    self.assertEqual(
        (datetime(2017, 3, 18, 0, 0, 0), datetime(2017, 3, 20, 0, 0, 0)),
        time_util.GetStartEndDates(None, None))
    self.assertEqual(
        (None, datetime(2017, 3, 20, 0, 0, 0)),
        time_util.GetStartEndDates(None, '2017-03-19'))
    self.assertEqual(
        (datetime(2017, 3, 18, 0, 0, 0), datetime(2017, 3, 20, 0, 0, 0)),
        time_util.GetStartEndDates('2017-03-18', None))
    self.assertEqual(
        (datetime(2017, 3, 15, 0, 0, 0), datetime(2017, 3, 16, 0, 0, 0)),
        time_util.GetStartEndDates('2017-03-15', '2017-03-16'))
