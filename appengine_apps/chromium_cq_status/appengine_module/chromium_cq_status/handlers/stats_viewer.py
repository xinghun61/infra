# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from appengine_module.chromium_cq_status.shared.utils import minutes_per_day

period_config = {
  '15-minutely': {
    'interval_minutes': 15,
    'window_length': minutes_per_day / 15,
    'data_points': 2 * minutes_per_day / 15,
  },
  'hourly': {
    'interval_minutes': 60,
    'window_length': 48,
    'data_points': 7 * 24,
  },
  'daily': {
    'interval_minutes': minutes_per_day,
    'window_length': 14,
    'data_points': 4 * 30,
  },
  'weekly': {
    'interval_minutes': 7 * minutes_per_day,
    'window_length': 4,
    'data_points': 104,
  },
}

class StatsViewer(webapp2.RequestHandler): # pragma: no cover
  def get(self, project, period):
    assert period in period_config
    config = period_config[period]
    data_points = self.request.get('data_points') or config['data_points']
    self.response.write(open('templates/stats_viewer.html').read() % {
      'project': project,
      'period': period,
      'interval_minutes': config['interval_minutes'],
      'window_length': config['window_length'],
      'data_points': data_points,
    })
