# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""V2-specific code.

This module contains Buildbucket v2 specific code, while the rest of the
code in this app is v1. In particular, this file implements a function that
converts a v1 Build datastore entity to buildbucket.v2.Build message.
"""

# Pylint doesn't like wildcard imports.
# pylint: disable=W0401

from . import builds
from .builds import *
from .steps import parse_steps
import model

model.set_status_to_v2(status_to_v2)
