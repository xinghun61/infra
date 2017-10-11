# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict

from common.findit_http_client import FinditHttpClient
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission

from model.wf_config import FinditConfig
from waterfall import buildbot


def _GetSupportedMasters():
  """Lists the supported main waterfall masters Findit runs analyses on."""
  return FinditConfig.Get().steps_for_masters_rules.get('supported_masters',
                                                        {}).keys()


def _GetBuildersOnMasters(masters, http_client):
  """Returns a dict of masters mapped to lists of their builders."""
  builders = {}
  for master in masters:
    builders[master] = buildbot.ListBuildersOnMaster(master, http_client)
  return builders


def _GetCoveredBuilders(trybot_config):
  """Returns a dict mapping masters to lists of builders covered in config."""
  covered_builders = {}
  for master, builders in trybot_config.iteritems():
    covered_builders[master] = builders.keys()
  return covered_builders


def _GetDiffBetweenDicts(trybots_1, trybots_2):
  """Returns a dict of masters on trybots_2: builders not in trybots_2."""
  missing = defaultdict(list)
  for master, builders in trybots_1.iteritems():
    trybots_2_builders = trybots_2.get(master, [])
    missing_builders = list(set(builders) - set(trybots_2_builders))
    if missing_builders:
      missing[master] = missing_builders
  return missing


def _GetAllTryservers(trybot_config):
  """Returns a list of unique tryservers used in config."""
  all_tryservers = set()
  for builders in trybot_config.itervalues():
    for config in builders.itervalues():
      tryserver = config.get('mastername')
      all_tryservers.add(tryserver)
  return list(all_tryservers)


def _GetAllFinditBuildersOnTryservers(tryservers, http_client):
  """Returns a dict of variable builders on tryservers."""
  tryserver_builders = defaultdict(list)
  for tryserver in tryservers:
    builders = buildbot.ListBuildersOnMaster(tryserver, http_client)
    for builder in builders:
      if 'variable' in builder:
        # Findit's trybots all have 'variable' in the name,
        tryserver_builders[tryserver].append(builder)
  return tryserver_builders


def _GetAllBuildersInConfig(trybot_config):
  """Returns a list of all variable builders referenced in config."""
  all_config_builders = set()
  for builders in trybot_config.itervalues():
    for builder in builders.itervalues():
      waterfall_builder = builder.get('waterfall_trybot')
      flake_builder = builder.get('flake_trybot')
      all_config_builders.add(waterfall_builder)
      all_config_builders.add(flake_builder)
  return list(all_config_builders)


def _GetUnusedVariableBuilders(trybot_config, http_client):
  """Gets a dict of unused variable builders in config."""
  all_tryservers = _GetAllTryservers(trybot_config)
  all_tryserver_builders = _GetAllFinditBuildersOnTryservers(
      all_tryservers, http_client)
  all_config_builders = _GetAllBuildersInConfig(trybot_config)
  unused_variable_builders = defaultdict(list)

  for tryserver, builders in all_tryserver_builders.iteritems():
    for _ in builders:
      unused_builders = list(set(builders) - set(all_config_builders))
      if unused_builders:
        unused_variable_builders[tryserver] = unused_builders

  return unused_variable_builders


class CheckTrybotMapping(BaseHandler):
  """Checks the coverage of main waterfall masters/builders against config."""

  PERMISSION_LEVEL = Permission.ADMIN

  def HandleGet(self):
    http_client = FinditHttpClient()
    supported_masters = _GetSupportedMasters()
    main_waterfall_builders = _GetBuildersOnMasters(supported_masters,
                                                    http_client)
    trybot_config = FinditConfig.Get().builders_to_trybots
    covered_builders = _GetCoveredBuilders(trybot_config)
    missing_builders = _GetDiffBetweenDicts(main_waterfall_builders,
                                            covered_builders)
    deprecated_builders = _GetDiffBetweenDicts(covered_builders,
                                               main_waterfall_builders)
    unused_variable_builders = _GetUnusedVariableBuilders(
        trybot_config, http_client)

    return {
        'template': 'check_trybot_mapping.html',
        'data': {
            'missing': missing_builders,
            'deprecated': deprecated_builders,
            'unused_variable_builders': unused_variable_builders
        }
    }
