# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import jinja2
import json
import os
import webapp2

from google.appengine.ext import ndb

from appengine_module.trooper_o_matic import models
from appengine_module.trooper_o_matic import timezones


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__),
                                                'templates')),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


class TreeHandler(webapp2.RequestHandler):
  """Displays summary of builds that did not meet SLO for the given Tree."""

  @staticmethod
  def _FormatGoogleChartsDateTime(dt):
    pt = timezones.UtcToPacific(dt)
    return 'Date(%d, %d, %d, %d, %d, %d)' % (
        pt.year, pt.month - 1, pt.day, pt.hour, pt.minute, pt.second)

  def get(self, tree):
    tree_key = ndb.Key(models.Tree, tree)
    data = models.BuildTimeStat.query(ancestor=tree_key).order(
        -models.BuildTimeStat.timestamp).fetch(limit=30)
    data.reverse()

    builds_cols = [
        {'id': 'timestamp', 'label': 'Time', 'type': 'datetime'},
        {'id': 'num_builds', 'label': 'Number of Builds', 'type': 'number'},
        {'id': 'num_over_median', 'label': 'Builds over 90m', 'type': 'number'},
        {'id': 'num_over_max', 'label': 'Builds over 480m', 'type': 'number'},
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

    offenders = [
      # TODO: Ideally this timestamp would be from the build rather
      # than the stat, but that's not in the model yet.
      [stat.timestamp.isoformat(), offender.buildtime,
       offender.master, offender.builder, offender.buildnumber]
          for stat in data for offender in stat.slo_offenders
    ]

    template = JINJA_ENVIRONMENT.get_template('tree.html')
    self.response.write(template.render({
        'offenders': json.dumps(offenders),
        'builds': json.dumps(builds_graph),
        'tree': tree.title(),
        'slo_buildtime_max': models.SLO_BUILDTIME_MAX,
    }))
