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
    assert cq_stats, 'CQStats key must be valid.'
    for list_stats in cq_stats.list_stats:
      if list_stats.name == name:
        if ranking == 'best':
          return list_stats.best_100
        if ranking == 'worst':
          return list_stats.worst_100
        assert False, 'Ranking string ' + ranking + ' must be best or worst.'
    assert False, 'Name ' + name + ' must be present in CQStats list stats.'
