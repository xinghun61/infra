# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from common import chromium_deps
from waterfall.base_pipeline import BasePipeline


def _GetOSPlatformName(master_name, builder_name):  # pragma: no cover
  """Returns the OS platform name based on the master and builder."""
  # TODO: make buildbot yield OS platform name as a build property and use it.
  # The code below is just a workaround.
  builder_name = builder_name.lower()
  if master_name == 'chromium.win':
    return 'win'
  elif master_name == 'chromium.linux':
    if 'android' in builder_name:
      return 'android'
    else:
      return 'unix'
  elif master_name == 'chromium.chromiumos':
    return 'unix'
  else:
    os_map = {
        'win': 'win',
        'linux': 'unix',
        'chromiumos': 'unix',
        'chromeos': 'unix',
        'android': 'android',
        'mac': 'mac',
        'ios': 'ios',
    }
    for os_name in os_map.keys():
      if os_name in builder_name:
        return os_map[os_name]

    logging.warn('Failed to detect the OS platform of builder "%s".',
                 builder_name)
    return 'all'  # Default to all platform.


def _GetDependencies(chromium_revision, os_platform):
  """Returns the dependencies used by the specified chromium revision."""
  deps = {}
  for path, dependency in chromium_deps.GetChromeDependency(
      chromium_revision, os_platform).iteritems():
    deps[path] = {
        'repo_url': dependency.repo_url,
        'revision': dependency.revision,
    }

  return deps


def _DetectDEPSRolls(change_logs, os_platform):
  """Detect DEPS rolls in the given CL change logs.

  Args:
    change_logs (dict): Output of pipeline PullChangelogPipeline.run().

  Returns:
    A dict in the following form:
    {
      'git_revision': [
        {
          'path': 'src/path/to/dependency/',
          'repo_url': 'https://url/to/dependency/repo.git',
          'new_revision': 'git_hash1',
          'old_revision': 'git_hash2',
        },
        ...
      ],
      ...
    }
  """
  deps_rolls = {}
  for revision, change_log in change_logs.iteritems():
    # Check DEPS roll only if the chromium DEPS file is changed by the CL.
    for touched_file in change_log['touched_files']:
      if touched_file['new_path'] == 'DEPS':
        # In git, r^ refers to the previous revision of r.
        old_revision = '%s^' % revision
        rolls = chromium_deps.GetChromiumDEPSRolls(
            old_revision, revision, os_platform)
        deps_rolls[revision] = [roll.ToDict() for roll in rolls]
        break

  return deps_rolls


class ExtractDEPSInfoPipeline(BasePipeline):
  """A pipeline to extract information of DEPS and dependency rolls."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, failure_info, change_logs):
    """
    Args:
      failure_info (dict): Output of pipeline DetectFirstFailurePipeline.run().
      change_logs (dict): Output of pipeline PullChangelogPipeline.run().

    Returns:
      A dict with the following form:
      {
        'deps': {
          'path/to/dependency/': {
            'revision': 'git_hash',
            'repo_url': 'https://url/to/dependency/repo.git',
          },
          ...
        },
        'deps_rolls': {
          'git_revision': [
            {
              'path': 'src/path/to/dependency/',
              'repo_url': 'https://url/to/dependency/repo.git',
              'new_revision': 'git_hash1',
              'old_revision': 'git_hash2',
            },
            ...
          ],
          ...
        }
      }
    """
    if not failure_info['failed'] or not failure_info['chromium_revision']:
      # Bail out if no failed step or no chromium revision.
      return {'deps':{}, 'deps_rolls': {}}

    chromium_revision = failure_info['chromium_revision']
    os_platform = _GetOSPlatformName(
        failure_info['master_name'], failure_info['builder_name'])

    return {
        'deps': _GetDependencies(chromium_revision, os_platform),
        'deps_rolls': _DetectDEPSRolls(change_logs, os_platform)
    }
