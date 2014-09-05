# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime, timedelta
import webapp2

from appengine_module.chromium_cq_status.model.cq_stats import CQStats
from appengine_module.chromium_cq_status.shared.config import DEFAULT_STATS_VIEW_DAYS  # pylint: disable=C0301
from appengine_module.chromium_cq_status.shared.utils import compressed_json_dumps  # pylint: disable=C0301

class StatsViewer(webapp2.RequestHandler): # pragma: no cover
  def get(self, project, period):
    interval_days = {
      'daily': 1,
      'weekly': 7,
    }[period]
    days = int(self.request.get('days') or DEFAULT_STATS_VIEW_DAYS)

    query = CQStats.query().order(CQStats.end).filter(
      CQStats.project == project,
      CQStats.interval_days == interval_days,
      CQStats.end >= datetime.utcnow() - timedelta(days),
    )
    cq_stats_dicts = [cq_stats.to_dict() for cq_stats in query]
    self.response.write(open('templates/stats_viewer.html').read() % {
      'project': project.capitalize(),
      'period': period,
      'raw_data': compressed_json_dumps(cq_stats_dicts),
    })
