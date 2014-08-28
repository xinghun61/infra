# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Converts between UTC and Pacific Time.

From https://developers.google.com/appengine/docs/python/datastore/
     typesandpropertyclasses?csw=1#datetime
TODO(sullivan): There has to be a simpler way. Look into pytz.
"""
import datetime
import time


# Unused argument - pylint: disable=W0613


class UtcTzinfo(datetime.tzinfo):

  def utcoffset(self, dt):
    return datetime.timedelta(0)

  def dst(self, dt):
    return datetime.timedelta(0)

  def tzname(self, dt):
    return 'UTC'

  # pylint: disable=R0201
  def olsen_name(self):
    return 'UTC'


class PacificTzinfo(datetime.tzinfo):
  """Implementation of the Pacific timezone."""

  def utcoffset(self, dt):
    return datetime.timedelta(hours=-8) + self.dst(dt)

  # pylint: disable=R0201
  def _FirstSunday(self, dt):
    """First Sunday on or after dt."""
    return dt + datetime.timedelta(days=(6-dt.weekday()))

  def dst(self, dt):
    # 2 am on the second Sunday in March
    dst_start = self._FirstSunday(datetime.datetime(dt.year, 3, 8, 2))
    # 1 am on the first Sunday in November
    dst_end = self._FirstSunday(datetime.datetime(dt.year, 11, 1, 1))

    if dst_start <= dt.replace(tzinfo=None) < dst_end:
      return datetime.timedelta(hours=1)
    else:
      return datetime.timedelta(hours=0)

  def tzname(self, dt):
    if self.dst(dt) == datetime.timedelta(hours=0):
      return 'PST'
    else:
      return 'PDT'


def UtcToPacific(utc_time):
  return datetime.datetime.fromtimestamp(time.mktime(utc_time.timetuple()),
                                         PacificTzinfo())


def PacificToUtc(pacific_time):
  return datetime.datetime.fromtimestamp(time.mktime(pacific_time.timetuple()),
                                         UtcTzinfo())
