# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import cStringIO
import csv

from recipe_engine import recipe_api


class OmahaproxyApi(recipe_api.RecipeApi):
  """APIs for interacting with omahaproxy."""

  @staticmethod
  def split_version(text):
    result = [int(x) for x in text.split('.')]
    assert len(result) == 4
    return result

  def history(self, min_major_version=None, exclude_platforms=None):
    exclude_platforms = exclude_platforms or []
    TEST_DATA = """os,channel,version,timestamp
        ios,canary,74.0.3729.169,2018-07-16 07:25:01.309860
        mac,canary,74.0.3729.169,2018-07-16 07:25:01.309860
        win64,canary_asan,74.0.3729.169,2018-05-31 10:11:01.811670
        win,canary,69.0.3446.0,2018-05-31 07:09:01.554990"""
    raw_history = self.m.url.get_text(
        'https://omahaproxy.appspot.com/history',
        default_test_data=TEST_DATA).output
    csv_reader = csv.reader(cStringIO.StringIO(raw_history))
    data = list(csv_reader)
    header = data[0]
    for row in data[1:]:
      candidate = {header[i]: row[i] for i in range(len(row))}
      if (min_major_version and
          self.split_version(candidate['version'])[0] < min_major_version):
        continue
      if row[0].strip() in exclude_platforms:
        continue
      yield candidate
