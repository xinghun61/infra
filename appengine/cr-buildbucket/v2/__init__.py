# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""V2-specific code.

This module contains Buildbucket v2 specific code, while the rest of the
code in this app is v1. In particular, this file implements a function that
converts a v1 Build datastore entity to buildbucket.v2.Build message.
"""

from . import builds
from .builds import BUILDER_PARAMETER
from .errors import UnsupportedBuild


def build_to_v2(build):  # pragma: no cover
  # TODO(nodir): fetch steps.
  return builds.build_to_v2_partial(build)
