# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Reads every Build and puts it back.

As a side effect, recomputes all NDB computed properties.
"""

from google.appengine.ext import ndb

from components import utils

import bulkproc
import config
import model

PROC_NAME = 'reput_builds'

bulkproc.register(
    PROC_NAME,
    lambda keys, _payload: _reput_builds(keys),
    keys_only=True,
)


def launch():  # pragma: no cover
  bulkproc.start(PROC_NAME)


def _reput_builds(build_keys):  # pragma: no cover
  res_iter = utils.async_apply(build_keys, _reput_build_async, unordered=True)
  # async_apply returns an iterator. We need to traverse it, otherwise nothing
  # will happen.
  for _ in res_iter:
    pass


@ndb.transactional_tasklet
def _reput_build_async(build_key):  # pragma: no cover
  build = yield build_key.get_async()
  if build:

    # Some old builds do not have a project.
    if not build.project:
      project_id, _ = yield config.get_bucket_async(build.bucket)
      # If the bucket no longer exists, assume it is from internal project
      # "chrome". The correctness of project value is not that important
      # in this case, we just need some well-formed value.
      build.project = project_id or 'chrome'

    # Some completed builds in prod and dev have no complete time.
    # Derive it from status_changed_time.
    if build.status == model.BuildStatus.COMPLETED and not build.complete_time:
      build.complete_time = build.status_changed_time
    yield build.put_async()
