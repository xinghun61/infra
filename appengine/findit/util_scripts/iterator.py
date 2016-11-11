# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Fetches entities and iterate over and process them."""

import os

import remote_api  # pylint: disable=W

_DEFAULT_BATCH_SIZE = 1000


# TODO(crbug.com/662540): Add unittests.
def ProjectEntity(entity, fields):  # pragma: no cover.
  """Projects fields from entity. Returns dict."""
  entity_info = {}
  for field in fields:
    if hasattr(entity, field):
      entity_info[field] = getattr(entity, field)
    else:
      entity_info[field] = None
  entity_info['id'] = entity.key.id()
  return entity_info


# TODO(crbug.com/662540): Add unittests.
def Iterate(query,
            fields,
            app_id,
            filter_func=None,
            batch_size=_DEFAULT_BATCH_SIZE,
            batch_run=False):  # pragma: no cover.
  """Iterates entities queried by query.

  Args:
    query (ndb.Query): The query to fetch entities.
    fields (list): Field names of an entity to be projected to a dict.
      If a given field name is not available, it is set to None.
      'id' is always added by default as an integer.
    app_id (str): App engine app id.
    filter_func (function): A function that does in memory filtering.
    batch_size (int): The number of entities to query at one time.
    batch_run (bool): If True, iterate batches of entities, if
      False, iterate each entity.

    An exmaple is available in crash_printer/print_crash.py.
  """
  remote_api.EnableRemoteApi(app_id)

  cursor = None
  while True:
    entities, next_cursor, more = query.fetch_page(batch_size,
                                                   start_cursor=cursor)
    if not more and not entities:
      break

    if filter_func:
      entities = filter_func(entities)

    entities = [ProjectEntity(entity, fields) for entity in entities]
    if batch_run:
      yield entities
    else:
      for entity in entities:
        yield entity

    if not more:
      break

    cursor = next_cursor
