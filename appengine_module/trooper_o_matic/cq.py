# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import jinja2
import os
import webapp2

from appengine_module.trooper_o_matic import controller
from appengine_module.trooper_o_matic import timezones


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__),
                                                'templates')),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


class CqHandler(webapp2.RequestHandler):

  @staticmethod
  def _FormatGoogleChartsDateTime(dt):
    pt = timezones.UtcToPacific(dt)
    return 'Date(%d, %d, %d, %d, %d, %d)' % (
        pt.year, pt.month - 1, pt.day, pt.hour, pt.minute, pt.second)

  def _CreateGoogleChartRows(self, data):
    return [{
        'c': [
            {'v': self._FormatGoogleChartsDateTime(stat.timestamp)},
            {'v': stat.min},
            {'v': stat.mean},
            {'v': stat.p50 or 0},
            {'v': stat.p90 or 0},
            {'v': stat.p99 or 0},
            ]} for stat in data]

  def get(self, project):
    cq_data = controller.get_cq_stats(project)
    length_cols = [
        {'id': 'timestamp', 'label': 'Time', 'type': 'datetime'},
        {'id': 'length', 'label': 'Commit Queue Length', 'type': 'number'},
    ]
    length_rows = [{
        'c': [
            {'v': self._FormatGoogleChartsDateTime(stat.timestamp)},
            {'v': stat.length},
            ]} for stat in cq_data['single_run_data']]
    length_graph = {'cols': length_cols, 'rows': length_rows}
    run_cols = [
        {'id': 'timestamp', 'label': 'Time', 'type': 'datetime'},
        {'id': 'min', 'label': 'Min', 'type': 'number'},
        {'id': 'mean', 'label': 'Mean', 'type': 'number'},
        {'id': 'p50', 'label': '50th', 'type': 'number'},
        {'id': 'p90', 'label': '90th', 'type': 'number'},
        {'id': 'p99', 'label': '99th', 'type': 'number'},
    ]
    single_run_rows = self._CreateGoogleChartRows(cq_data['single_run_data'])
    single_run_graph = {'cols': run_cols, 'rows': single_run_rows}
    queue_time_rows = self._CreateGoogleChartRows(cq_data['queue_time_data'])
    queue_time_graph = {'cols': run_cols, 'rows': queue_time_rows}
    total_time_rows = self._CreateGoogleChartRows(cq_data['total_time_data'])
    total_time_graph = {'cols': run_cols, 'rows': total_time_rows}

    template = JINJA_ENVIRONMENT.get_template('cq.html')
    self.response.write(template.render({
        'length': length_graph,
        'single_run': single_run_graph,
        'queue_time': queue_time_graph,
        'total_time': total_time_graph,
    }))
