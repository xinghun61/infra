# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from components import decorators
import jinja2
import webapp2

import service


ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader('templates'),
    autoescape=True,
)


def create_service():
  return service.BuildBucketService()


class MainHandler(webapp2.RequestHandler):  # pragma: no cover
  def get(self):
    tmpl = ENVIRONMENT.get_template('main.html')
    self.response.out.write(tmpl.render({}))


class CronResetExpiredBuilds(webapp2.RequestHandler):
  """Resets expired builds."""
  @decorators.require_cronjob
  def get(self):
    create_service().reset_expired_builds()


def get_frontend_routes():  # pragma: no cover
  return [webapp2.Route(r'/', MainHandler)]


def get_backend_routes():
  return [
      webapp2.Route(
          r'/internal/cron/buildbucket/reset_expired_builds',
          CronResetExpiredBuilds),
  ]
