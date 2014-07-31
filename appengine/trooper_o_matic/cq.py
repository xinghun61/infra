# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import jinja2
import os
import webapp2

from google.appengine.ext import ndb

import models
import timezones


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

  def get(self, project):
    project_key = ndb.Key('Project', project)
    data = models.CqStat.query(ancestor=project_key).order(
        -models.CqStat.timestamp).fetch(limit=500)
    data.reverse()
    length_cols = [
        {'id': 'timestamp', 'label': 'Time', 'type': 'datetime'},
        {'id': 'length', 'label': 'Commit Queue Length', 'type': 'number'},
    ]
    length_rows = [{
        'c': [
            {'v': self._FormatGoogleChartsDateTime(stat.timestamp)},
            {'v': stat.length},
            ]} for stat in data]
    length_graph = {'cols': length_cols, 'rows': length_rows}
    sanity_cols = [
        {'id': 'timestamp', 'label': 'Time', 'type': 'datetime'},
        {'id': 'min', 'label': 'Min', 'type': 'number'},
        {'id': 'mean', 'label': 'Mean', 'type': 'number'},
        {'id': 'p50', 'label': '50th', 'type': 'number'},
        {'id': 'p90', 'label': '90th', 'type': 'number'},
        {'id': 'p99', 'label': '99th', 'type': 'number'},
    ]
    sanity_rows = [{
        'c': [
            {'v': self._FormatGoogleChartsDateTime(stat.timestamp)},
            {'v': stat.min},
            {'v': stat.mean},
            {'v': stat.p50 or 0},
            {'v': stat.p90 or 0},
            {'v': stat.p99 or 0},
            ]} for stat in data]
    sanity_graph = {'cols': sanity_cols, 'rows': sanity_rows}
    max_cols = [
        {'id': 'timestamp', 'label': 'Time', 'type': 'datetime'},
        {'id': 'max', 'label': 'Commit Queue Max Time', 'type': 'number'},
    ]
    max_rows = [{
        'c': [
            {'v': self._FormatGoogleChartsDateTime(stat.timestamp)},
            {'v': stat.max},
            ]} for stat in data]
    max_graph = {'cols': max_cols, 'rows': max_rows}

    template = JINJA_ENVIRONMENT.get_template('cq.html')
    self.response.write(template.render({
        'length': length_graph,
        'sanity': sanity_graph,
        'max': max_graph,
    }))
