# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import calendar
import json
import jinja2
import os
import webapp2

from appengine_module.trooper_o_matic import controller


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__),
                                                'templates')),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


class CQHandler(webapp2.RequestHandler):
  def get(self, project):
    template = JINJA_ENVIRONMENT.get_template('cq.html')
    self.response.write(template.render({
        'project': project
    }))


class CQLengthJSONHandler(webapp2.RequestHandler):
  def get(self, project):
    cq_data = controller.get_cq_stats(project)
    length_cols = ['timestamp', 'length']
    length_rows = [
        [calendar.timegm(stat.timestamp.timetuple()), stat.length]
        for stat in cq_data['single_run_data']]
    length_data = {
        'cols': length_cols,
        'rows': length_rows,
        'unit': 'count',
    }

    self.response.headers['Content-Type'] = 'application/json'
    self.response.headers['Access-Control-Allow-Origin'] = '*'
    self.response.write(json.dumps(length_data))
