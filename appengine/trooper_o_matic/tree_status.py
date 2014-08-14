# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import jinja2
import json
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


class TreeStatusHandler(webapp2.RequestHandler):

  @staticmethod
  def _FormatGoogleChartsDateTime(dt):
    pt = timezones.UtcToPacific(dt)
    return 'Date(%d, %d, %d, %d, %d, %d)' % (
        pt.year, pt.month - 1, pt.day, pt.hour, pt.minute, pt.second)

  def get(self, project):
    project_key = ndb.Key('Project', project)
    data_1 = models.TreeOpenStat.query(
        models.TreeOpenStat.num_days == 1, ancestor=project_key).order(
        -models.TreeOpenStat.timestamp).fetch(limit=500)
    data_1.reverse()
    cols_1 = [
        {'id': 'timestamp', 'label': 'Time', 'type': 'datetime'},
        {'id': '1', 'label': 'Percent open last 24 hours', 'type': 'number'},
    ]
    rows_1 = [{
        'c': [
            {'v': self._FormatGoogleChartsDateTime(stat.timestamp)},
            {'v': stat.percent_open},
        ]} for stat in data_1]
    graph_1 = {'cols': cols_1, 'rows': rows_1}
    data_7 = models.TreeOpenStat.query(
        models.TreeOpenStat.num_days == 7, ancestor=project_key).order(
        -models.TreeOpenStat.timestamp).fetch(limit=500)
    data_7.reverse()
    cols_7 = [
        {'id': 'timestamp', 'label': 'Time', 'type': 'datetime'},
        {'id': '7', 'label': 'Percent open last 24 hours', 'type': 'number'}
    ]
    rows_7 = [{
        'c': [
            {'v': self._FormatGoogleChartsDateTime(stat.timestamp)},
            {'v': stat.percent_open}
        ]} for stat in data_7]
    graph_7 = {'cols': cols_7, 'rows': rows_7}

    data_gauge = [
          ['Label', 'Value'],
          ['1 Day', round(data_1[-1].percent_open, 0)],
          ['7 Days', round(data_7[-1].percent_open, 0)],
        ]

    template = JINJA_ENVIRONMENT.get_template('tree_status.html')
    self.response.write(template.render({
        'days_1': graph_1,
        'days_7': graph_7,
        'data_gauge': data_gauge,
    }))

class TreeStatusJSONHandler(webapp2.RequestHandler):
  def get(self, project, days):
    project_key = ndb.Key('Project', project)
    latest = models.TreeOpenStat.query(
        models.TreeOpenStat.num_days == int(days), ancestor=project_key).order(
        -models.TreeOpenStat.timestamp).get()

    data = {}
    data['timestamp'] = latest.timestamp.isoformat()
    data['num_days'] = latest.num_days
    data['percent_open'] = latest.percent_open

    self.response.headers['Content-Type'] = 'application/json'
    self.response.headers['Access-Control-Allow-Origin'] = '*'
    self.response.write(json.dumps(data))
