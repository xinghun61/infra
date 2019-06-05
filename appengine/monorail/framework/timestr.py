# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Time-to-string and time-from-string routines."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import calendar
import datetime
import time


class Error(Exception):
  """Exception used to indicate problems with time routines."""
  pass


HTML_TIME_FMT = '%a, %d %b %Y %H:%M:%S GMT'
HTML_DATE_WIDGET_FORMAT = '%Y-%m-%d'

MONTH_YEAR_FMT = '%b %Y'
MONTH_DAY_FMT = '%b %d'
MONTH_DAY_YEAR_FMT = '%b %d %Y'

# We assume that all server clocks are synchronized within this amount.
MAX_CLOCK_SKEW_SEC = 30


def TimeForHTMLHeader(when=None):
  """Return the given time (or now) in HTML header format."""
  if when is None:
    when = int(time.time())
  return time.strftime(HTML_TIME_FMT, time.gmtime(when))


def TimestampToDateWidgetStr(when):
  """Format a timestamp int for use by HTML <input type="date">."""
  return time.strftime(HTML_DATE_WIDGET_FORMAT, time.gmtime(when))


def DateWidgetStrToTimestamp(val_str):
  """Parse the HTML <input type="date"> string into a timestamp int."""
  return int(calendar.timegm(time.strptime(val_str, HTML_DATE_WIDGET_FORMAT)))


def FormatAbsoluteDate(
    timestamp, clock=datetime.datetime.utcnow,
    recent_format=MONTH_DAY_FMT, old_format=MONTH_YEAR_FMT):
  """Format timestamp like 'Sep 5', or 'Yesterday', or 'Today'.

  Args:
    timestamp: Seconds since the epoch in UTC.
    clock: callable that returns a datetime.datetime object when called with no
      arguments, giving the current time to use when computing what to display.
    recent_format: Format string to pass to strftime to present dates between
      six months ago and yesterday.
    old_format: Format string to pass to strftime to present dates older than
      six months or more than skew_tolerance in the future.

  Returns:
    If timestamp's date is today, "Today". If timestamp's date is yesterday,
    "Yesterday". If timestamp is within six months before today, return the
    time as formatted by recent_format. Otherwise, return the time as formatted
    by old_format.
  """
  ts = datetime.datetime.utcfromtimestamp(timestamp)
  now = clock()
  month_delta = 12 * now.year + now.month - (12 * ts.year + ts.month)
  delta = now - ts

  if ts > now:
    # If the time is slightly in the future due to clock skew, treat as today.
    skew_tolerance = datetime.timedelta(seconds=MAX_CLOCK_SKEW_SEC)
    if -delta <= skew_tolerance:
      return 'Today'
    # Otherwise treat it like an old date.
    else:
      fmt = old_format
  elif month_delta > 6 or delta.days >= 365:
    fmt = old_format
  elif delta.days == 1:
    return 'Yesterday'
  elif delta.days == 0:
    return 'Today'
  else:
    fmt = recent_format

  return time.strftime(fmt, time.gmtime(timestamp)).replace(' 0', ' ')


def FormatRelativeDate(timestamp, days_only=False, clock=None):
  """Return a short string that makes timestamp more meaningful to the user.

  Describe the timestamp relative to the current time, e.g., '4
  hours ago'.  In cases where the timestamp is more than 6 days ago,
  we return '' so that an alternative display can be used instead.

  Args:
    timestamp: Seconds since the epoch in UTC.
    days_only: If True, return 'N days ago' even for more than 6 days.
    clock: optional function to return an int time, like int(time.time()).

  Returns:
    String describing relative time.
  """
  if clock:
    now = clock()
  else:
    now = int(time.time())

  # TODO(jrobbins): i18n of date strings
  delta = int(now - timestamp)
  d_minutes = delta // 60
  d_hours = d_minutes // 60
  d_days = d_hours // 24
  if days_only:
    if d_days > 1:
      return '%s days ago' % d_days
    else:
      return ''

  if d_days > 6:
    return ''
  if d_days > 1:
    return '%s days ago' % d_days  # starts at 2 days
  if d_hours > 1:
    return '%s hours ago' % d_hours  # starts at 2 hours
  if d_minutes > 1:
    return '%s minutes ago' % d_minutes
  if d_minutes > 0:
    return '1 minute ago'
  if delta > -MAX_CLOCK_SKEW_SEC:
    return 'moments ago'
  return ''


def GetHumanScaleDate(timestamp, now=None):
  """Formats a timestamp to a course-grained and fine-grained time phrase.

  Args:
    timestamp: Seconds since the epoch in UTC.
    now: Current time in seconds since the epoch in UTC.

  Returns:
    A pair (course_grain, fine_grain) where course_grain is a string
    such as 'Today', 'Yesterday', etc.; and fine_grained is a string describing
    relative hours for Today and Yesterday, or an exact date for longer ago.
  """
  if now is None:
    now = int(time.time())

  now_year = datetime.datetime.fromtimestamp(now).year
  then_year = datetime.datetime.fromtimestamp(timestamp).year
  delta = int(now - timestamp)
  delta_minutes = delta // 60
  delta_hours = delta_minutes // 60
  delta_days = delta_hours // 24

  if 0 <= delta_hours < 24:
    if delta_hours > 1:
      return 'Today', '%s hours ago' % delta_hours
    if delta_minutes > 1:
      return 'Today', '%s min ago' % delta_minutes
    if delta_minutes > 0:
      return 'Today', '1 min ago'
    if delta > 0:
      return 'Today', 'moments ago'
  if 0 <= delta_hours < 48:
    return 'Yesterday', '%s hours ago' % delta_hours
  if 0 <= delta_days < 7:
    return 'Last 7 days', time.strftime(
        '%b %d, %Y', (time.localtime(timestamp)))
  if 0 <= delta_days < 30:
    return 'Last 30 days', time.strftime(
        '%b %d, %Y', (time.localtime(timestamp)))
  if delta > 0:
    if now_year == then_year:
      return 'Earlier this year', time.strftime(
          '%b %d, %Y', (time.localtime(timestamp)))
    return ('Before this year',
            time.strftime('%b %d, %Y', (time.localtime(timestamp))))
  if delta > -MAX_CLOCK_SKEW_SEC:
    return 'Today', 'moments ago'
  # Only say something is in the future if it is more than just clock skew.
  return 'Future', 'Later'
