# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Determines support level for different steps for masters."""

from model import wf_config

# Explicitly list unsupported masters. Additional work might be needed in order
# to support them.
_UNSUPPORTED_MASTERS = [
    'chromium.lkgr',  # Disable as results are not showed on Sheriff-o-Matic.
    'chromium.gpu',  # Disable as too many false positives.

    'chromium.memory.fyi',
    'chromium.gpu.fyi',

    'chromium.perf',
]


def MasterIsSupported(master_name):
  """Return True if the given master is supported, otherwise False."""
  return master_name in wf_config.Settings().masters_to_blacklisted_steps.keys()


def StepIsSupportedForMaster(step_name, master_name):
  """Determines whether or not a step is supported for the given build master.

  Args:
    step_name: The name of the step to check.
    master_name: The name of the build master to check.

  Returns:
    True if Findit supports analyzing the failure, False otherwise. If a master
    is not supported, then neither are any of its steps.
  """
  config = wf_config.Settings()
  masters_to_blacklisted_steps = config.masters_to_blacklisted_steps
  blacklisted_steps = masters_to_blacklisted_steps.get(master_name)
  if blacklisted_steps is None:
    return False

  return step_name not in blacklisted_steps


def GetTrybotForWaterfallBuilder(wf_mastername, wf_buildername):
  """Returns trybot mastername and buildername for the given waterfall builder.

  Args:
    wf_mastername: The mastername of a waterfall builder.
    wf_buildername: The buildername of a waterfall builder.

  Returns:
    (tryserver_mastername, tryserver_buildername)
    The trybot mastername and buildername to re-run compile in exactly the same
    configuration as the given waterfall builder. If the given waterfall builder
    is not supported yet, (None, None) is returned instead.
  """
  config = wf_config.Settings()
  trybot_config = config.builders_to_trybots.get(
      wf_mastername, {}).get(wf_buildername, {})
  return trybot_config.get('mastername'), trybot_config.get('buildername')
