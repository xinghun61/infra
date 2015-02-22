# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


_SUPPORTED_MASTERS = [
    # Masters of tree-closer waterfalls.
    'chromium',
    'chromium.win',
    'chromium.mac',
    'chromium.linux',
    'chromium.chromiumos',
    'chromium.chrome',
    'chromium.memory',
    'chromium.gpu',

    # Masters of non-tree-closer waterfalls.
    'chromium.lkgr',
]


# Explicitly list unsupported masters. Additional work might be needed in order
# to support them.
_UNSUPPORTED_MASTERS = [
    'chromium.memory.fyi',
    'chromium.gpu.fyi',

    'chromiumos',
    'client.nacl',
    'chromium.webkit',
    'chromium.perf',
]


def MasterIsSupported(master_name):  # pragma: no cover.
  """Return True if the given master is supported, otherwise False."""
  return master_name in _SUPPORTED_MASTERS
