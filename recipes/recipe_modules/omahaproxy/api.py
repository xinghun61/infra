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
        win64,canary_asan,69.0.3446.1,2018-05-31 10:11:01.811670
        win,canary,69.0.3446.0,2018-05-31 07:09:01.554990
        ios,beta,68.0.3440.9,2018-05-31 00:37:02.595620
        linux,stable,64.0.2564.109,2016-02-09 19:07:05.198510
        ios,stable,63.0.3239.73,2017-12-05 23:27:02.846600
        linux,stable,48.0.2564.109,2016-02-09 19:07:05.198510
        mac,canary,44.0.2376.0,2015-04-20 19:42:48.990730
        win,canary,41.0.2270.0,2015-01-08 19:48:09.982040
        linux,dev,41.0.2267.0,2015-01-06 19:58:10.377100
        mac,beta,36.0.1985.49,2014-06-04 17:40:47.808350"""
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
