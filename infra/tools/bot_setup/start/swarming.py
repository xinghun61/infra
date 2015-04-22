# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Sets up and starts a Swarm slave."""

import os
import re
import requests


def is_canary(slave_name):
  return (
      slave_name.startswith('swarm-canary-') or
      re.match(r'^swarm[0-9]-c4$', slave_name))


def start(slave_name, root_dir):
  try:
    os.mkdir(os.path.join(root_dir, 'swarming'))
  except OSError:
    pass

  url = 'https://chromium-swarm.appspot.com'
  if is_canary(slave_name):
    url = 'https://chromium-swarm-dev.appspot.com'

  exec requests.get('%s/bootstrap' % url).text

  return 0

