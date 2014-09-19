# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from appengine_module.chromium_cq_status.model.cq_stats import CQStats
from appengine_module.chromium_cq_status.shared.utils import cross_origin_json

class StatsDataPoints(webapp2.RequestHandler): # pragma: no cover
  @cross_origin_json
  def get(self, ranking, name, cq_stats_key): # pylint: disable-msg=R0201
    cq_stats = CQStats.get_by_id(int(cq_stats_key))
    assert cq_stats, '%s must match a CQStats entry.' % cq_stats_key
    for stats in cq_stats.count_stats + cq_stats.list_stats:
      if stats.name == name:
        if ranking == 'lowest':
          return stats.lowest_100
        if ranking == 'highest':
          return stats.highest_100
        assert False
    assert False, '%s must match a stat in the specified CQStats entry.' % name
