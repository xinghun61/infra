# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
from datetime import time
from datetime import timedelta


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
