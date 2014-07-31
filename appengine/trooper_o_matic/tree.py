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


class TreeHandler(webapp2.RequestHandler):
  """Displays counts of builds that did not meet SLO for the given Tree."""

  @staticmethod
  def _FormatGoogleChartsDateTime(dt):
    pt = timezones.UtcToPacific(dt)
    return 'Date(%d, %d, %d, %d, %d, %d)' % (
        pt.year, pt.month - 1, pt.day, pt.hour, pt.minute, pt.second)

  def get(self, tree):
    tree_key = ndb.Key('Tree', tree)
    data = models.BuildTimeStat.query(ancestor=tree_key).order(
        -models.BuildTimeStat.timestamp).fetch(limit=30)
    data.reverse()
    builds_cols = [
        {'id': 'timestamp', 'label': 'Time', 'type': 'datetime'},
        {'id': 'num_builds', 'label': 'Number of Builds', 'type': 'number'},
        {'id': 'num_over_median', 'label': 'Builds over 30m', 'type': 'number'},
        {'id': 'num_over_max', 'label': 'Builds over 60m', 'type': 'number'},
    ]
    builds_rows = [{
        'c': [
            {'v': self._FormatGoogleChartsDateTime(stat.timestamp),
             'key': stat.key.urlsafe()},
            {'v': stat.num_builds - (stat.num_over_median_slo +
                                     stat.num_over_max_slo)},
            {'v': stat.num_over_median_slo - stat.num_over_max_slo},
            {'v': stat.num_over_max_slo},
            ]} for stat in data]
    builds_graph = {'cols': builds_cols, 'rows': builds_rows}

    template = JINJA_ENVIRONMENT.get_template('tree.html')
    self.response.write(template.render({
        'builds': json.dumps(builds_graph),
        'tree': tree.title(),
    }))
