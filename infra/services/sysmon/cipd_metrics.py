# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob
import json
import logging
import os
import sys

from infra_libs import ts_mon

# Where to look for cipd packages.
ALL_VERSION_DIRS = {
  'win32': ['C:\\infra-python',
            'C:\\infra-tools',   # authutil cipd version file is here
            'C:\\infra-tools\\.versions'],
  'default': ['/opt/infra-python',
              '/opt/infra-tools',  # authutil cipd version file is here
              '/opt/infra-tools/.versions',
            ],
  }


package_instance_id = ts_mon.StringMetric(
  'cipd/packages/deployed/instance_id',
  description='instance ids of deployed packages.')


def list_cipd_versions(cipd_version_dir):
  """Return all *.cipd_version of CIPD_VERSION.json files found.

  Args:
    cipd_version_dir (str): path to a directory to look into.

  Returns:
    cipd_versions_path(list of str): paths to cipd version json files.
  """
  paths = []

  python_version = os.path.join(cipd_version_dir, 'CIPD_VERSION.json')
  if os.path.exists(python_version):
    paths.append(python_version)

  paths.extend(glob.glob(os.path.join(cipd_version_dir, '*.cipd_version')))
  return paths


# TODO(pgervais): Make a common function in infra_libs and use it here and in
#   service_manager
def read_cipd_version(cipd_version_file):
  """Read a CIPD_VERSION.json file and validate its content.

  Args:
    cipd_version_file(str): path to a CIPD_VERSION.json file

  Returns:
    cipd_version(dict): version information with keys 'instance_id' and
       'package_name'. None if any error happened.
  """
  try:
    with open(cipd_version_file) as f:
      cipd_version = json.load(f)
  except (OSError, ValueError):
    logging.exception('Failed to read file: %s', cipd_version_file)
    return None


  if ('instance_id' not in cipd_version
      or 'package_name' not in cipd_version):
    logging.error('Missing key in version file: %s', cipd_version_file)
    return None

  return cipd_version


def get_cipd_summary():
  """Collect cipd package info."""

  version_dirs = ALL_VERSION_DIRS.get(sys.platform,
                                      ALL_VERSION_DIRS['default'])

  for version_dir in version_dirs:
    cipd_version_files = list_cipd_versions(version_dir)
    for cipd_version_file in cipd_version_files:
      cipd_version = read_cipd_version(cipd_version_file)
      if cipd_version:
        package_instance_id.set(cipd_version['instance_id'],
                                {'package_name': cipd_version['package_name']})
