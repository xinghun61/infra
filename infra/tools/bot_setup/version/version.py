
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Returns the canonical version of bot setup scripts for hostname and image."""

DISABLED_BUILDERS = [
    'test_disabled_slave'
]


class BuilderDisabled(Exception):
  """This is raised when a builder should be disabled.

  By raising an exception, the startup sequence becomes interrupted.
  """
  pass


def get_version(slave_name=None, _image_name=None):
  if slave_name and slave_name in DISABLED_BUILDERS:
    raise BuilderDisabled()
  return 'origin/master'
