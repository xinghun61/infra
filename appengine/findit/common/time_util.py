# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import calendar
from datetime import datetime
from datetime import time
from datetime import timedelta

import pytz


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
  if not delta:
    return None
  hours, remainder = divmod(delta.seconds, 3600)
  minutes, seconds = divmod(remainder, 60)
  return '%02d:%02d:%02d' % (hours, minutes, seconds)


def FormatDatetime(date):
  if not date:
    return None
  else:
    return date.strftime('%Y-%m-%d %H:%M:%S UTC')


def GetDatetimeInTimezone(timezone_name, date_time=None):
  """Returns the datetime.datetime of the given one in the specified timezone.

  Args:
    timezone_name (str): The name of any timezone supported by pytz.
    date_time (datetime.datetime): The optional datetime to be converted into
        the new timezone. If not given, default to UTC now.

  Returns:
    A datetime.datetime of the given one in the specified timezone.
  """
  date_time = date_time or GetUTCNowWithTimezone()
  return date_time.astimezone(pytz.timezone(timezone_name))
