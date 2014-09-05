# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# FIXME: Everything in this file belongs in gatekeeper_ng_config.py

import logging

from infra.tools.builder_alerts.buildbot import master_name_from_url

def excluded_builders(master_config):
  return master_config[0].get('*', {}).get('excluded_builders', set())


def tree_for_master(master_url, gatekeeper_trees_config):
  """Get the name of the tree for a given master url, or the master's name."""
  for tree_name, tree_config in gatekeeper_trees_config.iteritems():
    if master_url in tree_config['masters']:
      return tree_name
  return master_name_from_url(master_url)


def apply_gatekeeper_rules(alerts, gatekeeper, gatekeeper_trees):
  filtered_alerts = []
  for alert in alerts:
    master_url = alert['master_url']
    config = gatekeeper.get(master_url)
    if not config:
      # Unclear if this should be set or not?
      # alert['would_close_tree'] = False
      filtered_alerts.append(alert)
      continue
    if alert['builder_name'] in excluded_builders(config):
      continue
    alert['would_close_tree'] = would_close_tree(
        config, alert['builder_name'], alert['step_name'])
    alert['tree'] = tree_for_master(master_url, gatekeeper_trees)
    filtered_alerts.append(alert)
  return filtered_alerts


def fetch_master_urls(gatekeeper, args):
  # Currently using gatekeeper.json, but could use:
  # https://chrome-infra-stats.appspot.com/_ah/api#p/stats/v1/stats.masters.list
  master_urls = gatekeeper.keys()
  if args.master_filter:
    master_urls = [url for url in master_urls if args.master_filter not in url]
  return master_urls


def would_close_tree(master_config, builder_name, step_name):
  # FIXME: Section support should be removed:
  master_config = master_config[0]
  builder_config = master_config.get(builder_name, {})
  if not builder_config:
    builder_config = master_config.get('*', {})

  # close_tree is currently unused in gatekeeper.json but planned to be.
  close_tree = builder_config.get('close_tree', True)
  if not close_tree:
    logging.debug('close_tree is false')
    return False

  # Excluded steps never close.
  excluded_steps = set(builder_config.get('excluded_steps', []))
  if step_name in excluded_steps:
    logging.debug('%s is an excluded_step' % step_name)
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

  logging.debug('%s not in closing_steps: %s' % (step_name, closing_steps))
  return False
