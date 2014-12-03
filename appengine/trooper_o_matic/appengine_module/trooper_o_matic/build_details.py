# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Shows details of builds which did not meet our SLO.

See template at templates/build_details.html for sortable table.
"""
import jinja2
import json
import os
import webapp2

from google.appengine.ext import ndb


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__),
                                                'templates')),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


class BuildDetailsHandler(webapp2.RequestHandler):

  def get(self, key):
    stats = ndb.Key(urlsafe=key).get()
    builds = [{
        'tree': stat.tree,
        'master': stat.master,
        'builder': stat.builder,
        'buildnumber': stat.buildnumber,
        'buildtime': stat.buildtime,
        'result': stat.result,
        'revision': stat.revision,
    } for stat in stats.slo_offenders]
    template = JINJA_ENVIRONMENT.get_template('build_details.html')
    self.response.write(template.render({
        'builds': json.dumps(builds),
    }))
