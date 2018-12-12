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

  to_put = []

  if not build.input_properties:
    params = build.parameters_actual or build.parameters or {}
    build.input_properties = struct_pb2.Struct()
    build.input_properties.update(params.get('properties') or {})
    to_put.append(build)

  if not out_props:
    props = struct_pb2.Struct()
    props.update((build.result_details or {}).get('properties') or {})
    to_put.append(
        model.BuildOutputProperties(
            key=model.BuildOutputProperties.key_for(build_key),
            properties=props,
        )
    )

  yield ndb.put_multi_async(to_put)
