
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Returns the canonical version of bot setup scripts for hostname and image."""


LKGR = '1013a4d4cd1a3c88aac6754ec2beae2dd8583503'
DISABLED_BUILDERS = [
    'test_disabled_slave'
]

CANARY_SLAVES = (
    ['swarm%d-c4' % i for i in xrange(1, 10)] +
    ['slave%d-c4' % i for i in xrange(250, 260)])


class BuilderDisabled(Exception):
  """This is raised when a builder should be disabled.

  By raising an exception, the startup sequence becomes interrupted.
  """
  pass


def get_version(slave_name=None, _image_name=None):
  if slave_name and slave_name in DISABLED_BUILDERS:
    raise BuilderDisabled()
  if not slave_name or slave_name in CANARY_SLAVES:
    return 'origin/master'
  return LKGR
