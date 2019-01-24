# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Fixes builds in the datastore.

This code changes each time something needs to be migrated once.
"""

import logging
import copy

from google.appengine.ext import ndb

from components import utils

import api_common
import bulkproc

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


EXCLUDE_TAGS = {
    'build_address',
    'builder',
    'swarming_dimension',
    'swarming_hostname',
    'swarming_tag',
    'swarming_task_id',
}


@ndb.transactional_tasklet
def _fix_build_async(build_key):  # pragma: no cover
  build = yield build_key.get_async()
  if not build:
    return

  old = copy.deepcopy(build.proto)
  tags, gitiles_commit, gerrit_changes = api_common.parse_v1_tags(build.tags)
  tags = [t for t in tags if t.key not in EXCLUDE_TAGS]

  new = build.proto
  new.ClearField('tags')
  new.input.ClearField('gitiles_commit')
  new.input.ClearField('gerrit_changes')

  new.tags.extend(tags)
  if gitiles_commit:
    new.input.gitiles_commit.CopyFrom(gitiles_commit)
  new.input.gerrit_changes.extend(gerrit_changes)

  if new != old:
    compare = (
        ('tags', old.tags, new.tags),
        ('gitiles_commit', old.input.gitiles_commit, new.input.gitiles_commit),
        ('gerrit_changes', old.input.gerrit_changes, new.input.gerrit_changes),
    )
    for title, old_v, new_v in compare:
      if old_v != new_v:
        logging.info('%s: %s: %s -> %s', build.key.id(), title, old_v, new_v)

    yield build.put_async()
