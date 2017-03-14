# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import calendar
from datetime import datetime
from datetime import timedelta

import pytz


def GetPSTNow():  # pragma: no cover
  """Returns datetime.now but in pst timezone. This is to mock for testing."""
  return datetime.now(pytz.timezone('US/Pacific'))


def GetUTCNow():  # pragma: no cover.
  """Returns the datetime.utcnow. This is to mock for testing."""
  return datetime.utcnow()


def GetUTCNowWithTimezone():  # pragma: no cover.
  """Returns datetime.now but in utc timezone. This is to mock for testing."""
  return datetime.now(pytz.utc)


def GetUTCNowTimestamp():  # pragma: no cover.
  """Returns the timestamp for datetime.utcnow. This is to mock for testing."""
  return calendar.timegm(GetUTCNow().timetuple())


def RemoveMicrosecondsFromDelta(delta):
  """Returns a timedelta object without microseconds based on delta."""
  return delta - timedelta(microseconds=delta.microseconds)


def FormatTimedelta(delta):
  """Returns a string representing the given time delta."""
  if not delta:
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
  """Parses a datetime from a string as serialized for callback."""
  if date == 'None':
    return None
  if not date or isinstance(date, datetime):
    return date
  valid_formats = [
      '%Y-%m-%d %H:%M:%S.%f',
      '%Y-%m-%dT%H:%M:%S.%f',
      '%Y-%m-%d %H:%M:%S',
      '%Y-%m-%dT%H:%M:%S',
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


def GetDatetimeInTimezone(timezone_name, date_time):
  """Returns the datetime.datetime of the given one in the specified timezone.

  Args:
    timezone_name (str): The name of any timezone supported by pytz.
    date_time (datetime.datetime): The optional datetime to be converted into
        the new timezone.

  Returns:
    A datetime.datetime of the given one in the specified timezone.
  """
  return date_time.astimezone(pytz.timezone(timezone_name))


def MicrosecondsToDatetime(microseconds):
  """Returns a datetime given the number of microseconds, or None."""
  if microseconds:
    return datetime.utcfromtimestamp(float(microseconds) / 1000000)
  return None


class TimeZoneInfo(object):
  """Gets time zone info from string like: +0800.

  The string is HHMM offset relative to UTC timezone."""

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
