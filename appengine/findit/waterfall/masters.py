# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


_SUPPORTED_MASTERS = [
    # Tree-closer.
    'chromium',
    'chromium.win',
    'chromium.mac',
    'chromium.linux',
    'chromium.chromiumos',
    'chromium.chrome',
    'chromium.memory',
    'chromium.webkit',

    # Non-tree-closer.
]


# Explicitly list unsupported masters. Additional work might be needed in order
# to support them.
_UNSUPPORTED_MASTERS = [
    'chromium.lkgr',  # Disable as results are not showed on Sheriff-o-Matic.
    'chromium.gpu',  # Disable as too many false positives.

    'chromium.memory.fyi',
    'chromium.gpu.fyi',

    'chromium.perf',
]


def MasterIsSupported(master_name):  # pragma: no cover.
  """Return True if the given master is supported, otherwise False."""
  return master_name in _SUPPORTED_MASTERS
