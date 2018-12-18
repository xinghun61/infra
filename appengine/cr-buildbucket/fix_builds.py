# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Fixes builds in the datastore.

This code changes each time something needs to be migrated once.
"""

from google.appengine.ext import ndb
from google.protobuf import struct_pb2

from components import utils

import bulkproc
import model

PROC_NAME = 'fix_builds'

bulkproc.register(
    PROC_NAME,
    lambda keys, _payload: _fix_builds(keys),
    keys_only=True,
)


def launch():  # pragma: no cover
  bulkproc.start(PROC_NAME)


def _fix_builds(build_keys):  # pragma: no cover
  res_iter = utils.async_apply(build_keys, _fix_build_async, unordered=True)
  # async_apply returns an iterator. We need to traverse it, otherwise nothing
  # will happen.
  for _ in res_iter:
    pass


@ndb.transactional_tasklet
def _fix_build_async(build_key):  # pragma: no cover
  build = yield build_key.get_async()
  if not build:
    return

  to_put = [build]
  yield ndb.put_multi_async(to_put)
