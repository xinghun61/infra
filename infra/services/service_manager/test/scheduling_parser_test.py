# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import unittest

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
  def test_minute_period(self):
    job_times = scheduling_parser.parse('every 5m')
    self.assertIsInstance(job_times, scheduling_parser.JobTimes)
    self.assertEqual(job_times.period, 5)
    self.assertEqual(job_times.offsets, [0])
    self.assertIsInstance(job_times.jitter, int)

  def test_minute_period_with_offset(self):
    job_times = scheduling_parser.parse('every 5m @ 1m')
    self.assertIsInstance(job_times, scheduling_parser.JobTimes)
    self.assertEqual(job_times.period, 5)
    self.assertEqual(job_times.offsets, [1])
    self.assertIsInstance(job_times.jitter, int)

  def test_one_week_period_with_multiple_offsets(self):
    job_times = scheduling_parser.parse('every 1w @ 1d, 2d 5m')
    self.assertIsInstance(job_times, scheduling_parser.JobTimes)
    self.assertEqual(job_times.period, 7*24*60)
    self.assertEqual(job_times.offsets, [24*60, 2*24*60 + 5])
    self.assertIsInstance(job_times.jitter, int)

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
    self.assertEqual(job_times.offsets, [1])
    self.assertIsInstance(job_times.jitter, int)

  # TODO(pgervais): test jitter
