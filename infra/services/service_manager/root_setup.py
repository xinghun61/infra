# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import os
import subprocess
import sys

UPSTART_CONFIG_FILENAME = '/etc/init/service_manager.conf'
UPSTART_CONFIG = """
start on runlevel [2345]
stop on runlevel [!2345]

respawn
respawn limit unlimited
post-stop exec sleep 60  # Don't respawn too fast.

pre-start script
  if [ ! -d /var/run/infra-services ]; then
    mkdir -v /var/run/infra-services
    chown -v chrome-bot:chrome-bot /var/run/infra-services
  fi
end script

exec su -c "/usr/bin/python /opt/infra-python/run.py infra.services.service_manager" chrome-bot
"""

SERVICES_DIRECTORY = '/etc/infra-services'


def root_setup():
  """Performs one-off setup to install service_manager on this machine."""

  if os.getuid() != 0:
    logging.error('This command must be run as root')
    return 1

  # Create the config directory.
  try:
    os.mkdir(SERVICES_DIRECTORY)
  except OSError:
    pass

  # Write the upstart config and start the service.
  with open(UPSTART_CONFIG_FILENAME, 'w') as fh:
    fh.write(UPSTART_CONFIG)

  subprocess.check_call(['initctl', 'reload-configuration'])
  status = subprocess.check_output(['initctl', 'status', 'service_manager'])
  if 'start' not in status:
    subprocess.check_call(['initctl', 'start', 'service_manager'])
  return 0


def write_service(name, root_directory, tool, args):
  """Creates a config file to ensure service_manager starts the given service.

  Call this from your service's own --root-setup handler.
  """

  with open(os.path.join(SERVICES_DIRECTORY, '%s.json' % name), 'w') as fh:
    json.dump({
      'name': name,
      'root_directory': root_directory,
      'tool': tool,
      'args': args,
    }, fh)
