# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Identifies mismatches between main waterfall builders and Findit trybots."""
import base64
from collections import defaultdict
import gzip
import io
import json
import os
import sys
import urllib
import urllib2


_REMOTE_API_DIR = os.path.join(os.path.dirname(__file__), os.path.pardir)
sys.path.insert(1, _REMOTE_API_DIR)

import remote_api
from model.wf_config import FinditConfig


NOT_AVAILABLE = 'N/A'


_MILO_RESPONSE_PREFIX = ')]}\'\n'
_MILO_MASTER_ENDPOINT = ('https://luci-milo.appspot.com/prpc/milo.Buildbot/'
                         'GetCompressedMasterJSON')


def _ProcessMiloData(data):
  if not data.startswith(_MILO_RESPONSE_PREFIX):
    return None
  data = data[len(_MILO_RESPONSE_PREFIX):]

  try:
    response_data = json.loads(data)
  except Exception:
    return None

  try:
    decoded_data = base64.b64decode(response_data.get('data'))
  except Exception:
    return None

  try:
    with io.BytesIO(decoded_data) as compressed_file:
      with gzip.GzipFile(fileobj=compressed_file) as decompressed_file:
        data_json = decompressed_file.read()
  except Exception:
    return None

  return json.loads(data_json)


def _GetBuilderList(master_name):
  try:
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    values = {'name': master_name}
    data = urllib.urlencode(values)
    req = urllib2.Request(_MILO_MASTER_ENDPOINT, None, headers)
    f = urllib2.urlopen(req, json.dumps(values), timeout=60)
  except Exception as e:
    print ('WARNING: Unable to reach builbot to retrieve trybot '
           'information')
    raise e

  data = _ProcessMiloData(f.read())
  return [bot for bot in data.get('builders', {}).keys()]

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

    try:
      main_waterfall_builders = _GetBuilderList(master)
    except Exception:
      print 'Data could not be retrieved for master %s. Skipping.' % master
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
      variable_builder = trybots[master][builder]['waterfall_trybot']
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
      variable_builder = builder_info['waterfall_trybot']
      variable_builders_in_config.add(variable_builder)

  for tryserver in tryservers:
    print 'Tryserver: %s' % tryserver

    try:
      tryserver_builders = _GetBuilderList(tryserver)
    except Exception:
      print 'Data could not be retrieved for %s' % tryserver
      print
      continue

    any_unused = False
    for builder in tryserver_builders:
      if ('variable' in builder and 'deflake' not in builder and builder not in
          variable_builders_in_config):
        print '\'%s\' is unused.' % builder
        any_unused = True

    if not any_unused:
      print 'OK'

    print
