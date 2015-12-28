# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import unittest

import pytz

from infra.services.service_manager import scheduling_parser


class TestParseTimeSpec(unittest.TestCase):
  # Specify m/h/d/w
  def test_minutes(self):
    ts = scheduling_parser.parse_time_spec('1m')
    self.assertEqual(ts.value, 1)
    self.assertEqual(ts.unit, 'm')
    self.assertEqual(ts.minutes, 1)

  def test_hours(self):
    ts = scheduling_parser.parse_time_spec('2h')
    self.assertEqual(ts.value, 2)
    self.assertEqual(ts.unit, 'h')
    self.assertEqual(ts.minutes, 2*60)

  def test_check_value_hours(self):
    ts = scheduling_parser.parse_time_spec('25h')
    self.assertEqual(ts.value, 25)
    self.assertEqual(ts.unit, 'h')
    self.assertEqual(ts.minutes, 25*60)

    with self.assertRaises(ValueError):
      scheduling_parser.parse_time_spec('25h', check_value=True)

  def test_check_value_minutes(self):
    ts = scheduling_parser.parse_time_spec('75m')
    self.assertEqual(ts.value, 75)
    self.assertEqual(ts.unit, 'm')
    self.assertEqual(ts.minutes, 75)

    with self.assertRaises(ValueError):
      scheduling_parser.parse_time_spec('75m', check_value=True)

  def test_day(self):
    ts = scheduling_parser.parse_time_spec('3d')
    self.assertEqual(ts.value, 3)
    self.assertEqual(ts.unit, 'd')
    self.assertEqual(ts.minutes, 3*24*60)

  def test_week(self):
    ts = scheduling_parser.parse_time_spec('4w')
    self.assertEqual(ts.value, 4)
    self.assertEqual(ts.unit, 'w')
    self.assertEqual(ts.minutes, 4*7*24*60)

  def test_invalid_unit(self):
    with self.assertRaises(ValueError):
      scheduling_parser.parse_time_spec('4t')

  # Specify time as hh:mm
  def test_utc_time(self):
    ts = scheduling_parser.parse_time_spec('10:20')
    self.assertEqual(ts.value, 10*60 + 20)
    self.assertEqual(ts.unit, 'hm')
    self.assertEqual(ts.minutes, 10*60 + 20)

  def test_utc_time_invalid_minutes(self):
    with self.assertRaises(ValueError):
      scheduling_parser.parse_time_spec('10:80')

  def test_utc_time_invalid_hours(self):
    with self.assertRaises(ValueError):
      scheduling_parser.parse_time_spec('25:00')

  # Specify time as a day name
  def test_day_name(self):
    ts = scheduling_parser.parse_time_spec('tue')
    self.assertEqual(ts.value, 1)
    self.assertEqual(ts.unit, 'd')
    self.assertEqual(ts.minutes, 24*60)

  def test_day_name_capital(self):
    # capital letters are not supported.
    with self.assertRaises(ValueError):
      scheduling_parser.parse_time_spec('TUE')

  # More error cases
  def test_invalid_input(self):
    with self.assertRaises(ValueError):
      scheduling_parser.parse_time_spec('garbage')


class TestParseTimeOffset(unittest.TestCase):
  def test_day_name(self):
    cases = ("tue 14:30", "tue 14h 30m", "1d 14:30", "1d 14h 30m")
    for case in cases:
      minutes = scheduling_parser.parse_time_offset(case)
      self.assertEqual(minutes, 2310)

  def test_day_name_default_values(self):
    cases = ("mon", "mon 00:00", "mon 0m")
    for case in cases:
      minutes = scheduling_parser.parse_time_offset(case)
      self.assertEqual(minutes, 0)

  def test_utc_time(self):
    cases = ("14:30", "14h 30m", "870m")
    for case in cases:
      minutes = scheduling_parser.parse_time_offset(case)
      self.assertEqual(minutes, 870)

  def test_invalid_strings(self):
    cases = ("14:30 2h", "1d 27h", "2h 250m", "20m 2h", "10:30 mon")
    for case in cases:
      with self.assertRaises(ValueError):
        print case  # cannot pass a msg argument to assertRaises
        scheduling_parser.parse_time_offset(case)


class TestParseTimeOffsets(unittest.TestCase):
  def test_empty_string(self):
    offsets = scheduling_parser.parse_time_offsets('')
    self.assertEqual(offsets, [])

  def test_one_offset(self):
    offsets = scheduling_parser.parse_time_offsets('5m')
    self.assertEqual(offsets, [5])

  def test_two_offsets(self):
    offsets = scheduling_parser.parse_time_offsets('5m, 1d 2h')
    self.assertEqual(offsets, [5, 24*60 + 2*60])

class TestParseOnePeriod(unittest.TestCase):
  # TODO(pgervais): test jitter
  def test_minute_period(self):
    job_times = scheduling_parser.parse('every 5m')
    self.assertIsInstance(job_times, scheduling_parser.JobTimes)
    self.assertEqual(job_times.period, 5)
    self.assertEqual(job_times.offsets_s, [0])

  def test_minute_period_with_offset(self):
    job_times = scheduling_parser.parse('every 5m @ 1m')
    self.assertIsInstance(job_times, scheduling_parser.JobTimes)
    self.assertEqual(job_times.period, 5)
    self.assertEqual(job_times.offsets_s, [60])

  def test_one_week_period_with_multiple_offsets(self):
    job_times = scheduling_parser.parse('every 1w @ 1d, 2d 5m')
    self.assertIsInstance(job_times, scheduling_parser.JobTimes)
    self.assertEqual(job_times.period, 7*24*60)
    self.assertEqual(job_times.offsets_s, [24*60*60, 2*24*60*60 + 5*60])

  def test_empty_string(self):
    with self.assertRaises(ValueError):
      scheduling_parser.parse('')

  def test_invalid_beginning(self):
    with self.assertRaises(ValueError):
      scheduling_parser.parse('never 5m')

  def test_several_at_signs(self):
    with self.assertRaises(ValueError):
      scheduling_parser.parse('every 5m @ 1m @ 5m')

  def test_smoke_several_every_clauses(self):
    job_times = scheduling_parser.parse('every 5m @ 1m every 1w @ mon')
    self.assertIsInstance(job_times, scheduling_parser.JobTimes)
    self.assertEqual(job_times.period, 5)
    self.assertEqual(job_times.offsets_s, [60])


class TestJobTimesOneOffset(unittest.TestCase):
  def test_minute_period(self):
    job_times = scheduling_parser.JobTimes(5, [0], 0)

    dts = job_times.next_times(datetime.datetime(2015, 12, 10, 0, 0, 1), 5)
    self.assertEqual(
      dts,
      [datetime.datetime(2015, 12, 10 , 0, 5, 0, tzinfo=pytz.UTC),
       datetime.datetime(2015, 12, 10 , 0, 10, 0, tzinfo=pytz.UTC),
       datetime.datetime(2015, 12, 10 , 0, 15, 0, tzinfo=pytz.UTC),
       datetime.datetime(2015, 12, 10 , 0, 20, 0, tzinfo=pytz.UTC),
       datetime.datetime(2015, 12, 10 , 0, 25, 0, tzinfo=pytz.UTC)]
    )

  def test_minute_period_with_negative_offset(self):
    job_times = scheduling_parser.JobTimes(5, [-1], 0)

    dts = job_times.next_times(datetime.datetime(2015, 12, 10, 0, 0, 1), 5)
    self.assertEqual(
      dts,
      [datetime.datetime(2015, 12, 10 , 0, 4, 0, tzinfo=pytz.UTC),
       datetime.datetime(2015, 12, 10 , 0, 9, 0, tzinfo=pytz.UTC),
       datetime.datetime(2015, 12, 10 , 0, 14, 0, tzinfo=pytz.UTC),
       datetime.datetime(2015, 12, 10 , 0, 19, 0, tzinfo=pytz.UTC),
       datetime.datetime(2015, 12, 10 , 0, 24, 0, tzinfo=pytz.UTC)]
    )

  def test_minute_period_with_offset(self):
    job_times = scheduling_parser.JobTimes(5, [1], 0)

    dts = job_times.next_times(datetime.datetime(2015, 12, 10, 0, 0, 1), 5)
    self.assertEqual(
      dts,
      [datetime.datetime(2015, 12, 10 , 0, 1, 0, tzinfo=pytz.UTC),
       datetime.datetime(2015, 12, 10 , 0, 6, 0, tzinfo=pytz.UTC),
       datetime.datetime(2015, 12, 10 , 0, 11, 0, tzinfo=pytz.UTC),
       datetime.datetime(2015, 12, 10 , 0, 16, 0, tzinfo=pytz.UTC),
       datetime.datetime(2015, 12, 10 , 0, 21, 0, tzinfo=pytz.UTC)]
    )

  def test_minute_period_with_offset_and_jitter(self):
    job_times = scheduling_parser.JobTimes(5, [1], 2)

    dts = job_times.next_times(datetime.datetime(2015, 12, 10, 0, 0, 1), 5)
    self.assertEqual(
      dts,
      [datetime.datetime(2015, 12, 10 , 0, 1, 2, tzinfo=pytz.UTC),
       datetime.datetime(2015, 12, 10 , 0, 6, 2, tzinfo=pytz.UTC),
       datetime.datetime(2015, 12, 10 , 0, 11, 2, tzinfo=pytz.UTC),
       datetime.datetime(2015, 12, 10 , 0, 16, 2, tzinfo=pytz.UTC),
       datetime.datetime(2015, 12, 10 , 0, 21, 2, tzinfo=pytz.UTC)]
    )

  def test_minute_period_with_jitter(self):
    job_times = scheduling_parser.JobTimes(5, [], 3)

    dts = job_times.next_times(datetime.datetime(2015, 12, 10, 0, 0, 1), 5)
    self.assertEqual(
      dts,
      [datetime.datetime(2015, 12, 10 , 0, 0, 3, tzinfo=pytz.UTC),
       datetime.datetime(2015, 12, 10 , 0, 5, 3, tzinfo=pytz.UTC),
       datetime.datetime(2015, 12, 10 , 0, 10, 3, tzinfo=pytz.UTC),
       datetime.datetime(2015, 12, 10 , 0, 15, 3, tzinfo=pytz.UTC),
       datetime.datetime(2015, 12, 10 , 0, 20, 3, tzinfo=pytz.UTC)]
    )

  def test_one_week_period(self):
    job_times = scheduling_parser.JobTimes(7*24*60, [0], 0)
    dts = job_times.next_times(datetime.datetime(2015, 12, 10, 0, 0, 1), 5)
    self.assertEqual(
      dts,
      [datetime.datetime(2015, 12, 14 , 0, 0, 0, tzinfo=pytz.UTC),
       datetime.datetime(2015, 12, 21 , 0, 0, 0, tzinfo=pytz.UTC),
       datetime.datetime(2015, 12, 28 , 0, 0, 0, tzinfo=pytz.UTC),
       datetime.datetime(2016,  1,  4 , 0, 0, 0, tzinfo=pytz.UTC),
       datetime.datetime(2016,  1, 11 , 0, 0, 0, tzinfo=pytz.UTC)]
    )

  def test_two_week_period(self):
    job_times = scheduling_parser.JobTimes(2*7*24*60, [0], 0)
    dts = job_times.next_times(datetime.datetime(2015, 12, 10, 0, 0, 1), 5)
    self.assertEqual(dts,
                     [datetime.datetime(2015, 12, 21, 0, 0, 0, tzinfo=pytz.UTC),
                      datetime.datetime(2016,  1,  4, 0, 0, 0, tzinfo=pytz.UTC),
                      datetime.datetime(2016,  1, 18, 0, 0, 0, tzinfo=pytz.UTC),
                      datetime.datetime(2016,  2,  1, 0, 0, 0, tzinfo=pytz.UTC),
                      datetime.datetime(2016,  2, 15, 0, 0, 0, tzinfo=pytz.UTC)]
                   )


class TestJobTimesMultipleOffsets(unittest.TestCase):
  def test_two_week_period_mon_tue(self):
    job_times = scheduling_parser.JobTimes(2*7*24*60, [0, 24*60], 0)
    dts = job_times.next_times(datetime.datetime(2015, 12, 10, 0, 0, 1), 5)
    self.assertEqual(dts,
                     [datetime.datetime(2015, 12, 21, 0, 0, 0, tzinfo=pytz.UTC),
                      datetime.datetime(2015, 12, 22, 0, 0, 0, tzinfo=pytz.UTC),
                      datetime.datetime(2016,  1,  4, 0, 0, 0, tzinfo=pytz.UTC),
                      datetime.datetime(2016,  1,  5, 0, 0, 0, tzinfo=pytz.UTC),
                      datetime.datetime(2016,  1, 18, 0, 0, 0, tzinfo=pytz.UTC)]
                   )

  def test_one_hour_period_2m_minus3m(self):
    job_times = scheduling_parser.JobTimes(60, [2, -3], 0)
    dts = job_times.next_times(datetime.datetime(2015, 12, 10, 0, 0, 1), 5)
    self.assertEqual(
      dts,
      [datetime.datetime(2015, 12, 10, 0,  2, 0, tzinfo=pytz.UTC),
       datetime.datetime(2015, 12, 10, 0, 57, 0, tzinfo=pytz.UTC),
       datetime.datetime(2015, 12, 10, 1,  2, 0, tzinfo=pytz.UTC),
       datetime.datetime(2015, 12, 10, 1, 57, 0, tzinfo=pytz.UTC),
       datetime.datetime(2015, 12, 10, 2,  2, 0, tzinfo=pytz.UTC),
     ]
    )


class TestSnappedDatetime(unittest.TestCase):
  def test_invalid_timezone(self):
    dt = datetime.datetime(
      2015, 1, 1).replace(tzinfo=pytz.timezone('US/Pacific'))
    with self.assertRaises(ValueError):
      scheduling_parser.snapped_datetime(dt, 1, 0)

  def test_minute_snap_already_snapped(self):
    # already matches period and offset
    dt = datetime.datetime(2015, 1, 12, 5, 2, 0)
    # snap to even minutes
    snapped = scheduling_parser.snapped_datetime(dt, 2, 0)
    self.assertEqual(snapped,
                     datetime.datetime(2015, 1, 12, 5, 0, 0, tzinfo=pytz.UTC))
    self.assertLess(snapped, dt.replace(tzinfo=pytz.UTC))

  def test_offset_larger_than_period(self):
    dt = datetime.datetime(2015, 1, 12, 5, 2, 0)
    # offset is -1:10 with period 1m
    snapped = scheduling_parser.snapped_datetime(dt, 1, -70)
    self.assertLess(snapped, dt.replace(tzinfo=pytz.UTC))
    self.assertEqual(snapped,
                     datetime.datetime(2015, 1, 12, 5, 1, 50, tzinfo=pytz.UTC))

  def test_minute_snap(self):
    dt = datetime.datetime(2015, 1, 12, 5, 2, 3)
    # snap to even minutes
    snapped = scheduling_parser.snapped_datetime(dt, 2, 0)
    self.assertLess(snapped, dt.replace(tzinfo=pytz.UTC))
    self.assertEqual(snapped,
                     datetime.datetime(2015, 1, 12, 5, 2, 0, tzinfo=pytz.UTC))

  def test_hour_snap(self):
    dt = datetime.datetime(2015, 1, 12, 5, 2, 3)
    # snap to beginning of hour
    snapped = scheduling_parser.snapped_datetime(dt, 60, 0)
    self.assertLess(snapped, dt.replace(tzinfo=pytz.UTC))
    self.assertEqual(snapped,
                     datetime.datetime(2015, 1, 12, 5, 0, 0, tzinfo=pytz.UTC))

  def test_hour_snap_with_offset(self):
    dt = datetime.datetime(2015, 1, 12, 5, 2, 3)
    # snap to beginning of even hours + 3 seconds
    snapped = scheduling_parser.snapped_datetime(dt, 2*60, 3)
    self.assertEqual(snapped,
                     datetime.datetime(2015, 1, 12, 4, 0, 3, tzinfo=pytz.UTC))
    self.assertLess(snapped, dt.replace(tzinfo=pytz.UTC))

  def test_hour_snap_with_negative_offset(self):
    dt = datetime.datetime(2015, 1, 12, 5, 2, 3)
    # snap to 3 seconds before the beginning of even hours
    snapped = scheduling_parser.snapped_datetime(dt, 2*60, -3)
    self.assertLess(snapped, dt.replace(tzinfo=pytz.UTC))
    self.assertEqual(snapped,
                     datetime.datetime(2015, 1, 12, 3, 59, 57, tzinfo=pytz.UTC))

  def test_day_snap(self):
    dt = datetime.datetime(2015, 1, 12, 5, 2, 3)
    snapped = scheduling_parser.snapped_datetime(dt, 24*60, 0)
    self.assertLess(snapped, dt.replace(tzinfo=pytz.UTC))
    self.assertEqual(snapped,
                     datetime.datetime(2015, 1, 12, 0, 0, 0, tzinfo=pytz.UTC))

  def test_day_of_week_snap_mon(self):
    # EPOCH starts with a Monday so offset == 0 means Monday
    # offset == 24*60*60 means Tuesday, etc.
    dt = datetime.datetime(2015, 12, 23, 5, 2, 3)  # 2015-12-23: Wed
    snapped = scheduling_parser.snapped_datetime(dt, 7*24*60, 0)
    self.assertLess(snapped, dt.replace(tzinfo=pytz.UTC))
    self.assertEqual(snapped,
                     datetime.datetime(2015, 12, 21, 0, 0, 0, tzinfo=pytz.UTC))

  def test_day_of_week_snap_tue(self):
    dt = datetime.datetime(2015, 12, 23, 5, 2, 3)  # 2015-12-23: Wed
    # snap to Tue 00:00:00
    snapped = scheduling_parser.snapped_datetime(dt, 7*24*60, 24*60*60)
    self.assertEqual(snapped,
                     datetime.datetime(2015, 12, 22, 0, 0, 0, tzinfo=pytz.UTC))
    self.assertLess(snapped, dt.replace(tzinfo=pytz.UTC))

  def test_day_of_week_snap_wed_0304(self):
    dt = datetime.datetime(2015, 12, 23, 5, 2, 3)  # 2015-12-23: Wed
    # snap to Wed 02:03:04
    snapped = scheduling_parser.snapped_datetime(
      dt, 7*24*60, 2*24*60*60 + 2*60*60 + 3*60 + 4)
    self.assertLess(snapped, dt.replace(tzinfo=pytz.UTC))
    self.assertEqual(
      snapped,
      datetime.datetime(2015, 12, 23, 02, 03, 04, tzinfo=pytz.UTC))
