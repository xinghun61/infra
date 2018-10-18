# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Reads every Build and puts it back.

As a side effect, recomputes all NDB computed properties.
"""

from google.appengine.ext import ndb

from components import utils

import bulkproc

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
    yield build.put_async()
