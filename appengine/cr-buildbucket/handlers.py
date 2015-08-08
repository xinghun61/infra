# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from components import decorators
import webapp2

import config
import metrics
import service

README_MD = (
    'https://chromium.googlesource.com/infra/infra/+/master/'
    'appengine/cr-buildbucket/README.md')


def create_service():
  return service.BuildBucketService()


class MainHandler(webapp2.RequestHandler):  # pragma: no cover
  """Redirects to README.md."""
  def get(self):
    return self.redirect(README_MD)


class CronResetExpiredBuilds(webapp2.RequestHandler):
  """Resets expired builds."""
  @decorators.require_cronjob
  def get(self):
    create_service().reset_expired_builds()


class CronSendMetrics(webapp2.RequestHandler):  # pragma: no cover
  """Resets expired builds."""
  @decorators.require_cronjob
  def get(self):
    metrics.send_all_metrics()


class CronUpdateBuckets(webapp2.RequestHandler):  # pragma: no cover
  """Updates buckets from configs."""
  @decorators.require_cronjob
  def get(self):
    config.cron_update_buckets()


class BuildHandler(webapp2.RequestHandler):  # pragma: no cover
  """Redirects to API explorer to see the build."""
  def get(self, build_id):
    api_path = '/_ah/api/buildbucket/v1/builds/%s' % build_id
    return self.redirect(api_path)


def get_frontend_routes():  # pragma: no cover
  return [
      webapp2.Route(r'/', MainHandler),
      webapp2.Route(r'/b/<build_id:\d+>', BuildHandler),
  ]


def get_backend_routes():
  return [
      webapp2.Route(
          r'/internal/cron/buildbucket/reset_expired_builds',
          CronResetExpiredBuilds),
      webapp2.Route(
          r'/internal/cron/buildbucket/send_metrics',
          CronSendMetrics),
      webapp2.Route(
          r'/internal/cron/buildbucket/update_buckets',
          CronUpdateBuckets),
  ]
