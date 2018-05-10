# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Sets up and starts a Swarming bot."""

import os
import re
import sys
import time

import requests

from .util import rmtree


def is_staging(hostname):
  return (
      hostname.startswith('swarm-staging-') or
      hostname == 'swarm0-c4')


def is_internal(hostname):
  return (
      hostname.startswith('swarm-cros-') or
      re.match(r'^swarm[0-9]+-c7$', hostname))


def get_access_token():
  r = requests.get(
      url='http://169.254.169.254/computeMetadata/v1/instance'
          '/service-accounts/default/token',
      headers={'Metadata-Flavor': 'Google'})
  r.raise_for_status()
  return r.json()['access_token']


def start(hostname, root_dir):
  while 'docker' in hostname:
    time.sleep(300)  # docker bots are initialized via puppet

  host_url = 'https://chromium-swarm.appspot.com'
  if is_staging(hostname):
    host_url = 'https://chromium-swarm-dev.appspot.com'
  elif is_internal(hostname):
    host_url = 'https://chrome-swarming.appspot.com'

  # Kill previous known bot location.
  if sys.platform != 'win32' and os.path.isdir('/b/swarm_slave'):
    rmtree('/b/swarm_slave', ignore_errors=True)

  bot_root = os.path.join(root_dir, 'swarming')
  if not os.path.isdir(bot_root):
    os.makedirs(bot_root)

  zip_file = os.path.join(bot_root, 'swarming_bot.zip')

  # 'stream=True' was known to have issues with GAE. Bot code is not large, it's
  # fine to download it in memory.
  r = requests.get(
      url='%s/bot_code' % host_url,
      headers={'Authorization': 'Bearer %s' % get_access_token()},
      stream=False)
  r.raise_for_status()
  with open(zip_file, 'wb') as f:
    f.write(r.content)

  # Use system python (or the depot_tools one on Windows) instead of the one
  # with infra_python virtual environment. We don't want this environment
  # leaking into the Swarming. Also it doesn't have win32 packages needed by
  # Swarming (they are present in depot_tools python).
  python = sys.executable
  if sys.platform.startswith('linux'):
    python = '/usr/bin/python'
  elif sys.platform.startswith('win'):
    python = 'c:\\setup\\depot_tools\\python.bat'

  os.environ['SWARMING_EXTERNAL_BOT_SETUP'] = '1'
  os.execv(python, [python, zip_file])
