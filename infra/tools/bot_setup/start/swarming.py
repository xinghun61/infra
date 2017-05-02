# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Sets up and starts a Swarming bot."""

import os
import re
import shutil
import sys

import requests


def is_staging(hostname):
  return (
      hostname.startswith('swarm-staging-') or
      re.match(r'^swarm[0-9]-c4$', hostname))


def is_internal(hostname):
  return hostname.startswith('swarm-cros-')


def start(hostname, root_dir):
  host_url = 'https://chromium-swarm.appspot.com'
  if is_staging(hostname):
    host_url = 'https://chromium-swarm-dev.appspot.com'
  elif is_internal(hostname):
    host_url = 'https://chrome-swarming.appspot.com'

  # Kill previous known bot location.
  if sys.platform != 'win32' and os.path.isdir('/b/swarm_slave'):
    shutil.rmtree('/b/swarm_slave', ignore_errors=True)

  bot_root = os.path.join(root_dir, 'swarming')
  if not os.path.isdir(bot_root):
    os.makedirs(bot_root)

  zip_file = os.path.join(bot_root, 'swarming_bot.zip')

  # 'stream=True' was known to have issues with GAE. Bot code is not large, it's
  # fine to download it in memory.
  r = requests.get('%s/bot_code' % host_url, stream=False)
  r.raise_for_status()
  with open(zip_file, 'wb') as f:
    f.write(r.content)

  os.environ['SWARMING_EXTERNAL_BOT_SETUP'] = '1'
  os.execv(sys.executable, [sys.executable, zip_file])
