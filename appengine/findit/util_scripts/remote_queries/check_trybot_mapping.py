# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Identifies mismatches between main waterfall builders and Findit trybots."""
from collections import defaultdict
import json
import os
import sys

_FINDIT_DIR = os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)
sys.path.insert(1, _FINDIT_DIR)
# Active script for Findit production.
from local_libs import remote_api
remote_api.EnableFinditRemoteApi()

from common.findit_http_client import FinditHttpClient
from common.swarmbucket import swarmbucket
from infra_api_clients import http_client_util
from model.wf_config import FinditConfig


def _GetCIBuilders():
  """Gets CI builders' information in a format like:

  {
    'Linux Tests': {
      'os': 'Ubuntu-16.04',
      'cpu': 'x86-64',
      ...
    },
    ...
  }
  """

  def get_dimensions_list(dimensions):
    dimension_dict = {}
    for dimension in dimensions:
      d_key, d_value = dimension.split(':', 1)
      dimension_dict[d_key] = d_value
    return dimension_dict

  all_builders = {}

  builders = swarmbucket.GetBuilders('luci.chromium.ci')
  for builder, builder_info in builders.iteritems():
    all_builders[builder] = get_dimensions_list(
        builder_info.get('swarming_dimensions'))
  return all_builders


def _GetBotsInPool(pool='luci.chromium.findit'):
  """Gets bots in the requested pool in the format like:

  {
    'vm1xxx': {
      'os': ['Linux', 'Ubuntu', 'Ubuntu-16.04'],
      'cpu': ['x86', 'x86-64']
    }
  }

  """
  bot_list_url = (
      'https://chromium-swarm.appspot.com/_ah/api/swarming/v1/bots/list?'
      'dimensions=pool:{}'.format(pool))
  content, error = http_client_util.SendRequestToServer(bot_list_url,
                                                        FinditHttpClient())
  if error or not content:
    return None
  content_dict = json.loads(content)
  bots_in_pool = {}
  for item in content_dict.get('items', []):
    dimensions = {d['key']: d['value'] for d in item.get('dimensions')}
    bots_in_pool[item.get('bot_id')] = dimensions

  return bots_in_pool


def _GetBuildersInMaster(master_name):
  url = (
      'https://luci-migration.appspot.com/masters/{master}/?format=json'.format(
          master=master_name))
  content, error = http_client_util.SendRequestToServer(url, FinditHttpClient())
  if error or not content:
    return None
  content_dict = json.loads(content)
  return content_dict.get('builders').keys()


def _GetSupportingFinditBots(builder_dimensions, bots_in_pool):
  return [
      bot_id for bot_id, bot_dims in bots_in_pool.iteritems()
      if all(d_value in bot_dims[d_key]
             for d_key, d_value in builder_dimensions.iteritems()
             if d_key in ('os', 'cpu'))
  ]


if __name__ == '__main__':
  ci_builders = _GetCIBuilders()
  findit_bots = _GetBotsInPool()

  steps_for_masters_rules = FinditConfig.Get().steps_for_masters_rules
  supported_masters = steps_for_masters_rules.get('supported_masters',
                                                  {}).keys()

  used_findit_bots = set()
  for master in sorted(supported_masters):
    if master not in supported_masters:
      print 'Master: %s not supported.' % master
      print
      continue

    builders_in_master = _GetBuildersInMaster(master)
    print 'Master: %s' % master
    not_supported_builders = {}
    for builder_name in sorted(builders_in_master):
      swarming_dimensions = ci_builders.get(builder_name)
      if not swarming_dimensions:
        print '{}/{} not found in ci_builders.'.format(master, builder_name)
        continue
      supporting_findit_bots = _GetSupportingFinditBots(swarming_dimensions,
                                                        findit_bots)
      if not supporting_findit_bots:
        not_supported_builders[builder_name] = swarming_dimensions
      else:
        used_findit_bots |= set(supporting_findit_bots)
        print builder_name, ':', supporting_findit_bots
    print
    if not_supported_builders:
      print 'Not supported builders:'
      print json.dumps(not_supported_builders, indent=2)
    else:
      print 'OK.'
    print

  unused_bots = set(findit_bots.keys()) - used_findit_bots
  print 'Unused Findit builders:'
  print sorted(list(unused_bots))
