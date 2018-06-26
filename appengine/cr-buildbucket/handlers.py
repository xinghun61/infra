# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import datetime
import json
import logging
import math
import posixpath

from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from components import auth
from components import config as config_api
from components import decorators
from components import endpoints_webapp2
from components import prpc
from components import utils

import webapp2

from swarming import swarmbucket_api
from v2 import api as v2_api
import access
import api
import bq
import bulkproc
import config
import model
import notifications
import search
import service
import swarming

README_MD = (
    'https://chromium.googlesource.com/infra/infra/+/master/'
    'appengine/cr-buildbucket/README.md'
)


class MainHandler(webapp2.RequestHandler):  # pragma: no cover
  """Redirects to README.md."""

  def get(self):
    return self.redirect(README_MD)


class CronCheckExpiredBuilds(webapp2.RequestHandler):
  """Resets expired builds."""

  @decorators.require_cronjob
  def get(self):
    service.check_expired_builds()


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


class TaskCancelSwarmingTask(webapp2.RequestHandler):  # pragma: no cover
  """Cancels a swarming task."""

  @decorators.require_taskqueue('backend-default')
  def post(self, host, task_id):
    swarming.cancel_task(host, task_id)


class UnregisterBuilders(webapp2.RequestHandler):  # pragma: no cover
  """Unregisters builders that didn't have builds for a long time."""

  @decorators.require_taskqueue('backend-default')
  def post(self):
    service.unregister_builders()


def get_frontend_routes():  # pragma: no cover
  endpoints_services = [
      api.BuildBucketApi,
      config_api.ConfigApi,
      swarmbucket_api.SwarmbucketApi,
  ]
  routes = [
      webapp2.Route(r'/', MainHandler),
      webapp2.Route(r'/b/<build_id:\d+>', BuildHandler),
  ]
  routes.extend(endpoints_webapp2.api_routes(endpoints_services))
  # /api routes should be removed once clients are hitting /_ah/api.
  routes.extend(
      endpoints_webapp2.api_routes(endpoints_services, base_path='/api')
  )

  prpc_server = prpc.Server()
  prpc_server.add_interceptor(auth.prpc_interceptor)
  prpc_server.add_service(access.AccessServicer())
  prpc_server.add_service(v2_api.BuildsApi())
  routes += prpc_server.get_routes()

  return routes


def get_backend_routes():
  return [  # pragma: no branch
      webapp2.Route(r'/internal/cron/buildbucket/check_expired_builds',
                    CronCheckExpiredBuilds),
      webapp2.Route(r'/internal/cron/buildbucket/update_buckets',
                    CronUpdateBuckets),
      webapp2.Route(r'/internal/cron/buildbucket/bq-export-prod',
                    bq.CronExportBuildsProd),
      webapp2.Route(r'/internal/cron/buildbucket/bq-export-experimental',
                    bq.CronExportBuildsExperimental),
      webapp2.Route(r'/internal/cron/buildbucket/unregister-builders',
                    UnregisterBuilders),
      webapp2.Route(r'/internal/task/buildbucket/notify/<build_id:\d+>',
                    notifications.TaskPublishNotification),
      webapp2.Route(
          r'/internal/task/buildbucket/cancel_swarming_task/<host>/<task_id>',
          TaskCancelSwarmingTask),
  ] + bulkproc.get_routes()
