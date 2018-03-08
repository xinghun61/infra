# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""V2-specific code.

This module contains Buildbucket v2 specific code, while the rest of the
code in this app is v1. In particular, this file implements a function that
converts a v1 Build datastore entity to buildbucket.v2.Build message.
"""

from google.appengine.ext import ndb

from . import builds
from . import errors
from .builds import BUILDER_PARAMETER
import model


def build_to_v2(build):  # pragma: no cover
  """Converts a model.Build to a build_pb.Build.

  Raises:
    errors.UnsupportedBuild: build is not eligible for conversion.
    errors.MalformedBuild: build has unexpected format.
  """
  # TODO(nodir): steps.
  return builds.build_to_v2_partial(build)
