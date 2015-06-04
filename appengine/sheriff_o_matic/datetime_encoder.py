# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import calendar
import datetime
import json


class DateTimeEncoder(json.JSONEncoder):

  def default(self, obj):  # pylint: disable=E0202
    if isinstance(obj, datetime.datetime):
      return calendar.timegm(obj.timetuple())
    # Let the base class default method raise the TypeError.
    return json.JSONEncoder.default(self, obj)

