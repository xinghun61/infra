# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os


def find_version(service_config):
  """Tries to discover the version of the service.

  Args:
    service_config: A dictionary containing the service's config.  See README
        for a description of the fields.

  Returns:
    An opaque dictionary containing information about the service's version.
    This dictionary can be serialized by the json module, and can be compared
    with the == operator to another such dictionary to determine whether the
    service's version has changed.
  """

  ret = {}
  for name, fn in VERSION_FINDERS.iteritems():
    data = fn(service_config)
    if data is not None:
      ret[name] = data
  return ret


def _cipd_version_finder(service_config):
  pkgs_dir = os.path.join(service_config['root_directory'], '.cipd', 'pkgs')
  if not os.path.isdir(pkgs_dir):
    # Probably not a CIPD package.
    return None

  ret = {}
  for name in os.listdir(pkgs_dir):
    current = os.path.join(pkgs_dir, name, '_current')
    if not os.path.islink(current):
      continue

    ret[name] = os.readlink(current)

  return ret


VERSION_FINDERS = {
    'cipd': _cipd_version_finder,
}
