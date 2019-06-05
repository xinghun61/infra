# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittest for timestr module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import calendar
import datetime
import time
import unittest

from framework import timestr


class TimeStrTest(unittest.TestCase):
  """Unit tests for timestr routines."""

  def testFormatAbsoluteDate(self):
    now = datetime.datetime(2008, 1, 1)

    def GetDate(*args):
      date = datetime.datetime(*args)
      return timestr.FormatAbsoluteDate(
          calendar.timegm(date.utctimetuple()), clock=lambda: now)

    self.assertEquals(GetDate(2008, 1, 1), 'Today')
    self.assertEquals(GetDate(2007, 12, 31), 'Yesterday')
    self.assertEquals(GetDate(2007, 12, 30), 'Dec 30')
    self.assertEquals(GetDate(2007, 1, 1), 'Jan 2007')
    self.assertEquals(GetDate(2007, 1, 2), 'Jan 2007')
    self.assertEquals(GetDate(2007, 12, 31), 'Yesterday')
    self.assertEquals(GetDate(2006, 12, 31), 'Dec 2006')
    self.assertEquals(GetDate(2007, 7, 1), 'Jul 1')
    self.assertEquals(GetDate(2007, 6, 30), 'Jun 2007')
    self.assertEquals(GetDate(2008, 1, 3), 'Jan 2008')

    # Leap year fun
    now = datetime.datetime(2008, 3, 1)
    self.assertEquals(GetDate(2008, 2, 29), 'Yesterday')

    # Clock skew
    now = datetime.datetime(2008, 1, 1, 23, 59, 59)
    self.assertEquals(GetDate(2008, 1, 2), 'Today')
    now = datetime.datetime(2007, 12, 31, 23, 59, 59)
    self.assertEquals(GetDate(2008, 1, 1), 'Today')
    self.assertEquals(GetDate(2008, 1, 2), 'Jan 2008')

  def testFormatRelativeDate(self):
    now = time.mktime(datetime.datetime(2008, 1, 1).timetuple())

    def TestSecsAgo(secs_ago, expected, expected_days_only):
      test_time = now - secs_ago
      actual = timestr.FormatRelativeDate(
          test_time, clock=lambda: now)
      self.assertEquals(actual, expected)
      actual_days_only = timestr.FormatRelativeDate(
          test_time, clock=lambda: now, days_only=True)
      self.assertEquals(actual_days_only, expected_days_only)

    TestSecsAgo(10 * 24 * 60 * 60, '', '10 days ago')
    TestSecsAgo(5 * 24 * 60 * 60 - 1, '4 days ago', '4 days ago')
    TestSecsAgo(5 * 60 * 60 - 1, '4 hours ago', '')
    TestSecsAgo(5 * 60 - 1, '4 minutes ago', '')
    TestSecsAgo(2 * 60 - 1, '1 minute ago', '')
    TestSecsAgo(60 - 1, 'moments ago', '')
    TestSecsAgo(0, 'moments ago', '')
    TestSecsAgo(-10, 'moments ago', '')
    TestSecsAgo(-100, '', '')

  def testGetHumanScaleDate(self):
    """Tests GetHumanScaleDate()."""
    now = time.mktime(datetime.datetime(2008, 4, 10, 20, 50, 30).timetuple())

    def GetDate(*args):
      date = datetime.datetime(*args)
      timestamp = time.mktime(date.timetuple())
      return timestr.GetHumanScaleDate(timestamp, now=now)

    self.assertEquals(
        GetDate(2008, 4, 10, 15), ('Today', '5 hours ago'))
    self.assertEquals(
        GetDate(2008, 4, 10, 19, 55), ('Today', '55 min ago'))
    self.assertEquals(
        GetDate(2008, 4, 10, 20, 48, 35), ('Today', '1 min ago'))
    self.assertEquals(
        GetDate(2008, 4, 10, 20, 49, 35), ('Today', 'moments ago'))
    self.assertEquals(
        GetDate(2008, 4, 10, 20, 50, 55), ('Today', 'moments ago'))
    self.assertEquals(
        GetDate(2008, 4, 9, 15), ('Yesterday', '29 hours ago'))
    self.assertEquals(
        GetDate(2008, 4, 5, 15), ('Last 7 days', 'Apr 05, 2008'))
    self.assertEquals(
        GetDate(2008, 3, 22, 15), ('Last 30 days', 'Mar 22, 2008'))
    self.assertEquals(
        GetDate(2008, 1, 2, 15), ('Earlier this year', 'Jan 02, 2008'))
    self.assertEquals(
        GetDate(2007, 12, 31, 15), ('Before this year', 'Dec 31, 2007'))
    self.assertEquals(
        GetDate(2008, 4, 11, 20, 49, 35), ('Future', 'Later'))
