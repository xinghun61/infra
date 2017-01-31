# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Determines support level for different steps for masters."""

from model.wf_config import FinditConfig

# Explicitly list unsupported masters. Additional work might be needed in order
# to support them.
_UNSUPPORTED_MASTERS = [
    'chromium.lkgr',  # Disable as results are not showed on Sheriff-o-Matic.
    'chromium.gpu',  # Disable as too many false positives.

    'chromium.memory.fyi',
    'chromium.gpu.fyi',

    'chromium.perf',
]


def _ConvertOldMastersFormatToNew(masters_to_blacklisted_steps):
  """Converts the old masters format to the new rules dict.

  Args:
    masters_to_blacklisted_steps: A dict in the format:
    {
        'master1': ['step1', 'step2', ...],
        'master2': ['step3', 'step4', ...]
    }

  Returns:
    A dict in the latest rules dict format:
    {
        'supported_masters': {
            'master1': {
                'unsupported_steps: ['step1', 'step2', ...], (if any)
            }
        },
        'global': {}
    }
  """
  supported_masters = {}
  steps_for_masters_rules_in_latest_format = {
      'supported_masters': supported_masters,
      'global': {}
  }

  for master, unsupported_steps in masters_to_blacklisted_steps.iteritems():
    supported_masters[master] = {}
    if unsupported_steps:
      supported_masters[master]['unsupported_steps'] = unsupported_steps

  return steps_for_masters_rules_in_latest_format


def _ConvertOldTrybotFormatToNew(builders_to_trybots):
  """Converts the legacy trybot mapping format into the updated one.

  Args:
    builders_to_trybots (dict): A dict in the legacy format
        {
            'master': {
                'builder': {
                    'mastername': 'tryserver master name',
                    'buildername': 'waterfall_trybot',
                },
                ...
            },
            ...
        }

  Returns:
        {
            'master': {
                'builder': {
                    'mastername': 'tryserver master name',
                    'waterfall_trybot': 'waterfall_trybot',
                    'flake_trybot': 'flake_trybot'
                },
                ...
            },
            ...
        }
  """
  for builders in builders_to_trybots.itervalues():
    for trybot_mapping in builders.itervalues():
      trybot = trybot_mapping.get('buildername')
      if trybot:
        trybot_mapping.update({'waterfall_trybot': trybot})
        trybot_mapping.update({'flake_trybot': trybot})
        trybot_mapping.pop('buildername')
  return builders_to_trybots


def GetStepsForMastersRules(settings=None, version=None):
  if settings is None:
    settings = FinditConfig.Get(version)
  return (settings.steps_for_masters_rules or
          _ConvertOldMastersFormatToNew(settings.masters_to_blacklisted_steps))


def MasterIsSupported(master_name):
  """Returns ``True`` if the given master is supported, otherwise ``False``."""
  return master_name in GetStepsForMastersRules()['supported_masters']


def StepIsSupportedForMaster(step_name, master_name):
  """Determines whether or not a step is supported for the given build master.

  Args:
    step_name: The name of the step to check.
    master_name: The name of the build master to check.

  Returns:
    True if Findit supports analyzing the failure, False otherwise.
    Rules:
      1. If a master is not supported, then neither are any of its steps.
      2. If a master specifies check_global = True, then all of its steps are
         supported except those according to those blacklisted under global.
      3. If a master specifies check_global = True, but also specifies a
         supported_steps, then supported_steps is to override any blacklisted
         steps under global.
      4. If a master specifies check_global = True, but also species its own
         unsupported_list, those unsupported_steps are in addition to those
         under global.
      5. If a master specifies check_global = False, then all steps under
         'supported_steps' are always supported and nothing else.
         'unsupported_steps' is not allowed.
  """
  if not MasterIsSupported(master_name):
    return False

  steps_for_masters_rules = GetStepsForMastersRules()
  supported_masters = steps_for_masters_rules['supported_masters']

  supported_master = supported_masters[master_name]
  check_global = supported_master.get('check_global', True)

  if not check_global:
    supported_steps = supported_master['supported_steps']
    return step_name in supported_steps

  supported_steps = supported_master.get('supported_steps', [])
  unsupported_steps = supported_master.get('unsupported_steps', [])
  global_unsupported_steps = (
      steps_for_masters_rules['global'].get('unsupported_steps', []))

  return (step_name in supported_steps or
          (step_name not in unsupported_steps and
           step_name not in global_unsupported_steps))


def GetFlakeTrybot(wf_mastername, wf_buildername):
  """Returns tryserver master and builder for running flake try jobs.

  Args:
    wf_mastername: The mastername of a waterfall builder.
    wf_buildername: The buildername of a waterfall builder.

  Returns:
    (tryserver_mastername, tryserver_buildername)
    The trybot mastername and buildername to re-run flake try jobs, or
    (None, None) if not supported.
  """
  trybot_config = _ConvertOldTrybotFormatToNew(
      FinditConfig.Get().builders_to_trybots)
  bot_dict = trybot_config.get(wf_mastername, {}).get(wf_buildername, {})
  return bot_dict.get('mastername'), bot_dict.get('flake_trybot')


def GetWaterfallTrybot(wf_mastername, wf_buildername):
  """Returns tryserver master and builder for running reliable failure try jobs.

  Args:
    wf_mastername: The mastername of a waterfall builder.
    wf_buildername: The buildername of a waterfall builder.

  Returns:
    (tryserver_mastername, tryserver_buildername)
    The trybot mastername and buildername to rerun reliable failures
    (compile/test) in exactly the same configuration as the given main waterfall
    builder. If the given waterfall builder is not supported yet, (None, None)
    is returned.
  """
  trybot_config = _ConvertOldTrybotFormatToNew(
      FinditConfig.Get().builders_to_trybots)
  bot_dict = trybot_config.get(wf_mastername, {}).get(wf_buildername, {})
  return bot_dict.get('mastername'), bot_dict.get('waterfall_trybot')


def EnableStrictRegexForCompileLinkFailures(wf_mastername, wf_buildername):
  """Returns True if strict regex should be used for the given builder."""
  trybot_config = FinditConfig.Get().builders_to_trybots.get(
      wf_mastername, {}).get(wf_buildername, {})
  return trybot_config.get('strict_regex', False)


def ShouldSkipTestTryJobs(wf_mastername, wf_buildername):
  """Returns True if test try jobs should be triggered.

    By default, test try jobs should be supported unless the master/builder
    specifies to bail out.

  Args:
    wf_mastername: The mastername of a waterfall builder.
    wf_buildername: The buildername of a waterfall builder.

  Returns:
    True if test try jobs are to be skipped, False otherwise.
  """
  trybot_config = FinditConfig.Get().builders_to_trybots.get(
      wf_mastername, {}).get(wf_buildername, {})
  return trybot_config.get('not_run_tests', False)


def GetTryJobSettings():
  return FinditConfig().Get().try_job_settings


def GetSwarmingSettings():
  return FinditConfig().Get().swarming_settings


def GetDownloadBuildDataSettings():
  return FinditConfig().Get().download_build_data_settings


def GetActionSettings():
  return FinditConfig().Get().action_settings


def GetCheckFlakeSettings():
  return FinditConfig().Get().check_flake_settings
