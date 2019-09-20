# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.api.modules import modules

from components import auth
from components import config as config_api
from components import decorators
from components import endpoints_webapp2
from components import prpc

import webapp2

from legacy import api as legacy_api
from legacy import api_common
from legacy import swarmbucket_api
import access
import api
import bq
import bulkproc
import config
import expiration
import model
import notifications
import service
import swarming
import user

README_MD = (
    'https://chromium.googlesource.com/infra/infra/+/master/'
    'appengine/cr-buildbucket/README.md'
)


class DummyStartHandler(auth.AuthenticatingHandler):  # pragma: no cover
  """Dummy handler for /_ah/start.

  Derived from AuthenticatingHandler to initialize auth db before the first
  request.
  """

  @auth.public
  def get(self):
    pass


class MainHandler(webapp2.RequestHandler):  # pragma: no cover
  """Redirects to README.md."""

  def get(self):
    return self.redirect(README_MD)


class CronUpdateBuckets(webapp2.RequestHandler):  # pragma: no cover
  """Updates buckets from configs."""

  @decorators.require_cronjob
  def get(self):
    config.cron_update_buckets()


class BuildRPCHandler(webapp2.RequestHandler):  # pragma: no cover
  """Redirects to API explorer to see the build."""

  def get(self, build_id):
    api_path = '/_ah/api/buildbucket/v1/builds/%s' % build_id
    return self.redirect(api_path)


class ViewBuildHandler(auth.AuthenticatingHandler):  # pragma: no cover
  """Redirects to API explorer to see the build."""

  @auth.public
  def get(self, build_id):
    try:
      build_id = int(build_id)
    except ValueError:
      self.response.write('invalid build id')
      self.abort(400)

    build = model.Build.get_by_id(build_id)
    can_view = build and user.can_view_build_async(build).get_result()

    if not can_view:
      if auth.get_current_identity().is_anonymous:
        return self.redirect(self.create_login_url(self.request.url))
      self.response.write('build %d not found' % build_id)
      self.abort(404)

    return self.redirect(str(api_common.get_build_url(build)))


class TaskCancelSwarmingTask(webapp2.RequestHandler):  # pragma: no cover
  """Cancels a swarming task."""

  @decorators.require_taskqueue('backend-default')
  def post(self, host, task_id):
    swarming.cancel_task(host, task_id)


class UnregisterBuilders(webapp2.RequestHandler):  # pragma: no cover
  """Unregisters builders that didn't have builds for a long time."""

  @decorators.require_cronjob
  def get(self):
    service.unregister_builders()


def _beefy_service_interceptor(
    request, context, call_details, continuation
):  # pragma: no cover
  """Requires the requester to be a member of "buildbucket-beefy-users" group.
  """
  if auth.is_group_member('buildbucket-beefy-users'):
    return continuation(request, context, call_details)

  who = auth.get_current_identity().to_bytes()
  logging.warning('%s tried to use beefy service', who)
  context.set_code(prpc.StatusCode.PERMISSION_DENIED)
  context.set_details(
      '%s is not allowed to use beefy buildbucket service' % who
  )
  return None


def get_frontend_routes():  # pragma: no cover
  endpoints_services = [
      legacy_api.BuildBucketApi,
      config_api.ConfigApi,
      swarmbucket_api.SwarmbucketApi,
  ]
  routes = [
      webapp2.Route(r'/_ah/start', DummyStartHandler),
      webapp2.Route(r'/', MainHandler),
      webapp2.Route(r'/b/<build_id:\d+>', BuildRPCHandler),
      webapp2.Route(r'/build/<build_id:\d+>', ViewBuildHandler),
  ]
  routes.extend(endpoints_webapp2.api_routes(endpoints_services))
  # /api routes should be removed once clients are hitting /_ah/api.
  routes.extend(
      endpoints_webapp2.api_routes(endpoints_services, base_path='/api')
  )

  prpc_server = prpc.Server()
  prpc_server.add_interceptor(auth.prpc_interceptor)
  if modules.get_current_module_name() == 'beefy':
    prpc_server.add_interceptor(_beefy_service_interceptor)
  prpc_server.add_service(access.AccessServicer())
  prpc_server.add_service(api.BuildsApi())
  routes += prpc_server.get_routes()

  return routes


def get_backend_routes():  # pragma: no cover
  prpc_server = prpc.Server()
  prpc_server.add_interceptor(auth.prpc_interceptor)
  prpc_server.add_service(api.BuildsApi())

  return [  # pragma: no branch
      webapp2.Route(r'/internal/cron/buildbucket/expire_build_leases',
                    expiration.CronExpireBuildLeases),
      webapp2.Route(r'/internal/cron/buildbucket/expire_builds',
                    expiration.CronExpireBuilds),
      webapp2.Route(r'/internal/cron/buildbucket/delete_builds',
                    expiration.CronDeleteBuilds),
      webapp2.Route(r'/internal/cron/buildbucket/update_buckets',
                    CronUpdateBuckets),
      webapp2.Route(r'/internal/cron/buildbucket/bq-export',
                    bq.CronExportBuilds),
      webapp2.Route(r'/internal/cron/buildbucket/unregister-builders',
                    UnregisterBuilders),
      webapp2.Route(r'/internal/task/buildbucket/notify/<build_id:\d+>',
                    notifications.TaskPublishNotification),
      webapp2.Route(
          r'/internal/task/buildbucket/cancel_swarming_task/<host>/<task_id>',
          TaskCancelSwarmingTask),
  ] + bulkproc.get_routes() + prpc_server.get_routes()
