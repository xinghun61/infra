# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import logging
import re


LOGGER = logging.getLogger(__name__)

TimeSpec = collections.namedtuple('TimeSpec', ('value', 'unit', 'minutes'))


TIMESPEC_RE = re.compile('^(?P<value>[0-9]+)(?P<unit>[mhdw])$')
UTCTIME_RE = re.compile('^(?P<hours>[0-9][0-9]):(?P<minutes>[0-9][0-9])$')
DAYNAME_RE = re.compile('^(?P<day>mon|tue|wed|thu|fri|sat|sun)$')
DAYNAME_NUM = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4,
               'sat': 5, 'sun': 6}
UNITS_ORDER = ('w', 'd', 'h', 'm')


class JobTimes(object):  # pragma: no cover
  def __init__(self, period, offsets, jitter):
    """This object computes a sequence of timestamps.

    Ex: period = 5, offsets = [0] would compute a series of datetime.datetime
      objects spaced by 5 minutes, aligned with the hour (e.g. 08:00, 08:05,
      08:10 would be part of the sequence). The alignment can be controlled with
      the "offsets" argument:
      period = 5, offsets = [3] would compute timestamps spaced by 5 min, but
      this time 08:03, 08:08, 08:13, etc. would be part of the sequence.

    Specifying several offsets is possible. The result is the union of all
    sequences obtained for all offsets.
    Ex: period = 5, offsets = [0, 3] would output 08:00, 08:03, 08:05,
      08:08, 08:10, 08:13, etc.

    The starting point for all offsets is Monday 2006-01-01T00:00:00Z.

    Args:
      period (int): time separating two timestamps, in minutes
      offsets (list of int): offset times, in minutes
      jitter (int): additional offset applied to all timestamps, in *seconds*.
    """
    # Yes the epoch is not the Unix one. It makes the numbers smaller, avoids
    # some weirdness around the year 2000 (which wasn't a leap year) and
    # allows to start on a Monday (1970-1-1 is a Thursday), which simplifies
    # computations when weeks are involved.
    self.period = period
    self.offsets = offsets or [0]
    self.jitter = jitter

  def next_time(self, utc_dt):
    # returns the closest future scheduling time after utc_dt.
    # utc_dt: datetime.datetime. Naive is interpreted as UTC, non-naive non-UTC
    # raise ValueError.
    pass

  def next_times(self, utc_dt, num):
    # Returns a list of future scheduling times after utc_dt
    # Like next_time(), but returns a list instead of a single value.
    times = []
    for _ in xrange(num):
      utc_dt = self.next_time(utc_dt)
      times.append(utc_dt)

    return times


def parse_time_offsets(s):
  """Parse a string containing comma-separated time offsets.

  See parse_time_offset() for a specification of the time offset format.

  Args:
    s (str): string with comma-separated time offsets. Ex: "2m, 4h 1m, 10:30"

  Returns:
    offsets (list of int): offsets in minutes.
  """
  if not s:
    return []
  return [parse_time_offset(part) for part in s.split(',')]


def parse_time_offset(s):
  """Parse a string specifying a time offset.

  Type of strings admitted (all examples on a single line are synonyms):
  "tue 14:30", "tue 14h 30m", "1d 14:30", "1d 14h 30m"
  "14:30" "14h 30m" "870m"
  "mon" "mon 00:00" "mon 0m"
  "1d" "24h" "1440m"

  These are invalid:
  "14:30 2h"
  "1d 27h"
  "2h 250m"
  "20m 2h"
  "10:30 mon"

  Returns:
    minutes: duration expressed in minutes.
  """
  minutes = 0
  last_unit = -1
  s = s.strip()
  parts = s.split(' ')
  for n, part in enumerate(parts):
    ts = parse_time_spec(part, check_value=n>0)
    if UNITS_ORDER.index(ts.unit[0]) <= last_unit:
      raise ValueError('Invalid time specification: %s' % s)
    last_unit = UNITS_ORDER.index(ts.unit[-1])
    minutes += ts.minutes
  return minutes


def parse_time_spec(s, check_value=False):
  """Turn a string like '4d' into a number of minutes

  Args:
    s (str): string to parse.

  Keyword Args:
    check_value (bool): if True, raises ValueError when an hour or minute
      specification is above 23 or 59 respectively.

  Returns:
    TimeSpec: parsed result, containing the original values in the string
      (number and unit), as well as the duration converted to minutes.
  """
  s = s.strip()

  match = TIMESPEC_RE.match(s)
  if match:
    value = int(match.groupdict()['value'])
    unit = match.groupdict()['unit']
    if unit == 'm':
      if check_value and value > 59:
        raise ValueError('Invalid value for minutes: %d' % value)
      minutes = value
    elif unit == 'h':
      if check_value and value > 23:
        raise ValueError('Invalid value for hours: %d' % value)
      minutes = value * 60
    elif unit == 'd':
      minutes = value * 1440 # 24*60
    elif unit == 'w': # pragma: no branch
      minutes = value * 10080 # 24*60*7
    else:  # pragma: no cover
      raise AssertionError('This line must not be reached. Check for '
                           'consistency between parse_time_spec() and the '
                           'regular expression TIMESPEC_RE.')
    return TimeSpec(value, unit, minutes)

  match = UTCTIME_RE.match(s)
  if match:
    hours = int(match.groupdict()['hours'])
    if hours > 24:
      raise ValueError('Invalid time: %s' % s)
    minutes = int(match.groupdict()['minutes'])
    if minutes > 59:
      raise ValueError('Invalid time: %s' % s)
    value = (hours * 60 + minutes)
    return TimeSpec(value, 'hm', value)

  match = DAYNAME_RE.match(s)
  if match:
    value = DAYNAME_NUM[match.groupdict()['day']]
    return TimeSpec(value, 'd', value * 1440)

  raise ValueError('Unable to parse time spec: %s' % s)


def parse(s, _jitter=None):
  """Parse a scheduling string and return a JobTimes object.

  Examples of scheduling strings:
  - "every 5m @ 1m"
  - "every 1w @ mon 10:30"

  See also parse_time_spec().

  Args:
    s(str): scheduling string

  Returns
    job_times (JobTimes): computer-friendly representation of s.
  """
  # _jitter is here to force the jitter time. Used for testing only.

  s = s.strip()
  if not s:
    raise ValueError('Expected a string starting with "every", got'
                     ' empty string.')

  parts = s.split('every ')
  if parts[0]:
    raise ValueError('scheduling string must start with the word "every" '
                     'followed by a space. Got %s' % s)

  # TODO(pgervais): process other 'every' clauses as well.
  if len(parts) > 2:
    LOGGER.warning('Found several "every" clause in scheduling string, '
                'will process only the first: %s', s)
  s = parts[1].strip()

  # Get period and offset ("every" <period> "@" <offset>)
  parts = s.split('@')
  if len(parts) > 2:
    raise ValueError('Expected a single separating @, got %d: %s'
                     % (len(parts), s))

  period = parse_time_spec(parts[0]).minutes

  offsets = []
  if len(parts) == 2:
    offsets = parse_time_offsets(parts[1])

  # TODO(pgervais): implement jitter support.
  # _jitter == 0 is valid input
  jitter = _jitter if _jitter is not None else 0

  return JobTimes(period, offsets, jitter)
