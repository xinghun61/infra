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
  build, out_props = yield [
      build_key.get_async(),
      model.BuildOutputProperties.key_for(build_key).get_async(),
  ]
  if not build:
    return

  futs = []

  if not build.input_properties:
    build.input_properties = struct_pb2.Struct()
    params = build.parameters_actual or build.parameters or {}
    src = params.get('properties')
    if isinstance(src, dict):
      build.input_properties.update(src)
    futs.append(build.put_async())

  if not out_props:
    src = (build.result_details or {}).get('properties') or {}
    if isinstance(src, dict):
      dest = struct_pb2.Struct()
      dest.update(src)
      out_props = model.BuildOutputProperties(
          key=model.BuildOutputProperties.key_for(build_key),
          properties=dest,
      )
      futs.append(out_props.put_async())

  yield futs
