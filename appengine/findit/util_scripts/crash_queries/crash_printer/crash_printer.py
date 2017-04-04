# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys

from crash_queries import crash_iterator

PROPERTIES = ['signature', 'platform']


def PrintCrash(crash):
  for crash_property in PROPERTIES:
    print getattr(crash, crash_property)
  print '\n'


def CrashPrinter(client_id, app_id,
                 start_date=None, end_date=None,
                 print_func=PrintCrash, signature=None):
  property_values = {'signature': signature} if signature else None
  for crash in crash_iterator.CachedCrashIterator(
      client_id, app_id, start_date=start_date, end_date=end_date,
      property_values=property_values):
    print_func(crash)
