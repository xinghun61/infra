# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Identifies mismatches between main waterfall builders and Findit trybots."""
from collections import defaultdict
import json
import os
import sys

from google.appengine.api import urlfetch

_REMOTE_API_DIR = os.path.join(os.path.dirname(__file__), os.path.pardir)
sys.path.insert(1, _REMOTE_API_DIR)

import remote_api
from model.wf_config import FinditConfig


BUILDER_URL_TEMPLATE = 'http://build.chromium.org/p/%s/json/builders'
NOT_AVAILABLE = 'N/A'


if __name__ == '__main__':
  remote_api.EnableRemoteApi(app_id='findit-for-me')

  trybots = FinditConfig.Get().builders_to_trybots
  steps_for_masters_rules = FinditConfig.Get().steps_for_masters_rules
  main_waterfall_cache = {}
  variable_builders_cache = defaultdict(list)
  tryservers = set()

  print 'Determining missing support...'

  supported_masters = steps_for_masters_rules.get(
      'supported_masters', {}).keys()
  for master in supported_masters:
    print 'Master: %s' % master

    if not trybots.get(master):
      print 'Not found. Tryjobs for %s may not be supported.' % master
      print
      continue

    json_url = BUILDER_URL_TEMPLATE % master
    try:
      result = urlfetch.fetch(json_url, deadline=60)
      main_waterfall_builders = json.loads(result.content).keys()
    except Exception:
      print 'Data could not be retrieved from %s. Skipping.' % json_url
      print
      main_waterfall_cache[master] = NOT_AVAILABLE
      continue

    # Cache the results for later when checking for deprecated trybots.
    main_waterfall_cache[master] = main_waterfall_builders

    any_missing = False
    for builder in main_waterfall_builders:
      if builder not in trybots[master]:
        any_missing = True
        print '\'%s\' is missing.' % builder
        continue

      # Cache the variable builders in use for determining if any should be
      # deprecated.
      tryserver = trybots[master][builder]['mastername']
      tryservers.add(tryserver)
      variable_builder = trybots[master][builder]['buildername']
      variable_builders_cache[variable_builder].append(
          {
              'master': master,
              'builder': builder
          })

    if not any_missing:
      print 'OK'

    print

  print 'Determining deprecated bots...'

  for master, trybot_mapping in trybots.iteritems():
    print 'Master: %s' % master

    any_deprecated = False
    if master not in supported_masters:
      print '\'%s\' is deprecated.' % master
      any_deprecated = False
    elif main_waterfall_cache.get(master) == NOT_AVAILABLE:
      print 'Unable to determine support. Skipping.'
      print
      continue

    for builder in trybot_mapping.keys():
      if builder not in main_waterfall_cache.get(master, []):
        print '\'%s\' is deprecated.' % builder
        any_deprecated = True

    if not any_deprecated:
      print 'OK'

    print

  print 'Determining unused variable builders...'

  # Keep track of all variable builders in config.
  variable_builders_in_config = set()
  for master, builders in trybots.iteritems():
    for builder_info in builders.values():
      variable_builder = builder_info['buildername']
      variable_builders_in_config.add(variable_builder)

  for tryserver in tryservers:
    print 'Tryserver: %s' % tryserver

    json_url = BUILDER_URL_TEMPLATE % tryserver
    try:
      result = urlfetch.fetch(json_url, deadline=60)
      tryserver_builders = json.loads(result.content).keys()
    except Exception:
      print 'Data could not be retrieved from %s' % json_url
      print
      continue

    any_unused = False
    for builder in tryserver_builders:
      if 'variable' in builder and builder not in variable_builders_in_config:
        print '\'%s\' is unused.' % builder
        any_unused = True

    if not any_unused:
      print 'OK'

    print
