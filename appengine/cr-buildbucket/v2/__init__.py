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
from . import steps
from .builds import BUILDER_PARAMETER
import model


@ndb.tasklet
def build_to_v2_async(build, allowed_logdog_hosts):  # pragma: no cover
  """Converts a model.Build to a build_pb.Build.

  Makes RPCs to fetch details, not present in the given model.Build.

  Returns:
    Tuple (build, finalized) where build is build_pb.Build and finalized is
    True if the build won't change in the future.

  Raises:
    errors.UnsupportedBuild: build is not eligible for conversion.
    errors.MalformedBuild: build has unexpected format.
    errors.StepFetchError: failed to fetch build steps from LogDog.
  """
  ret = builds.build_to_v2_partial(build)
  finalized = True

  if build.result != model.BuildResult.CANCELED:
    build_steps, finalized = yield steps.fetch_steps_async(
        build, allowed_logdog_hosts)
    ret.steps.extend(build_steps)

  raise ndb.Return(ret, finalized)
