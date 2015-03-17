# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" The functions in this module are to deal with failure alerts.

1. Pull latest alerts from Sheriff-O-Matic.
2. Extract build failures alerts out of data from Sheriff-O-Matic.
3. Extract new failures by comparing latest build failures with old ones.
"""

import collections
import json
import re

from waterfall import buildbot
from waterfall import masters


_ALERTS_SOURCE_URL = 'https://sheriff-o-matic.appspot.com/alerts'


def GetLatestAlerts(http_client):
  status_code, content = http_client.Get(_ALERTS_SOURCE_URL, timeout_seconds=10)
  if status_code != 200:
    return None

  try:
    return json.loads(content)
  except Exception:
    return None


def GetBuildFailureAlerts(alert_data):
  """Parses alerts from Sheriff-O-Matic and returns build-level failure alerts.

  Args:
    alert_data (dict): A dict containing the de-serialized data from
        https://sheriff-o-matic.appspot.com/alerts.

  Returns:
    A dict containing information about failures, of the following form:
    {
      'master_name': {
        'builder_name': {
          'earliest_build': 123,
          'latest_build': 125,
          'failed_steps': ['step1', 'step2', ...],
        },
        ...
      },
      ...
    }
  """
  failures = collections.defaultdict(dict)

  for alert in alert_data.get('alerts', []):
    master_name = buildbot.GetMasterNameFromUrl(alert['master_url'])

    if not (master_name and masters.MasterIsSupported(master_name)):
      continue

    builder_name = alert['builder_name']
    failing_build = alert['failing_build']
    last_failing_build = alert['last_failing_build']
    step_name = alert['step_name']

    builder_info = failures[master_name].get(builder_name)
    if not builder_info:
      failures[master_name][builder_name] = {
          'earliest_build': failing_build,
          'latest_build': last_failing_build,
          'failed_steps': [step_name],
      }
    else:
      if builder_info['earliest_build'] > failing_build:
        builder_info['earliest_build'] = failing_build
      if builder_info['latest_build'] < last_failing_build:
        builder_info['latest_build'] = last_failing_build
      if step_name not in builder_info['failed_steps']:
        builder_info['failed_steps'].append(step_name)
        builder_info['failed_steps'].sort()

  return failures


def GetNewFailures(failures, old_failures):
  """Returns new build failures after comparing current failures and old ones.

  Args:
    failures (dict): Current failures, as output by
        :func:`GetBuildFailureAlerts`.
    old_failures (dict): Old failures, as output by
        :func:`GetBuildFailureAlerts`.

  Returns:
    A dict of following form:
    {
      'master_name': {
        'builder_name': 124,  # Latest failed build number.
        ...
      },
      ...
    }
  """
  new_failures = collections.defaultdict(dict)

  for master_name, builders in failures.iteritems():
    for builder_name, build_info in builders.iteritems():
      old_build_info = old_failures.get(master_name, {}).get(builder_name)

      # Check if there is some new failure.
      if (old_build_info and
          old_build_info['latest_build'] == build_info['latest_build'] and
          old_build_info['failed_steps'] == build_info['failed_steps']):
        continue

      new_failures[master_name][builder_name] = build_info['latest_build']

  return new_failures
