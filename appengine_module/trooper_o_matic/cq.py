# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import calendar
import jinja2
import os
import webapp2

from appengine_module.trooper_o_matic import controller


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__),
                                                'templates')),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


class CqHandler(webapp2.RequestHandler):
  def get(self, project):
    cq_data = controller.get_cq_stats(project)
    length_cols = [
        {'id': 'timestamp', 'label': 'Time', 'type': 'number'},
        {'id': 'length', 'label': 'Commit Queue Length', 'type': 'number'},
    ]
    length_rows = [{
        'c': [
            {'v': calendar.timegm(stat.timestamp.timetuple())},
            {'v': stat.length},
            ]} for stat in cq_data['single_run_data']]
    length_graph = {'cols': length_cols, 'rows': length_rows}

    template = JINJA_ENVIRONMENT.get_template('cq.html')
    self.response.write(template.render({
        'project': project,
        'length': length_graph,
    }))
