# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import calendar
from datetime import datetime
from datetime import time
from datetime import timedelta


def GetPSTNow():
  # For simplicity, assume PST is UTC - 8 hours.
  return GetUTCNow() - timedelta(hours=8)


def ConvertPSTToUTC(pst_datetime):
  # For simplicity, assume UTC is PST + 8 hours.
  return pst_datetime + timedelta(hours=8)


def GetUTCNow():  # pragma: no cover.
  """Returns the datetime.utcnow. This is to mock for testing."""
  return datetime.utcnow()


def ConvertToTimestamp(date_time):
  """Returns the given data time as a time stamp."""
  return calendar.timegm(date_time.timetuple())


def GetUTCNowTimestamp():  # pragma: no cover.
  """Returns the timestamp for datetime.utcnow. This is to mock for testing."""
  return ConvertToTimestamp(GetUTCNow())


def RemoveMicrosecondsFromDelta(delta):
  """Returns a timedelta object without microseconds based on delta."""
  return delta - timedelta(microseconds=delta.microseconds)


def FormatTimedelta(delta):
  """Returns a string representing the given time delta."""
  if delta is None:
    return None
  hours, remainder = divmod(delta.total_seconds(), 3600)
  minutes, seconds = divmod(remainder, 60)
  return '%02d:%02d:%02d' % (hours, minutes, seconds)


def FormatDatetime(date):
  """Returns a string representing the given UTC datetime."""
  if not date:
    return None
  else:
    return date.strftime('%Y-%m-%d %H:%M:%S UTC')


def DatetimeFromString(date):
  """Parses a datetime from a serialized string."""
  if date == 'None':
    return None
  if not date or isinstance(date, datetime):
    return date
  valid_formats = [
      '%Y-%m-%d %H:%M:%S.%f000',
      '%Y-%m-%d %H:%M:%S.%f',
      '%Y-%m-%d %H:%M:%S',
      '%Y-%m-%dT%H:%M:%S.%f',
      '%Y-%m-%dT%H:%M:%S',
      '%Y-%m-%d',
  ]
  for format_str in valid_formats:
    try:
      return datetime.strptime(date, format_str)
    except ValueError:
      pass
  raise ValueError('%s is not in a known datetime format' % date)


def FormatDuration(datetime_start, datetime_end):
  """Returns a string representing the given time duration or None."""
  if not datetime_start or not datetime_end:
    return None
  return FormatTimedelta(datetime_end - datetime_start)


def MicrosecondsToDatetime(microseconds):
  """Returns a datetime given the number of microseconds, or None."""
  if microseconds:
    return datetime.utcfromtimestamp(float(microseconds) / 1000000)
  return None


def SecondsToHMS(seconds):
  """Converts seconds to HH:MM:SS as a string."""
  if seconds is not None:
    return FormatTimedelta(timedelta(seconds=seconds))
  return None


def GetMostRecentUTCMidnight():
  return datetime.combine(GetUTCNow(), time.min)


def GetStartEndDates(start, end, default_start=None, default_end=None):
  """Gets start and end dates for handlers that specify date ranges."""
  midnight_today = GetMostRecentUTCMidnight()
  midnight_yesterday = midnight_today - timedelta(days=1)
  midnight_tomorrow = midnight_today + timedelta(days=1)

  if not start and not end:
    # If neither start nor end specified, range is everything since yesterday.
    # If ``default_start`` and ``default_end`` are specified, the range is from
    # ``default_start`` to ``default_end``.
    return default_start or midnight_yesterday, default_end or midnight_tomorrow
  elif not start and end:
    # If only end is specified, range is everything up until then. If
    # ``default_start`` is specified, range is since ``default_start`` until
    # ``end``.
    return default_start or None, midnight_tomorrow
  elif start and not end:
    # If only start is specified, range is everything since then. If
    # ``default_end`` is specified, the range is everything since ``start``
    # until ``default_end``.
    return DatetimeFromString(start), default_end or midnight_tomorrow

  # Both start and end are specified, range is everything in between.
  return (DatetimeFromString(start), DatetimeFromString(end))


class TimeZoneInfo(object):
  """Gets time zone info from string like: +0800.

  The string is HHMM offset relative to UTC timezone.
  """

  def __init__(self, offset_str):
    self._utcoffset = self.GetOffsetFromStr(offset_str)

  def GetOffsetFromStr(self, offset_str):
    offset = int(offset_str[-4:-2]) * 60 + int(offset_str[-2:])
    if offset_str[0] == '-':
      offset = -offset
    return timedelta(minutes=offset)

  def LocalToUTC(self, naive_time):
    """Localizes naive datetime and converts it to utc naive datetime.

    Args:
      naive_time(datetime): naive time in local time zone, for example '+0800'.

    Return:
      A naive datetime object in utc time zone.
      For example:
      For TimeZoneInfo('+0800'), and naive local time is
      datetime(2016, 9, 1, 10, 0, 0), the returned result should be
      datetime(2016, 9, 1, 2, 0, 0) in utc time.
    """
    return naive_time - self._utcoffset
