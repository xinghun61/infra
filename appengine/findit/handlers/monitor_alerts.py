# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging

from base_handler import BaseHandler
from base_handler import Permission
from common.http_client_appengine import HttpClientAppengine
from waterfall import buildbot
from waterfall import build_failure_analysis_pipelines
from waterfall import waterfall_config


_ALERTS_SOURCE_URL = 'https://sheriff-o-matic.appspot.com/alerts'
_BUILD_FAILURE_ANALYSIS_TASKQUEUE = 'build-failure-analysis-queue'


def _GetLatestBuildFailures(http_client):
  """Returns latest build failures from alerts in Sheriff-o-Matic.

  Returns:
    A list of following form:
    [
      {
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 123,
        'failed_steps': ['a', 'b']
      },
      ...
    ]
  """
  status_code, content = http_client.Get(_ALERTS_SOURCE_URL, timeout_seconds=30)
  if status_code != 200:
    logging.error('Failed to pull alerts from Sheriff-o-Matic.')
    return []

  data = json.loads(content)
  alerts = data.get('alerts', [])

  # Explicit delete: sometimes the content pulled from SoM could be as big as
  # ~30MB and the parsed json result as big as 150+MB.
  del content
  del data

  # Alerts from Sheriff-o-Matic (indirectly from builder_alerts) are per-step,
  # or per-test etc. But analysis of build failures by Findit is per-build.
  # Thus use a dict to de-duplicate.
  build_failures = {}
  for alert in alerts:
    master_name = buildbot.GetMasterNameFromUrl(alert['master_url'])
    if not (master_name and waterfall_config.MasterIsSupported(master_name)):
      continue

    builder_name = alert['builder_name']
    build_number = alert['last_failing_build']
    key = '%s-%s-%d' % (master_name, builder_name, build_number)
    if key not in build_failures:
      build_failures[key] = {
          'master_name': master_name,
          'builder_name': builder_name,
          'build_number': build_number,
          'failed_steps': [alert['step_name']],
      }
    elif alert['step_name'] not in build_failures[key]['failed_steps']:
      build_failures[key]['failed_steps'].append(alert['step_name'])

  del alerts

  return build_failures.values()


class MonitorAlerts(BaseHandler):
  """Monitors alerts in Sheriff-O-Matic and triggers analysis automatically.

  This handler is to pull the latest alerts from Sheriff-O-Matic, and then
  schedule incremental analysis of new build failures if needed.

  A logged-in admin could trigger a run by navigating to the url directly.
  """

  PERMISSION_LEVEL = Permission.ADMIN

  HTTP_CLIENT = HttpClientAppengine()

  def HandleGet(self):
    build_failures = _GetLatestBuildFailures(self.HTTP_CLIENT)

    for build_failure in build_failures:
      build_failure_analysis_pipelines.ScheduleAnalysisIfNeeded(
          build_failure['master_name'],
          build_failure['builder_name'],
          build_failure['build_number'],
          failed_steps=build_failure['failed_steps'],
          force=False,
          queue_name=_BUILD_FAILURE_ANALYSIS_TASKQUEUE)
