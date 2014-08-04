# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# FIXME: Everything in this file belongs in gatekeeper_ng_config.py

import logging

# Python logging is stupidly verbose to configure.
def setup_logging():
  logger = logging.getLogger(__name__)
  logger.setLevel(logging.DEBUG)
  handler = logging.StreamHandler()
  handler.setLevel(logging.DEBUG)
  formatter = logging.Formatter('%(levelname)s: %(message)s')
  handler.setFormatter(formatter)
  logger.addHandler(handler)
  return logger, handler


log, logging_handler = setup_logging()


def excluded_builders(master_config):
  return master_config[0].get('*', {}).get('excluded_builders', set())


# pylint: disable=C0301
# FIXME: This is currently baked into:
# https://chromium.googlesource.com/chromium/tools/build/+/master/scripts/slave/gatekeeper_launch.py
# http://crbug.com/394961
MASTER_CONFIG = {
  'chromium-status': [
    'chromium',
    'chromium.chrome',
    'chromium.chromiumos',
    'chromium.gpu',
    'chromium.linux',
    'chromium.mac',
    'chromium.memory',
    'chromium.win',
  ],
  'blink-status': [
    'chromium.webkit',
  ],
}


def tree_for_master(master_name):
  for tree_name, master_names in MASTER_CONFIG.items():
    if master_name in master_names:
      return tree_name


def would_close_tree(master_config, builder_name, step_name):
  # FIXME: Section support should be removed:
  master_config = master_config[0]
  builder_config = master_config.get(builder_name, {})
  if not builder_config:
    builder_config = master_config.get('*', {})

  # close_tree is currently unused in gatekeeper.json but planned to be.
  close_tree = builder_config.get('close_tree', True)
  if not close_tree:
    log.debug('close_tree is false')
    return False

  # Excluded steps never close.
  excluded_steps = set(builder_config.get('excluded_steps', []))
  if step_name in excluded_steps:
    log.debug('%s is an excluded_step' % step_name)
    return False

  # See gatekeeper_ng_config.py for documentation of
  # the config format.
  # forgiving/closing controls if mails are sent on close.
  # steps/optional controls if step-absence indicates failure.
  # this function assumes the step is present and failing
  # and thus doesn't care between these 4 types:
  closing_steps = (builder_config.get('forgiving_steps', set()) |
    builder_config.get('forgiving_optional', set()) |
    builder_config.get('closing_steps', set()) |
    builder_config.get('closing_optional', set()))

  # A '*' in any of the above types means it applies to all steps.
  if '*' in closing_steps:
    return True

  if step_name in closing_steps:
    return True

  log.debug('%s not in closing_steps: %s' % (step_name, closing_steps))
  return False
