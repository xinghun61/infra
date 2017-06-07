# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
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


def _cipd_version_file_finder(service_config):
  """Load the CIPD VERSION.json file."""

  filename = service_config.get('cipd_version_file')
  if not filename or not os.path.isfile(filename):
    return None

  with open(filename) as fh:
    return json.load(fh)


VERSION_FINDERS = {
    'cipd_version_file': _cipd_version_file_finder,
}
