# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for deps_related operations.

It provides functions to:
  * Get os platform name based on master_name and builder_name
  * Get dependencies used by the specified chromium revision
  * Get DEPS rolls in the given CL change logs
"""

import logging


def GetOSPlatformName(master_name, builder_name):
  """Returns the OS platform name based on the master and builder."""
  # TODO: make buildbot yield OS platform name as a build property and use it.
  # The code below is just a workaround.
  builder_name = builder_name.lower()
  master_os_map = {
      'chromium.win': {
          'default': 'win'
      },
      'chromium.linux': {
          'android': 'android',
          'default': 'unix'
      },
      'chromium.chromiumos': {
          'default': 'unix'
      },
      'default': {
          'win': 'win',
          'linux': 'unix',
          'chromiumos': 'unix',
          'chromeos': 'unix',
          'android': 'android',
          'mac': 'mac',
          'ios': 'ios',
          'default': 'all',  # Default to all platform.
      }
  }

  os_map = master_os_map.get(master_name, master_os_map['default'])
  for os_name in os_map.keys():
    if os_name in builder_name:
      return os_map[os_name]

  if os_map == master_os_map['default']:
    logging.warning('Failed to detect the OS platform of builder "%s".',
                    builder_name)
  return os_map['default']


def GetDependencies(chromium_revision, os_platform, dep_fetcher):
  """Returns the dependencies used by the specified chromium revision."""
  deps_result = {}
  for path, dependency in dep_fetcher.GetDependency(chromium_revision,
                                                    os_platform).iteritems():
    deps_result[path] = {
        'repo_url': dependency.repo_url,
        'revision': dependency.revision,
    }

  return deps_result


def DetectDependencyRoll(revision, change_log, os_platform, dep_fetcher):
  """Detect DEPS roll in the given CL change log.

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
  # Check DEPS roll only if the chromium DEPS file is changed by the CL.
  for touched_file in change_log['touched_files']:
    if touched_file['new_path'] == 'DEPS':
      # In git, r^ refers to the previous revision of r.
      old_revision = '%s^' % revision
      rolls = dep_fetcher.GetDependencyRolls(old_revision, revision,
                                             os_platform)
      return [roll.ToDict() for roll in rolls]

  return []


def DetectDependencyRolls(change_logs, os_platform, dep_fetcher):
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
    roll = DetectDependencyRoll(revision, change_log, os_platform, dep_fetcher)
    if roll:
      deps_rolls[revision] = roll

  return deps_rolls
