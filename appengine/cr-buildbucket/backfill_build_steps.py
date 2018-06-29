# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Migrates model.BuildAnnotations to model.BuildSteps."""

import logging

from google.appengine.ext import ndb
from google.appengine.runtime import apiproxy_errors

from components import utils

from proto import build_pb2

import bulkproc
import model

PROC_NAME = 'backfill_build_steps'

bulkproc.register(
    PROC_NAME,
    lambda keys, _payload: _process_build_annotations(keys),
    entity_kind='BuildAnnotations',
    keys_only=True,
)


def launch():  # pragma: no cover
  bulkproc.start(PROC_NAME)


def _process_build_annotations(build_ann_keys):  # pragma: no cover
  # async_apply returns an iterator. We need to traverse it, otherwise nothing
  # will happen.
  res_iter = utils.async_apply(
      build_ann_keys, _migrate_annotations_async, unordered=True
  )
  for _ in res_iter:
    pass


@ndb.tasklet
def _migrate_annotations_async(build_ann_key):  # pragma: no cover
  build_ann = yield build_ann_key.get_async()
  if not build_ann:  # pragma: no cover
    return

  container = build_pb2.Build(steps=build_ann.parse_steps())
  build_steps = model.BuildSteps(
      key=model.BuildSteps.key_for(build_ann_key.parent()),
      steps=container.SerializeToString(),
  )
  try:
    yield build_steps.put_async()
  except apiproxy_errors.RequestTooLargeError:
    logging.warning(
        'steps of build %d are too large. Skipping',
        build_ann_key.parent().id(),
    )
