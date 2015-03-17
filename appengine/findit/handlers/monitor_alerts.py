# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import zlib

from google.appengine.api import memcache

from base_handler import BaseHandler
from base_handler import Permission
from common.http_client_appengine import HttpClientAppengine
from waterfall import alerts
from waterfall import build_failure_analysis_pipelines


_BUILD_FAILURE_ANALYSIS_TASKQUEUE = 'build-failure-analysis-queue'

_MEMCACHE_ALERTS_KEY = 'FAILURE_ALERTS'
_MEMCACHE_ALERTS_EXPIRATION_SECONDS = 60 * 60


def _CacheAlerts(latest_alerts):
  compress_level = 9
  alert_data = zlib.compress(json.dumps(latest_alerts), compress_level)
  memcache.set(_MEMCACHE_ALERTS_KEY, alert_data,
               _MEMCACHE_ALERTS_EXPIRATION_SECONDS)


def _GetCachedAlerts():
  alert_data = memcache.get(_MEMCACHE_ALERTS_KEY)
  if not alert_data:  # pragma: no cover.
    return {
        'date': 0,
        'build_failures': {},
    }

  return json.loads(zlib.decompress(alert_data))


class MonitorAlerts(BaseHandler):
  """Monitors alerts in Sheriff-O-Matic and triggers analysis automatically.

  This handler is to pull the latest alerts from Sheriff-O-Matic, compare to
  the cached alerts from last run, and then trigger analysis of new build
  failures.

  It is mainly to be called by a Cron job. A logged-in admin could also trigger
  a run by navigating to the url directly.
  """

  PERMISSION_LEVEL = Permission.ADMIN

  HTTP_CLIENT = HttpClientAppengine()

  def HandleGet(self):
    latest_alerts = alerts.GetLatestAlerts(self.HTTP_CLIENT)
    if not latest_alerts:  # pragma: no cover.
      logging.warn('Failed to pull latest alerts.')
      return

    cached_alerts = _GetCachedAlerts()

    latest_alert_date = latest_alerts['date']
    if cached_alerts['date'] >= latest_alert_date:  # pragma: no cover.
      logging.info('Cached alerts is up-to-date.')
      return

    latest_build_failures = alerts.GetBuildFailureAlerts(latest_alerts)

    new_build_failures = alerts.GetNewFailures(
        latest_build_failures, cached_alerts['build_failures'])

    for master_name, builders in new_build_failures.iteritems():
      for builder_name, build_number in builders.iteritems():
        build_failure_analysis_pipelines.ScheduleAnalysisIfNeeded(
            master_name, builder_name, build_number,
            force=True, queue_name=_BUILD_FAILURE_ANALYSIS_TASKQUEUE)

    _CacheAlerts({
        'date': latest_alert_date,
        'build_failures': latest_build_failures,
    })
