# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys

from crash_queries import crash_iterator

CRASH_INFO_FIELDS = ['signature', 'platform']


def PrintCrashInfo(crash):
  for crash_info_field in CRASH_INFO_FIELDS:
    print '%s: %s' % (crash_info_field, crash[crash_info_field])


def CrashPrinter(client_id, app_id,
                 start_date, end_date,
                 print_func=PrintCrashInfo,
                 signature=None):

  property_values = {'signature': signature} if signature else None
  for crash in crash_iterator.IterateCrashes(client_id, app_id,
                                             fields=CRASH_INFO_FIELDS,
                                             start_date=start_date,
                                             end_date=end_date,
                                             property_values=property_values):
    print_func(crash)
