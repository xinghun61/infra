# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from common.waterfall import buildbucket_client
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from gae_libs.http.http_client_appengine import HttpClientAppengine
from waterfall import swarming_util

_FINDIT_SWARMING_POOL = 'Chrome.Findit'
_TARGET_MASTER = 'luci.chromium.try'
_PLATFORM_BUILDER_MAP = {
    'Linux': 'LUCI linux_chromium_variable',
    'Mac': 'LUCI mac_chromium_variable',
    'Windows': 'LUCI win_chromium_variable',
}
_PLATFORM_CACHE_NAME_MAP = {
    'Linux': swarming_util.GetCacheName('chromium.linux', 'Linux Builder'),
    'Mac': swarming_util.GetCacheName('chromium.mac', 'Mac Builder'),
    'Windows': swarming_util.GetCacheName('chromium.win', 'Win Builder'),
}
_BOT_UPDATE_RECIPE = 'findit/chromium/preemptive_bot_update'


def _BotUpdateTryJob(bot_id, platform):
  builder_name = _PLATFORM_BUILDER_MAP[platform]
  cache_name = _PLATFORM_CACHE_NAME_MAP[platform]

  return buildbucket_client.TryJob(
      _TARGET_MASTER,
      builder_name,
      None,  # revision.
      {'recipe': _BOT_UPDATE_RECIPE},  # properties.
      [],  # tags.
      None,  # additional_build_parameters.
      cache_name,
      ['id:%s' % bot_id, 'pool:%s' % _FINDIT_SWARMING_POOL])  # dimensions.


def _TriggerUpdateJobs():
  tryjobs = []
  http_client = HttpClientAppengine()
  for os_name in _PLATFORM_BUILDER_MAP:
    dimensions = ['pool:%s' % _FINDIT_SWARMING_POOL, 'os:%s' % os_name]
    bots = swarming_util.GetBotsByDimension(dimensions, http_client)
    for b in swarming_util.OnlyAvailable(bots):
      tryjobs.append(_BotUpdateTryJob(b['bot_id'], os_name))
  return buildbucket_client.TriggerTryJobs(tryjobs)


def _LogResults(results):
  for error, build in results:
    if error:
      logging.error('Failed to trigger periodic bot update due to %s',
                    error.reason)
      logging.error('Buildbucket failure message: %s' % error.message)
    else:
      logging.info('Triggered periodic bot update '
                   'cr-buildbucket.appspot.com/b/%s', build.id)


class PeriodicBotUpdate(BaseHandler):
  """Triggers bot update jobs on idle swarming bots in the Findit pool."""
  PERMISSION_LEVEL = Permission.APP_SELF

  def HandleGet(self):
    results = _TriggerUpdateJobs()
    _LogResults(results)
    return {
        'data': {
            'builds': [build.response for error, build in results if not error],
            'errors': [error.response for error, build in results if error]
        }
    }
